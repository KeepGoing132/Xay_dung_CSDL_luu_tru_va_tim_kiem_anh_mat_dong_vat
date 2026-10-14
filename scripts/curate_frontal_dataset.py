"""Prepare contact sheets and build a dataset from explicit visual-review decisions."""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import random
import shutil
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.check_near_duplicates import difference_hash

SOURCE_PAGE = "https://github.com/clovaai/stargan-v2#animal-faces-hq-dataset-afhq"
SOURCE_ARCHIVE = "https://dl.dropboxusercontent.com/s/vkzjokiwof5h8w6/afhq_v2.zip"


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_sheets(rows, directory, name, tile=220, columns=6, per_page=36):
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 17)
    for start in range(0, len(rows), per_page):
        chunk = rows[start:start + per_page]
        height = (len(chunk) + columns - 1) // columns
        canvas = Image.new("RGB", (tile * columns, (tile + 32) * height), "white")
        draw = ImageDraw.Draw(canvas)
        for index, row in enumerate(chunk):
            with Image.open(row["path"]) as image:
                image = image.convert("RGB").resize((tile - 4, tile - 4), Image.Resampling.LANCZOS)
            x, y = index % columns * tile, index // columns * (tile + 32)
            canvas.paste(image, (x + 2, y + 2))
            draw.text((x + 5, y + tile + 1), row["id"], font=font, fill="black")
        canvas.save(directory / f"{name}-{start // per_page + 1:02d}.jpg", quality=95)


def prepare(args):
    archive = args.archive.resolve()
    catalog = archive / "unused/data/review/hq-faces-20261010/afhq-v2-color.csv"
    with catalog.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    output = ROOT / "data/review/frontal512-20261010"
    output.mkdir(parents=True, exist_ok=True)
    candidates = []
    for group, count, prefix in [("cat", 360, "C"), ("dog", 480, "D"), ("wild", 720, "W")]:
        members = [r for r in rows if r["group"] == group]
        random.Random(20261010).shuffle(members)
        selected = []
        for index, row in enumerate(members[:count], start=1):
            path = archive / "unused" / row["relative_path"]
            selected.append({"id": f"{prefix}{index:03d}", "path": str(path), "member": row["member"],
                             "source_sha256": row["sha256"], "source_group": group,
                             "archive_relative_path": row["relative_path"]})
        candidates.extend(selected)
        make_sheets(selected, output, f"candidates-{group}")
    (output / "candidates.json").write_text(json.dumps([
        {k: v for k, v in row.items() if k != "path"} for row in candidates
    ], indent=2), encoding="utf-8")
    print(f"Prepared {len(candidates)} candidates: {output}")


def build(args):
    review = ROOT / "data/review/frontal512-20261010"
    candidates = {r["id"]: r for r in json.loads((review / "candidates.json").read_text())}
    decisions = json.loads((review / "decisions.json").read_text())
    selections = []
    for species, identifiers in decisions["accepted"].items():
        for identifier in identifiers:
            row = dict(candidates[identifier])
            row["path"] = str(args.archive.resolve() / "unused" / row["archive_relative_path"])
            row["species"] = species
            selections.append(row)
    assert len({r["id"] for r in selections}) == len(selections)
    required = decisions["split_counts"]
    chosen, used_bytes, hashes, near_duplicates = [], set(), [], []
    for row in selections:
        path = Path(row["path"])
        data = path.read_bytes()
        checksum = sha256(data).hexdigest()
        if checksum != row["source_sha256"]:
            raise ValueError(f"Source hash changed: {path}")
        with Image.open(path) as image:
            if image.mode != "RGB" or image.size != (512, 512):
                raise ValueError(f"Nonuniform source: {path}")
        h = difference_hash(path)
        duplicate = next((old["id"] for old, old_hash in hashes if (h ^ old_hash).bit_count() <= 5), None)
        if checksum in used_bytes or duplicate:
            near_duplicates.append({"id": row["id"], "duplicate_of": duplicate})
            continue
        used_bytes.add(checksum)
        hashes.append((row, h))
        chosen.append(row)
    final = []
    manifest_rows = []
    for species, counts in required.items():
        rows = [r for r in chosen if r["species"] == species]
        needed = sum(counts.values())
        if len(rows) < needed:
            raise ValueError(f"Not enough visually accepted {species}: {len(rows)} < {needed}")
        random.Random(20261010).shuffle(rows)
        index = 0
        for split, count in counts.items():
            for row in rows[index:index + count]:
                relative = f"original/{split}/{species}/{Path(row['member']).name}"
                destination = ROOT / "data" / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    if sha256(destination.read_bytes()).hexdigest() != row["source_sha256"]:
                        raise ValueError(f"Refusing to overwrite another image: {destination}")
                else:
                    shutil.copy2(row["path"], destination)
                entry = dict(row, relative_path=relative, split=split, path=str(destination))
                final.append(entry)
                manifest_rows.append({
                    "relative_path": relative, "species_name": species, "source_url": SOURCE_PAGE,
                    "license_note": "AFHQ v2; CC BY-NC 4.0; NAVER Corporation; original PNG unchanged",
                    "split": split, "group_id": "afhq-v2:" + Path(row["member"]).name,
                    "crop_x": "", "crop_y": "", "crop_size": "", "quality_status": "approved",
                    "review_note": "Visual review: frontal/level eyes, visible eyes-nose-mouth, centered close face, clear color; native 512x512",
                    "source_archive": "afhq_v2.zip", "source_member": row["member"],
                })
            index += count
    write_csv(ROOT / "data/manifests/frontal512_manifest.csv", manifest_rows)
    write_csv(ROOT / "data/manifests/frontal512_sources.csv", [
        {"relative_path": r["relative_path"], "species": r["species"], "source_page": SOURCE_PAGE,
         "download_url": SOURCE_ARCHIVE, "archive_member": r["member"], "source_sha256": r["source_sha256"],
         "license": "CC BY-NC 4.0", "credit": "NAVER Corporation; Choi et al., StarGAN v2, CVPR 2020",
         "modifications": "none; original source PNG", "visual_review_id": r["id"]} for r in final])
    for split in ["gallery", "validation", "test"]:
        make_sheets([dict(r, id=f"{r['id']} {r['species']}") for r in final if r["split"] == split],
                    review, f"selected-{split}", tile=256, columns=5, per_page=25)
    (review / "final-selection.json").write_text(json.dumps([
        {k: v for k, v in row.items() if k != "path"} for row in final
    ], indent=2), encoding="utf-8")
    (review / "near-duplicate-rejections.json").write_text(json.dumps(near_duplicates, indent=2), encoding="utf-8")
    print(f"Built {len(final)} images; gallery={sum(r['split']=='gallery' for r in final)}; near duplicates omitted={len(near_duplicates)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "build"])
    parser.add_argument("--archive", type=Path, default=ROOT.parent / "BTL_luu_tru_20261010")
    args = parser.parse_args()
    prepare(args) if args.action == "prepare" else build(args)
