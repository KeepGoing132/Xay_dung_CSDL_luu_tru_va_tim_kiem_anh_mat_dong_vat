from dataclasses import replace
from io import BytesIO
import csv

import pytest
from PIL import Image
from starlette.testclient import TestClient

from backend.src.config import BACKGROUND_BUNDLE_NAME, BACKGROUND_PREPROCESS_VERSION, AppConfig
from backend.src.errors import AppError
from backend.src.features import extract_features
from backend.src.ingestion import REQUIRED_COLUMNS
from backend.src.models import SearchRequest
from backend.src.preprocessing import preprocess_image
from backend.src.repository import Repository
from backend.src.search_service import SearchService
from backend.src.similarity import compare_features
from backend.src.models import Weights
from scripts.import_background_dataset import run_import
from backend import app as web


def cutout_bytes(color=(50, 100, 150)):
    image = Image.new("RGBA", (128, 128), (*color, 255))
    image.putpixel((0, 0), (*color, 0))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def background_config(config):
    return replace(config, db_path=config.data_root / "background_white.db",
                   bundle_name=BACKGROUND_BUNDLE_NAME, preprocess_version=BACKGROUND_PREPROCESS_VERSION)


def make_dataset(config, count=5):
    cutouts = config.data_root / "background_removed" / "test"
    rows = []
    for index in range(count):
        color = (30 + index * 20, 70, 100)
        original = config.data_root / "original" / "gallery" / f"{index}.png"
        original.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (128, 128), color).save(original)
        cutout = cutouts / "gallery" / f"{index}.png.png"
        cutout.parent.mkdir(parents=True, exist_ok=True)
        cutout.write_bytes(cutout_bytes(color))
        row = {column: "" for column in REQUIRED_COLUMNS}
        row.update(relative_path=config.relative_to_data(original), species_name="cat", split="gallery",
                   group_id=f"source-{index}", quality_status="approved")
        rows.append(row)
    source = config.data_root / "manifests" / "source.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(REQUIRED_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return source, cutouts, config.data_root / "manifests" / "background.csv"


def test_background_preprocessing_preserves_foreground_and_composites_white():
    processed = preprocess_image(cutout_bytes(), preprocess_version=BACKGROUND_PREPROCESS_VERSION)
    assert processed.rgb[0, 0].tolist() == [255, 255, 255]
    assert processed.rgb[50, 50].tolist() == [50, 100, 150]
    buffer = BytesIO()
    Image.new("RGB", (128, 128)).save(buffer, format="PNG")
    with pytest.raises(AppError, match="PNG"):
        preprocess_image(buffer.getvalue(), preprocess_version=BACKGROUND_PREPROCESS_VERSION)


def test_import_pending_review_then_approve_and_search_without_duplicates(app_config):
    config = background_config(app_config)
    source, cutouts, manifest = make_dataset(config)
    pending = run_import(config, source, cutouts, manifest)
    assert (pending["database_images"], pending["database_vectors"], pending["approved_candidates"]) == (5, 15, 0)
    approved = run_import(config, source, cutouts, manifest, reviewed=True)
    assert (approved["created"], approved["skipped"], approved["approved_candidates"]) == (0, 5, 5)
    assert not approved["acceptance_ready"]
    assert not app_config.db_path.exists()
    repository = Repository(config)
    response = SearchService(config, repository).search(
        SearchRequest(cutout_bytes(), bundle_name=config.bundle_name)
    )
    assert len({item.image_id for item in response.items}) == 5
    assert repository.get_search_items(response.query_id)[0]["rank"] == 1
    with repository.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM images").fetchone()[0] == 5
        assert connection.execute("SELECT COUNT(*) FROM image_features").fetchone()[0] == 15
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()


def test_incomplete_cutouts_fail_before_creating_database(app_config):
    config = background_config(app_config)
    source, cutouts, manifest = make_dataset(config)
    (cutouts / "gallery" / "0.png.png").unlink()
    with pytest.raises(ValueError, match="Missing"):
        run_import(config, source, cutouts, manifest)
    assert not config.db_path.exists() and not manifest.exists()


def test_baseline_database_and_source_manifest_are_protected(app_config):
    config = background_config(app_config)
    source, cutouts, manifest = make_dataset(config)
    with pytest.raises(ValueError, match="baseline"):
        run_import(replace(config, db_path=app_config.db_path), source, cutouts, manifest)
    with pytest.raises(ValueError, match="source manifest"):
        run_import(config, source, cutouts, source)


def test_config_ids_cannot_mix_baseline_and_background_features(app_config):
    baseline_repository = Repository(app_config)
    baseline_repository.create_schema()
    baseline_bundle = baseline_repository.ensure_baseline_bundle()
    background_repository = Repository(replace(background_config(app_config), db_path=app_config.db_path))
    background_bundle = background_repository.ensure_baseline_bundle()
    payload = cutout_bytes()
    baseline = extract_features(preprocess_image(payload), baseline_bundle)
    background = extract_features(preprocess_image(payload, preprocess_version=BACKGROUND_PREPROCESS_VERSION), background_bundle)
    assert set(baseline.config_ids.values()).isdisjoint(background.config_ids.values())
    with pytest.raises(AppError) as error:
        compare_features(baseline, background, Weights())
    assert error.value.code == "CONFIG_MISMATCH"


def test_background_profile_paths_and_unknown_profile():
    config = AppConfig.default(profile=BACKGROUND_BUNDLE_NAME)
    assert config.db_path.name == "background_white.db"
    assert config.default_manifest_path.name == "background_white_manifest.csv"
    with pytest.raises(ValueError):
        AppConfig.default(profile="invalid")


def test_background_http_uses_matching_profile_and_rejects_raw_query(app_config, monkeypatch):
    config = background_config(app_config)
    source, cutouts, manifest = make_dataset(config)
    run_import(config, source, cutouts, manifest, reviewed=True)
    repository = Repository(config)
    service = SearchService(config, repository)
    monkeypatch.setattr(web, "services", lambda: (config, repository, service))
    with TestClient(web.app) as client:
        assert "PNG đã tách nền" in client.get("/").text
        assert "background-white-v1" in client.get("/").text
        result = client.post("/api/search", files={"image": ("query.png", cutout_bytes(), "image/png")})
        assert result.status_code == 200
        assert len({r["image_id"] for r in result.json()["items"]}) == 5
        raw = Image.new("RGB", (128, 128))
        buffer = BytesIO()
        raw.save(buffer, format="PNG")
        invalid = client.post("/api/search", files={"image": ("raw.png", buffer.getvalue(), "image/png")})
        assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "BACKGROUND_REQUIRED"
