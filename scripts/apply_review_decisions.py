from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Chuyển chỉ số contact sheet thành danh sách loại trừ ổn định")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--append-existing",
        type=Path,
        help="Merge stable source-member rejections from an earlier review round",
    )
    args = parser.parse_args()

    with args.manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        manifest_rows = list(csv.DictReader(stream))
    with args.decisions.open("r", encoding="utf-8-sig", newline="") as stream:
        decisions = list(csv.DictReader(stream))

    by_split = {
        split: [row for row in manifest_rows if row["split"] == split]
        for split in ("gallery", "validation", "test")
    }
    rejected: list[dict[str, str | int]] = []
    stable_seen: set[tuple[str, str]] = set()
    if args.append_existing:
        with args.append_existing.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                key = (row["source_archive"].casefold(), row["source_member"])
                if key not in stable_seen:
                    rejected.append(dict(row))
                    stable_seen.add(key)
    seen: set[tuple[str, int]] = set()
    for decision in decisions:
        split = decision["split"].strip()
        if split not in by_split:
            raise ValueError(f"Split không hợp lệ: {split}")
        for raw_index in decision["indices"].split():
            index = int(raw_index)
            key = (split, index)
            if key in seen:
                raise ValueError(f"Chỉ số lặp: {split} {index}")
            seen.add(key)
            if not 1 <= index <= len(by_split[split]):
                raise ValueError(f"Chỉ số ngoài phạm vi: {split} {index}")
            row = by_split[split][index - 1]
            if not row.get("source_archive") or not row.get("source_member"):
                raise ValueError(f"Không thể loại ảnh thiếu nguồn ổn định: {split} {index}")
            rejected_row = {
                    "split": split,
                    "review_index": index,
                    "species_name": row["species_name"],
                    "relative_path": row["relative_path"],
                    "source_archive": row["source_archive"],
                    "source_member": row["source_member"],
                    "reason": decision["reason"].strip(),
                }
            stable_key = (
                str(rejected_row["source_archive"]).casefold(),
                str(rejected_row["source_member"]),
            )
            if stable_key not in stable_seen:
                rejected.append(rejected_row)
                stable_seen.add(stable_key)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rejected[0]))
        writer.writeheader()
        writer.writerows(rejected)
    print(f"rejected={len(rejected)} output={args.output}")


if __name__ == "__main__":
    main()
