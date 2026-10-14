from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from backend.src.features import extract_features
from backend.src.preprocessing import preprocess_image
from backend.src.repository import Repository


def png_bytes(array: np.ndarray) -> bytes:
    stream = BytesIO()
    Image.fromarray(array.astype(np.uint8), mode="RGB").save(stream, format="PNG")
    return stream.getvalue()


def test_feature_dimensions_and_normalization(app_config) -> None:
    repository = Repository(app_config)
    repository.create_schema()
    bundle = repository.ensure_baseline_bundle()
    y, x = np.mgrid[:128, :128]
    image = np.stack((x * 2, y * 2, (x + y) % 256), axis=2).astype(np.uint8)
    features = extract_features(preprocess_image(png_bytes(image)), bundle)
    assert features.hsv.shape == (128,)
    assert features.hog.shape == (1764,)
    assert features.lbp.shape == (160,)
    assert np.isclose(features.hsv.sum(), 1.0)
    assert np.isclose(np.linalg.norm(features.hog), 1.0)
    assert np.isclose(features.lbp.sum(), 1.0)
    assert np.allclose(features.lbp.reshape(16, 10).sum(axis=1), 1 / 16)


def test_uniform_image_has_zero_hog(app_config) -> None:
    repository = Repository(app_config)
    repository.create_schema()
    bundle = repository.ensure_baseline_bundle()
    image = np.full((128, 128, 3), 127, dtype=np.uint8)
    features = extract_features(preprocess_image(png_bytes(image)), bundle)
    assert np.count_nonzero(features.hog) == 0
    assert "zero_gradient" in features.warnings

