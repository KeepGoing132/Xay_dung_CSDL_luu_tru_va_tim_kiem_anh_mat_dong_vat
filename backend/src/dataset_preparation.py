"""Prepare immutable gallery-only calibration for the four-descriptor dataset."""
import csv
from PIL import Image
from .background_import import build_manifest
from .calibration_preparation import prepare_calibration
from .config import OFFICIAL_MASK_DIRECTORY

def prepare_manifest_calibration(config, *, allow_partial=False):
    source_manifest = config.source_manifest_path
    with source_manifest.open(encoding="utf-8-sig", newline="") as stream:
        sources = list(csv.DictReader(stream))
    # The model receives the same normalized RGB canvas as query_cutout.
    for row in sources:
        with Image.open(config.resolve_data_path(row["relative_path"])) as image:
            if image.mode != "RGB" or image.size != (512, 512) or image.getexif().get(274, 1) != 1:
                raise ValueError(f"Source must already be normalized RGB 512: {row['relative_path']}")
        if any(row.get(key, "").strip() for key in ("crop_x", "crop_y", "crop_size")):
            raise ValueError(f"Normalize source crop before segmentation: {row['relative_path']}")
    cutouts = config.data_root / "background_removed" / OFFICIAL_MASK_DIRECTORY
    # Mask test nằm ở background_removed-test nên chỉ dựng manifest mask cho gallery.
    _, rows, _ = build_manifest(config, source_manifest, cutouts, allow_partial=allow_partial, reviewed=True,
                                source_splits={"gallery"})
    # Source approval permits fitting; retrieval still requires separate mask review.
    return prepare_calibration(config, rows, workers=4)
