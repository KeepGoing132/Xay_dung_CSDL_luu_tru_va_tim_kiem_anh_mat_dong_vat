from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig, PROFILE_SETTINGS, default_weights_for
from backend.src.models import SearchRequest, Weights
from backend.src.repository import Repository
from backend.src.search_service import SearchService


def default_query(config: AppConfig) -> Path:
    manifest = config.default_manifest_path
    with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        row = next(row for row in csv.DictReader(stream) if row["split"] == "test")
    return config.resolve_data_path(row["relative_path"])


def make_sheet(config: AppConfig, query: Path, response, output: Path) -> None:
    tile = 180
    sheet = Image.new("RGB", (tile * 6, 230), "#07111f")
    font = ImageFont.load_default()
    draw = ImageDraw.Draw(sheet)
    images = [("QUERY", query, None)] + [
        (f"#{item.rank} ID {item.image_id}", config.resolve_data_path(item.processed_path), item.scores.total)
        for item in response.items
    ]
    for index, (label, path, score) in enumerate(images):
        image = Image.open(path).convert("RGB").resize((160, 160), Image.Resampling.LANCZOS)
        x = index * tile + 10
        sheet.paste(image, (x, 10))
        draw.text((x, 180), label, fill="white", font=font)
        if score is not None:
            draw.text((x, 198), f"score {score:.4f}", fill="#38bdf8", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy một truy vấn thật và xuất bằng chứng top 5")
    parser.add_argument("--query", type=Path)
    parser.add_argument("--weights", nargs=3, type=float, metavar=("HSV", "HOG", "LBP"), default=None)
    parser.add_argument("--profile", choices=list(PROFILE_SETTINGS))
    parser.add_argument("--weights-json", type=Path, help="JSON mapping or selected_weights.json")
    args = parser.parse_args()
    config = AppConfig.default(args.profile)
    repository = Repository(config)
    repository.create_schema()
    query = args.query or default_query(config)
    weights = Weights(*args.weights) if args.weights else Weights.from_dict(default_weights_for(config.bundle_name))
    if args.weights_json:
        supplied = json.loads(args.weights_json.read_text(encoding="utf-8"))
        weights = Weights.from_dict(supplied.get("weights", supplied))
    response = SearchService(config, repository).search(
        SearchRequest(query.read_bytes(), weights=weights, bundle_name=config.bundle_name)
    )
    output_dir = config.result_directory("demo")
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "query_id": response.query_id,
        "query": str(query),
        "candidate_count": response.candidate_count,
        "weights": response.effective_weights.as_dict(),
        "timings_ms": response.timings,
        "results": [
            {
                "rank": item.rank,
                "image_id": item.image_id,
                "species": item.species_name,
                "path": item.processed_path,
                "scores": {**item.scores.as_dict(), "total": item.scores.total},
            }
            for item in response.items
        ],
    }
    json_path = output_dir / "latest_search.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    sheet_path = output_dir / "latest_top5.jpg"
    make_sheet(config, query, response, sheet_path)
    print(json_path)
    print(sheet_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
