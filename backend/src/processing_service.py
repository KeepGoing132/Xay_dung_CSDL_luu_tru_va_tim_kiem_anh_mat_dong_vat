"""Local background processing, ingestion and explicit mask review."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile
import threading
from uuid import uuid4

from PIL import Image

from .background_import import run_import
from .config import AppConfig, SOURCE_PREPROCESS_VERSION, BACKGROUND_MODEL_SHA256, OFFICIAL_MASK_DIRECTORY, OFFICIAL_QUERY_PIPELINE
from .cutouts import validate_cutout
from .errors import invalid
from .preprocessing import preprocess_image, encode_processed_png
from .repository import Repository

QUERY_MODEL_LOCK = threading.Lock()

class ProcessingCancelled(Exception):
    pass


def read_model_progress(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    # Ignore an in-progress append; read the last complete JSON event.
    complete = raw.rsplit("\n", 1)[0]
    return json.loads(complete.rsplit("\n", 1)[-1])




class DatasetProcessingService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.cutouts = config.data_root / "background_removed" / OFFICIAL_MASK_DIRECTORY
        # Ảnh test tách riêng khỏi gallery: mask của chúng ở background_removed-test/.
        self.test_cutouts = config.data_root / "background_removed-test" / OFFICIAL_MASK_DIRECTORY
        self.jobs_root = self.config.data_root / "processing_jobs"
        self.model_script = self.config.project_root / "animal_face_model" / "remove_background.py"
        self.model_python = self.model_script.parent / ".venv" / "Scripts" / "python.exe"
        self._query_lock = QUERY_MODEL_LOCK

    def sources(self) -> list[dict]:
        with self.config.source_manifest_path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            path = self.config.resolve_data_path(row["relative_path"])
            if not path.is_relative_to(self.config.source_root.resolve()) or not path.is_file():
                raise ValueError(f"Missing or invalid source: {row['relative_path']}")
        return rows

    def cutout_path(self, row: dict) -> Path:
        relative = self.config.resolve_data_path(row["relative_path"]).relative_to(self.config.source_root.resolve())
        root = self.test_cutouts if row.get("mask_split", row.get("split")) == "test" else self.cutouts
        return root / relative.parent / (relative.name + ".png")

    def relocate_test_cutouts(self) -> dict:
        """Chuyển mask của ảnh test ra thư mục riêng; idempotent, kiểm checksum khi ghi đè."""
        moved = skipped = 0
        for row in self.sources():
            if row.get("mask_split", row.get("split")) != "test":
                continue
            target = self.cutout_path(row)
            source = self.cutouts / target.relative_to(self.test_cutouts)
            if not source.is_file():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.read_bytes() != source.read_bytes():
                    raise ValueError(f"Test mask conflict: {self.config.relative_to_data(target)}")
                source.unlink()
                skipped += 1
            else:
                source.replace(target)
                moved += 1
        for directory in sorted((self.cutouts).rglob("*"), reverse=True):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        return {"moved": moved, "already_present": skipped}

    def preview_path(self, source_id: int, kind: str) -> Path:
        rows = self.sources()
        if source_id < 0 or source_id >= len(rows) or kind not in {"original", "mask"}:
            raise ValueError("Invalid preview request")
        row = rows[source_id]
        path = self.config.resolve_data_path(row["relative_path"]) if kind == "original" else self.cutout_path(row)
        self.config.relative_to_data(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    def catalog(self, offset: int = 0, limit: int = 24, ready_only: bool = False) -> dict:
        if offset < 0 or limit < 1 or limit > 48:
            raise ValueError("Invalid review page")
        rows = self.sources()
        records = Repository(self.config).audit_image_records() if self.config.db_path.exists() else []
        stored = {row["original_path"]: row for row in records}
        items = []
        visible = [(index, row) for index, row in enumerate(rows)
                   if not ready_only or self.cutout_path(row).is_file()]
        for index, row in visible[offset:offset + limit]:
            cutout = self.cutout_path(row)
            checksum = sha256(cutout.read_bytes()).hexdigest() if cutout.is_file() else None
            record = stored.get(self.config.relative_to_data(cutout))
            if record and checksum != record["original_sha256"]:
                record = None
            items.append({"source_id": index, "species": row["species_name"], "split": row["split"],
                          "source_path": row["relative_path"], "source_url": row["source_url"],
                          "original_url": f"/api/processing/preview/{index}/original",
                          "mask_url": f"/api/processing/preview/{index}/mask?version={checksum}" if checksum else None,
                          "image_id": record["image_id"] if record else None,
                          "quality_status": record["quality_status"] if record else "not_imported"})
        return {"total": len(rows), "page_total": len(visible), "offset": offset, "limit": limit, "items": items,
                "cutouts": sum(self.cutout_path(row).is_file() for row in rows), "imported": len(stored),
                "approved_gallery": sum(row["split"] == "gallery" and row["quality_status"] == "approved" and row["active"] for row in records),
                "output_folder": self.config.relative_to_data(self.cutouts),
                "database": self.config.relative_to_data(self.config.db_path), "image_size": self.config.image_size}

    def review(self, source_ids: list[int], status: str, *, review_note: str | None = None) -> dict:
        rows = self.sources()
        note = "Background mask visually reviewed in the application" if review_note is None else review_note
        if not isinstance(note, str) or not note.strip() or len(note) > 1000:
            raise ValueError("Invalid review note")
        if not isinstance(status, str) or status not in {"approved", "rejected", "pending"} or not source_ids or len(source_ids) > len(rows):
            raise ValueError("Choose images and a valid review decision")
        if any(type(index) is not int or index < 0 or index >= len(rows) for index in source_ids):
            raise ValueError("Invalid source ID")
        repository = Repository(self.config)
        if not self.config.db_path.exists():
            raise ValueError("Extract and import features before approving masks")
        decisions = []
        for index in sorted(set(source_ids)):
            row = rows[index]
            if row['split'] == 'unassigned':
                raise ValueError(f"Assign a split before importing/reviewing: {row['relative_path']}")
            if status == "approved" and row["quality_status"] != "approved":
                raise ValueError(f"Source has not been approved: {row['relative_path']}")
            cutout = self.cutout_path(row)
            validate_cutout(self.config.resolve_data_path(row["relative_path"]), cutout)
            checksum = sha256(cutout.read_bytes()).hexdigest()
            if repository.find_image_by_original_sha(checksum) is None:
                raise ValueError(f"Features have not been imported: {self.config.relative_to_data(cutout)}")
            decisions.append((checksum, status, note))
        repository.set_image_qualities(decisions)
        # Keep manifest and DB decisions in sync for future CLI imports/evaluations.
        manifest = self.config.default_manifest_path
        if manifest.exists():
            with manifest.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                fields, contents = reader.fieldnames, list(reader)
            reviewed = {self.config.relative_to_data(self.cutout_path(rows[index])) for index in source_ids}
            for row in contents:
                if row["relative_path"] in reviewed:
                    row["quality_status"] = status
                    row["review_note"] = note
            temporary = manifest.with_suffix(".tmp")
            with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(contents)
            temporary.replace(manifest)
        return {"updated": len(decisions), "quality_status": status}

    def _model(self, arguments: list[str], log: Path, cancelled: threading.Event) -> None:
        arguments = [*arguments, "--provider", "directml", "--threads", "2"]
        if not self.model_python.is_file() or not self.model_script.is_file():
            raise FileNotFoundError("The local background model environment is missing")
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8") as stream:
            process = subprocess.Popen([str(self.model_python), str(self.model_script), *arguments],
                                       cwd=self.config.project_root, stdout=stream, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                while process.poll() is None:
                    if cancelled.wait(0.25):
                        raise ProcessingCancelled()
                if process.returncode:
                    detail = log.read_text(encoding="utf-8", errors="replace")[-3000:]
                    raise ValueError(f"Background model failed (exit {process.returncode}): {detail}")
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=15)

    def run(self, action: str, limit: int | None, update, cancelled: threading.Event, job_id: str) -> dict:
        if not isinstance(action, str) or action not in {"remove_background", "extract_features", "pipeline"}:
            raise ValueError("Unsupported processing action")
        rows = self.sources()
        if limit is not None and (type(limit) is not int or limit < 1 or limit > len(rows)):
            raise ValueError("Invalid processing limit")
        result = {}
        if action in {"remove_background", "pipeline"}:
            progress_file = self.jobs_root / f"{job_id}.model-progress.jsonl"
            arguments = ["--input", str(self.config.source_root), "--output", str(self.cutouts),
                         "--resume", "--manifest", str(self.config.source_manifest_path),
                         "--progress-file", str(progress_file)]
            if limit:
                arguments += ["--limit", str(limit)]
            update(phase="remove_background", completed=0, total=min(limit or len(rows), len(rows)))
            stopped = threading.Event()

            def watch():
                previous = None
                while not stopped.wait(0.5):
                    if progress_file.exists():
                        try:
                            progress = read_model_progress(progress_file)
                            if progress == previous:
                                continue
                            previous = progress
                        except (OSError, json.JSONDecodeError):
                            continue  # The next poll retries an incomplete progress event.
                        update(**progress)

            watcher = threading.Thread(target=watch, daemon=True)
            watcher.start()
            try:
                self._model(arguments, self.jobs_root / f"{job_id}.model.log", cancelled)
                result["test_masks"] = self.relocate_test_cutouts()
                # Mask của ảnh truy vấn được tính và cache theo yêu cầu ở
                # background_removed/queries/{pipeline}; không seed sẵn cả bộ ảnh.
                if progress_file.exists():
                    progress = read_model_progress(progress_file)
                    update(**progress)
                    result["segmentation"] = progress
            finally:
                stopped.set()
                watcher.join(timeout=2)
        if action in {"extract_features", "pipeline"}:
            if cancelled.is_set():
                raise ProcessingCancelled()
            update(phase="extract_features", completed=0, total=0)

            def importing(completed, total, source, created, skipped, failed):
                if cancelled.is_set():
                    raise ProcessingCancelled()
                update(completed=completed, total=total, source=source, created=created, skipped=skipped, failed=failed)

            from .dataset_preparation import prepare_manifest_calibration
            prepare_manifest_calibration(self.config)
            result["import"] = run_import(self.config, self.config.source_manifest_path,
                                           self.cutouts, self.config.default_manifest_path,
                                           allow_partial=limit is not None, progress=importing, limit=limit)
        return result

    def query_cutout(self, payload: bytes, crop=None) -> bytes:
        # Normalize the query to the same 512 canvas used by the source gallery.
        source = preprocess_image(payload, crop, preprocess_version=SOURCE_PREPROCESS_VERSION)
        rgb_png = encode_processed_png(source)
        pipeline = OFFICIAL_QUERY_PIPELINE
        key = sha256((BACKGROUND_MODEL_SHA256 + pipeline).encode() + rgb_png).hexdigest()
        output = self.config.data_root / "background_removed" / "queries" / pipeline
        cutout = output / (key + ".png.png")
        temporary_root = self.jobs_root / "temporary"
        temporary_root.mkdir(parents=True, exist_ok=True)
        with self._query_lock, tempfile.TemporaryDirectory(prefix="query-mask-", dir=temporary_root) as directory:
            input_path = Path(directory) / (key + ".png")
            input_path.write_bytes(rgb_png)
            try:
                if not cutout.exists():
                    self._model(["--input", str(input_path), "--output", str(output)],
                                self.jobs_root / "query-model.log", threading.Event())
                validate_cutout(input_path, cutout)
            except (OSError, ValueError) as exc:
                raise invalid("BACKGROUND_FAILED", "Không thể tách nền ảnh truy vấn", reason=str(exc)) from exc
            return cutout.read_bytes()


class ProcessingJobs:
    """One local background job at a time; status survives browser refresh."""
    def __init__(self, service: DatasetProcessingService):
        self.service = service
        self._lock = threading.RLock()
        self._cancelled = threading.Event()
        self._worker = None
        self._active = None
        self.service.jobs_root.mkdir(parents=True, exist_ok=True)
        for path in self.service.jobs_root.glob("job-*.json"):
            job = json.loads(path.read_text(encoding="utf-8"))
            if job["status"] == "running":
                job.update(status="interrupted", error="Server restarted; run again to resume validated images")
                self._save(job)

    def _save(self, job: dict) -> None:
        destination = self.service.jobs_root / f"job-{job['job_id']}.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(destination)

    def latest(self) -> dict | None:
        with self._lock:
            if self._active:
                return dict(self._active)
            paths = sorted(self.service.jobs_root.glob("job-*.json"), key=lambda path: path.stat().st_mtime_ns)
            return json.loads(paths[-1].read_text(encoding="utf-8")) if paths else None

    @property
    def busy(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def start(self, action: str, limit: int | None = None) -> dict:
        if not isinstance(action, str) or action not in {"remove_background", "extract_features", "pipeline"}:
            raise ValueError("Unsupported action")
        count = len(self.service.sources())
        if limit is not None and (type(limit) is not int or limit < 1 or limit > count):
            raise ValueError("Invalid processing limit")
        with self._lock:
            if self.busy:
                raise invalid("PROCESSING_BUSY", "Một tác vụ đang chạy; hãy đợi hoặc dừng tác vụ đó")
            self._cancelled = threading.Event()
            self._active = {"job_id": uuid4().hex, "action": action, "limit": limit, "status": "running",
                            "phase": "starting", "completed": 0, "total": count,
                            "started_at": datetime.now(timezone.utc).isoformat(), "error": None}
            self._save(self._active)
            snapshot = dict(self._active)
            self._worker = threading.Thread(target=self._run, daemon=True)
            self._worker.start()
            return snapshot

    def _run(self):
        def update(**changes):
            with self._lock:
                self._active.update(changes)
                self._save(self._active)

        try:
            result = self.service.run(self._active["action"], self._active["limit"], update,
                                      self._cancelled, self._active["job_id"])
            update(status="completed", result=result)
        except ProcessingCancelled:
            update(status="cancelled", error="Đã dừng; ảnh và vector thành công được giữ để tiếp tục")
        except Exception as exc:
            update(status="failed", error=f"{type(exc).__name__}: {exc}")
        finally:
            update(finished_at=datetime.now(timezone.utc).isoformat())

    def cancel(self) -> dict | None:
        self._cancelled.set()
        return self.latest()

    def shutdown(self):
        self._cancelled.set()
        if self._worker:
            self._worker.join(timeout=5)
