"""Score pooled human judgments; missing judgments are errors, never automatic negatives."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean


def visual_metrics(results, judgments, threshold=4):
    if not 0 <= threshold <= 6:
        raise ValueError("Threshold must be in [0,6]")
    graded = {}
    seen = set()
    raters = set()
    for row in judgments:
        key = (row["query_key"], str(row["image_id"]))
        rater = row["rater"].strip()
        if not rater:
            raise ValueError(f"Missing rater for {key}")
        if (*key, rater) in seen:
            raise ValueError(f"Duplicate judgment: {key}, {rater}")
        try:
            grades = [int(row[name]) for name in ("shape_grade", "color_grade", "texture_grade")]
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Incomplete judgment: {key}") from exc
        if any(value not in {0, 1, 2} for value in grades):
            raise ValueError(f"Grades must be 0, 1 or 2: {key}")
        seen.add((*key, rater))
        raters.add(rater)
        graded.setdefault(key, []).append(sum(grades))
    queries = {}
    for row in results:
        entries = queries.setdefault(row["run_id"], {}).setdefault(row["query_key"], [])
        if not row["error"]:
            entries.append(row)
    metrics = []
    for run, by_query in queries.items():
        precision = []
        failed = 0
        for query, items in by_query.items():
            if not items:
                failed += 1
                continue
            if sorted(int(item["rank"]) for item in items) != [1, 2, 3, 4, 5] or len({item["image_id"] for item in items}) != 5:
                raise ValueError(f"Expected five unique results: {run}/{query}")
            keys = [(query, str(item["image_id"])) for item in items]
            missing = [key for key in keys if key not in graded]
            if missing:
                raise ValueError(f"Missing judgments: {missing[:5]}")
            precision.append(sum(mean(graded[key]) >= threshold for key in keys) / 5)
        metrics.append({"run_id": run, "n_queries": len(by_query), "n_failed": failed,
                        "visual_p5_successful": mean(precision) if precision else None,
                        "visual_p5_all": sum(precision) / len(by_query)})
    return {"threshold": threshold, "aggregation": "mean rubric total across available raters per pair",
            "n_raters": len(raters), "raters": sorted(raters), "n_graded_pairs": len(graded), "metrics": metrics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.results.open(encoding="utf-8-sig", newline="") as stream:
        results = list(csv.DictReader(stream))
    with args.judgments.open(encoding="utf-8-sig", newline="") as stream:
        judgments = list(csv.DictReader(stream))
    report = visual_metrics(results, judgments)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
