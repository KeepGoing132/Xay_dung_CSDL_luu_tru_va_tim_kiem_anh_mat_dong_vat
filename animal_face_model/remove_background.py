"""Remove backgrounds with the local model; preserve source images and native size."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys

from PIL import Image, ImageOps

MODEL_DIR = Path(__file__).resolve().parent
ROOT = MODEL_DIR.parent
sys.path.insert(0, str(ROOT))
from backend.src.cutouts import validate_cutout
MODEL_SHA256 = "5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT / "data").as_posix()
    except ValueError:
        return path.name


def create_session(threads: int):
    model = MODEL_DIR / "birefnet-general-lite.onnx"
    if not model.is_file():
        raise FileNotFoundError(f"Local model missing: {model}")
    checksum = sha256(model.read_bytes()).hexdigest()
    if checksum != MODEL_SHA256:
        raise ValueError(f"Model checksum mismatch: {model}")
    os.environ["U2NET_HOME"] = str(MODEL_DIR)
    os.environ["OMP_NUM_THREADS"] = str(threads)
    os.environ.pop("MODEL_CHECKSUM_DISABLED", None)
    from rembg import new_session

    return new_session("birefnet-general-lite", providers=["CPUExecutionProvider"])


def process_image(source: Path, destination: Path, session) -> dict:
    from rembg import remove

    source_bytes = source.read_bytes()
    with Image.open(source) as image:
        rgb = ImageOps.exif_transpose(image).convert("RGB")
    result = remove(rgb, session=session, putalpha=True)
    if result.mode != "RGBA" or result.size != rgb.size:
        raise ValueError("Unexpected output mode or dimensions")
    if result.convert("RGB").tobytes() != rgb.tobytes():
        raise ValueError("Foreground RGB was modified")
    alpha_min, alpha_max = result.getchannel("A").getextrema()
    if alpha_max == 0:
        raise ValueError("Empty foreground mask; review this image")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        result.save(stream, format="PNG")
    return {
        "source": display_path(source), "output": display_path(destination),
        "source_sha256": sha256(source_bytes).hexdigest(),
        "output_sha256": sha256(destination.read_bytes()).hexdigest(),
        "width": result.width, "height": result.height, "mode": result.mode,
        "alpha_range": [alpha_min, alpha_max],
        "warning": "no_background_removed" if alpha_min == 255 else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Image or directory (recursive)")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "background_removed")
    parser.add_argument("--limit", type=int, help="Process only the first N images")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--resume", action="store_true", help="Reuse existing cutouts only after source/mask validation")
    parser.add_argument("--progress-file", type=Path, help="Write structured progress for the local application")
    parser.add_argument("--manifest", type=Path, help="Process only original images listed by the project manifest")
    args = parser.parse_args()
    if args.threads < 1 or (args.limit is not None and args.limit < 1):
        parser.error("threads and limit must be positive")
    source_root = args.input.resolve()
    output_root = args.output.resolve()
    if not source_root.exists():
        parser.error(f"Input does not exist: {source_root}")
    for protected in (ROOT / "data" / "original", ROOT / "data" / "processed", ROOT / "data" / "queries"):
        if output_root == protected.resolve() or protected.resolve() in output_root.parents:
            parser.error("Output must be separate from the application's original/processed/query images")
    if source_root.is_dir() and (output_root == source_root or source_root in output_root.parents):
        parser.error("Output must be outside the input directory")
    sources = [source_root] if source_root.is_file() else sorted(
        path for path in source_root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if args.manifest:
        with args.manifest.open(encoding="utf-8-sig", newline="") as stream:
            sources = sorted((ROOT / "data" / row["relative_path"]).resolve() for row in csv.DictReader(stream))
        if any(not path.is_file() or source_root not in path.parents for path in sources):
            parser.error("Manifest contains a missing source or a path outside the input directory")
    if args.limit is not None:
        sources = sources[:args.limit]
    if not sources:
        parser.error("No images found")
    jobs = []
    for source in sources:
        relative = Path(source.name) if source_root.is_file() else source.relative_to(source_root)
        destination = output_root / relative.parent / (relative.name + ".png")
        if destination.exists() and not args.resume:
            parser.error(f"Output already exists; choose another directory: {destination}")
        if destination.exists():
            validate_cutout(source, destination)
        jobs.append((source, destination))
    session = None
    records, errors = [], []
    reused = 0
    for index, (source, destination) in enumerate(jobs, start=1):
        try:
            if destination.exists():
                validation = validate_cutout(source, destination)
                records.append({"source": display_path(source), "output": display_path(destination),
                                "source_sha256": sha256(source.read_bytes()).hexdigest(),
                                "output_sha256": sha256(destination.read_bytes()).hexdigest(),
                                "reused": True, **validation})
                reused += 1
            else:
                if session is None:
                    session = create_session(args.threads)
                records.append(process_image(source, destination, session))
                validate_cutout(source, destination)
            print(f"[{index}/{len(jobs)}] OK: {source.name}", flush=True)
        except Exception as exc:
            errors.append({"source": display_path(source), "output": display_path(destination),
                           "reason": f"{type(exc).__name__}: {exc}"})
            print(f"[{index}/{len(jobs)}] ERROR: {source}: {exc}", file=sys.stderr, flush=True)
        if args.progress_file:
            args.progress_file.parent.mkdir(parents=True, exist_ok=True)
            progress = {"completed": index, "total": len(jobs), "succeeded": index - len(errors),
                        "failed": len(errors), "source": source.relative_to(source_root).as_posix() if source_root.is_dir() else source.name,
                        "errors": errors}
            # Append events: Windows can refuse replacing a file while the UI reads it.
            with args.progress_file.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(progress, ensure_ascii=True) + "\n")
    output_root.mkdir(parents=True, exist_ok=True)
    report = {
        "model": "birefnet-general-lite", "model_sha256": MODEL_SHA256,
        "provider": "CPUExecutionProvider", "threads": args.threads,
        "rembg": version("rembg"), "onnxruntime": version("onnxruntime"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total": len(jobs), "succeeded": len(jobs) - len(errors), "failed": len(errors), "reused": reused,
        "images": records, "errors": errors,
    }
    report_path = output_root / ("processing-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".json")
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(f"Report: {report_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
