from __future__ import annotations

from dataclasses import dataclass, replace
from copy import deepcopy
import os
from pathlib import Path


PREPROCESS_VERSION = "preprocess-v1"
BUNDLE_NAME = "baseline-v1"
BACKGROUND_BUNDLE_NAME = "background-white-v1"
BACKGROUND_PREPROCESS_VERSION = "preprocess-bg-white-v1"
NATIVE512_BUNDLE_NAME = "native512-v1"
NATIVE512_PREPROCESS_VERSION = "preprocess-512-v1"
BACKGROUND512_BUNDLE_NAME = "background512-white-v1"
BACKGROUND512_PREPROCESS_VERSION = "preprocess-bg-white-512-v1"
EXPANDED512_BUNDLE_NAME = "expanded512-v1"
REFINED512_BUNDLE_NAME = "refined512-v1"
PROFILE_SETTINGS = {
    BUNDLE_NAME: (PREPROCESS_VERSION, 128, "app.db", "frontal512_manifest.csv", False),
    BACKGROUND_BUNDLE_NAME: (BACKGROUND_PREPROCESS_VERSION, 128, "background_white.db", "background_white_manifest.csv", True),
    NATIVE512_BUNDLE_NAME: (NATIVE512_PREPROCESS_VERSION, 512, "native512.db", "frontal512_manifest.csv", False),
    BACKGROUND512_BUNDLE_NAME: (BACKGROUND512_PREPROCESS_VERSION, 512, "background512_white.db", "background512_white_manifest.csv", True),
    EXPANDED512_BUNDLE_NAME: (NATIVE512_PREPROCESS_VERSION, 512, "expanded512.db", "frontal512_manifest.csv", False),
    REFINED512_BUNDLE_NAME: (NATIVE512_PREPROCESS_VERSION, 512, "refined512.db", "frontal512_manifest.csv", False),
}


def preprocessing_size(version: str) -> int:
    for preprocess, size, *_ in PROFILE_SETTINGS.values():
        if preprocess == version:
            return size
    raise ValueError(f"Unsupported preprocessing version: {version}")


def requires_background(version: str) -> bool:
    return version in {BACKGROUND_PREPROCESS_VERSION, BACKGROUND512_PREPROCESS_VERSION}

FEATURE_SPECS = {
    "hsv": {
        "name": "hsv-v1",
        "feature_type": "HSV",
        "dimension": 128,
        "parameters": {
            "bins": [8, 4, 4],
            "ranges": [[0.0, 1.0], [0.0, 1.0], [0.0, 1.0]],
            "normalization": "L1",
            "flatten_order": "C",
        },
    },
    "hog": {
        "name": "hog-v1",
        "feature_type": "HOG",
        "dimension": 1764,
        "parameters": {
            "orientations": 9,
            "pixels_per_cell": [16, 16],
            "cells_per_block": [2, 2],
            "block_norm": "L2-Hys",
            "transform_sqrt": False,
            "normalization": "L2",
            "epsilon": 1e-12,
        },
    },
    "lbp": {
        "name": "lbp-v1",
        "feature_type": "LBP",
        "dimension": 160,
        "parameters": {
            "points": 8,
            "radius": 1,
            "method": "uniform",
            "grid": [4, 4],
            "bins": 10,
            "normalization": "L1-per-region-then-global",
        },
    },
}

EXTRA_FEATURE_SPECS = {
    "spatial_hsv": {
        "feature_type": "SPATIAL_HSV", "dimension": 512,
        "parameters": {"grid": [2, 2], "bins": [8, 4, 4],
                       "ranges": [[0.0, 1.0]] * 3, "normalization": "L1-per-region-then-global",
                       "similarity": {"metric": "intersection"}},
    },
    "color_moments": {
        "feature_type": "COLOR_MOMENTS", "dimension": 36,
        "parameters": {"grid": [2, 2], "color_space": "RGB-unit",
                       "statistics": ["mean", "std_ddof0", "signed_cuberoot_third_mapped_01"],
                       "normalization": "bounded", "value_range": [0.0, 1.0],
                       "similarity": {"metric": "mean_l1_exp", "scale": 0.1}},
    },
    "glcm": {
        "feature_type": "GLCM", "dimension": 48,
        "parameters": {"levels": 32, "distances": [1, 3], "angles_degrees": [0, 45, 90, 135],
                       "properties": ["contrast", "dissimilarity", "homogeneity", "ASM", "energy", "correlation"],
                       "symmetric": True, "normed": True, "normalization": "bounded",
                       "value_range": [0.0, 1.0], "similarity": {"metric": "mean_l1_exp", "scale": 0.1}},
    },
}

FEATURE_LABELS = {
    "hsv": ("HSV", "Màu sắc tổng thể"), "hog": ("HOG", "Cấu trúc đường biên"),
    "lbp": ("LBP", "Kết cấu cục bộ"), "spatial_hsv": ("HSV vùng", "Vị trí phân bố màu · lưới 2×2"),
    "color_moments": ("Moments màu", "Trung bình, độ phân tán và bất đối xứng màu"),
    "glcm": ("GLCM", "Quan hệ mức xám ở nhiều hướng và khoảng cách"),
}


def default_weights_for(profile: str) -> dict[str, float]:
    if profile == REFINED512_BUNDLE_NAME:
        # Equal family weights; the three color descriptors share one third.
        return {"hsv": 1/9, "hog": 1/3, "lbp": 1/6, "spatial_hsv": 1/9,
                "color_moments": 1/9, "glcm": 1/6}
    if profile == EXPANDED512_BUNDLE_NAME:
        return {"hsv": 0.1, "hog": 0.3, "lbp": 0.2, "spatial_hsv": 0.15,
                "color_moments": 0.1, "glcm": 0.15}
    return {"hsv": 0.1, "hog": 0.45, "lbp": 0.45}


def feature_specs_for(bundle_name: str, preprocess_version: str) -> dict:
    if (bundle_name, preprocess_version) == (BUNDLE_NAME, PREPROCESS_VERSION):
        return FEATURE_SPECS
    if bundle_name not in PROFILE_SETTINGS or PROFILE_SETTINGS[bundle_name][0] != preprocess_version:
        raise ValueError(f"Unsupported bundle/preprocessing pair: {bundle_name}/{preprocess_version}")
    specs = deepcopy(FEATURE_SPECS)
    if bundle_name in {EXPANDED512_BUNDLE_NAME, REFINED512_BUNDLE_NAME}:
        specs.update(deepcopy(EXTRA_FEATURE_SPECS))
    for key, spec in specs.items():
        spec["name"] = f"{key}-bg-white-v1" if bundle_name == BACKGROUND_BUNDLE_NAME else f"{key}-{bundle_name}"
        if preprocessing_size(preprocess_version) == 512:
            spec["parameters"]["input_size"] = [512, 512]
    if preprocessing_size(preprocess_version) == 512:
        specs["hog"]["dimension"] = (512 // 16 - 1) ** 2 * 2 * 2 * 9
    if bundle_name == EXPANDED512_BUNDLE_NAME:
        for spec in specs.values():
            spec["parameters"]["implementation_version"] = "expanded-extractors-v1"
    if bundle_name == REFINED512_BUNDLE_NAME:
        prior = {"kind": "elliptic_cosine", "center": [0.5, 0.5],
                 "radii": [0.48, 0.5], "floor": 0.15}
        for spec in specs.values():
            spec["parameters"].update(implementation_version="refined-extractors-v1", spatial_prior=deepcopy(prior))
        specs["hog"]["dimension"] = 9864
        specs["hog"]["parameters"]["scales"] = [
            {"pixels_per_cell": [32, 32], "weight": 0.5},
            {"pixels_per_cell": [64, 64], "weight": 0.5},
        ]
        specs["lbp"]["dimension"] = 864
        specs["lbp"]["parameters"].update(
            scales=[{"points": 8, "radius": 1}, {"points": 16, "radius": 2}, {"points": 24, "radius": 3}],
            normalization="L1", regional_mass="spatial_prior")
        specs["glcm"]["dimension"] = 40
        specs["glcm"]["parameters"].update(
            distances=[2, 6], properties=["contrast", "dissimilarity", "homogeneity", "energy", "correlation"],
            pair_weight="geometric_mean", offset_rounding="nearest_even")
        for key, spec in specs.items():
            metric = "cosine_exp" if key == "hog" else "intersection_exp"
            if key in {"color_moments", "glcm"}:
                metric = "standardized_l1_exp"
            # Placeholder used only while fitting. Runtime requires the frozen calibration.
            spec["parameters"]["similarity"] = {"metric": metric, "scale": 1.0}
    return specs


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    data_root: Path
    db_path: Path
    migration_path: Path
    artifacts_root: Path
    preprocess_version: str = PREPROCESS_VERSION
    bundle_name: str = BUNDLE_NAME

    @classmethod
    def default(cls, profile: str | None = None) -> "AppConfig":
        root = Path(__file__).resolve().parents[2]
        profile = profile or os.environ.get("CBIR_PROFILE", REFINED512_BUNDLE_NAME)
        if profile not in PROFILE_SETTINGS:
            raise ValueError(f"Unknown CBIR_PROFILE: {profile}")
        preprocess, _, database, _, _ = PROFILE_SETTINGS[profile]
        return cls(
            project_root=root,
            data_root=root / "data",
            db_path=root / "data" / database,
            migration_path=root / "migrations" / "001_init.sql",
            artifacts_root=root / "artifacts",
            bundle_name=profile,
            preprocess_version=preprocess,
        )

    @property
    def default_manifest_path(self) -> Path:
        name = PROFILE_SETTINGS[self.bundle_name][3]
        return self.data_root / "manifests" / name

    @property
    def image_size(self) -> int:
        return preprocessing_size(self.preprocess_version)

    @property
    def background_input(self) -> bool:
        return requires_background(self.preprocess_version)

    def result_directory(self, category: str) -> Path:
        if self.bundle_name == BUNDLE_NAME:
            return self.data_root / category
        return self.data_root / category / self.bundle_name

    def for_profile(self, profile: str) -> "AppConfig":
        if profile not in PROFILE_SETTINGS:
            raise ValueError(f"Unknown CBIR_PROFILE: {profile}")
        preprocess, _, database, _, _ = PROFILE_SETTINGS[profile]
        return replace(self, bundle_name=profile, preprocess_version=preprocess,
                       db_path=self.data_root / database)

    def ensure_runtime_dirs(self) -> None:
        for path in (
            self.data_root,
            self.data_root / "original",
            self.data_root / "processed",
            self.data_root / "queries",
            self.data_root / "manifests",
            self.artifacts_root / "figures",
            self.artifacts_root / "evaluation",
        ):
            path.mkdir(parents=True, exist_ok=True)

    def resolve_data_path(self, relative_path: str) -> Path:
        path = (self.data_root / relative_path).resolve()
        root = self.data_root.resolve()
        if path != root and root not in path.parents:
            raise ValueError(f"Path escapes data root: {relative_path}")
        return path

    def relative_to_data(self, path: Path) -> str:
        return path.resolve().relative_to(self.data_root.resolve()).as_posix()
