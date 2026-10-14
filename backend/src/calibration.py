"""Frozen distance calibration from gallery descriptors, without species labels."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import numpy as np

from .config import REFINED512_BUNDLE_NAME
from .errors import invalid
from .similarity import feature_distance


CALIBRATION_SETTINGS = {"seed": 20261013, "pair_count": 4096, "coordinate_scale_floor": .02,
                        "distance_scale_floor": .01, "distance_clip": 5.0}


def canonical_hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def calibration_path(config):
    return config.data_root / "calibration" / config.bundle_name / "gallery.json"


def fit_calibration(vectors, specs, settings=None):
    """Rows must be gallery-only, in deterministic order; caller records their provenance."""
    settings = settings or CALIBRATION_SETTINGS
    keys = list(specs)
    if set(vectors) != set(keys):
        raise ValueError("Calibration feature groups do not match")
    arrays = {key: np.asarray(vectors[key], dtype=np.float64) for key in keys}
    n = len(arrays[keys[0]])
    if n < 2:
        raise ValueError("At least two gallery images are required for calibration")
    for key, array in arrays.items():
        if array.shape != (n, specs[key]["dimension"]) or not np.isfinite(array).all():
            raise ValueError(f"Invalid calibration vectors: {key}")
    rng = np.random.default_rng(settings["seed"])
    count = min(settings["pair_count"], n*(n-1)//2)
    pairs = set()
    while len(pairs) < count:
        a, b = map(int, rng.integers(0, n, 2))
        if a != b:
            pairs.add((min(a, b), max(a, b)))
    pairs = sorted(pairs)
    metrics, diagnostics = {}, {}
    for key, array in arrays.items():
        metric = deepcopy(specs[key]["parameters"]["similarity"])
        if metric["metric"] == "standardized_l1_exp":
            iqr = np.percentile(array, 75, axis=0) - np.percentile(array, 25, axis=0)
            metric["coordinate_scales"] = np.maximum(iqr, settings["coordinate_scale_floor"]).tolist()
            metric["distance_clip"] = settings["distance_clip"]
        distances = np.asarray([feature_distance(array[a], array[b], metric) for a, b in pairs])
        metric["scale"] = max(float(np.median(distances)), settings["distance_scale_floor"])
        metrics[key] = metric
        diagnostics[key] = {"distance_p10": float(np.percentile(distances, 10)),
                            "distance_median": float(np.median(distances)),
                            "distance_p90": float(np.percentile(distances, 90)),
                            "score_median": float(np.median(np.exp(-np.log(2)*distances/metric["scale"])))}
    return {"schema_version": 1, "profile": REFINED512_BUNDLE_NAME, "source_split": "gallery",
            "descriptor_sha256": canonical_hash(specs), "n_gallery": n, "n_pairs": len(pairs),
            "settings": settings, "metrics": metrics, "diagnostics": diagnostics}


def calibrated_specs(config, specs):
    if config.bundle_name != REFINED512_BUNDLE_NAME:
        return specs
    path = calibration_path(config)
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if (artifact["schema_version"] != 1 or artifact["profile"] != config.bundle_name
                or artifact["source_split"] != "gallery" or artifact["descriptor_sha256"] != canonical_hash(specs)
                or set(artifact["metrics"]) != set(specs) or artifact["n_gallery"] < 2):
            raise ValueError("Calibration metadata does not match descriptors")
        result = deepcopy(specs)
        for name, spec in result.items():
            metric = artifact["metrics"][name]
            if (metric["metric"] != spec["parameters"]["similarity"]["metric"]
                    or not np.isfinite(metric["scale"]) or metric["scale"] <= 0):
                raise ValueError(f"Invalid score scale for {name}")
            if metric["metric"] == "standardized_l1_exp":
                scales = np.asarray(metric["coordinate_scales"], dtype=float)
                if (scales.shape != (spec["dimension"],) or not np.isfinite(scales).all() or (scales <= 0).any()
                        or not np.isfinite(metric["distance_clip"]) or metric["distance_clip"] <= 0):
                    raise ValueError(f"Invalid coordinate scales for {name}")
            spec["parameters"]["similarity"] = metric
            spec["parameters"]["calibration_sha256"] = canonical_hash(artifact)
        return result
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise invalid("CONFIG_MISMATCH", "Thiếu hoặc sai hiệu chỉnh; chạy scripts/prepare_refined_profile.py",
                      path=str(path), reason=str(exc)) from exc
