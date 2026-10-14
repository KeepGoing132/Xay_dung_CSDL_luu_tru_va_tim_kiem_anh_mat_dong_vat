from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image
import pytest

from backend.src.errors import AppError
from backend.src.models import CropBox
from backend.src.preprocessing import preprocess_image


def encode(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


@pytest.mark.parametrize(
    "image",
    [
        Image.new("RGB", (180, 120), (10, 20, 30)),
        Image.new("L", (180, 120), 128),
        Image.new("RGBA", (180, 120), (10, 20, 30, 80)),
    ],
)
def test_preprocess_modes_to_rgb(image: Image.Image) -> None:
    result = preprocess_image(encode(image))
    assert result.rgb.shape == (128, 128, 3)
    assert result.rgb.dtype == np.uint8
    assert result.crop == CropBox(30, 0, 120)
    assert len(result.pixel_sha256) == 64


def test_invalid_crop_is_not_clamped() -> None:
    with pytest.raises(AppError) as caught:
        preprocess_image(encode(Image.new("RGB", (100, 80))), CropBox(50, 0, 60))
    assert caught.value.code == "INVALID_CROP"


@pytest.mark.parametrize("payload", [b"", b"not an image"])
def test_invalid_image(payload: bytes) -> None:
    with pytest.raises(AppError) as caught:
        preprocess_image(payload)
    assert caught.value.code == "INVALID_IMAGE"

