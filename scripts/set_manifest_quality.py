from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Cập nhật trạng thái duyệt sau khi xem contact sheet")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--status", required=True, choices=["pending", "approved", "rejected"])
    parser.add_argument("--split", action="append", choices=["gallery", "validation", "test"])
    args = parser.parse_args()
    config = AppConfig.default()
    manifest = args.manifest or config.default_manifest_path
    with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        rows = list(reader)
    targets = set(args.split or ["gallery", "validation", "test"])
    changed = 0
    for row in rows:
        if row["split"] in targets:
            row["quality_status"] = args.status
            changed += 1
    with manifest.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Đã cập nhật {changed} dòng thành {args.status}: {manifest}")


if __name__ == "__main__":
    main()
