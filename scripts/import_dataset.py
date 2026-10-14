from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.src.config import AppConfig, PROFILE_SETTINGS
from backend.src.ingestion import IngestionService
from backend.src.repository import Repository


def main() -> None:
    parser = argparse.ArgumentParser(description="Nhập manifest và trích xuất cấu hình CBIR_PROFILE đang chọn")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--errors", type=Path)
    parser.add_argument("--profile", choices=list(PROFILE_SETTINGS))
    args = parser.parse_args()
    config = AppConfig.default(args.profile)
    config.ensure_runtime_dirs()
    repository = Repository(config)
    repository.create_schema()
    manifest = args.manifest or config.default_manifest_path
    def progress(completed, total, source, created, skipped, failed):
        if completed % 25 == 0 or completed == total:
            print(f"{completed}/{total}: created={created} skipped={skipped} failed={failed}", flush=True)
    summary = IngestionService(config, repository).import_manifest(manifest, progress=progress)
    print(f"total={summary.total} created={summary.created} skipped={summary.skipped} failed={summary.failed}")
    if summary.errors:
        output = args.errors or config.data_root / "manifests" / "rejected.csv"
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["row_number", "relative_path", "code", "message"])
            writer.writeheader()
            for error in summary.errors:
                writer.writerow(error.__dict__)
        print(f"Errors: {output}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
