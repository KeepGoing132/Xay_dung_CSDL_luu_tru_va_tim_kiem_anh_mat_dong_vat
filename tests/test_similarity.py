from __future__ import annotations

import numpy as np
import pytest

from backend.src.errors import AppError
from backend.src.models import Candidate, FeatureBundle, Weights
from backend.src.similarity import compare_features, normalize_weights, rank_candidates


def bundle(config_id: int = 1, scale: float = 1.0) -> FeatureBundle:
    hsv = np.zeros(128); hsv[0] = 1
    hog = np.zeros(1764); hog[0] = scale
    lbp = np.zeros(160); lbp[0] = 1
    return FeatureBundle(hsv, hog, lbp, {"hsv": config_id, "hog": config_id + 1, "lbp": config_id + 2})


def test_weights_are_normalized() -> None:
    assert normalize_weights(Weights(2, 1, 1)) == Weights(0.5, 0.25, 0.25)


def test_large_finite_weights_do_not_overflow() -> None:
    assert normalize_weights(Weights(1e308, 1e308, 1e308)) == Weights()


@pytest.mark.parametrize("weights", [Weights(-1, 1, 1), Weights(0, 0, 0), Weights(float("nan"), 1, 1)])
def test_invalid_weights(weights: Weights) -> None:
    with pytest.raises(AppError) as caught:
        normalize_weights(weights)
    assert caught.value.code == "INVALID_WEIGHTS"


def test_config_mismatch() -> None:
    with pytest.raises(AppError) as caught:
        compare_features(bundle(1), bundle(9), Weights())
    assert caught.value.code == "CONFIG_MISMATCH"


def test_stable_tie_break_uses_image_id() -> None:
    query = bundle()
    candidates = [
        Candidate(image_id=image_id, processed_path=f"{image_id}.png", species_name=None, features=bundle())
        for image_id in [9, 4, 7, 1, 3]
    ]
    result = rank_candidates(query, candidates, Weights(), k=5)
    assert [item.image_id for item in result] == [1, 3, 4, 7, 9]
