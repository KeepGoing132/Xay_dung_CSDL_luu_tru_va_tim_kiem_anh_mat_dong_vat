from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig


def difference_hash(path: Path, size: int = 16) -> int:
    with Image.open(path) as image:
        gray = ImageOps.grayscale(ImageOps.exif_transpose(image))
        resized = gray.resize((size + 1, size), Image.Resampling.LANCZOS)
        if hasattr(resized, "get_flattened_data"):
            pixels = list(resized.get_flattened_data())
        else:
            pixels = list(resized.getdata())
    value = 0
    width = size + 1
    for y in range(size):
        for x in range(size):
            value = (value << 1) | int(pixels[y * width + x] > pixels[y * width + x + 1])
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Báo cáo cặp ảnh gần trùng bằng dHash 256 bit")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--max-distance", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = AppConfig.default()
    with args.manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    hashes = [difference_hash(config.resolve_data_path(row["relative_path"])) for row in rows]
    pairs: list[dict[str, str | int]] = []
    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            distance = (hashes[left] ^ hashes[right]).bit_count()
            if distance <= args.max_distance:
                pairs.append(
                    {
                        "distance": distance,
                        "left_split": rows[left]["split"],
                        "left_path": rows[left]["relative_path"],
                        "right_split": rows[right]["split"],
                        "right_path": rows[right]["relative_path"],
                    }
                )
    pairs.sort(key=lambda pair: (int(pair["distance"]), str(pair["left_path"])))
    output = args.output or args.manifest.with_name(args.manifest.stem + "_near_duplicates.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["distance", "left_split", "left_path", "right_split", "right_path"],
        )
        writer.writeheader()
        writer.writerows(pairs)
    cross_split = sum(pair["left_split"] != pair["right_split"] for pair in pairs)
    print(f"images={len(rows)} pairs={len(pairs)} cross_split={cross_split} output={output}")


if __name__ == "__main__":
    main()
