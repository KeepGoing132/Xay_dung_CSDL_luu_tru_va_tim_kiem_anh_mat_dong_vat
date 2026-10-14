from __future__ import annotations

import argparse
import csv
from io import BytesIO
from pathlib import Path, PurePosixPath
import re
import sys
from zipfile import ZipFile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.download_afd import COMPACT_20_ARCHIVES, DATASET_PAGE
from backend.src.config import AppConfig


AFD_LICENSE = "AFD - Creative Commons Attribution 4.0, Pengfei Xu"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
AFHQ_TYPES = ("cat", "dog")
TYPE_COUNT = len(COMPACT_20_ARCHIVES) + len(AFHQ_TYPES)


def species_from_archive(path: Path) -> str:
    return path.stem


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not slug:
        raise ValueError(f"Không tạo được slug từ {value!r}")
    return slug


def identity_from_member(member: str) -> str:
    parts = PurePosixPath(member).parts[1:-1]
    numeric = next((part for part in parts if part.isdigit()), None)
    if numeric is None:
        raise ValueError(f"Không xác định được cá thể AFD từ đường dẫn: {member}")
    return numeric


def scene_from_member(member: str) -> str:
    stem = PurePosixPath(member).stem
    return re.sub(r"-[12]$", "", stem)


def image_members(archive: ZipFile) -> dict[str, list[str]]:
    scenes: dict[tuple[str, str], str] = {}
    for member in archive.namelist():
        if PurePosixPath(member).suffix.casefold() not in IMAGE_SUFFIXES:
            continue
        identity = identity_from_member(member)
        key = (identity, scene_from_member(member))
        current = scenes.get(key)
        if current is None or (member.endswith("-1.jpg") and not current.endswith("-1.jpg")):
            scenes[key] = member
    groups: dict[str, list[str]] = {}
    for (identity, _), member in scenes.items():
        groups.setdefault(identity, []).append(member)
    for members in groups.values():
        members.sort()
    return groups


def take_round_robin(groups: list[tuple[str, list[str]]], count: int) -> list[tuple[str, str]]:
    selected: list[tuple[str, str]] = []
    index = 0
    while len(selected) < count:
        progressed = False
        for identity, members in groups:
            if index < len(members):
                selected.append((identity, members[index]))
                progressed = True
                if len(selected) == count:
                    return selected
        if not progressed:
            break
        index += 1
    raise RuntimeError(f"Chỉ chọn được {len(selected)}/{count} ảnh từ nhóm cá thể đã cấp")


def split_identity_groups(
    groups: dict[str, list[str]],
    gallery_count: int,
    query_count: int,
    excluded_members: set[str] | None = None,
) -> dict[str, list[tuple[str, str]]]:
    excluded = excluded_members or set()
    filtered = {
        identity: [member for member in members if member not in excluded]
        for identity, members in groups.items()
    }
    ordered = sorted(
        ((identity, members) for identity, members in filtered.items() if members),
        key=lambda item: (int(item[0]), item[0]),
    )
    if len(ordered) < 3:
        raise RuntimeError("Cần ít nhất ba cá thể để tách gallery/validation/test")

    by_size = sorted(ordered, key=lambda item: (len(item[1]), int(item[0]), item[0]))
    max_query_groups = min(query_count, (len(ordered) - 1) // 2)
    allocation = None
    for query_group_count in range(max_query_groups, 0, -1):
        candidate_test = by_size[:query_group_count]
        candidate_validation = by_size[query_group_count : query_group_count * 2]
        reserved = {
            identity for identity, _ in candidate_test + candidate_validation
        }
        candidate_gallery = [item for item in ordered if item[0] not in reserved]
        if (
            sum(len(items) for _, items in candidate_test) >= query_count
            and sum(len(items) for _, items in candidate_validation) >= query_count
            and sum(len(items) for _, items in candidate_gallery) >= gallery_count
        ):
            allocation = (
                candidate_gallery,
                candidate_validation,
                candidate_test,
            )
            break
    if allocation is None:
        raise RuntimeError(
            "Not enough approved identity-disjoint images for gallery/validation/test"
        )
    remaining, validation_groups, test_groups = allocation
    if sum(len(items) for _, items in test_groups) < query_count:
        raise RuntimeError("Không đủ ảnh test trong các nhóm cá thể độc lập đã cấp")
    if sum(len(items) for _, items in validation_groups) < query_count:
        raise RuntimeError("Không đủ ảnh validation trong các nhóm cá thể độc lập đã cấp")
    if sum(len(items) for _, items in remaining) < gallery_count:
        raise RuntimeError("Không đủ ảnh/cá thể độc lập cho gallery sau khi giữ query ngoài gallery")

    return {
        "gallery": take_round_robin(remaining, gallery_count),
        "validation": take_round_robin(validation_groups, query_count),
        "test": take_round_robin(test_groups, query_count),
    }


def extension_for(raw: bytes) -> str:
    with Image.open(BytesIO(raw)) as image:
        image.verify()
        return {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(image.format or "", ".img")


def write_afd_image(
    config: AppConfig,
    archive: ZipFile,
    member: str,
    species: str,
    split: str,
    sequence: int,
) -> Path:
    raw = archive.read(member)
    suffix = extension_for(raw)
    folder = config.data_root / "original" / "mixed-20" / split / slugify(species)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"afd-{slugify(species)}-{sequence:03d}{suffix}"
    if not destination.exists():
        destination.write_bytes(raw)
    return destination


def afd_rows(
    config: AppConfig,
    archive_dir: Path,
    gallery_count: int,
    query_count: int,
    status: str,
    rejections: dict[str, set[str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    expected = {name.casefold() for name in COMPACT_20_ARCHIVES}
    archives = {path.name.casefold(): path for path in archive_dir.glob("*.zip")}
    missing = sorted(expected - set(archives))
    if missing:
        raise FileNotFoundError(f"Thiếu gói AFD: {', '.join(missing)}")

    for archive_name in sorted(COMPACT_20_ARCHIVES, key=str.casefold):
        archive_path = archives[archive_name.casefold()]
        species = species_from_archive(archive_path)
        with ZipFile(archive_path) as archive:
            selected = split_identity_groups(
                image_members(archive),
                gallery_count,
                query_count,
                rejections.get(archive_path.name.casefold(), set()),
            )
            sequence = 0
            for split in ("gallery", "validation", "test"):
                for identity, member in selected[split]:
                    sequence += 1
                    destination = write_afd_image(
                        config, archive, member, species, split, sequence
                    )
                    rows.append(
                        {
                            "relative_path": config.relative_to_data(destination),
                            "species_name": species,
                            "source_url": DATASET_PAGE,
                            "license_note": AFD_LICENSE,
                            "split": split,
                            "group_id": f"afd:{slugify(species)}:{identity}",
                            "crop_x": "",
                            "crop_y": "",
                            "crop_size": "",
                            "quality_status": status,
                            "review_note": (
                                "AFD animal-face image; identity-disjoint split; "
                                "center-square preprocessing; "
                                + (
                                    "visually approved after rejection review"
                                    if status == "approved"
                                    else "pending visual review"
                                )
                            ),
                            "source_archive": archive_path.name,
                            "source_member": member,
                        }
                    )
    return rows


def afhq_rows(
    manifest: Path, gallery_count: int, query_count: int, status: str
) -> list[dict[str, str]]:
    with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        source_rows = list(csv.DictReader(stream))
    rows: list[dict[str, str]] = []
    limits = {"gallery": gallery_count, "validation": query_count, "test": query_count}
    for species in AFHQ_TYPES:
        for split, limit in limits.items():
            matches = [
                row
                for row in source_rows
                if row["species_name"] == species and row["split"] == split
            ]
            if len(matches) < limit:
                raise RuntimeError(f"AFHQ thiếu {species}/{split}: {len(matches)}/{limit}")
            for row in matches[:limit]:
                copied = dict(row)
                copied["quality_status"] = status
                copied["review_note"] = (
                    copied.get("review_note", "") + "; selected for balanced mixed-20 snapshot"
                ).strip("; ")
                copied["source_archive"] = ""
                copied["source_member"] = ""
                rows.append(copied)
    return rows


def load_rejections(path: Path) -> dict[str, set[str]]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    result: dict[str, set[str]] = {}
    for row in rows:
        archive = row.get("source_archive", "").strip().casefold()
        member = row.get("source_member", "").strip()
        if archive and member:
            result.setdefault(archive, set()).add(member)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo snapshot 20 loại từ AFHQ + AFD")
    parser.add_argument("--gallery-per-type", type=int, default=25)
    parser.add_argument("--queries-per-type", type=int, default=5)
    parser.add_argument("--quality-status", choices=["pending", "approved"], default="pending")
    parser.add_argument("--afd-dir", type=Path)
    parser.add_argument("--afhq-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rejections", type=Path)
    args = parser.parse_args()
    if args.gallery_per_type * TYPE_COUNT < 500:
        raise ValueError(
            f"Gallery phải >=500; {TYPE_COUNT} loại x {args.gallery_per_type} chỉ có "
            f"{TYPE_COUNT * args.gallery_per_type} ảnh"
        )
    if args.queries_per_type < 1:
        raise ValueError("queries-per-type phải >=1 cho mỗi split")

    config = AppConfig.default()
    config.ensure_runtime_dirs()
    archive_dir = args.afd_dir or config.data_root / "downloads" / "afd"
    afhq_manifest = args.afhq_manifest or config.data_root / "manifests" / "afhq_manifest.csv"
    rejection_path = args.rejections or config.data_root / "manifests" / "mixed_20_rejections.csv"
    rejections = load_rejections(rejection_path)
    rows = afhq_rows(afhq_manifest, args.gallery_per_type, args.queries_per_type, args.quality_status)
    rows.extend(
        afd_rows(
            config,
            archive_dir,
            args.gallery_per_type,
            args.queries_per_type,
            args.quality_status,
            rejections,
        )
    )
    output = args.output or config.data_root / "manifests" / "mixed_20_manifest.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Manifest: {output}")
    for split in ("gallery", "validation", "test"):
        print(f"{split}: {sum(row['split'] == split for row in rows)}")
    print(f"types: {len({row['species_name'] for row in rows})}")
    print(f"quality_status: {args.quality_status}")
    print(f"rejected_source_members: {sum(len(items) for items in rejections.values())}")


if __name__ == "__main__":
    main()
