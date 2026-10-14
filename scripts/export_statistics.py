from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig
from backend.src.repository import Repository


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    config = AppConfig.default()
    repository = Repository(config)
    output_dir = config.result_directory("statistics")
    dataset_rows = repository.statistics_groups()
    config_rows = repository.registered_configs()
    feature_stat_rows: list[dict[str, object]] = []
    feature_summary_rows: list[dict[str, object]] = []
    for config_row in config_rows:
        vectors = repository.vectors_for_config(config_row["config_id"])
        if not vectors:
            continue
        matrix = np.asarray(vectors, dtype=np.float64)
        mins = matrix.min(axis=0)
        maxs = matrix.max(axis=0)
        means = matrix.mean(axis=0)
        stds = matrix.std(axis=0, ddof=0)
        for index in range(matrix.shape[1]):
            feature_stat_rows.append(
                {"config": config_row["name"], "dimension_index": index, "min": mins[index], "max": maxs[index], "mean": means[index], "std_ddof0": stds[index]}
            )
        norms = np.linalg.norm(matrix, axis=1)
        feature_summary_rows.append(
            {"config": config_row["name"], "feature_type": config_row["feature_type"], "dimension": config_row["dimension"], "n_vectors": matrix.shape[0], "norm_mean": float(norms.mean()), "norm_std_ddof0": float(norms.std(ddof=0)), "zero_vector_rate": float(np.mean(norms <= 1e-12))}
        )
    write_csv(output_dir / "dataset_stats.csv", dataset_rows)
    write_csv(output_dir / "feature_stats.csv", feature_stat_rows)
    write_csv(output_dir / "feature_summary.csv", feature_summary_rows)
    print(output_dir / "dataset_stats.csv")
    print(output_dir / "feature_stats.csv")
    print(output_dir / "feature_summary.csv")


if __name__ == "__main__":
    main()
