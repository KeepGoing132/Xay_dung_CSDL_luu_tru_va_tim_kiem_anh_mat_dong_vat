from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import json
from hashlib import sha256


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


@dataclass(frozen=True)
class BundleConfig:
    name: str
    hsv: FeatureConfig
    hog: FeatureConfig
    lbp: FeatureConfig
    extras: dict[str, FeatureConfig] = field(default_factory=dict)

    @property
    def configs(self) -> dict[str, FeatureConfig]:
        return {"hsv": self.hsv, "hog": self.hog, "lbp": self.lbp, **self.extras}

    @property
    def preprocess_version(self) -> str:
        versions = {config.preprocess_version for config in self.configs.values()}
        if len(versions) != 1:
            raise ValueError("Bundle contains mixed preprocessing versions")
        return next(iter(versions))

    @property
    def config_ids(self) -> dict[str, int]:
        return {name: config.config_id for name, config in self.configs.items()}

    @property
    def signature(self) -> str:
        specs = {name: {"name": spec.name, "dimension": spec.dimension, "parameters": spec.parameters,
                        "preprocess_version": spec.preprocess_version, "feature_type": spec.feature_type}
                 for name, spec in self.configs.items()}
        return sha256(json.dumps(specs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class FeatureBundle:
    hsv: np.ndarray
    hog: np.ndarray
    lbp: np.ndarray
    config_ids: dict[str, int]
    warnings: tuple[str, ...] = ()
    preprocess_version: str = "preprocess-v1"
    extras: dict[str, np.ndarray] = field(default_factory=dict)
    similarities: dict[str, dict[str, Any]] = field(default_factory=dict)
    config_signature: str = ""

    @property
    def vectors(self) -> dict[str, np.ndarray]:
        return {"hsv": self.hsv, "hog": self.hog, "lbp": self.lbp, **self.extras}


@dataclass(frozen=True)
class Weights:
    hsv: float = 1 / 3
    hog: float = 1 / 3
    lbp: float = 1 / 3
    extras: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float]:
        return {"hsv": self.hsv, "hog": self.hog, "lbp": self.lbp, **self.extras}

    @classmethod
    def from_dict(cls, values: dict[str, float]) -> "Weights":
        return cls(*(values.get(key, 0.0) for key in ("hsv", "hog", "lbp")),
                   extras={key: value for key, value in values.items() if key not in {"hsv", "hog", "lbp"}})


@dataclass(frozen=True)
class Scores:
    hsv: float
    hog: float
    lbp: float
    total: float
    extras: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float]:
        return {"hsv": self.hsv, "hog": self.hog, "lbp": self.lbp, **self.extras}

    def contributions(self, weights: Weights) -> dict[str, float]:
        values = weights.as_dict()
        return {name: score * values.get(name, 0.0) for name, score in self.as_dict().items()}


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
    weights: Weights = field(default_factory=Weights)
    bundle_name: str = "baseline-v1"


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
