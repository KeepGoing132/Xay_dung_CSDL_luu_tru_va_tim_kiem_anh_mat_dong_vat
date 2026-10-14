from __future__ import annotations

import argparse
import csv
from pathlib import Path, PurePosixPath
import shutil
import sys
from zipfile import ZipFile

from PIL import Image
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig


SOURCE_URL = "https://github.com/clovaai/stargan-v2#animal-faces-hq-dataset-afhq"
LICENSE_NOTE = "AFHQ - Creative Commons Attribution-NonCommercial 4.0, NAVER Corporation"
DOMAINS = ("cat", "dog", "wild")
MIN_GALLERY_IMAGES = 500


def validate_sample_sizes(gallery_per_domain: int, queries_per_domain: int) -> None:
    if gallery_per_domain < 1 or gallery_per_domain * len(DOMAINS) < MIN_GALLERY_IMAGES:
        minimum = (MIN_GALLERY_IMAGES + len(DOMAINS) - 1) // len(DOMAINS)
        raise ValueError(
            f"Cần ít nhất {minimum} ảnh cho mỗi domain để gallery ba domain đạt "
            f"tối thiểu {MIN_GALLERY_IMAGES} ảnh"
        )
    if queries_per_domain < 2 or queries_per_domain % 2:
        raise ValueError("queries-per-domain phải là số chẵn >= 2")


def members_for(archive: ZipFile, split: str, domain: str) -> list[str]:
    suffixes = {".jpg", ".jpeg", ".png", ".webp"}
    selected = []
    for member in archive.namelist():
        path = PurePosixPath(member)
        parts = [part.casefold() for part in path.parts]
        if split in parts and domain in parts and path.suffix.casefold() in suffixes:
            selected.append(member)
    return sorted(selected)


def copy_member(archive: ZipFile, member: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(member) as source, destination.open("wb") as target:
        shutil.copyfileobj(source, target, length=1024 * 1024)


def manifest_row(config: AppConfig, member: str, destination: Path, domain: str, split: str, status: str):
    return {
        "relative_path": config.relative_to_data(destination),
        "species_name": domain,
        "source_url": SOURCE_URL,
        "license_note": LICENSE_NOTE,
        "split": split,
        "group_id": f"afhq:{member}",
        "crop_x": "",
        "crop_y": "",
        "crop_size": "",
        "quality_status": status,
        "review_note": "AFHQ aligned 512x512 source; center-square preprocessing",
    }


def extension_for(image_bytes: bytes) -> str:
    from io import BytesIO

    with Image.open(BytesIO(image_bytes)) as image:
        return {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(image.format or "", ".img")


def prepare_from_parquet(
    config: AppConfig,
    parquet_dir: Path,
    gallery_per_domain: int,
    queries_per_domain: int,
    status: str,
) -> list[dict[str, str]]:
    label_names = {0: "cat", 1: "dog", 2: "wild"}
    gallery_counts = {name: 0 for name in DOMAINS}
    query_counts = {name: 0 for name in DOMAINS}
    rows: list[dict[str, str]] = []
    global_index = 0
    shards = sorted(parquet_dir.glob("*.parquet"))
    if not shards:
        raise FileNotFoundError(f"Không có parquet shard trong {parquet_dir}")
    for shard in shards:
        parquet = pq.ParquetFile(shard)
        for batch in parquet.iter_batches(batch_size=128, columns=["image", "label"]):
            data = batch.to_pydict()
            for image_info, label in zip(data["image"], data["label"]):
                global_index += 1
                domain = label_names[int(label)]
                split: str | None = None
                if domain in gallery_counts and gallery_counts[domain] < gallery_per_domain:
                    split = "gallery"
                    gallery_counts[domain] += 1
                    sequence = gallery_counts[domain]
                elif query_counts[domain] < queries_per_domain:
                    sequence = query_counts[domain] + 1
                    split = "validation" if query_counts[domain] < queries_per_domain // 2 else "test"
                    query_counts[domain] += 1
                if split is None:
                    continue
                raw = image_info.get("bytes") if isinstance(image_info, dict) else None
                if raw is None:
                    raise RuntimeError("Parquet image record không chứa bytes")
                suffix = extension_for(raw)
                filename = f"afhq-{global_index:06d}-{sequence:03d}{suffix}"
                destination = config.data_root / "original" / split / domain / filename
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    destination.write_bytes(raw)
                source_id = image_info.get("path") if isinstance(image_info, dict) else None
                member = source_id or f"huggan/AFHQ:row-{global_index}"
                row = manifest_row(config, member, destination, domain, split, status)
                row["review_note"] += "; transported via Hugging Face HugGAN mirror"
                rows.append(row)
                if (
                    all(value >= gallery_per_domain for value in gallery_counts.values())
                    and all(value >= queries_per_domain for value in query_counts.values())
                ):
                    return rows
    raise RuntimeError(
        f"Không đủ bản ghi. Gallery={gallery_counts}, query={query_counts}, rows={len(rows)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Chọn tập AFHQ cân bằng và tạo manifest tái lập")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--parquet-dir", type=Path)
    parser.add_argument("--gallery-per-domain", type=int, default=200)
    parser.add_argument("--queries-per-domain", type=int, default=40)
    parser.add_argument("--quality-status", choices=["pending", "approved"], default="pending")
    args = parser.parse_args()
    config = AppConfig.default()
    config.ensure_runtime_dirs()
    validate_sample_sizes(args.gallery_per_domain, args.queries_per_domain)

    parquet_dir = args.parquet_dir or config.data_root / "downloads" / "afhq-huggingface"
    if parquet_dir.is_dir() and list(parquet_dir.glob("*.parquet")):
        rows = prepare_from_parquet(
            config,
            parquet_dir,
            args.gallery_per_domain,
            args.queries_per_domain,
            args.quality_status,
        )
    else:
        archive_path = args.archive or config.data_root / "downloads" / "afhq.zip"
        if not archive_path.is_file():
            raise FileNotFoundError(f"Chưa có archive hoặc parquet: {archive_path}, {parquet_dir}")
        rows = []
        with ZipFile(archive_path) as archive:
            for domain in DOMAINS:
                candidates = members_for(archive, "train", domain)
                if len(candidates) < args.gallery_per_domain:
                    raise RuntimeError(f"AFHQ train/{domain} chỉ có {len(candidates)} ảnh")
                for member in candidates[: args.gallery_per_domain]:
                    filename = PurePosixPath(member).name
                    destination = config.data_root / "original" / "gallery" / domain / filename
                    if not destination.exists():
                        copy_member(archive, member, destination)
                    rows.append(manifest_row(config, member, destination, domain, "gallery", args.quality_status))

            half = args.queries_per_domain // 2
            for domain in DOMAINS:
                candidates = members_for(archive, "val", domain)
                if len(candidates) < args.queries_per_domain:
                    raise RuntimeError(f"AFHQ val/{domain} chỉ có {len(candidates)} ảnh")
                for index, member in enumerate(candidates[: args.queries_per_domain]):
                    split = "validation" if index < half else "test"
                    filename = PurePosixPath(member).name
                    destination = config.data_root / "original" / split / domain / filename
                    if not destination.exists():
                        copy_member(archive, member, destination)
                    rows.append(manifest_row(config, member, destination, domain, split, args.quality_status))

    output = config.data_root / "manifests" / "afhq_manifest.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Manifest: {output}")
    print(f"Gallery: {sum(row['split'] == 'gallery' for row in rows)}")
    print(f"Validation: {sum(row['split'] == 'validation' for row in rows)}")
    print(f"Test: {sum(row['split'] == 'test' for row in rows)}")
    print(f"Quality status: {args.quality_status}")


if __name__ == "__main__":
    main()
