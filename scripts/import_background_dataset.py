"""CLI for the shared background-image ingestion service."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig, BACKGROUND_BUNDLE_NAME, BACKGROUND512_BUNDLE_NAME
from backend.src.background_import import build_manifest, run_import

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutouts-dir", type=Path, default=Path("data/background_removed/all-images"))
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--allow-partial", action="store_true", help="For small trials; not an acceptance dataset")
    parser.add_argument("--reviewed", action="store_true", help="Only after reviewing masks; inherit source approval")
    parser.add_argument("--profile", choices=[BACKGROUND_BUNDLE_NAME, BACKGROUND512_BUNDLE_NAME], default=BACKGROUND512_BUNDLE_NAME)
    args = parser.parse_args()
    config = AppConfig.default(profile=args.profile)
    if args.db:
        config = replace(config, db_path=args.db.resolve())
    try:
        source_manifest = args.source_manifest or AppConfig.default(profile="baseline-v1").default_manifest_path
        result = run_import(config, source_manifest.resolve(), args.cutouts_dir.resolve(),
                            (args.manifest or config.default_manifest_path).resolve(),
                            allow_partial=args.allow_partial, reviewed=args.reviewed)
    except (ValueError, OSError, sqlite3.Error) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
