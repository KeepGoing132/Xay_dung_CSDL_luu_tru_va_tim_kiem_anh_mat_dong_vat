"""Validate transparent cutouts without changing the source or mask."""
from pathlib import Path

from PIL import Image, ImageOps


def validate_cutout(source: Path, cutout: Path) -> dict:
    with Image.open(source) as image:
        rgb = ImageOps.exif_transpose(image).convert("RGB")
    with Image.open(cutout) as image:
        if image.mode != "RGBA" or image.size != rgb.size or image.convert("RGB").tobytes() != rgb.tobytes():
            raise ValueError(f"Cutout must retain source RGB and EXIF-oriented dimensions: {cutout}")
        minimum, maximum = image.getchannel("A").getextrema()
        if minimum == 255 or maximum == 0:
            raise ValueError(f"Missing or empty transparency mask: {cutout}")
        return {"width": image.width, "height": image.height, "mode": image.mode,
                "alpha_range": [minimum, maximum]}
