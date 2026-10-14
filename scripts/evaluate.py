"""Reproducible retrieval evaluation; labels and visual judgments stay separate."""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
from importlib.metadata import version
import json
import platform
from pathlib import Path
from statistics import mean, median
from time import perf_counter
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig, PROFILE_SETTINGS, default_weights_for
from backend.src.features import extract_features
from backend.src.ingestion import IngestionService
from backend.src.models import Weights
from backend.src.preprocessing import preprocess_image
from backend.src.repository import Repository
from backend.src.similarity import normalize_weights, compare_features, rank_scored_candidates

BASELINE_RUNS = {
    "A_HSV": Weights(1, 0, 0), "B_HOG": Weights(0, 1, 0), "C_LBP": Weights(0, 0, 1),
    "D_EQUAL": Weights(1, 1, 1),
}
TUNING_RUNS = {
    "T_COLOR": Weights(.5, .25, .25), "T_SHAPE": Weights(.25, .5, .25),
    "T_TEXTURE": Weights(.25, .25, .5), "T_COLOR_SHAPE": Weights(.45, .45, .1),
    "T_SHAPE_TEXTURE": Weights(.1, .45, .45),
}


def percentile95(values):
    return float(np.percentile(values, 95)) if values else ""


def validate_query_split(rows, records):
    if not rows:
        raise ValueError("The requested evaluation split is empty")
    groups = {record["group_id"] for record in records if record["split"] == "gallery"}
    paths = {record["original_path"] for record in records if record["split"] == "gallery"}
    seen = set()
    for row in rows:
        if row["group_id"] in groups or row["relative_path"] in paths:
            raise ValueError(f"Query overlaps gallery: {row['relative_path']}")
        if row["relative_path"] in seen:
            raise ValueError(f"Duplicate query: {row['relative_path']}")
        seen.add(row["relative_path"])
        if row["quality_status"] != "approved":
            raise ValueError(f"Query has not been approved: {row['relative_path']}")


def evaluate_runs(rows, runs, config, bundle, candidates, gallery_pixel_hashes=(), gallery_byte_hashes=()):
    per_query_rows = []
    known_species = {candidate.species_name.casefold() for candidate in candidates if candidate.species_name}
    accumulators = {key: {"p5": [], "latencies": [], "failed": 0, "by_label": {}, "known_total": 0} for key in runs}
    for index, row in enumerate(rows, 1):
        known = row["species_name"].casefold() in known_species
        for values in accumulators.values():
            values["known_total"] += int(known)
        base = {"query_key": row["relative_path"], "query_group_id": row["group_id"], "query_species": row["species_name"]}
        try:
            start = perf_counter()
            payload = config.resolve_data_path(row["relative_path"]).read_bytes()
            processed = preprocess_image(payload, IngestionService._crop_from_row(row), preprocess_version=config.preprocess_version)
            if processed.pixel_sha256 in gallery_pixel_hashes or sha256(payload).hexdigest() in gallery_byte_hashes:
                raise ValueError(f"Query pixels/bytes overlap gallery: {row['relative_path']}")
            query_features = extract_features(processed, bundle)
            components = [compare_features(query_features, candidate.features, Weights(1, 0, 0)) for candidate in candidates]
            shared_ms = (perf_counter() - start) * 1000
        except Exception as exc:
            if "overlap gallery" in str(exc):
                raise
            for run_id in runs:
                accumulators[run_id]["failed"] += 1
                per_query_rows.append({"run_id": run_id, **base, "rank": "", "image_id": "", "candidate_species": "",
                                       "scores_json": "", "total": "", "same_species": "", "latency_ms": "", "error": str(exc)})
            continue
        for run_id, weights in runs.items():
            start = perf_counter()
            items = rank_scored_candidates(candidates, components, weights, 5)
            latency = shared_ms + (perf_counter() - start) * 1000
            accumulators[run_id]["latencies"].append(latency)
            matches = 0
            for item in items:
                same = bool(item.species_name and item.species_name.casefold() == row["species_name"].casefold()) if known else None
                matches += int(same is True)
                per_query_rows.append({"run_id": run_id, **base, "rank": item.rank, "image_id": item.image_id,
                                       "candidate_species": item.species_name, "scores_json": json.dumps(item.scores.as_dict(), sort_keys=True),
                                       "total": item.scores.total, "same_species": "" if same is None else int(same),
                                       "latency_ms": latency, "error": ""})
            if known:
                values = accumulators[run_id]
                values["p5"].append(matches / 5)
                values["by_label"].setdefault(row["species_name"], []).append(matches / 5)
        if index % 10 == 0:
            print(f"Evaluated {index}/{len(rows)} queries", flush=True)
    metrics = []
    for run_id, weights in runs.items():
        values = accumulators[run_id]
        metrics.append({"run_id": run_id, "n_queries": len(rows), "n_failed": values["failed"],
                        "n_known_queries": len(values["p5"]),
                        "mean_same_species_p5": mean(values["p5"]) if values["p5"] else "",
                        "mean_all_known_p5": sum(values["p5"]) / values["known_total"] if values["known_total"] else "",
                        "macro_label_p5": mean(mean(v) for v in values["by_label"].values()) if values["by_label"] else "",
                        "per_label_p5": json.dumps({key: mean(v) for key, v in values["by_label"].items()}, sort_keys=True),
                        "latency_median_ms": median(values["latencies"]) if values["latencies"] else "",
                        "latency_p95_ms": percentile95(values["latencies"]),
                        "weights": json.dumps(normalize_weights(weights).as_dict(), sort_keys=True)})
    return per_query_rows, metrics


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=list(PROFILE_SETTINGS))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--split", choices=["validation", "test"], default="validation")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("limit must be positive")
    config = AppConfig.default(args.profile)
    repository = Repository(config)
    repository.create_schema()
    bundle = repository.ensure_baseline_bundle()
    load_start = perf_counter()
    loaded = repository.load_candidates(bundle)
    load_ms = (perf_counter() - load_start) * 1000
    if len(loaded.candidates) < 500:
        raise SystemExit(f"Evaluation requires at least 500 valid gallery images; got {len(loaded.candidates)}")
    manifest = args.manifest or config.default_manifest_path
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        all_rows = list(csv.DictReader(stream))
    records = repository.audit_image_records()
    rows = [row for row in all_rows if row["split"] == args.split]
    validate_query_split(rows, records)
    split_groups = {}
    for row in all_rows:
        split_groups.setdefault(row["group_id"], set()).add(row["split"])
    if any(len(splits) > 1 for splits in split_groups.values()):
        raise ValueError("Manifest contains source groups crossing splits")
    if args.limit:
        rows = rows[:args.limit]
    output = args.output_dir or config.result_directory("evaluation")
    output.mkdir(parents=True, exist_ok=True)
    selected_path = output / "selected_weights.json"
    signature = {"bundle_name": bundle.name, "config_ids": bundle.config_ids,
                 "manifest_sha256": sha256(manifest.read_bytes()).hexdigest(),
                 "gallery_fingerprint_sha256": sha256(repr(repository.gallery_fingerprint(bundle)).encode()).hexdigest()}
    runs = dict(BASELINE_RUNS)
    if bundle.extras:
        for key in bundle.extras:
            runs[f"SINGLE_{key.upper()}"] = Weights.from_dict({key: 1})
        runs["F_EQUAL_ALL"] = Weights.from_dict({key: 1 for key in bundle.configs})
        runs["G_DEFAULT_ALL"] = Weights.from_dict(default_weights_for(bundle.name))
        runs["H_SHAPE_SPATIAL_TEXTURE"] = Weights.from_dict({"hog": .6, "spatial_hsv": .2, "glcm": .2})
    if args.split == "validation":
        runs.update(TUNING_RUNS)
    else:
        if not selected_path.exists():
            raise ValueError("Run full validation first to select weights")
        selected = json.loads(selected_path.read_text(encoding="utf-8"))
        if selected.get("signature") != signature:
            raise ValueError("Selected weights belong to another dataset/configuration; rerun validation")
        runs["E_SELECTED"] = Weights.from_dict(selected["weights"])
    gallery = [r for r in records if r["split"] == "gallery"]
    per_query, metrics = evaluate_runs(rows, runs, config, bundle, loaded.candidates,
                                      {r["processed_sha256"] for r in gallery}, {r["original_sha256"] for r in gallery})
    write_csv(output / f"per_query_results_{args.split}.csv", per_query)
    write_csv(output / f"metrics_{args.split}.csv", metrics)
    if args.split == "validation" and args.limit is None:
        eligible = [r for r in metrics if r["mean_all_known_p5"] != "" and r["n_failed"] == 0]
        if not eligible:
            raise ValueError("No complete run with known-label queries; weights were not selected")
        best = sorted(eligible, key=lambda r: (-r["mean_all_known_p5"], r["run_id"]))[0]
        selected_path.write_text(json.dumps({"signature": signature, "selected_from": best["run_id"],
            "validation_mean_same_species_p5": best["mean_all_known_p5"], "weights": json.loads(best["weights"]),
            "rule": "max validation mean_all_known_p5; no failed queries; tie by run_id; labels only, not visual judgments"}, indent=2), encoding="utf-8")
    experiment = {**signature, "split": args.split, "n_queries": len(rows), "candidate_count": len(loaded.candidates),
                  "query_keys": [r["relative_path"] for r in rows],
                  "rejected_candidates": [r.__dict__ for r in loaded.rejected],
                  "preprocess_version": bundle.preprocess_version,
                  "parameters": {k: v.parameters for k, v in bundle.configs.items()},
                  "dimensions": {k: v.dimension for k, v in bundle.configs.items()},
                  "runs": {k: normalize_weights(v).as_dict() for k, v in runs.items()},
                  "platform": platform.platform(), "python": platform.python_version(),
                  "libraries": {k: version(k) for k in ["numpy", "scikit-image", "pillow"]},
                  "gallery_load_ms": load_ms,
                  "timing_note": "query read/preprocess/extract/all component scores/rank; shared component time attributed to each run; gallery load separate; no web, segmentation, previews or persistence",
                  "note": "Same-label P@5 is not species probability or visual relevance. Human judgments are still required."}
    (output / f"experiment_{args.split}.json").write_text(json.dumps(experiment, indent=2), encoding="utf-8")
    pairs = sorted({(r["query_key"], r["image_id"]) for r in per_query if r["image_id"] != ""})
    judgments = output / f"judgments_pool_{args.split}.csv"
    if not judgments.exists():
        write_csv(judgments, [{"query_key": key, "image_id": image_id, "shape_grade": "", "color_grade": "", "texture_grade": "", "rater": ""} for key, image_id in pairs])
    print(output / f"metrics_{args.split}.csv")


if __name__ == "__main__":
    main()
