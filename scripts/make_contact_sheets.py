from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo contact sheet để duyệt trực quan manifest ảnh")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--split", default="gallery", choices=["gallery", "validation", "test"])
    parser.add_argument("--per-sheet", type=int, default=60)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = AppConfig.default()
    manifest = args.manifest or config.default_manifest_path
    with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["split"] == args.split]
    output_dir = args.output_dir or config.data_root / "review" / f"contact-{args.split}"
    output_dir.mkdir(parents=True, exist_ok=True)
    cols = 10
    rows_per_sheet = (args.per_sheet + cols - 1) // cols
    tile_w, tile_h = 144, 168
    font = ImageFont.load_default()
    for sheet_index, offset in enumerate(range(0, len(rows), args.per_sheet), start=1):
        chunk = rows[offset : offset + args.per_sheet]
        sheet = Image.new("RGB", (cols * tile_w, rows_per_sheet * tile_h), "white")
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(chunk):
            image = Image.open(config.resolve_data_path(row["relative_path"])).convert("RGB")
            thumb = ImageOps.fit(image, (128, 128), method=Image.Resampling.LANCZOS)
            x = (index % cols) * tile_w + 8
            y = (index // cols) * tile_h + 4
            sheet.paste(thumb, (x, y))
            label = f"{offset + index + 1:03d} {row['species_name']}"
            draw.text((x, y + 132), label, fill="black", font=font)
            draw.text((x, y + 146), Path(row["relative_path"]).stem[:18], fill="#444444", font=font)
        output = output_dir / f"{args.split}-{sheet_index:02d}.jpg"
        sheet.save(output, quality=90)
        print(output)


if __name__ == "__main__":
    main()
