"""Prepare source manifest, segment, fit the VLAD codebook, calibrate and import the four-descriptor dataset."""
from pathlib import Path
import argparse
import csv
import json
from hashlib import sha256
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig
from backend.src.processing_service import DatasetProcessingService


def prepare_sources(config):
    portable = config.data_root / "dataset512-left/manifest.csv"
    with portable.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    if config.pca_components:
        fields = [*fields, 'mask_split']
        for row in rows:
            row['mask_split'] = row['split']
            if row['split'] == 'test':
                row['split'] = 'validation'
    for row in rows:
        row["relative_path"] = row["data_relative_path"]
        # The selected images have already been cropped to RGB 512. Original
        # crop coordinates remain in the untouched portable provenance manifest.
        for key in ("crop_x", "crop_y", "crop_size"):
            row[key] = ""
        path = config.resolve_data_path(row["relative_path"])
        if not path.is_relative_to(config.source_root.resolve()) or not path.is_file():
            raise ValueError(f"Missing/unsafe source: {row['relative_path']}")
        if sha256(path.read_bytes()).hexdigest() != row['file_sha256']:
            raise ValueError(f"Source changed since selection: {row['relative_path']}")
    config.source_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = config.source_manifest_path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(config.source_manifest_path)
    return rows


def prepare_codebook_only(config):
    """Fit hoặc kiểm tra lại codebook VLAD đóng băng từ mask gallery đã có."""
    from backend.src.background_import import build_manifest
    from backend.src.calibration_preparation import prepare_codebook
    from backend.src.config import OFFICIAL_MASK_DIRECTORY, feature_specs_for
    from backend.src.codebook import codebook_path
    cutouts = config.data_root / "background_removed" / OFFICIAL_MASK_DIRECTORY
    _, rows, _ = build_manifest(config, config.source_manifest_path, cutouts, reviewed=True,
                               source_splits={"gallery"})
    gallery = sorted((row for row in rows
                      if row["split"] == "gallery" and row["quality_status"] == "approved"),
                     key=lambda row: row["relative_path"])
    if not gallery:
        raise ValueError("No approved gallery masks; run --action remove_background first")
    artifact = prepare_codebook(config, feature_specs_for(config.bundle_name), gallery, workers=1)
    return {"codebook": codebook_path(config),
            "gallery_rows": len(gallery), "images_sampled": artifact["n_images_sampled"],
            "descriptors": artifact["n_descriptors"], "clusters": artifact["settings"]["clusters"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=["sources", "codebook", "remove_background", "extract_features", "pipeline"], default="pipeline")
    parser.add_argument("--limit", type=int, help="Limit segmentation/import for a smoke check; calibration still needs 500 gallery masks")
    args = parser.parse_args()
    config = AppConfig.default()
    rows = prepare_sources(config)
    print(json.dumps({"sources": len(rows), "unassigned": sum(r["split"] == "unassigned" for r in rows)}))
    if args.action == "codebook":
        print(json.dumps(prepare_codebook_only(config), ensure_ascii=True, indent=2))
    elif args.action != "sources":
        result = DatasetProcessingService(config).run(args.action, args.limit,
            lambda **event: print(json.dumps(event), flush=True), threading.Event(), "prepare-dataset")
        print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
