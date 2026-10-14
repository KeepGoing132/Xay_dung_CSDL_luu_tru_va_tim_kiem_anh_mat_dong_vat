from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig


DATASET_ID = "z3x59pv4bz"
DATASET_VERSION = 7
DATASET_PAGE = f"https://data.mendeley.com/datasets/{DATASET_ID}/{DATASET_VERSION}"
API_ROOT = "https://data.mendeley.com/public-api"
ACCEPT = "application/vnd.mendeley-public-dataset.1+json"
COMPACT_20_ARCHIVES = {
    "Ailurus fulgens.zip",
    "Cebus apella.zip",
    "Cebus olivaceus.zip",
    "Cercopithecus neglectus.zip",
    "Cercopithecus nictitans.zip",
    "Chlorocebus sabaeus.zip",
    "Erythrocebus patas.zip",
    "Lemur catta.zip",
    "Macaca fascicularis.zip",
    "Macaca thibetana.zip",
    "Mandrillus sphinx.zip",
    "mongooses.zip",
    "Nomascus leucogenys.zip",
    "Pan troglodytes.zip",
    "Panthera leo.zip",
    "Panthera tigris.zip",
    "Papio anubis.zip",
    "Saimiri sciureus.zip",
}


def read_json(url: str) -> dict:
    request = Request(url, headers={"Accept": ACCEPT, "User-Agent": "animal-face-cbir/1.0"})
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def list_face_archives() -> list[dict]:
    folder_payload = read_json(f"{API_ROOT}/datasets/{DATASET_ID}/folders/{DATASET_VERSION}")
    folders = folder_payload if isinstance(folder_payload, list) else folder_payload["value"]
    face_folder = next((item for item in folders if item["name"].casefold() == "face images"), None)
    if face_folder is None:
        raise RuntimeError("AFD không còn thư mục 'face images' ở endpoint công khai")
    query = urlencode(
        {
            "folder_id": face_folder["id"],
            "version": DATASET_VERSION,
            "$start": 0,
            "$limit": 1000,
        }
    )
    file_payload = read_json(f"{API_ROOT}/datasets/{DATASET_ID}/files?{query}")
    files = file_payload if isinstance(file_payload, list) else file_payload["value"]
    return sorted(
        (item for item in files if item["filename"].casefold().endswith(".zip")),
        key=lambda item: item["filename"].casefold(),
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if curl:
        subprocess.run(
            [
                curl,
                "--location",
                "--fail",
                "--retry",
                "5",
                "--continue-at",
                "-",
                "--output",
                str(partial),
                url,
            ],
            check=True,
        )
    else:
        request = Request(url, headers={"User-Agent": "animal-face-cbir/1.0"})
        with urlopen(request, timeout=120) as response, partial.open("wb") as stream:
            shutil.copyfileobj(response, stream, length=1024 * 1024)
    if not partial.is_file() or partial.stat().st_size == 0:
        raise RuntimeError(f"Tệp tải về rỗng: {url}")
    partial.replace(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tải các gói ảnh khuôn mặt AFD từ Mendeley Data")
    parser.add_argument(
        "--archive",
        action="append",
        help="Tên gói không phân biệt hoa thường; có thể lặp lại. Bỏ qua để tải tất cả.",
    )
    parser.add_argument(
        "--snapshot",
        choices=["compact-20", "all"],
        default="all",
        help="compact-20 gồm 18 loại AFD để ghép với cat/dog thành đúng 20 loại.",
    )
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    config = AppConfig.default()
    output_dir = args.output or config.data_root / "downloads" / "afd"
    archives = list_face_archives()
    requested = {name.casefold() for name in args.archive or []}
    if not requested and args.snapshot == "compact-20":
        requested = {name.casefold() for name in COMPACT_20_ARCHIVES}
    if requested:
        archives = [item for item in archives if item["filename"].casefold() in requested]
        found = {item["filename"].casefold() for item in archives}
        missing = sorted(requested - found)
        if missing:
            raise ValueError(f"Không tìm thấy gói AFD: {', '.join(missing)}")

    total_bytes = sum(int(item["content_details"]["size"]) for item in archives)
    print(f"AFD archives={len(archives)} total={total_bytes / 1024**2:.1f} MiB source={DATASET_PAGE}")
    for item in archives:
        detail = item["content_details"]
        print(f"- {item['filename']}: {int(detail['size']) / 1024**2:.1f} MiB")
        if args.list_only:
            continue
        destination = output_dir / item["filename"]
        expected_hash = detail["sha256_hash"].casefold()
        if destination.is_file() and sha256(destination) == expected_hash:
            print(f"  đã có, SHA-256 hợp lệ: {destination}")
            continue
        download(detail["download_url"], destination)
        actual_hash = sha256(destination)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"SHA-256 sai cho {destination.name}: expected={expected_hash}, actual={actual_hash}"
            )
        print(f"  đã tải và kiểm tra SHA-256: {destination}")


if __name__ == "__main__":
    main()
