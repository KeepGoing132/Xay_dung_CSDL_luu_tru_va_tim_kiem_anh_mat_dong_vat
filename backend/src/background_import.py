"""Validate cutouts, extract features and import into a separate SQLite profile."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import shutil
from contextlib import closing

from .config import BACKGROUND_BUNDLE_NAME, BACKGROUND512_BUNDLE_NAME
from .cutouts import validate_cutout
from .ingestion import IngestionService
from .repository import Repository

def build_manifest(config, source_manifest, cutouts_dir, allow_partial=False, reviewed=False, limit=None):
    with source_manifest.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        sources = list(reader)
    if limit is not None:
        if type(limit) is not int or limit < 1 or limit > len(sources):
            raise ValueError("Invalid import limit")
        sources = sorted(sources, key=lambda row: config.resolve_data_path(row["relative_path"]))[:limit]
    rows, missing = [], []
    for source in sources:
        original_relative = Path(source["relative_path"])
        if original_relative.parts[0] != "original":
            raise ValueError(f"Source manifest must refer to original/ images: {original_relative}")
        relative = Path(*original_relative.parts[1:])
        cutout = cutouts_dir / relative.parent / (relative.name + ".png")
        if not cutout.is_file():
            missing.append(source["relative_path"])
            continue
        original = config.resolve_data_path(source["relative_path"])
        try:
            validate_cutout(original, cutout)
        except (OSError, ValueError) as exc:
            raise ValueError(f"Invalid cutout {cutout}: {exc}") from exc
        row = dict(source)
        row["license_note"] = source.get("license_note", "") + "; derived alpha mask, source RGB preserved; white composite for features"
        row["relative_path"] = config.relative_to_data(cutout)
        row["quality_status"] = source["quality_status"] if reviewed or source["quality_status"] == "rejected" else "pending"
        row["review_note"] = source.get("review_note", "") + (
            "; background mask reviewed" if reviewed else "; background mask pending review"
        )
        rows.append(row)
    if missing and not allow_partial:
        raise ValueError(f"Missing {len(missing)}/{len(sources)} cutouts; first: {missing[0]}. Run the model on data/original first.")
    if not rows:
        raise ValueError("No matching cutouts found")
    return fields, rows, missing


def run_import(config, source_manifest, cutouts_dir, manifest, *, allow_partial=False, reviewed=False, progress=None, limit=None):
    if config.bundle_name not in {BACKGROUND_BUNDLE_NAME, BACKGROUND512_BUNDLE_NAME}:
        raise ValueError("Background import requires a background-white profile")
    if config.db_path.resolve() in {(config.data_root / name).resolve() for name in ("app.db", "native512.db", "expanded512.db", "refined512.db")}:
        raise ValueError("Cannot overwrite the baseline database")
    if manifest.resolve() == source_manifest.resolve():
        raise ValueError("Cannot overwrite the source manifest")
    config.relative_to_data(cutouts_dir)
    config.relative_to_data(manifest)
    config.relative_to_data(config.db_path)
    fields, rows, missing = build_manifest(config, source_manifest, cutouts_dir, allow_partial, reviewed, limit)
    previous_rows = []
    if manifest.exists():
        with manifest.open(encoding="utf-8-sig", newline="") as stream:
            previous_rows = list(csv.DictReader(stream))
    backup = None
    if config.db_path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        backup = config.db_path.with_suffix(f".before-import-{stamp}.db")
        with closing(sqlite3.connect(config.db_path.as_uri() + "?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(backup)) as target:
                source.backup(target)
    repository = Repository(config)
    repository.create_schema()
    if config.bundle_name == BACKGROUND512_BUNDLE_NAME:
        # Store immutable mask inputs so later manual corrections cannot alter history.
        for row in rows:
            cutout = config.resolve_data_path(row["relative_path"])
            checksum = sha256(cutout.read_bytes()).hexdigest()
            snapshot = config.data_root / "background_removed" / "versions" / row["split"] / row["species_name"] / (cutout.name + "." + checksum[:16] + ".png")
            config.relative_to_data(snapshot)
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            if snapshot.exists():
                if sha256(snapshot.read_bytes()).hexdigest() != checksum:
                    raise ValueError(f"Mask snapshot conflict: {config.relative_to_data(snapshot)}")
            else:
                shutil.copy2(cutout, snapshot)
            row["relative_path"] = config.relative_to_data(snapshot)
    existing = {}
    for row in rows:
        checksum = sha256(config.resolve_data_path(row["relative_path"]).read_bytes()).hexdigest()
        existing[checksum] = row
    manifest.parent.mkdir(parents=True, exist_ok=True)
    summary = IngestionService(config, repository).import_rows(rows, progress=progress)
    if not summary.failed:
        repository.update_image_attributions([(checksum, row["relative_path"], row["source_url"], row["license_note"]) for checksum, row in existing.items()])
        if config.bundle_name == BACKGROUND512_BUNDLE_NAME:
            repository.retire_other_mask_versions([(row["group_id"], checksum) for checksum, row in existing.items()])
    if reviewed and not summary.failed:
        for checksum, row in existing.items():
            repository.set_image_quality(checksum, row["quality_status"], row["review_note"])
    elif not summary.failed:
        # A rerun must keep previous explicit mask decisions, not silently reset them.
        decisions = {row["original_path"]: row for row in repository.audit_image_records()}
        for row in rows:
            stored = decisions.get(row["relative_path"])
            if stored:
                row["quality_status"] = stored["quality_status"]
                row["review_note"] = stored["review_note"] or ""
    if not summary.failed:
        # A limited run must not discard other previously imported source groups.
        merged = {row["group_id"]: row for row in previous_rows}
        merged.update({row["group_id"]: row for row in rows})
        temporary = manifest.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(merged.values())
        temporary.replace(manifest)
    bundle = repository.ensure_baseline_bundle()
    loaded = repository.load_candidates(bundle)
    stats = repository.dataset_integrity()
    result = {
        "database": config.relative_to_data(config.db_path), "manifest": config.relative_to_data(manifest),
        "profile": config.bundle_name, "preprocess_version": config.preprocess_version,
        "total": summary.total, "created": summary.created, "skipped": summary.skipped,
        "failed": summary.failed, "errors": [error.__dict__ for error in summary.errors],
        "missing_cutouts": missing, "database_images": stats["image_count"], "database_vectors": stats["vector_count"],
        "approved_candidates": len(loaded.candidates), "rejected_candidates": [r.__dict__ for r in loaded.rejected],
        "acceptance_ready": len(loaded.candidates) >= 500 and not loaded.rejected,
        "integrity": stats["integrity"], "foreign_key_errors": stats["foreign_key_errors"],
        "backup": config.relative_to_data(backup) if backup else None,
    }
    report = manifest.with_suffix(".import.json")
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if summary.failed or loaded.rejected or stats["integrity"] != "ok" or stats["foreign_key_errors"]:
        raise ValueError(f"Import verification failed; details: {report}")
    return result


