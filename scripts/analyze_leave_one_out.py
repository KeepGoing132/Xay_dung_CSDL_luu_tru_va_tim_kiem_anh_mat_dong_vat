"""So sánh các run bỏ-một-đặc-trưng với run đầy đủ trên cùng bộ query.

Đọc metrics_<split>.csv và per_query_results_<split>.csv do evaluate.py sinh ra, tính
chênh lệch P@5/top-1/top-5 và đối chiếu theo từng query (thắng/hòa/thua), để trả lời
một nhóm đặc trưng — ví dụ Gabor — đóng góp dương hay âm trên bộ query độc lập.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig

METRIC_COLUMNS = ("mean_same_species_p5", "mean_all_known_p5", "macro_label_p5",
                  "top1_accuracy", "top5_accuracy", "latency_median_ms")


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def per_query_scores(rows: list[dict]) -> dict[str, dict[str, dict]]:
    """run_id -> query_key -> {p5, top1, any_hit} từ các dòng top-5."""
    grouped: dict[str, dict[str, dict]] = {}
    for row in rows:
        if not row.get("image_id"):
            continue
        run = grouped.setdefault(row["run_id"], {})
        entry = run.setdefault(row["query_key"], {"matches": 0, "top1": 0, "scores": []})
        entry["matches"] += int(row["same_species"] == "1")
        entry["top1"] += int(row["rank"] == "1" and row["same_species"] == "1")
        entry["scores"].append(float(row["total"]))
    for run in grouped.values():
        for entry in run.values():
            entry["p5"] = entry["matches"] / 5
            entry["any_hit"] = int(entry["matches"] > 0)
    return grouped


def compare(run: str, grouped: dict, reference_run: str) -> dict:
    reference = grouped.get(reference_run, {})
    win = loss = tie = 0
    top1_gained = top1_lost = 0
    any_gained = any_lost = 0
    for query, entry in grouped.get(run, {}).items():
        base = reference.get(query)
        if base is None:
            continue
        if entry["p5"] > base["p5"]:
            win += 1
        elif entry["p5"] < base["p5"]:
            loss += 1
        else:
            tie += 1
        if entry["top1"] > base["top1"]:
            top1_gained += 1
        elif entry["top1"] < base["top1"]:
            top1_lost += 1
        if entry["any_hit"] > base["any_hit"]:
            any_gained += 1
        elif entry["any_hit"] < base["any_hit"]:
            any_lost += 1
    return {"paired_queries": win + loss + tie, "p5_win": win, "p5_loss": loss, "p5_tie": tie,
            "top1_gained": top1_gained, "top1_lost": top1_lost,
            "any_hit_gained": any_gained, "any_hit_lost": any_lost}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Thư mục chứa metrics_<split>.csv và per_query_results_<split>.csv")
    parser.add_argument("--split", default="test")
    parser.add_argument("--reference", default="ALL4_DEFAULT")
    parser.add_argument("--prefix", default="ALL4_NO_", help="Tiền tố các run bỏ-một-đặc-trưng")
    args = parser.parse_args()
    metrics = {row["run_id"]: row for row in read_csv(args.output_dir / f"metrics_{args.split}.csv")}
    if args.reference not in metrics:
        raise SystemExit(f"Thiếu run tham chiếu {args.reference} trong metrics_{args.split}.csv")
    grouped = per_query_scores(read_csv(args.output_dir / f"per_query_results_{args.split}.csv"))
    base = metrics[args.reference]
    rows = []
    for run_id, values in metrics.items():
        row = {"run_id": run_id, "n_queries": values["n_queries"], "n_failed": values["n_failed"]}
        for column in METRIC_COLUMNS:
            row[column] = values[column]
            row[f"delta_{column}"] = (round(float(values[column]) - float(base[column]), 4)
                                      if values[column] != "" and base[column] != "" else "")
        row["family"] = "reference" if run_id == args.reference else (
            "leave_one_out" if run_id.startswith(args.prefix) else "other")
        if run_id != args.reference:
            row.update(compare(run_id, grouped, args.reference))
        rows.append(row)
    # Run tham chiếu mặc định giữ tên cũ; tham chiếu khác gắn hậu tố để không ghi đè nhau.
    suffix = "" if args.reference == "ALL4_DEFAULT" else f"_vs_{args.reference}"
    output = args.output_dir / f"leave_one_out_{args.split}{suffix}.csv"
    fieldnames = list(rows[0])
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "reference": args.reference, "split": args.split,
        "base_metrics": {column: base[column] for column in METRIC_COLUMNS},
        "runs": [{"run_id": row["run_id"], "family": row["family"],
                  "delta_mean_same_species_p5": row["delta_mean_same_species_p5"],
                  "delta_top1_accuracy": row["delta_top1_accuracy"],
                  "p5_win": row.get("p5_win"), "p5_loss": row.get("p5_loss")} for row in rows],
    }
    (args.output_dir / f"leave_one_out_{args.split}{suffix}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(output)


if __name__ == "__main__":
    main()
