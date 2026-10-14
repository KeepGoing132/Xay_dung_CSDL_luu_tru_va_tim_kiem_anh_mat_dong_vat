"""Compare default top-five retrievals without using labels as relevance judgments."""
from __future__ import annotations

import argparse
import base64
import csv
from hashlib import sha256
from html import escape
from io import BytesIO
import json
from pathlib import Path
import sys
from time import perf_counter

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig, default_weights_for
from backend.src.features import extract_features
from backend.src.ingestion import IngestionService
from backend.src.models import Weights
from backend.src.preprocessing import preprocess_image
from backend.src.repository import Repository
from backend.src.similarity import rank_candidates
from scripts.evaluate import validate_query_split, write_csv


def compare_profiles(configs, split, output):
    output.mkdir(parents=True, exist_ok=True)
    with configs[0].default_manifest_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = [r for r in csv.DictReader(stream) if r["split"] == split]
    engines, signatures = [], {}
    for config in configs:
        repo = Repository(config)
        bundle = repo.ensure_baseline_bundle()
        records = repo.audit_image_records()
        validate_query_split(rows, records)
        loaded = repo.load_candidates(bundle)
        if len(loaded.candidates) < 500 or loaded.rejected:
            raise ValueError(f"Invalid gallery for {config.bundle_name}")
        gallery = {r["image_id"]: r for r in records if r["split"] == "gallery"}
        weights = Weights.from_dict(default_weights_for(config.bundle_name))
        engines.append((config, bundle, loaded.candidates, gallery, weights))
        signatures[config.bundle_name] = {"config_signature": bundle.signature,
            "gallery_fingerprint": sha256(repr(repo.gallery_fingerprint(bundle)).encode()).hexdigest(),
            "weights": weights.as_dict()}
    galleries = [{row["original_path"]: row["original_sha256"] for row in e[3].values()} for e in engines]
    if any(gallery != galleries[0] for gallery in galleries[1:]):
        raise ValueError("Profile galleries are not the same source images")
    pictures = {}
    def thumbnail(relative):
        if relative not in pictures:
            with Image.open(configs[0].resolve_data_path(relative)) as image:
                image = image.convert("RGB"); image.thumbnail((160, 160))
                stream = BytesIO(); image.save(stream, format="JPEG", quality=85)
            pictures[relative] = "data:image/jpeg;base64," + base64.b64encode(stream.getvalue()).decode()
        return pictures[relative]
    results, sections, pool = [], [], {}
    for index, row in enumerate(rows, 1):
        panels = []
        for config, bundle, candidates, gallery, weights in engines:
            payload = config.resolve_data_path(row["relative_path"]).read_bytes()
            image = preprocess_image(payload, IngestionService._crop_from_row(row), preprocess_version=config.preprocess_version)
            if any(image.pixel_sha256 == g["processed_sha256"] or sha256(payload).hexdigest() == g["original_sha256"] for g in gallery.values()):
                raise ValueError(f"Query overlaps gallery: {row['relative_path']}")
            start = perf_counter()
            features = extract_features(image, bundle)
            items = rank_candidates(features, candidates, weights, 5)
            elapsed = (perf_counter()-start)*1000
            cards = []
            for item in items:
                path = gallery[item.image_id]["original_path"]
                # Use the source path as a stable ID across independent databases.
                key = (row["relative_path"], path)
                pool[key] = {"query_key": key[0], "image_id": key[1], "shape_grade": "", "color_grade": "",
                             "texture_grade": "", "rater": ""}
                results.append({"run_id": config.bundle_name, "query_key": row["relative_path"], "rank": item.rank,
                    "image_id": path, "database_image_id": item.image_id, "total": item.scores.total,
                    "scores_json": json.dumps(item.scores.as_dict()), "latency_ms": elapsed, "error": ""})
                cards.append(f'<figure><img src="{thumbnail(path)}" alt="Kết quả {item.rank}"><figcaption>#{item.rank}</figcaption></figure>')
            panels.append(f'<div><h3>{escape(config.bundle_name)}</h3><div class="results">{"".join(cards)}</div></div>')
        sections.append(f'<section><h2>Truy vấn {index}</h2><img class="query" src="{thumbnail(row["relative_path"])}" alt="Ảnh truy vấn">{"".join(panels)}</section>')
        if index % 10 == 0:
            print(f"Compared {index}/{len(rows)} {split} queries", flush=True)
    write_csv(output / f"results_{split}.csv", results)
    judgments = output / f"judgments_{split}.csv"
    if not judgments.exists():
        write_csv(judgments, list(pool.values()))
    (output / f"metadata_{split}.json").write_text(json.dumps({"split": split, "n_queries": len(rows),
        "n_pairs_to_judge": len(pool), "profiles": signatures, "labels_used": False,
        "timing_note": "extract+rank; gallery load, query IO/preprocess and preview excluded",
        "visual_p5": None, "note": "Unrated comparison, not proof of better visual retrieval."}, indent=2), encoding="utf-8")
    html = '<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
    html += '<title>Đối chiếu kết quả truy hồi</title><style>body{font:16px system-ui;max-width:1100px;margin:24px auto;padding:16px;background:#f5f6fa;color:#172038}section{background:white;padding:20px;margin:24px 0;border-radius:12px}h3{font-size:16px}.results{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}figure{margin:0}img{width:100%;aspect-ratio:1;object-fit:contain}.query{width:160px;border:3px solid #4968bf}figcaption{text-align:center}@media(max-width:600px){.results{gap:4px}section{padding:10px}}</style>'
    html += '<h1>Đối chiếu top 5 theo nội dung thị giác</h1><p>Cùng ảnh truy vấn và gallery; dùng trọng số mặc định của từng cấu hình. Không dùng nhãn loài để chấm điểm. Hãy xem màu sắc, đường nét và kết cấu; thứ tự ảnh là thứ tự truy hồi.</p><p>Đây là kết quả chưa được chấm. Điền bảng judgments tương ứng để tính Visual P@5. Không so trực tiếp trị số điểm giữa hai cấu hình.</p>'
    html += ''.join(sections) + '</html>'
    report = output / f"comparison_{split}.html"
    report.write_text(html, encoding="utf-8")
    print(report, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["validation", "test"], default="validation")
    args = parser.parse_args()
    config = AppConfig.default("refined512-v1")
    compare_profiles([config.for_profile("expanded512-v1"), config], args.split,
                     config.artifacts_root / "evaluation/refined512-v1")


if __name__ == "__main__":
    main()
