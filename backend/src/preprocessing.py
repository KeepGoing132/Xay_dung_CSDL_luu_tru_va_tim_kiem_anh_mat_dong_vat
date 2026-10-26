from __future__ import annotations

from hashlib import sha256
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import PREPROCESS_VERSION, preprocessing_size, requires_background
from .errors import AppError, invalid
from .models import CropBox, ProcessedImage


def _open_or_raise(image_bytes: bytes) -> Image.Image:
    if not image_bytes:
        raise invalid("INVALID_IMAGE", "Tệp ảnh rỗng")
    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise invalid("INVALID_IMAGE", "Không thể giải mã ảnh", reason=str(exc)) from exc
    return ImageOps.exif_transpose(image)


def _to_rgb_on_white(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(background, rgba).convert("RGB")
    return image.convert("RGB")


def _resolve_crop(image: Image.Image, crop: CropBox | None) -> CropBox:
    width, height = image.size
    if width <= 0 or height <= 0:
        raise invalid("INVALID_IMAGE", "Ảnh có kích thước không hợp lệ", width=width, height=height)
    if crop is None:
        size = min(width, height)
        return CropBox(x=(width - size) // 2, y=(height - size) // 2, size=size)
    if crop.size <= 0 or crop.x < 0 or crop.y < 0:
        raise invalid("INVALID_CROP", "Vùng cắt phải có tọa độ không âm và cạnh dương")
    if crop.x + crop.size > width or crop.y + crop.size > height:
        raise invalid(
            "INVALID_CROP",
            "Vùng cắt nằm ngoài ảnh sau khi sửa hướng EXIF",
            image_width=width,
            image_height=height,
            crop={"x": crop.x, "y": crop.y, "size": crop.size},
        )
    return crop


def preprocess_image(
    image_bytes: bytes, crop: CropBox | None = None, *, preprocess_version: str = PREPROCESS_VERSION
) -> ProcessedImage:
    try:
        size = preprocessing_size(preprocess_version)
    except ValueError:
        raise invalid("CONFIG_MISMATCH", "Phiên bản tiền xử lý không được hỗ trợ", version=preprocess_version)
    image = _open_or_raise(image_bytes)
    if requires_background(preprocess_version):
        if not (image.mode in {"RGBA", "LA"} or "transparency" in image.info):
            raise invalid("BACKGROUND_REQUIRED", "Hãy chạy tách nền và chọn PNG có nền trong suốt")
        minimum, maximum = image.convert("RGBA").getchannel("A").getextrema()
        if minimum == 255 or maximum == 0:
            raise invalid("BACKGROUND_REQUIRED", "Mask tách nền rỗng hoặc chưa có vùng nền trong suốt")
    resolved = _resolve_crop(image, crop)
    box = (resolved.x, resolved.y, resolved.x + resolved.size, resolved.y + resolved.size)
    image = _to_rgb_on_white(image)
    cropped = image.crop(box)
    resized = cropped if cropped.size == (size, size) else cropped.resize((size, size), Image.Resampling.BILINEAR)
    rgb = np.asarray(resized, dtype=np.uint8)
    if rgb.shape != (size, size, 3):
        raise invalid("INVALID_IMAGE", f"Ảnh chuẩn hóa không có shape RGB {size}x{size}", shape=list(rgb.shape))
    rgb = np.ascontiguousarray(rgb)
    return ProcessedImage(
        rgb=rgb,
        crop=resolved,
        preprocess_version=preprocess_version,
        pixel_sha256=sha256(rgb.tobytes(order="C")).hexdigest(),
    )


def encode_processed_png(image: ProcessedImage) -> bytes:
    stream = BytesIO()
    Image.fromarray(image.rgb, mode="RGB").save(stream, format="PNG", optimize=True)
    return stream.getvalue()
