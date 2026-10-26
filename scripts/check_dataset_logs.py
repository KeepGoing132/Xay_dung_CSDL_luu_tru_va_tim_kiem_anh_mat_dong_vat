"""Kiểm tra đồng bộ log từng ảnh: manifest, orientation-log, inventory, manifest chạy, ATTRIBUTION.

Mỗi ảnh trong data/dataset512-left/images512 phải có đúng một dòng ở manifest.csv và
orientation-log.csv; checksum/kích thước trong log phải khớp file thật; inventory.csv và
manifest chạy của profile đang chọn (mặc định foreground4_hogpca512_sources.csv) và ATTRIBUTION.html phải khớp cùng
tập ảnh. Lệnh trả mã lỗi 1 khi phát hiện lệch.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import re
import sys
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_pixels(path: Path) -> str:
    from PIL import Image

    with Image.open(path) as image:
        return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()


def check(config) -> list[str]:
    problems: list[str] = []
    root = config.data_root / "dataset512-left"
    data_root = config.data_root
    disk = {str(p.relative_to(data_root)).replace("\\", "/") for p in (root / "images512").glob("*/*.png")}

    manifest = load(root / "manifest.csv")
    man_paths = [row["data_relative_path"] for row in manifest]
    for path in man_paths:
        if path not in disk:
            problems.append(f"manifest row without file: {path}")
    for path in sorted(disk - set(man_paths)):
        problems.append(f"image without manifest row: {path}")
    for path, count in Counter(man_paths).items():
        if count > 1:
            problems.append(f"duplicate manifest rows ({count}): {path}")
    for row in manifest:
        path = data_root / row["data_relative_path"]
        if not path.exists():
            continue
        if sha256_file(path) != row["file_sha256"]:
            problems.append(f"file_sha256 mismatch: {row['data_relative_path']}")
        if sha256_pixels(path) != row["pixel_sha256"]:
            problems.append(f"pixel_sha256 mismatch: {row['data_relative_path']}")
        if row["width"] != "512" or row["height"] != "512":
            problems.append(f"logged size is not 512x512: {row['data_relative_path']}")

    orientation = load(root / "orientation-log.csv")
    ori_paths = [row["orientation_output_relative_path"] for row in orientation]
    for path in ori_paths:
        if path not in disk:
            problems.append(f"orientation row without file: {path}")
    for path in sorted(disk - set(ori_paths)):
        problems.append(f"image without orientation row: {path}")
    for path, count in Counter(ori_paths).items():
        if count > 1:
            problems.append(f"duplicate orientation rows ({count}): {path}")
    for row in orientation:
        path = data_root / row["orientation_output_relative_path"]
        if path.exists() and sha256_file(path) != row["file_sha256"]:
            problems.append(f"orientation checksum mismatch: {row['orientation_output_relative_path']}")

    inventory = load(root / "inventory.csv")
    counts = Counter(row["species_name"] for row in manifest)
    declared = {row["species_name"]: int(row["selected_count"]) for row in inventory}
    if dict(counts) != declared:
        problems.append(f"inventory does not match manifest: {declared} vs {dict(counts)}")
    minimums = {row["species_name"]: int(row["minimum_total"]) for row in inventory}
    for species, count in counts.items():
        if count < minimums.get(species, 0):
            problems.append(f"species below minimum: {species} {count} < {minimums[species]}")

    runtime = load(config.source_manifest_path)
    runtime_paths = {row["relative_path"] for row in runtime}
    if runtime_paths != disk:
        problems.append(
            f"runtime manifest differs: only runtime {len(runtime_paths - disk)}, only disk {len(disk - runtime_paths)}"
        )

    page = (root / "ATTRIBUTION.html").read_text(encoding="utf-8")
    page_paths = {f"dataset512-left/{src}" for src in re.findall(r'<img loading="lazy" src="([^"]+)"', page)}
    if page_paths != disk:
        problems.append(
            f"ATTRIBUTION differs: only page {len(page_paths - disk)}, only disk {len(disk - page_paths)}"
        )

    review = load(root / "quality-review.csv")
    unknown = [row for row in review if row.get("current_status", "").startswith("replacement in dataset") is False and not row.get("current_status")]
    if unknown:
        problems.append(f"quality-review rows without current_status: {len(unknown)}")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    config = AppConfig.default()
    problems = check(config)
    images = len(list((config.data_root / "dataset512-left/images512").glob("*/*.png")))
    if not args.quiet:
        print(f"images={images} problems={len(problems)}")
    for problem in problems[:40]:
        print(" -", problem)
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
