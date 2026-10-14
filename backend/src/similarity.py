from __future__ import annotations

import math

import numpy as np

from .errors import invalid
from .models import Candidate, FeatureBundle, Scores, SearchItem, Weights


def normalize_weights(weights: Weights) -> Weights:
    mapping = weights.as_dict()
    values = np.asarray(list(mapping.values()), dtype=np.float64)
    if not np.isfinite(values).all() or (values < 0).any():
        raise invalid("INVALID_WEIGHTS", "Trọng số phải hữu hạn và không âm")
    scale = float(values.max())
    if scale <= 0:
        raise invalid("INVALID_WEIGHTS", "Tổng trọng số phải lớn hơn 0")
    # Scale first: a sum of valid finite inputs can overflow float64.
    values /= scale
    values /= float(values.sum())
    return Weights.from_dict(dict(zip(mapping, map(float, values))))


def histogram_intersection(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        raise invalid("CONFIG_MISMATCH", "Hai histogram khác số chiều")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise invalid("INVALID_VECTOR", "Histogram chứa NaN hoặc Infinity")
    return float(np.minimum(left, right).sum())


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        raise invalid("CONFIG_MISMATCH", "Hai vector HOG khác số chiều")
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm <= 1e-12 or right_norm <= 1e-12:
        return 0.0
    return float(np.dot(left, right) / (left_norm * right_norm))


def _bounded(value: float) -> float:
    if not math.isfinite(value):
        raise invalid("INVALID_VECTOR", "Điểm tương đồng không hữu hạn")
    if value < -1e-8 or value > 1.0 + 1e-8:
        raise invalid("INVALID_VECTOR", "Điểm tương đồng nằm ngoài [0,1]", value=value)
    return float(np.clip(value, 0.0, 1.0))


def feature_distance(left: np.ndarray, right: np.ndarray, metric: dict) -> float:
    """Distance before the frozen, gallery-fitted score transform."""
    if left.shape != right.shape:
        raise invalid("CONFIG_MISMATCH", "Vector khác số chiều khi tính khoảng cách")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise invalid("INVALID_VECTOR", "Vector không hợp lệ khi tính khoảng cách")
    if metric["metric"] == "intersection_exp":
        return 1 - _bounded(histogram_intersection(left, right))
    if metric["metric"] == "cosine_exp":
        return 1 - _bounded(cosine_similarity(left, right))
    if metric["metric"] == "standardized_l1_exp":
        scales = np.asarray(metric["coordinate_scales"], dtype=np.float64)
        if scales.shape != left.shape or not np.isfinite(scales).all() or (scales <= 0).any():
            raise invalid("CONFIG_MISMATCH", "Thang đo từng chiều không hợp lệ")
        return float(np.minimum(np.abs(left-right) / scales, metric["distance_clip"]).mean())
    raise invalid("CONFIG_MISMATCH", "Phép đo khoảng cách không được hỗ trợ")


def calibrated_similarity(left, right, metric):
    distance = feature_distance(left, right, metric)
    scale = metric["scale"]
    if not math.isfinite(scale) or scale <= 0:
        raise invalid("CONFIG_MISMATCH", "Thang điểm hiệu chỉnh không hợp lệ")
    if metric["metric"] == "cosine_exp" and min(np.linalg.norm(left), np.linalg.norm(right)) <= 1e-12:
        return 0.0
    return _bounded(float(np.exp(-math.log(2) * distance / scale)))


def compare_features(query: FeatureBundle, candidate: FeatureBundle, weights: Weights) -> Scores:
    if (query.config_ids != candidate.config_ids or query.preprocess_version != candidate.preprocess_version
            or query.similarities != candidate.similarities or query.vectors.keys() != candidate.vectors.keys()
            or query.config_signature != candidate.config_signature):
        raise invalid(
            "CONFIG_MISMATCH",
            "Không thể so sánh vector khác cấu hình",
            query_config=query.config_ids,
            candidate_config=candidate.config_ids,
            query_preprocess=query.preprocess_version,
            candidate_preprocess=candidate.preprocess_version,
        )
    effective = normalize_weights(weights)
    unknown = set(effective.extras) - set(query.extras)
    if unknown:
        raise invalid("INVALID_WEIGHTS", "Trọng số không thuộc cấu hình", features=sorted(unknown))
    if "hsv" in query.similarities:
        components = {name: calibrated_similarity(left, candidate.vectors[name], query.similarities[name])
                      for name, left in query.vectors.items()}
        total = _bounded(sum(score * effective.as_dict().get(name, 0.0) for name, score in components.items()))
        return Scores(components["hsv"], components["hog"], components["lbp"], total,
                      {name: value for name, value in components.items() if name in query.extras})
    hsv_score = _bounded(histogram_intersection(query.hsv, candidate.hsv))
    hog_score = _bounded(cosine_similarity(query.hog, candidate.hog))
    lbp_score = _bounded(histogram_intersection(query.lbp, candidate.lbp))
    extras = {}
    for name, left in query.extras.items():
        right = candidate.extras[name]
        if left.shape != right.shape:
            raise invalid("CONFIG_MISMATCH", "Vector khác số chiều", feature=name)
        if not np.isfinite(left).all() or not np.isfinite(right).all():
            raise invalid("INVALID_VECTOR", "Vector chứa giá trị không hữu hạn", feature=name)
        metric = query.similarities[name]
        if metric["metric"] == "intersection":
            score = histogram_intersection(left, right)
        elif metric["metric"] == "mean_l1_exp":
            score = np.exp(-np.mean(np.abs(left - right)) / metric["scale"])
        else:
            raise invalid("CONFIG_MISMATCH", "Phép so sánh chưa được hỗ trợ", feature=name)
        extras[name] = _bounded(float(score))
    components = {"hsv": hsv_score, "hog": hog_score, "lbp": lbp_score, **extras}
    values = effective.as_dict()
    total = _bounded(sum(score * values.get(name, 0.0) for name, score in components.items()))
    return Scores(hsv=hsv_score, hog=hog_score, lbp=lbp_score, total=total, extras=extras)


def rank_candidates(
    query: FeatureBundle,
    candidates: tuple[Candidate, ...] | list[Candidate],
    weights: Weights,
    k: int = 5,
) -> tuple[SearchItem, ...]:
    components = [compare_features(query, candidate.features, weights) for candidate in candidates]
    return rank_scored_candidates(candidates, components, weights, k)


def rank_scored_candidates(candidates, components: list[Scores], weights: Weights, k: int = 5) -> tuple[SearchItem, ...]:
    """Reuse component scores when evaluating several weights on the same query."""
    if k <= 0:
        raise ValueError("k must be positive")
    if len(candidates) < k:
        raise invalid(
            "INSUFFICIENT_GALLERY",
            "Gallery không đủ ứng viên hợp lệ",
            candidate_count=len(candidates),
            required=k,
        )
    if len(components) != len(candidates):
        raise ValueError("Component count differs from candidates")
    effective = normalize_weights(weights)
    scored = []
    for candidate, component in zip(candidates, components):
        if set(effective.as_dict()) - set(component.as_dict()):
            raise invalid("INVALID_WEIGHTS", "Trọng số không thuộc cấu hình")
        total = _bounded(sum(component.contributions(effective).values()))
        scored.append((candidate, Scores(component.hsv, component.hog, component.lbp, total, component.extras)))
    scored.sort(key=lambda pair: (-pair[1].total, pair[0].image_id))
    items: list[SearchItem] = []
    seen: set[int] = set()
    for candidate, scores in scored:
        if candidate.image_id in seen:
            continue
        seen.add(candidate.image_id)
        items.append(
            SearchItem(
                rank=len(items) + 1,
                image_id=candidate.image_id,
                processed_path=candidate.processed_path,
                species_name=candidate.species_name,
                scores=scores,
            )
        )
        if len(items) == k:
            break
    if len(items) < k:
        raise invalid(
            "INSUFFICIENT_GALLERY",
            "Không đủ ID ảnh duy nhất để trả kết quả",
            unique_candidates=len(seen),
            required=k,
        )
    return tuple(items)
