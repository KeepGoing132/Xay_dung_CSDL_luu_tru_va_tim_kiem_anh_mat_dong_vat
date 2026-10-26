from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import json
from hashlib import sha256
from .config import DEFAULT_WEIGHTS, PREPROCESS_VERSION


@dataclass(frozen=True)
class CropBox:
    x: int
    y: int
    size: int


@dataclass(frozen=True)
class ProcessedImage:
    rgb: np.ndarray
    crop: CropBox
    preprocess_version: str
    pixel_sha256: str


@dataclass(frozen=True)
class FeatureConfig:
    config_id: int
    name: str
    feature_type: str
    dimension: int
    parameters: dict[str, Any]
    preprocess_version: str
    projection: Any = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class BundleConfig:
    name: str
    configs: dict[str, FeatureConfig]

    @classmethod
    def from_configs(cls, name, configs):
        from .config import FEATURE_KEYS
        if set(configs) != set(FEATURE_KEYS):
            raise ValueError("A bundle must contain exactly the four configured descriptors")
        return cls(name, dict(configs))

    @property
    def hog(self):
        return self.configs["hog"]

    @property
    def preprocess_version(self):
        versions = {c.preprocess_version for c in self.configs.values()}
        if len(versions) != 1:
            raise ValueError("Mixed preprocessing versions")
        return next(iter(versions))

    @property
    def config_ids(self):
        return {key: value.config_id for key, value in self.configs.items()}

    @property
    def signature(self):
        specs = {key: {"name": c.name, "dimension": c.dimension, "parameters": c.parameters,
                       "preprocess_version": c.preprocess_version, "feature_type": c.feature_type}
                 for key, c in self.configs.items()}
        return sha256(json.dumps(specs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class FeatureBundle:
    vectors: dict[str, np.ndarray]
    config_ids: dict[str, int]
    warnings: tuple[str, ...] = ()
    preprocess_version: str = PREPROCESS_VERSION
    similarities: dict[str, dict[str, Any]] = field(default_factory=dict)
    config_signature: str = ""

    @classmethod
    def from_vectors(cls, vectors, **kwargs):
        from .config import FEATURE_KEYS
        if set(vectors) != set(FEATURE_KEYS) or set(kwargs["config_ids"]) != set(vectors):
            raise ValueError("Vectors/config IDs must contain exactly four descriptors")
        return cls(dict(vectors), **kwargs)

    @property
    def extras(self):
        """Vector nhỏ để xem trước; VLAD 4.096 chiều có biểu diễn cụm riêng."""
        return {k: v for k, v in self.vectors.items() if k not in {"hog", "rootsift_vlad"}}


@dataclass(frozen=True)
class Weights:
    values: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    def as_dict(self):
        return dict(self.values)

    @classmethod
    def from_dict(cls, values):
        from .config import FEATURE_KEYS
        from .errors import invalid
        unknown = set(values) - set(FEATURE_KEYS)
        if unknown:
            raise invalid("INVALID_WEIGHTS", "Trọng số không thuộc bốn đặc trưng", features=sorted(unknown))
        return cls({key: float(values.get(key, 0)) for key in FEATURE_KEYS})


@dataclass(frozen=True)
class Scores:
    values: dict[str, float]
    total: float

    def as_dict(self):
        return dict(self.values)

    def contributions(self, weights):
        values = weights.as_dict()
        return {key: score * values.get(key, 0) for key, score in self.values.items()}

    @classmethod
    def from_components(cls, components, total):
        return cls(dict(components), total)


@dataclass(frozen=True)
class Candidate:
    image_id: int
    processed_path: str
    species_name: str | None
    features: FeatureBundle


@dataclass(frozen=True)
class RejectedCandidate:
    image_id: int
    processed_path: str
    reason: str


@dataclass(frozen=True)
class LoadCandidatesResult:
    candidates: tuple[Candidate, ...]
    rejected: tuple[RejectedCandidate, ...]


@dataclass(frozen=True)
class SearchRequest:
    image_bytes: bytes
    crop: CropBox | None = None
    weights: Weights | None = None
    bundle_name: str | None = None


@dataclass(frozen=True)
class SearchItem:
    rank: int
    image_id: int
    processed_path: str
    species_name: str | None
    scores: Scores


@dataclass(frozen=True)
class SearchResponse:
    query_id: int
    query_path: str
    items: tuple[SearchItem, ...]
    effective_weights: Weights
    candidate_count: int
    timings: dict[str, float]
    warnings: tuple[str, ...]
    query_features: FeatureBundle
    processed_query: ProcessedImage


@dataclass(frozen=True)
class ImportErrorRecord:
    row_number: int
    relative_path: str
    code: str
    message: str


@dataclass(frozen=True)
class ImportSummary:
    total: int
    created: int
    skipped: int
    failed: int
    errors: tuple[ImportErrorRecord, ...]


@dataclass(frozen=True)
class ImageMetadata:
    species_name: str | None
    original_path: str
    processed_path: str
    original_sha256: str
    processed_sha256: str
    source_url: str | None
    license_note: str | None
    split: str
    group_id: str
    crop: CropBox
    preprocess_version: str
    quality_status: str
    active: bool
    review_note: str | None = None


@dataclass(frozen=True)
class DatasetPaths:
    data_root: Path
    db_path: Path
    migration_path: Path
