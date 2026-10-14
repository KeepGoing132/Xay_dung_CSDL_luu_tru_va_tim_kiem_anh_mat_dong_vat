"""Fit label-free gallery calibration, freeze it, then import the refined profile."""
from __future__ import annotations

import csv
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.calibration import calibration_path, fit_calibration, canonical_hash, calibrated_specs
from backend.src.config import AppConfig, REFINED512_BUNDLE_NAME, feature_specs_for
from backend.src.features import extract_features
from backend.src.ingestion import IngestionService
from backend.src.models import BundleConfig, FeatureConfig
from backend.src.preprocessing import preprocess_image
from backend.src.repository import Repository


def descriptor_bundle(config, specs):
    groups = {name: FeatureConfig(i, spec["name"], spec["feature_type"], spec["dimension"],
                                 spec["parameters"], config.preprocess_version)
              for i, (name, spec) in enumerate(specs.items(), 1)}
    return BundleConfig(config.bundle_name, groups["hsv"], groups["hog"], groups["lbp"],
                        {key: group for key, group in groups.items() if key not in {"hsv", "hog", "lbp"}})


def prepare_calibration(config, rows, minimum_gallery=500):
    specs = feature_specs_for(config.bundle_name, config.preprocess_version)
    path = calibration_path(config)
    groups, paths = {}, set()
    for row in rows:
        if row["relative_path"] in paths:
            raise ValueError(f"Duplicate path: {row['relative_path']}")
        paths.add(row["relative_path"])
        groups.setdefault(row["group_id"], set()).add(row["split"])
    if any(len(splits) > 1 for splits in groups.values()):
        raise ValueError("Source group crosses dataset splits")
    gallery = sorted((row for row in rows if row["split"] == "gallery" and row["quality_status"] == "approved"),
                     key=lambda row: row["relative_path"])
    if len(gallery) < minimum_gallery:
        raise ValueError(f"Need {minimum_gallery} approved gallery images, got {len(gallery)}")
    source_records = []
    for row in gallery:
        payload = config.resolve_data_path(row["relative_path"]).read_bytes()
        source_records.append({"path": row["relative_path"], "sha256": sha256(payload).hexdigest(),
                               "crop": [row.get(key, "") for key in ["crop_x", "crop_y", "crop_size"]]})
    source_hash = canonical_hash(source_records)
    if path.exists():
        calibrated_specs(config, specs)
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact.get("gallery_source_sha256") != source_hash:
            raise ValueError("Gallery changed after calibration; create a new profile instead of overwriting")
        print("Reusing frozen calibration", flush=True)
        return artifact
    bundle = descriptor_bundle(config, specs)
    vectors = {key: [] for key in specs}
    seen_pixels = set()
    for index, row in enumerate(gallery, 1):
        try:
            image = preprocess_image(config.resolve_data_path(row["relative_path"]).read_bytes(),
                                     IngestionService._crop_from_row(row), preprocess_version=config.preprocess_version)
            if image.pixel_sha256 in seen_pixels:
                raise ValueError("Duplicate gallery pixels")
            seen_pixels.add(image.pixel_sha256)
            features = extract_features(image, bundle)
        except Exception as exc:
            raise ValueError(f"Calibration failed: {row['relative_path']}: {exc}") from exc
        for key, vector in features.vectors.items():
            vectors[key].append(vector)
        if index % 25 == 0:
            print(f"Calibration descriptors {index}/{len(gallery)}", flush=True)
    artifact = fit_calibration(vectors, specs)
    artifact.update(gallery_source_sha256=source_hash, source_records=source_records,
                    preprocessing_version=config.preprocess_version,
                    libraries={key: version(key) for key in ["numpy", "scikit-image", "pillow"]},
                    note="Gallery only; no species labels, validation or test images used. Not a relevance probability.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(artifact, stream, indent=2)
    return artifact


def main():
    config = AppConfig.default(REFINED512_BUNDLE_NAME)
    # Preserve a recoverable demo through the repository's SQLite backup API.
    backup_root = config.data_root / "backups/before-refined512"
    for profile in ["expanded512-v1", "native512-v1"]:
        source = config.for_profile(profile)
        if source.db_path.exists():
            destination = backup_root / source.db_path.name
            if not destination.exists():
                Repository(source).backup_to(destination)
    with config.default_manifest_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    prepare_calibration(config, rows)
    repo = Repository(config)
    repo.create_schema()
    def progress(done, total, path, created, skipped, failed):
        if done % 25 == 0 or failed:
            print(f"Import {done}/{total}: created={created} skipped={skipped} failed={failed} ({path})", flush=True)
    result = IngestionService(config, repo).import_rows(rows, progress)
    folder = config.result_directory("statistics")
    folder.mkdir(parents=True, exist_ok=True)
    report = {**result.__dict__, "errors": [e.__dict__ for e in result.errors]}
    (folder / "import.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    if result.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
