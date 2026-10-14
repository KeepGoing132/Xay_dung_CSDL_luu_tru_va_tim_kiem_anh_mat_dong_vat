from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig


AFHQ_URL = "https://www.dropbox.com/s/t9l9o3vsx2jai3z/afhq.zip?dl=1"
HF_FILES = (
    "https://huggingface.co/datasets/huggan/AFHQ/resolve/main/data/train-00000-of-00002.parquet?download=true",
    "https://huggingface.co/datasets/huggan/AFHQ/resolve/main/data/train-00001-of-00002.parquet?download=true",
)


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
        if partial.stat().st_size == 0:
            raise RuntimeError(f"Downloaded file is empty: {url}")
        partial.replace(destination)
        return
    existing = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": "animal-face-cbir/1.0"}
    if existing:
        headers["Range"] = f"bytes={existing}-"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        resumed = existing > 0 and response.status == 206
        mode = "ab" if resumed else "wb"
        if not resumed:
            existing = 0
        total_header = response.headers.get("Content-Length")
        expected = existing + int(total_header) if total_header else None
        downloaded = existing
        with partial.open(mode) as stream:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                stream.write(chunk)
                downloaded += len(chunk)
                if downloaded % (50 * 1024 * 1024) < len(chunk):
                    if expected:
                        print(f"{downloaded / 1024**2:.0f}/{expected / 1024**2:.0f} MiB")
                    else:
                        print(f"{downloaded / 1024**2:.0f} MiB")
    if expected is not None and downloaded != expected:
        raise RuntimeError(f"Download incomplete: expected {expected}, got {downloaded}")
    partial.replace(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tải AFHQ từ nguồn chính thức của StarGAN v2")
    parser.add_argument("--source", choices=["huggingface", "dropbox"], default="huggingface")
    parser.add_argument("--url", default=AFHQ_URL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = AppConfig.default()
    config.ensure_runtime_dirs()
    if args.source == "dropbox":
        output = args.output or config.data_root / "downloads" / "afhq.zip"
        if output.exists() and output.stat().st_size > 100_000_000:
            print(f"Archive đã tồn tại: {output} ({output.stat().st_size / 1024**2:.1f} MiB)")
            return
        download(args.url, output)
        print(f"Đã tải: {output} ({output.stat().st_size / 1024**2:.1f} MiB)")
        return

    output_dir = args.output or config.data_root / "downloads" / "afhq-huggingface"
    output_dir.mkdir(parents=True, exist_ok=True)
    for url in HF_FILES:
        filename = url.split("/")[-1].split("?", 1)[0]
        output = output_dir / filename
        if output.exists() and output.stat().st_size > 100_000_000:
            print(f"Shard đã tồn tại: {output} ({output.stat().st_size / 1024**2:.1f} MiB)")
            continue
        download(url, output)
        print(f"Đã tải: {output} ({output.stat().st_size / 1024**2:.1f} MiB)")


if __name__ == "__main__":
    main()
