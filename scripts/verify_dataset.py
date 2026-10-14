from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig
from backend.src.repository import Repository


def main() -> None:
    config = AppConfig.default()
    repository = Repository(config)
    bundle = repository.ensure_baseline_bundle()
    with repository.connect() as connection:
        splits = [tuple(row) for row in connection.execute("SELECT split, COUNT(*) FROM images GROUP BY split ORDER BY split")]
        species = [
            tuple(row)
            for row in connection.execute(
                """
                SELECT s.name, COUNT(*) FROM images i JOIN species s USING(species_id)
                WHERE split='gallery' GROUP BY s.name ORDER BY s.name
                """
            )
        ]
        features = [
            tuple(row)
            for row in connection.execute(
                """
                SELECT fc.name, fc.dimension, COUNT(*)
                FROM image_features f JOIN feature_configs fc USING(config_id)
                GROUP BY fc.config_id ORDER BY fc.config_id
                """
            )
        ]
        missing = connection.execute(
            """
            SELECT COUNT(*) FROM images i WHERE split='gallery' AND
            (SELECT COUNT(*) FROM image_features f WHERE f.image_id=i.image_id) != 3
            """
        ).fetchone()[0]
        duplicate_hashes = connection.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT original_sha256, COUNT(*) AS n FROM images
                GROUP BY original_sha256 HAVING n > 1
            )
            """
        ).fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    loaded = repository.load_candidates(bundle)
    print(f"splits={splits}")
    print(f"gallery_species={species}")
    print(f"features={features}")
    print(f"missing_gallery_vectors={missing}")
    print(f"duplicate_original_hashes={duplicate_hashes}")
    print(f"candidate_count={len(loaded.candidates)} rejected={len(loaded.rejected)}")
    print(f"db_integrity={integrity}")
    failures = []
    if sum(count for split, count in splits if split == "gallery") < 500:
        failures.append("gallery < 500")
    if missing:
        failures.append("gallery thiếu vector")
    if duplicate_hashes:
        failures.append("trùng checksum gốc")
    if len(loaded.candidates) < 500 or loaded.rejected:
        failures.append("candidate set không đạt")
    if integrity != "ok":
        failures.append("SQLite integrity check lỗi")
    if failures:
        raise SystemExit("; ".join(failures))


if __name__ == "__main__":
    main()
