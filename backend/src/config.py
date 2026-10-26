"""Four descriptors: HOG/PCA, regional HSV, RootSIFT/VLAD and Gabor."""
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
import os

# Stable baseline identity for shared masks/codebook and reproducible PCA preparation.
BUNDLE_NAME = "foreground4-v1"
# All application/CLI defaults use PCA512; select the baseline explicitly to compare.
DEFAULT_BUNDLE_NAME = "foreground4-hogpca512-v1"
PCA_PROFILES = {f"foreground4-hogpca{n}-v1": n for n in (128, 256, 512)}
OFFICIAL_BUNDLE_NAME = os.environ.get("CBIR_PROFILE") or DEFAULT_BUNDLE_NAME
OFFICIAL_PREPROCESS_VERSION = PREPROCESS_VERSION = "preprocess-birefnet-white-512-v1"
SOURCE_PREPROCESS_VERSION = "preprocess-rgb512-v1"
BACKGROUND_MODEL_SHA256 = "5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333"
OFFICIAL_MASK_DIRECTORY = BUNDLE_NAME
OFFICIAL_QUERY_PIPELINE = "birefnet-dml-white-512-v2"
OFFICIAL_MODEL_RUNTIME = "1.24.4"
OFFICIAL_REMBG_VERSION = "2.0.67"
FEATURE_KEYS = ("hog", "spatial_hsv", "rootsift_vlad", "gabor")
FEATURE_LABELS = {
    "hog": ("HOG đa tỉ lệ", "Đường biên, mắt, mõm và hình dáng mặt ở hai kích thước ô"),
    "spatial_hsv": ("HSV vùng", "Phân bố màu vùng mặt: nền tối, mảng sáng, mõm, trán"),
    "rootsift_vlad": ("RootSIFT + VLAD", "Chi tiết cục bộ ở nhiều vị trí, gộp bằng VLAD"),
    "gabor": ("Gabor đa hướng", "Kết cấu theo hướng và tần số, hữu ích cho sọc và lông"),
}
DEFAULT_WEIGHTS = {"hog": 8/17, "spatial_hsv": 3/17, "rootsift_vlad": 4/17, "gabor": 2/17}
CODEBOOK_SETTINGS = {"clusters": 32, "seed": 20261020, "iterations": 25, "sample_cap": 300000,
                     "image_cap": 250, "minimum_samples": 512}
PROFILE_SETTINGS = {BUNDLE_NAME: (PREPROCESS_VERSION, 512, "foreground4.db", "foreground4_manifest.csv", True)}
for _profile, _components in PCA_PROFILES.items():
    PROFILE_SETTINGS[_profile] = (PREPROCESS_VERSION, 512, f"foreground4_hogpca{_components}.db",
                                   f"foreground4_hogpca{_components}_manifest.csv", True)
if OFFICIAL_BUNDLE_NAME not in PROFILE_SETTINGS:
    raise ValueError(f"Unsupported CBIR_PROFILE: {OFFICIAL_BUNDLE_NAME}")
SEGMENTATION_BACKGROUND = {
    "model": "birefnet-general-lite",
    "model_sha256": BACKGROUND_MODEL_SHA256,
    "provider": "DmlExecutionProvider",
    "device_id": 0,
    "disable_graph_fusion": True,
    "putalpha": True,
    "onnxruntime_directml": OFFICIAL_MODEL_RUNTIME,
    "rembg": OFFICIAL_REMBG_VERSION,
    "canvas": [512, 512],
    "composite": "white",
    "pipeline": "crop-resize-segment-composite-v1",
}
ELLIPTIC_PRIOR = {"kind": "elliptic_cosine", "center": [0.5, 0.5], "radii": [0.48, 0.5], "floor": 0.15}
FEATURE_SPECS = {
    "hog": {
        "name": "hog-foreground4-v1",
        "feature_type": "HOG",
        "dimension": 9864,
        "parameters": {
            "orientations": 9,
            "pixels_per_cell": [16, 16],
            "cells_per_block": [2, 2],
            "block_norm": "L2-Hys",
            "transform_sqrt": False,
            "normalization": "L2",
            "epsilon": 1e-12,
            "input_size": [512, 512],
            "implementation_version": "foreground4-extractors-v1",
            "spatial_prior": ELLIPTIC_PRIOR,
            "scales": [{"pixels_per_cell": [32, 32], "weight": 0.5},
                       {"pixels_per_cell": [64, 64], "weight": 0.5}],
            "similarity": {"metric": "cosine_exp", "scale": 1.0},
            "background": SEGMENTATION_BACKGROUND,
        },
    },
    "spatial_hsv": {
        "name": "spatial_hsv-foreground4-v1",
        "feature_type": "SPATIAL_HSV",
        "dimension": 512,
        "parameters": {
            "grid": [2, 2],
            "bins": [8, 4, 4],
            "ranges": [[0.0, 1.0], [0.0, 1.0], [0.0, 1.0]],
            "normalization": "L1-per-region-then-global",
            "input_size": [512, 512],
            "implementation_version": "foreground4-extractors-v1",
            "spatial_prior": ELLIPTIC_PRIOR,
            "similarity": {"metric": "intersection_exp", "scale": 1.0},
            "background": SEGMENTATION_BACKGROUND,
        },
    },
    "rootsift_vlad": {
        "name": "rootsift_vlad-foreground4-v1",
        "feature_type": "ROOTSIFT_VLAD",
        "dimension": 4096,
        "parameters": {
            "descriptor": "dense_rootsift",
            "sampling": "regular_grid_inside_spatial_prior",
            "scales": [{"sigma": 1.0, "patch_size": 16, "cell_size": 4, "step": 8},
                       {"sigma": 2.0, "patch_size": 24, "cell_size": 6, "step": 8},
                       {"sigma": 3.5, "patch_size": 32, "cell_size": 8, "step": 8}],
            "cells_per_descriptor": [4, 4],
            "orientation_bins": 36,
            "descriptor_bins": 8,
            "descriptor_dimension": 128,
            "patch_window": "gaussian_sigma_equal_half_patch",
            "flat_patch_threshold": 1e-6,
            "prior_threshold": 0.35,
            "clip": 0.2,
            "root_sift": "l1_normalize_then_sqrt",
            "normalization": "L2",
            "normalization_steps": "l2-clip0.2-l2-rootsift-intra-cluster-l2-global-l2",
            "signed_values": True,
            "input_size": [512, 512],
            "implementation_version": "foreground4-rootsift-vlad-v1",
            "spatial_prior": ELLIPTIC_PRIOR,
            "vlad": {"clusters": CODEBOOK_SETTINGS["clusters"], "assignment": "nearest_l2",
                     "intra_normalization": True, "power_normalization": False,
                     "codebook": "calibration/foreground4-v1/rootsift_codebook.json"},
            "similarity": {"metric": "cosine_signed_exp", "scale": 1.0},
            "background": SEGMENTATION_BACKGROUND,
        },
    },
    "gabor": {
        "name": "gabor-foreground4-v1",
        "feature_type": "GABOR",
        "dimension": 96,
        "parameters": {
            "analysis_size": 128,
            "frequencies": [0.1, 0.2, 0.3],
            "angles_degrees": [0, 45, 90, 135],
            "bandwidth": 1.0,
            "n_stds": 3,
            "grid": [2, 2],
            "statistics": ["mean_magnitude", "std_magnitude"],
            "boundary": "reflect",
            "normalization": "bounded",
            "input_size": [512, 512],
            "implementation_version": "foreground4-extractors-v1",
            "spatial_prior": ELLIPTIC_PRIOR,
            "similarity": {"metric": "standardized_l1_exp", "scale": 1.0},
            "background": SEGMENTATION_BACKGROUND,
        },
    },
}


def preprocessing_size(version):
    if version not in {PREPROCESS_VERSION, SOURCE_PREPROCESS_VERSION}:
        raise ValueError(f"Unsupported preprocessing version: {version}")
    return 512


def requires_background(version):
    preprocessing_size(version)
    return version == PREPROCESS_VERSION


def default_weights_for(profile=OFFICIAL_BUNDLE_NAME):
    if profile not in PROFILE_SETTINGS:
        raise ValueError(f"Unsupported configuration: {profile}")
    return dict(DEFAULT_WEIGHTS)


def feature_labels_for(profile=OFFICIAL_BUNDLE_NAME):
    if profile not in PROFILE_SETTINGS:
        raise ValueError(f"Unsupported configuration: {profile}")
    labels = dict(FEATURE_LABELS)
    if profile in PCA_PROFILES:
        components = PCA_PROFILES.get(profile, 512)
        labels["hog"] = ("HOG-PCA", f"HOG đa tỉ lệ nén còn {components} chiều bằng PCA học từ gallery")
    return labels


def feature_specs_for(bundle_name=OFFICIAL_BUNDLE_NAME, preprocess_version=PREPROCESS_VERSION):
    if bundle_name not in PROFILE_SETTINGS or preprocess_version != PREPROCESS_VERSION:
        raise ValueError(f"Unsupported bundle/preprocessing pair: {bundle_name}/{preprocess_version}")
    specs = deepcopy(FEATURE_SPECS)
    if bundle_name in PCA_PROFILES:
        for key, spec in specs.items():
            spec["name"] = f"{key}-{bundle_name}"
        hog = specs["hog"]
        hog["dimension"] = PCA_PROFILES.get(bundle_name, 512)
        hog["parameters"].update(signed_values=True,
            pca={"input_dimension": 9864, "components": hog["dimension"], "whiten": False,
                 "artifact": f"calibration/{bundle_name}/hog_pca.json"},
            similarity={"metric": "cosine_signed_exp", "scale": 1.0})
    return specs


OFFICIAL_DIMENSIONS = sum(spec["dimension"] for spec in feature_specs_for().values())


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    data_root: Path
    db_path: Path
    migration_path: Path
    artifacts_root: Path
    preprocess_version: str = PREPROCESS_VERSION
    bundle_name: str = OFFICIAL_BUNDLE_NAME

    @classmethod
    def default(cls, profile=None):
        profile = profile or OFFICIAL_BUNDLE_NAME
        if profile not in PROFILE_SETTINGS:
            raise ValueError(f"Unsupported configuration: {profile}")
        root = Path(__file__).resolve().parents[2]
        return cls(root, root / "data", root / "data" / PROFILE_SETTINGS[profile][2],
                   root / "migrations/001_init.sql", root / "artifacts", bundle_name=profile)

    @property
    def default_manifest_path(self):
        return self.data_root / "manifests" / PROFILE_SETTINGS[self.bundle_name][3]

    @property
    def source_manifest_path(self):
        return self.default_manifest_path.with_name(self.default_manifest_path.name.replace('_manifest.csv', '_sources.csv'))

    @property
    def pca_components(self):
        return PCA_PROFILES.get(self.bundle_name)

    @property
    def source_root(self):
        return self.data_root / "dataset512-left/images512"

    @property
    def image_size(self):
        return 512

    @property
    def background_input(self):
        return True

    def result_directory(self, category):
        return self.data_root / category / self.bundle_name

    def for_profile(self, profile):
        if profile not in PROFILE_SETTINGS:
            raise ValueError(f"Unsupported configuration: {profile}")
        return replace(self, bundle_name=profile, db_path=self.data_root / PROFILE_SETTINGS[profile][2])

    def ensure_runtime_dirs(self):
        for path in (self.data_root, self.data_root / "manifests", self.artifacts_root):
            path.mkdir(parents=True, exist_ok=True)

    def resolve_data_path(self, relative_path: str) -> Path:
        path = (self.data_root / relative_path).resolve()
        root = self.data_root.resolve()
        if path != root and root not in path.parents:
            raise ValueError(f"Path escapes data root: {relative_path}")
        return path

    def relative_to_data(self, path: Path) -> str:
        return path.resolve().relative_to(self.data_root.resolve()).as_posix()
