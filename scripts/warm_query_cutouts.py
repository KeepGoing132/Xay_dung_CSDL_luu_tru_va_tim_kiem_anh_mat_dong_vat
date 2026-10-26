"""Nạp trước cache mask cho ảnh truy vấn bằng đúng khoá cache của pipeline.

Mỗi lượt truy vấn lạ phải khởi động lại model tách nền một lần (nạp ONNX + tạo phiên
DirectML), nên đánh giá một bộ query mới rất chậm. Script này tính trước khoá cache
sha256(model + pipeline + pixel RGB sau tiền xử lý) cho từng dòng manifest, chạy model
một lần cho cả lô rồi ghi vào data/background_removed/queries/{pipeline}. Kết quả trùng
khớp với đường truy vấn thật vì cache có nội dung là khoá; lần chạy sau chỉ kiểm tra và
bỏ qua ảnh đã có.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import (AppConfig, BACKGROUND_MODEL_SHA256, OFFICIAL_QUERY_PIPELINE,
                                SOURCE_PREPROCESS_VERSION)
from backend.src.ingestion import IngestionService
from backend.src.preprocessing import encode_processed_png, preprocess_image

MODEL_PYTHON = Path("animal_face_model/.venv/Scripts/python.exe")
MODEL_SCRIPT = Path("animal_face_model/remove_background.py")


def query_cache_key(payload: bytes, crop) -> tuple[str, bytes]:
    source = preprocess_image(payload, crop, preprocess_version=SOURCE_PREPROCESS_VERSION)
    rgb_png = encode_processed_png(source)
    key = sha256((BACKGROUND_MODEL_SHA256 + OFFICIAL_QUERY_PIPELINE).encode() + rgb_png).hexdigest()
    return key, rgb_png


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, default=Path("tmp/query-warm"))
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    config = AppConfig.default()
    with args.manifest.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    cache = config.data_root / "background_removed" / "queries" / OFFICIAL_QUERY_PIPELINE
    cache.mkdir(parents=True, exist_ok=True)
    if args.work_dir.exists():
        shutil.rmtree(args.work_dir)
    inputs, outputs = args.work_dir / "inputs", args.work_dir / "outputs"
    inputs.mkdir(parents=True)
    outputs.mkdir(parents=True)
    pending = []
    for row in rows:
        payload = config.resolve_data_path(row["relative_path"]).read_bytes()
        crop = IngestionService._crop_from_row(row)
        key, rgb_png = query_cache_key(payload, crop)
        if (cache / f"{key}.png.png").is_file():
            continue
        (inputs / f"{key}.png").write_bytes(rgb_png)
        pending.append(key)
    print(f"manifest={len(rows)} cần nạp={len(pending)} đã có cache={len(rows) - len(pending)}", flush=True)
    if not pending:
        return
    if not MODEL_PYTHON.is_file() or not MODEL_SCRIPT.is_file():
        raise SystemExit("Thiếu môi trường model cục bộ (animal_face_model)")
    subprocess.run([str(MODEL_PYTHON), str(MODEL_SCRIPT), "--input", str(inputs), "--output", str(outputs),
                    "--provider", "directml", "--threads", str(args.threads)], check=True)
    copied = 0
    for key in pending:
        produced, target = outputs / f"{key}.png.png", cache / f"{key}.png.png"
        if produced.is_file() and not target.exists():
            shutil.copy2(produced, target)
            copied += 1
    print(f"đã ghi cache={copied} thiếu={len(pending) - copied}", flush=True)
    if copied != len(pending):
        raise SystemExit("Một số ảnh không tạo được mask; xem báo cáo trong thư mục outputs")


if __name__ == "__main__":
    main()
