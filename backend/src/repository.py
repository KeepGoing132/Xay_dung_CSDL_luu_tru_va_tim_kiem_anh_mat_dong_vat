from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

import numpy as np
from PIL import Image

from .config import AppConfig, feature_specs_for
from .calibration import calibrated_specs
from .errors import AppError, invalid
from .models import (
    BundleConfig,
    Candidate,
    FeatureBundle,
    FeatureConfig,
    ImageMetadata,
    LoadCandidatesResult,
    RejectedCandidate,
    SearchItem,
    Weights,
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Repository:
    def __init__(self, config: AppConfig):
        self.config = config

    def backup_to(self, destination: Path) -> None:
        if destination.exists():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(self.config.db_path.resolve().as_uri() + "?mode=ro", uri=True)
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise invalid("PERSISTENCE_ERROR", "Bản sao CSDL không hợp lệ", path=str(destination))
        finally:
            source.close()
            target.close()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.config.db_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
        finally:
            connection.close()

    def create_schema(self) -> None:
        if not self.config.migration_path.exists():
            raise FileNotFoundError(self.config.migration_path)
        sql = self.config.migration_path.read_text(encoding="utf-8")
        with self.connect() as connection:
            connection.executescript(sql)
            connection.commit()
            for migration in sorted(self.config.migration_path.parent.glob("[0-9][0-9][0-9]_*.sql")):
                version = int(migration.name.split("_", 1)[0])
                if connection.execute("SELECT 1 FROM schema_migrations WHERE version=?", (version,)).fetchone():
                    continue
                rebuild_images = migration.name in {"003_image_sizes.sql", "004_extended_features.sql"}
                try:
                    if rebuild_images:
                        connection.execute("PRAGMA foreign_keys = OFF")
                    connection.executescript("BEGIN IMMEDIATE;\n" + migration.read_text(encoding="utf-8"))
                    if connection.execute("PRAGMA foreign_key_check").fetchall():
                        raise invalid("PERSISTENCE_ERROR", "Migration tạo lỗi khóa ngoại", migration=migration.name)
                    connection.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)", (version,))
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
                finally:
                    if rebuild_images:
                        connection.execute("PRAGMA foreign_keys = ON")

    def upsert_species(self, name: str | None, connection: sqlite3.Connection) -> int | None:
        if name is None or not name.strip():
            return None
        normalized = " ".join(name.split()).casefold()
        connection.execute("INSERT OR IGNORE INTO species(name) VALUES (?)", (normalized,))
        row = connection.execute("SELECT species_id FROM species WHERE name = ?", (normalized,)).fetchone()
        if row is None:
            raise invalid("PERSISTENCE_ERROR", "Không thể tạo hoặc đọc species", name=normalized)
        return int(row["species_id"])

    def register_feature_config(self, spec: dict[str, Any]) -> FeatureConfig:
        parameters_json = _canonical_json(spec["parameters"])
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM feature_configs WHERE name = ?", (spec["name"],)
            ).fetchone()
            if row is not None:
                actual = (
                    row["feature_type"],
                    int(row["dimension"]),
                    row["parameters_json"],
                    row["preprocess_version"],
                )
                expected = (
                    spec["feature_type"],
                    int(spec["dimension"]),
                    parameters_json,
                    self.config.preprocess_version,
                )
                if actual != expected:
                    raise invalid(
                        "CONFIG_CONFLICT",
                        "Tên cấu hình đã tồn tại với tham số khác",
                        name=spec["name"],
                    )
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO feature_configs(name, feature_type, dimension, parameters_json, preprocess_version)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        spec["name"],
                        spec["feature_type"],
                        int(spec["dimension"]),
                        parameters_json,
                        self.config.preprocess_version,
                    ),
                )
                connection.commit()
                row = connection.execute(
                    "SELECT * FROM feature_configs WHERE config_id = ?", (cursor.lastrowid,)
                ).fetchone()
            assert row is not None
            return self._feature_config_from_row(row)

    @staticmethod
    def _feature_config_from_row(row: sqlite3.Row) -> FeatureConfig:
        return FeatureConfig(
            config_id=int(row["config_id"]),
            name=str(row["name"]),
            feature_type=str(row["feature_type"]),
            dimension=int(row["dimension"]),
            parameters=json.loads(row["parameters_json"]),
            preprocess_version=str(row["preprocess_version"]),
        )

    def ensure_baseline_bundle(self) -> BundleConfig:
        specs = feature_specs_for(self.config.bundle_name, self.config.preprocess_version)
        specs = calibrated_specs(self.config, specs)
        configs = {name: self.register_feature_config(spec) for name, spec in specs.items()}
        return BundleConfig(name=self.config.bundle_name, hsv=configs["hsv"], hog=configs["hog"], lbp=configs["lbp"],
                            extras={name: spec for name, spec in configs.items() if name not in {"hsv", "hog", "lbp"}})

    def find_image_by_original_sha(self, checksum: str) -> int | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT image_id FROM images WHERE original_sha256 = ?", (checksum,)
            ).fetchone()
            return int(row["image_id"]) if row else None

    def set_image_quality(self, checksum: str, status: str, review_note: str | None) -> None:
        if status not in {"pending", "approved", "rejected"}:
            raise ValueError(f"Unknown quality status: {status}")
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE images SET quality_status=?, active=?, review_note=? WHERE original_sha256=?",
                (status, int(status != "rejected"), review_note, checksum),
            )
            if cursor.rowcount != 1:
                raise invalid("MISSING_IMAGE_FILE", "Không có ảnh cần cập nhật trạng thái", checksum=checksum)
            connection.commit()

    def dataset_integrity(self) -> dict[str, Any]:
        with self.connect() as connection:
            return {
                "integrity": connection.execute("PRAGMA integrity_check").fetchone()[0],
                "foreign_key_errors": [dict(row) for row in connection.execute("PRAGMA foreign_key_check")],
                "image_count": connection.execute("SELECT COUNT(*) FROM images").fetchone()[0],
                "vector_count": connection.execute("SELECT COUNT(*) FROM image_features").fetchone()[0],
            }

    def set_image_qualities(self, decisions: list[tuple[str, str, str]]) -> None:
        if any(status not in {"approved", "pending", "rejected"} for _, status, _ in decisions):
            raise ValueError("Invalid quality status")
        with self.connect() as connection:
            try:
                connection.execute("BEGIN")
                for checksum, status, note in decisions:
                    cursor = connection.execute(
                        "UPDATE images SET quality_status=?, active=?, review_note=? WHERE original_sha256=?",
                        (status, int(status != "rejected"), note, checksum))
                    if cursor.rowcount != 1:
                        raise invalid("MISSING_IMAGE_FILE", "Không tìm thấy ảnh để duyệt", checksum=checksum)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def update_image_attributions(self, records: list[tuple[str, str, str, str]]) -> None:
        with self.connect() as connection:
            with connection:
                connection.executemany("UPDATE images SET original_path=?, source_url=?, license_note=? WHERE original_sha256=?",
                                       [(path, url or None, note or None, checksum) for checksum, path, url, note in records])

    def retire_other_mask_versions(self, records: list[tuple[str, str]]) -> None:
        with self.connect() as connection:
            with connection:
                connection.executemany(
                    "UPDATE images SET active=0, quality_status='rejected', review_note='Superseded mask; immutable input and vectors retained for history' "
                    "WHERE group_id=? AND original_sha256!=? AND preprocess_version=? AND active=1",
                    [(group, checksum, self.config.preprocess_version) for group, checksum in records])

    def audit_image_records(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT i.*, s.name AS species_name FROM images i "
                "LEFT JOIN species s USING(species_id) ORDER BY i.image_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def audit_feature_records(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM image_features ORDER BY image_id, config_id").fetchall()
        return [dict(row) for row in rows]

    def statistics_groups(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT i.split, COALESCE(s.name, 'unknown') AS species, i.quality_status, i.active, COUNT(*) AS image_count "
                "FROM images i LEFT JOIN species s USING(species_id) "
                "GROUP BY i.split, COALESCE(s.name, 'unknown'), i.quality_status, i.active ORDER BY i.split, species"
            ).fetchall()
        return [dict(row) for row in rows]

    def registered_configs(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM feature_configs ORDER BY config_id").fetchall()
        return [dict(row) for row in rows]

    def vectors_for_config(self, config_id: int) -> list[list[float]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT vector_json FROM image_features WHERE config_id=? ORDER BY image_id", (config_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    @staticmethod
    def _validate_vector(vector: np.ndarray, config: FeatureConfig) -> np.ndarray:
        array = np.asarray(vector, dtype=np.float64)
        if array.shape != (config.dimension,):
            raise invalid(
                "INVALID_VECTOR",
                "Vector sai số chiều",
                config_id=config.config_id,
                expected=config.dimension,
                actual=int(array.size),
            )
        if not np.isfinite(array).all() or (array < -1e-12).any():
            raise invalid("INVALID_VECTOR", "Vector chứa NaN, Infinity hoặc giá trị âm")
        normalization = config.parameters["normalization"]
        if normalization.startswith("L1") and not np.isclose(array.sum(), 1.0, atol=1e-6, rtol=0):
            raise invalid("INVALID_VECTOR", "Histogram không chuẩn hóa L1", config_id=config.config_id)
        if normalization == "L2":
            norm = float(np.linalg.norm(array))
            if not (norm <= 1e-12 or np.isclose(norm, 1.0, atol=1e-6, rtol=0)):
                raise invalid("INVALID_VECTOR", "Vector không chuẩn hóa L2", config_id=config.config_id)
        if normalization == "bounded" and (array > 1.0 + 1e-12).any():
            raise invalid("INVALID_VECTOR", "Vector vượt miền [0,1]", config_id=config.config_id)
        return array

    def insert_image_with_features(
        self,
        metadata: ImageMetadata,
        features: FeatureBundle,
        bundle: BundleConfig,
    ) -> int:
        expected_ids = bundle.config_ids
        if (metadata.preprocess_version != bundle.preprocess_version
                or features.preprocess_version != bundle.preprocess_version
                or bundle.name != self.config.bundle_name):
            raise invalid("CONFIG_MISMATCH", "Metadata hoặc bundle không khớp profile lưu trữ")
        if features.config_ids != expected_ids:
            raise invalid("CONFIG_MISMATCH", "Feature bundle không khớp cấu hình lưu")
        if features.vectors.keys() != bundle.configs.keys():
            raise invalid("CONFIG_MISMATCH", "Bundle thiếu hoặc thừa vector")
        vectors = {name: self._validate_vector(features.vectors[name], spec) for name, spec in bundle.configs.items()}
        with self.connect() as connection:
            try:
                connection.execute("BEGIN")
                species_id = self.upsert_species(metadata.species_name, connection)
                cursor = connection.execute(
                    """
                    INSERT INTO images(
                        species_id, original_path, processed_path, width, height, channels,
                        original_sha256, processed_sha256, source_url, license_note, split,
                        group_id, crop_json, preprocess_version, quality_status, active, review_note
                    ) VALUES (?, ?, ?, ?, ?, 3, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        species_id,
                        metadata.original_path,
                        metadata.processed_path,
                        self.config.image_size,
                        self.config.image_size,
                        metadata.original_sha256,
                        metadata.processed_sha256,
                        metadata.source_url,
                        metadata.license_note,
                        metadata.split,
                        metadata.group_id,
                        _canonical_json({"x": metadata.crop.x, "y": metadata.crop.y, "size": metadata.crop.size}),
                        metadata.preprocess_version,
                        metadata.quality_status,
                        int(metadata.active),
                        metadata.review_note,
                    ),
                )
                image_id = int(cursor.lastrowid)
                for name, vector in vectors.items():
                    config = bundle.configs[name]
                    warning = "zero_gradient" if name == "hog" and "zero_gradient" in features.warnings else None
                    connection.execute(
                        """
                        INSERT INTO image_features(image_id, config_id, vector_json, vector_norm, warning)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            image_id,
                            config.config_id,
                            json.dumps(vector.tolist(), separators=(",", ":"), allow_nan=False),
                            float(np.linalg.norm(vector)),
                            warning,
                        ),
                    )
                connection.commit()
                return image_id
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                if "images.original_sha256" in str(exc):
                    raise invalid("DUPLICATE_IMAGE", "Ảnh đã được nhập", checksum=metadata.original_sha256) from exc
                raise invalid("PERSISTENCE_ERROR", "Ràng buộc CSDL từ chối ảnh", reason=str(exc)) from exc
            except Exception:
                connection.rollback()
                raise

    def load_candidates(self, bundle: BundleConfig) -> LoadCandidatesResult:
        candidates: list[Candidate] = []
        rejected: list[RejectedCandidate] = []
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT i.*, s.name AS species_name FROM images i LEFT JOIN species s USING(species_id) "
                "WHERE i.split='gallery' AND i.active=1 AND i.quality_status='approved' "
                "AND i.preprocess_version=? ORDER BY i.image_id", (bundle.preprocess_version,)
            ).fetchall()
            ids = tuple(bundle.config_ids.values())
            placeholders = ",".join("?" for _ in ids)
            features = connection.execute(
                "SELECT f.image_id, f.config_id, f.vector_json FROM image_features f JOIN images i USING(image_id) "
                "WHERE i.split='gallery' AND i.active=1 AND i.quality_status='approved' "
                f"AND i.preprocess_version=? AND f.config_id IN ({placeholders})",
                (bundle.preprocess_version, *ids),
            ).fetchall()
        stored = {(row["image_id"], row["config_id"]): row["vector_json"] for row in features}
        for row in rows:
            image_id = int(row["image_id"])
            processed_path = str(row["processed_path"])
            try:
                actual_path = self.config.resolve_data_path(processed_path)
            except ValueError:
                rejected.append(RejectedCandidate(image_id, processed_path, "INVALID_IMAGE_PATH"))
                continue
            if not actual_path.is_file():
                rejected.append(RejectedCandidate(image_id, processed_path, "MISSING_IMAGE_FILE"))
                continue
            try:
                with Image.open(actual_path) as image:
                    image.load()
                    if image.mode != "RGB" or image.size != (row["width"], row["height"]):
                        raise ValueError("Image dimensions/mode differ from stored metadata")
                    if sha256(image.tobytes()).hexdigest() != row["processed_sha256"]:
                        raise ValueError("Image pixels differ from the vector input checksum")
            except (OSError, ValueError, Image.DecompressionBombError) as exc:
                rejected.append(RejectedCandidate(image_id, processed_path, f"INVALID_IMAGE: {exc}"))
                continue
            if any((image_id, spec.config_id) not in stored for spec in bundle.configs.values()):
                rejected.append(RejectedCandidate(image_id, processed_path, "MISSING_FEATURE"))
                continue
            try:
                vectors = {name: self._validate_vector(np.asarray(json.loads(stored[image_id, spec.config_id])), spec)
                           for name, spec in bundle.configs.items()}
            except (ValueError, TypeError, AppError) as exc:
                rejected.append(RejectedCandidate(image_id, processed_path, f"INVALID_VECTOR: {exc}"))
                continue
            candidates.append(Candidate(
                image_id=image_id, processed_path=processed_path, species_name=row["species_name"],
                features=FeatureBundle(
                    hsv=vectors["hsv"], hog=vectors["hog"], lbp=vectors["lbp"], config_ids=bundle.config_ids,
                    preprocess_version=bundle.preprocess_version,
                    extras={name: vectors[name] for name in bundle.extras},
                    similarities={name: spec.parameters["similarity"] for name, spec in bundle.configs.items() if "similarity" in spec.parameters},
                    config_signature=bundle.signature,
                )))
        return LoadCandidatesResult(tuple(candidates), tuple(rejected))

    def gallery_fingerprint(self, bundle: BundleConfig) -> tuple:
        """Track row edits and file disappearance/restoration, including rejected rows."""
        with self.connect() as connection:
            revision = connection.execute("SELECT revision FROM gallery_revision WHERE singleton=1").fetchone()[0]
            rows = connection.execute(
                """
                SELECT image_id, processed_path
                FROM images
                WHERE split='gallery' AND active=1 AND quality_status='approved'
                  AND preprocess_version=?
                ORDER BY image_id
                """,
                (bundle.preprocess_version,),
            ).fetchall()
        files = []
        for row in rows:
            try:
                path = self.config.resolve_data_path(row["processed_path"])
                stat = path.stat() if path.is_file() else None
                signature = (stat.st_size, stat.st_mtime_ns) if stat else None
            except (OSError, ValueError):
                signature = None
            files.append((row["image_id"], row["processed_path"], signature))
        return (revision, tuple(sorted(bundle.config_ids.items())), bundle.preprocess_version, tuple(files))

    def save_search(
        self,
        *,
        query_path: str,
        query_sha256: str,
        bundle: BundleConfig,
        weights: Weights,
        candidate_count: int,
        timings: dict[str, float],
        items: tuple[SearchItem, ...],
        gallery_signature: str | None = None,
    ) -> int:
        if len(items) != 5 or [item.rank for item in items] != [1, 2, 3, 4, 5]:
            raise invalid("PERSISTENCE_ERROR", "Kết quả phải có đúng rank 1..5")
        if len({item.image_id for item in items}) != 5:
            raise invalid("PERSISTENCE_ERROR", "Kết quả chứa image_id trùng")
        for item in items:
            if item.scores.as_dict().keys() != bundle.configs.keys():
                raise invalid("PERSISTENCE_ERROR", "Điểm thành phần không khớp cấu hình")
            values = [*item.scores.as_dict().values(), item.scores.total]
            if not all(np.isfinite(value) and 0 <= value <= 1 for value in values):
                raise invalid("PERSISTENCE_ERROR", "Điểm không hữu hạn hoặc ngoài [0,1]")
            recomputed = sum(item.scores.contributions(weights).values())
            if abs(recomputed - item.scores.total) > 1e-6:
                raise invalid("PERSISTENCE_ERROR", "total_score không khớp weighted sum")
        duration = sum(timings.get(name, 0.0) for name in ("preprocess_ms", "extract_ms", "load_ms", "rank_ms"))
        search_config = {
            "bundle_name": bundle.name,
            "config_ids": bundle.config_ids,
            "preprocess_version": bundle.preprocess_version,
            "weights": weights.as_dict(),
            "k": 5,
            "algorithm_version": "calibrated-cbir-v1" if "similarity" in bundle.hsv.parameters else "weighted-cbir-v2",
            "config_signature": bundle.signature,
            "parameters": {name: spec.parameters for name, spec in bundle.configs.items()},
            "dimensions": {name: spec.dimension for name, spec in bundle.configs.items()},
            "gallery_signature": gallery_signature,
            "library_versions": {name: version(name) for name in ("numpy", "scikit-image", "pillow")},
        }
        with self.connect() as connection:
            try:
                connection.execute("BEGIN")
                cursor = connection.execute(
                    """
                    INSERT INTO search_queries(
                        query_path, query_sha256, search_config_json, candidate_count, duration_ms, timings_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        query_path,
                        query_sha256,
                        _canonical_json(search_config),
                        candidate_count,
                        duration,
                        _canonical_json(timings),
                    ),
                )
                query_id = int(cursor.lastrowid)
                connection.executemany(
                    """
                    INSERT INTO search_results(
                        query_id, rank, image_id, hsv_score, hog_score, lbp_score, total_score, extra_scores_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            query_id,
                            item.rank,
                            item.image_id,
                            item.scores.hsv,
                            item.scores.hog,
                            item.scores.lbp,
                            item.scores.total,
                            _canonical_json(item.scores.extras),
                        )
                        for item in items
                    ],
                )
                connection.commit()
                return query_id
            except Exception as exc:
                connection.rollback()
                if isinstance(exc, AppError):
                    raise
                raise invalid("PERSISTENCE_ERROR", "Không thể lưu truy vấn", reason=str(exc)) from exc

    def dashboard_stats(self) -> dict[str, Any]:
        with self.connect() as connection:
            totals = connection.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN split='gallery' AND active=1 AND quality_status='approved' THEN 1 ELSE 0 END) AS gallery,
                    SUM(CASE WHEN split='validation' THEN 1 ELSE 0 END) AS validation,
                    SUM(CASE WHEN split='test' THEN 1 ELSE 0 END) AS test
                FROM images
                """
            ).fetchone()
            by_species = connection.execute(
                """
                SELECT COALESCE(s.name, 'unknown') AS species, COUNT(*) AS total
                FROM images i LEFT JOIN species s ON s.species_id=i.species_id
                WHERE i.split='gallery' AND i.active=1 AND i.quality_status='approved'
                GROUP BY COALESCE(s.name, 'unknown') ORDER BY species
                """
            ).fetchall()
            configs = connection.execute(
                "SELECT name, feature_type, dimension, preprocess_version FROM feature_configs ORDER BY config_id"
            ).fetchall()
            searches = connection.execute("SELECT COUNT(*) AS total FROM search_queries").fetchone()
        return {
            "total_images": int(totals["total"] or 0),
            "approved_gallery": int(totals["gallery"] or 0),
            "validation": int(totals["validation"] or 0),
            "test": int(totals["test"] or 0),
            "searches": int(searches["total"] or 0),
            "by_species": [dict(row) for row in by_species],
            "configs": [dict(row) for row in configs],
        }

    def recent_searches(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT query_id, query_path, candidate_count, duration_ms, created_at
                FROM search_queries ORDER BY query_id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def original_paths(self, image_ids: list[int]) -> dict[int, str]:
        if not image_ids:
            return {}
        placeholders = ",".join("?" for _ in image_ids)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT image_id, original_path FROM images WHERE image_id IN ({placeholders})",
                image_ids,
            ).fetchall()
        return {int(row["image_id"]): str(row["original_path"]) for row in rows}

    def get_search_items(self, query_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT r.rank, r.image_id, i.processed_path, s.name AS species_name,
                       r.hsv_score, r.hog_score, r.lbp_score, r.total_score, r.extra_scores_json
                FROM search_results r
                JOIN images i ON i.image_id=r.image_id
                LEFT JOIN species s ON s.species_id=i.species_id
                WHERE r.query_id=? ORDER BY r.rank
                """,
                (query_id,),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["scores"] = {"hsv": item["hsv_score"], "hog": item["hog_score"], "lbp": item["lbp_score"],
                              **json.loads(item.pop("extra_scores_json")), "total": item["total_score"]}
            items.append(item)
        return items
