from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor
import json
from hashlib import sha256
from pathlib import Path
from typing import Callable

from .config import AppConfig
from .errors import AppError, invalid
from .features import extract_features
from .models import CropBox, ImageMetadata, ImportErrorRecord, ImportSummary
from .preprocessing import encode_processed_png, preprocess_image
from .repository import Repository


REQUIRED_COLUMNS = {
    "relative_path",
    "species_name",
    "source_url",
    "license_note",
    "split",
    "group_id",
    "crop_x",
    "crop_y",
    "crop_size",
    "quality_status",
    "review_note",
}


class IngestionService:
    def __init__(self, config: AppConfig, repository: Repository, features_by_sha=None):
        self.config = config
        self.repository = repository
        self.features_by_sha = features_by_sha

    @staticmethod
    def _crop_from_row(row: dict[str, str]) -> CropBox | None:
        values = [row.get("crop_x", "").strip(), row.get("crop_y", "").strip(), row.get("crop_size", "").strip()]
        if not any(values):
            return None
        if not all(values):
            raise invalid("INVALID_CROP", "crop_x, crop_y và crop_size phải cùng có giá trị")
        try:
            return CropBox(x=int(values[0]), y=int(values[1]), size=int(values[2]))
        except ValueError as exc:
            raise invalid("INVALID_CROP", "Tọa độ crop phải là số nguyên") from exc

    def import_manifest(self, manifest_path: Path, progress: Callable | None = None) -> ImportSummary:
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Manifest thiếu cột: {', '.join(sorted(missing))}")
            rows = list(reader)
        return self.import_rows(rows, progress)

    def import_rows(self, rows: list[dict], progress: Callable | None = None) -> ImportSummary:
        bundle = self.repository.ensure_bundle()
        errors: list[ImportErrorRecord] = []
        created = skipped = failed = 0

        for row_number, row in enumerate(rows, start=2):
            relative_path = row.get("relative_path", "").strip()
            processed_path: Path | None = None
            owns_processed = False
            try:
                if row.get("split") not in {"gallery", "validation", "test"}:
                    raise invalid("INVALID_MANIFEST", "split không hợp lệ", split=row.get("split"))
                if row.get("quality_status") not in {"pending", "approved", "rejected"}:
                    raise invalid(
                        "INVALID_MANIFEST",
                        "quality_status không hợp lệ",
                        quality_status=row.get("quality_status"),
                    )
                original_path = self.config.resolve_data_path(relative_path)
                if not original_path.is_file():
                    raise invalid("MISSING_IMAGE_FILE", "Không tìm thấy ảnh gốc", path=relative_path)
                image_bytes = original_path.read_bytes()
                original_sha = sha256(image_bytes).hexdigest()
                if self.repository.find_image_by_original_sha(original_sha) is not None:
                    skipped += 1
                    continue
                processed = preprocess_image(
                    image_bytes, self._crop_from_row(row), preprocess_version=self.config.preprocess_version
                )
                processed_relative = Path("processed") / self.config.bundle_name / row["split"] / row["species_name"].strip().casefold() / f"{original_path.stem}-{original_sha[:12]}.png"
                processed_path = self.config.resolve_data_path(processed_relative.as_posix())
                processed_path.parent.mkdir(parents=True, exist_ok=True)
                encoded = encode_processed_png(processed)
                if processed_path.exists():
                    if processed_path.read_bytes() != encoded:
                        raise invalid("PROCESSED_CONFLICT", "Ảnh xử lý đã tồn tại với nội dung khác", path=processed_relative.as_posix())
                else:
                    processed_path.write_bytes(encoded)
                    owns_processed = True
                features = (self.features_by_sha[original_sha] if self.features_by_sha is not None
                            else extract_features(processed, bundle))
                if features.config_signature != bundle.signature:
                    raise invalid("CONFIG_MISMATCH", "Đặc trưng không khớp toàn bộ cấu hình nhập")
                metadata = ImageMetadata(
                    species_name=row["species_name"].strip() or None,
                    original_path=self.config.relative_to_data(original_path),
                    processed_path=self.config.relative_to_data(processed_path),
                    original_sha256=original_sha,
                    processed_sha256=processed.pixel_sha256,
                    source_url=row["source_url"].strip() or None,
                    license_note=row["license_note"].strip() or None,
                    split=row["split"],
                    group_id=row["group_id"].strip() or original_sha,
                    crop=processed.crop,
                    preprocess_version=processed.preprocess_version,
                    quality_status=row["quality_status"],
                    active=row["quality_status"] != "rejected",
                    review_note=row["review_note"].strip() or None,
                )
                self.repository.insert_image_with_features(metadata, features, bundle)
                created += 1
            except Exception as exc:
                failed += 1
                if owns_processed and processed_path is not None and processed_path.exists():
                    processed_path.unlink()
                code = exc.code if isinstance(exc, AppError) else "IMPORT_ERROR"
                errors.append(
                    ImportErrorRecord(
                        row_number=row_number,
                        relative_path=relative_path,
                        code=code,
                        message=str(exc) + ("; " + json.dumps(exc.details, ensure_ascii=False) if isinstance(exc, AppError) and exc.details else ""),
                    )
                )
            finally:
                if progress:
                    progress(row_number - 1, len(rows), relative_path, created, skipped, failed)
        return ImportSummary(
            total=len(rows),
            created=created,
            skipped=skipped,
            failed=failed,
            errors=tuple(errors),
        )


def _extract_import_row(job):
    config, bundle, row = job
    path = config.resolve_data_path(row["relative_path"])
    try:
        payload = path.read_bytes()
        image = preprocess_image(payload, IngestionService._crop_from_row(row), preprocess_version=config.preprocess_version)
        return sha256(payload).hexdigest(), extract_features(image, bundle)
    except Exception as exc:
        raise ValueError(f"Feature extraction failed: {row['relative_path']}: {exc}") from exc


def extract_import_features(config, repository, rows, workers=4):
    """Parallel numeric extraction; ordered writes still use normal ingestion validation."""
    bundle = repository.ensure_bundle()
    pending = [row for row in rows if repository.find_image_by_original_sha(
        sha256(config.resolve_data_path(row["relative_path"]).read_bytes()).hexdigest()) is None]
    if not pending:
        return {}
    result = {}
    with ProcessPoolExecutor(max_workers=workers) as executor:
        jobs = ((config, bundle, row) for row in pending)
        for index, (digest, features) in enumerate(executor.map(_extract_import_row, jobs), 1):
            result[digest] = features
            if index % 25 == 0:
                print(f"Prepared import vectors {index}/{len(pending)}", flush=True)
    return result
