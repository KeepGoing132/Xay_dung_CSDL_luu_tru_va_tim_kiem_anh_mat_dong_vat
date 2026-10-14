"""Verify source provenance, image bytes, splits and every stored feature vector."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.src.config import AppConfig
from backend.src.features import extract_features
from backend.src.models import CropBox
from backend.src.preprocessing import preprocess_image
from backend.src.repository import Repository
from scripts.check_near_duplicates import difference_hash


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def verify(config):
    repository = Repository(config)
    bundle = repository.ensure_baseline_bundle()
    manifest = read_csv(config.default_manifest_path)
    sources = read_csv(config.data_root / "manifests/frontal512_sources.csv")
    records = repository.audit_image_records()
    features = repository.audit_feature_records()
    by_path = {row["relative_path"]: row for row in manifest}
    source_by_path = {row["relative_path"]: row for row in sources}
    assert len(by_path) == len(manifest) == len(records) == 600
    assert len(source_by_path) == len(sources) == 600
    assert set(by_path) == set(source_by_path) == {row["original_path"] for row in records}
    stored = {(r["image_id"], r["config_id"]): r for r in features}
    assert len(stored) == len(features) == 600 * len(bundle.config_ids)
    hashes, pixel_hashes, dhashes, groups = set(), set(), [], {}
    difference = 0.0
    for row in records:
        relative = row["original_path"]
        context = f"image_id={row['image_id']} path={relative}"
        entry, source = by_path[relative], source_by_path[relative]
        for key in ["split", "group_id", "quality_status", "species_name", "source_url", "license_note"]:
            assert row[key] == entry[key], f"Metadata mismatch: {key}; {context}"
        assert row["quality_status"] == "approved" and row["active"] == 1, context
        assert row["preprocess_version"] == config.preprocess_version, context
        assert source["archive_member"] == entry["source_member"], context
        assert source["source_page"] == entry["source_url"] and source["license"] == "CC BY-NC 4.0", context
        path = config.resolve_data_path(relative)
        raw = path.read_bytes()
        checksum = sha256(raw).hexdigest()
        assert checksum == source["source_sha256"] == row["original_sha256"], context
        assert checksum not in hashes, f"Duplicate bytes: {context}"
        hashes.add(checksum)
        with Image.open(path) as image:
            assert image.mode == "RGB" and image.size == (512, 512), context
            pixels = np.asarray(image)
            assert np.max(pixels.max(axis=2).astype(int) - pixels.min(axis=2).astype(int)) > 10, f"Grayscale: {context}"
            pixel_hash = sha256(pixels.tobytes()).hexdigest()
            assert pixel_hash not in pixel_hashes, f"Duplicate pixels: {context}"
            pixel_hashes.add(pixel_hash)
        crop = CropBox(**json.loads(row["crop_json"]))
        processed = preprocess_image(raw, crop, preprocess_version=config.preprocess_version)
        assert processed.pixel_sha256 == row["processed_sha256"], context
        with Image.open(config.resolve_data_path(row["processed_path"])) as image:
            assert image.mode == "RGB" and image.size == (config.image_size, config.image_size), context
            assert np.array_equal(np.asarray(image), processed.rgb), context
        computed = extract_features(processed, bundle)
        for key, config_id in bundle.config_ids.items():
            actual = np.asarray(json.loads(stored[(row["image_id"], config_id)]["vector_json"]), dtype=float)
            expected = computed.vectors[key]
            assert actual.shape == expected.shape and np.isfinite(actual).all(), context
            delta = float(np.max(np.abs(actual - expected)))
            difference = max(difference, delta)
            assert delta <= 1e-12, f"Vector mismatch: {key}; {context}"
        dhashes.append((relative, row["split"], difference_hash(path)))
        groups.setdefault(row["group_id"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in groups.values()), "Group crosses splits"
    near = []
    for index, (left, left_split, left_hash) in enumerate(dhashes):
        for right, right_split, right_hash in dhashes[index + 1:]:
            distance = (left_hash ^ right_hash).bit_count()
            if distance <= 5:
                near.append({"left": left, "right": right, "distance": distance, "cross_split": left_split != right_split})
    assert not near, near
    stats = repository.dataset_integrity()
    assert stats["integrity"] == "ok" and not stats["foreign_key_errors"], stats
    loaded = repository.load_candidates(bundle)
    assert len(loaded.candidates) == 500 and not loaded.rejected
    split_counts = Counter(row["split"] for row in records)
    assert split_counts == {"gallery": 500, "validation": 50, "test": 50}
    return {
        "snapshot": "frontal512-20261010", "images": len(records), "vectors": len(features),
        "split_counts": dict(split_counts), "source_dimensions": [512, 512], "source_mode": "RGB",
        "processed_dimensions": [config.image_size, config.image_size], "source_records": len(sources),
        "species_counts": dict(Counter(row["species_name"] for row in records)),
        "candidate_count": len(loaded.candidates), "rejected_candidates": len(loaded.rejected),
        "duplicate_bytes": 0, "duplicate_pixels": 0, "near_duplicates_dhash256_hamming5": len(near),
        "cross_split_groups": 0, "recomputed_vectors": len(features), "maximum_vector_difference": difference,
        "preprocess_version": config.preprocess_version, "bundle_name": config.bundle_name,
        "config_ids": bundle.config_ids, "database_integrity": stats,
        "visual_review": "Explicit contact-sheet decisions; no measured pose angle or animal identity guarantee",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", default="native512-v1", choices=["baseline-v1", "native512-v1", "expanded512-v1", "refined512-v1"])
    args = parser.parse_args()
    config = AppConfig.default(profile=args.profile)
    if args.db:
        config = replace(config, db_path=args.db.resolve())
    result = verify(config)
    output = args.output or config.result_directory("statistics") / "frontal512-verification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
