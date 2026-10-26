"""Codebook VLAD đóng băng cho nhóm RootSIFT + VLAD: chỉ fit trên gallery, có checksum nguồn.

Codebook là tham số của cấu hình đặc trưng (giống hiệu chỉnh thang điểm): nằm ở
data/calibration/{profile}/rootsift_codebook.json, ghi descriptor_sha256 của spec gốc và
checksum từng ảnh gallery đã lấy mẫu. `with_codebook_specs` bơm tâm cụm vào tham số
rootsift_vlad để mọi tiến trình nhập/truy vấn dùng đúng một codebook.
"""
from __future__ import annotations

import json
from hashlib import sha256
from importlib.metadata import version

import numpy as np

from .calibration import canonical_hash
from .config import AppConfig, CODEBOOK_SETTINGS, BUNDLE_NAME, feature_specs_for
from .errors import invalid
from .rootsift import dense_rootsift, fit_codebook


def codebook_path(config: AppConfig) -> str:
    profile = BUNDLE_NAME if config.pca_components else config.bundle_name
    return f"calibration/{profile}/rootsift_codebook.json"


def codebook_groups(specs: dict) -> list[str]:
    return [name for name, spec in specs.items() if isinstance(spec["parameters"].get("vlad"), dict)]


def load_codebook(config: AppConfig, specs: dict) -> dict:
    if config.pca_components:
        config = config.for_profile(BUNDLE_NAME)
        specs = feature_specs_for(BUNDLE_NAME)
    path = config.resolve_data_path(codebook_path(config))
    groups = codebook_groups(specs)
    if not groups:
        raise ValueError("Configuration has no VLAD group")
    spec = specs[groups[0]]
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        centroids = np.asarray(artifact["centroids"], dtype=np.float64)
        expected = (int(spec["parameters"]["vlad"]["clusters"]), int(spec["parameters"]["descriptor_dimension"]))
        if (artifact["schema_version"] != 1 or artifact["profile"] != config.bundle_name
                or artifact["source_split"] != "gallery"
                or artifact["descriptor_sha256"] != canonical_hash(specs)
                or centroids.shape != expected or not np.isfinite(centroids).all()):
            raise ValueError("Codebook metadata does not match the descriptors")
        return artifact
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise invalid("CONFIG_MISMATCH", "Thiếu hoặc sai codebook VLAD; chạy scripts/prepare_dataset.py",
                      path=config.relative_to_data(path), reason=str(exc)) from exc


def with_codebook_specs(config: AppConfig, specs: dict) -> dict:
    """Trả bản sao specs có tâm cụm VLAD đã đóng băng, kèm hash codebook trong tham số."""
    groups = codebook_groups(specs)
    if not groups:
        return specs
    artifact = load_codebook(config, specs)
    result = json.loads(json.dumps(specs))
    for name in groups:
        parameters = result[name]["parameters"]
        parameters["vlad"]["codebook_centroids"] = artifact["centroids"]
        parameters["vlad"]["codebook_sha256"] = canonical_hash(artifact)
        parameters["vlad"]["codebook_gallery_sha256"] = artifact["gallery_source_sha256"]
        parameters["vlad"]["codebook_samples"] = artifact["n_descriptors"]
    return result


def source_records_all(images: list[tuple[str, np.ndarray]]) -> list[dict]:
    return [{"sha256": sha256(np.ascontiguousarray(image).tobytes()).hexdigest()} for _, image in images]


def fit_codebook_artifact(config: AppConfig, specs: dict, images: list[tuple[str, np.ndarray]]) -> dict:
    """Fit codebook từ ảnh gallery đã tiền xử lý; idempotent khi codebook đã tồn tại và khớp."""
    if config.pca_components:
        config = config.for_profile(BUNDLE_NAME)
        specs = feature_specs_for(BUNDLE_NAME)
    groups = codebook_groups(specs)
    if not groups:
        raise ValueError("Configuration has no VLAD group")
    spec = specs[groups[0]]
    if not images:
        raise ValueError("Codebook fitting needs gallery images")
    settings = CODEBOOK_SETTINGS
    step = max(1, len(images) // int(settings["image_cap"])) if len(images) > settings["image_cap"] else 1
    sampled = images[::step][: settings["image_cap"]]
    source_records = [{"path": config.relative_to_data(config.resolve_data_path(path)),
                       "sha256": sha256(np.ascontiguousarray(image).tobytes()).hexdigest()}
                      for path, image in sampled]
    # Hash theo nội dung của toàn bộ gallery (đa tập, không phụ thuộc đường dẫn hay thứ tự)
    # để đổi tên/di chuyển file mask không bị coi là đổi gallery.
    gallery_hash = canonical_hash(sorted(record["sha256"] for record in source_records_all(images)))
    path = config.resolve_data_path(codebook_path(config))
    if path.exists():
        artifact = load_codebook(config, specs)
        if artifact["gallery_source_sha256"] != gallery_hash:
            raise ValueError("Gallery changed after codebook freeze; create a new profile instead of overwriting")
        print("Reusing frozen VLAD codebook", flush=True)
        return artifact
    blocks = [dense_rootsift(image, spec["parameters"]) for _, image in sampled]
    descriptors = np.concatenate([block for block in blocks if block.size], axis=0) if any(
        block.size for block in blocks) else np.zeros((0, int(spec["parameters"]["descriptor_dimension"])))
    if descriptors.shape[0] < max(int(settings["minimum_samples"]), int(settings["clusters"])):
        raise ValueError(f"Not enough RootSIFT descriptors for the codebook: {descriptors.shape[0]}")
    if descriptors.shape[0] > settings["sample_cap"]:
        indices = np.linspace(0, descriptors.shape[0] - 1, int(settings["sample_cap"]), dtype=np.int64)
        descriptors = descriptors[indices]
    centroids = fit_codebook(descriptors, int(settings["clusters"]),
                             seed=int(settings["seed"]), iterations=int(settings["iterations"]))
    artifact = {
        "schema_version": 1, "profile": config.bundle_name, "source_split": "gallery",
        "descriptor_sha256": canonical_hash(specs), "gallery_source_sha256": gallery_hash,
        "settings": {key: settings[key] for key in ("clusters", "seed", "iterations", "sample_cap")},
        "n_gallery": len(images), "n_images_sampled": len(sampled), "n_descriptors": int(descriptors.shape[0]),
        "descriptor_dimension": int(descriptors.shape[1]), "source_records": source_records,
        "libraries": {name: version(name) for name in ["numpy", "scipy", "scikit-image", "pillow"]},
        "note": "Gallery-only dense RootSIFT k-means codebook; test images are never sampled. Values are not probabilities.",
        "centroids": centroids.tolist(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(artifact, stream, indent=1)
    return artifact
