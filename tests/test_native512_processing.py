from dataclasses import replace
from io import BytesIO
import csv
import json
import threading

import numpy as np
from PIL import Image
import pytest
from starlette.testclient import TestClient

from backend import app as web
from backend.src.background_import import run_import
from backend.src.config import NATIVE512_BUNDLE_NAME, BACKGROUND512_BUNDLE_NAME
from backend.src.errors import AppError
from backend.src.features import extract_features, extract_lbp
from backend.src.ingestion import IngestionService, REQUIRED_COLUMNS
from backend.src.models import SearchRequest, Weights
from backend.src.preprocessing import preprocess_image
from backend.src.processing_service import DatasetProcessingService, ProcessingJobs, ProcessingCancelled, read_model_progress
from backend.src.repository import Repository
from backend.src.search_service import SearchService
from backend.src.similarity import compare_features


def png(image):
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def dataset(config, count=6):
    service = DatasetProcessingService(config)
    rows = []
    for index in range(count):
        y, x = np.mgrid[:512, :512]
        rgb = np.stack(((x + index * 23) % 256, (y + index * 17) % 256,
                        ((x // 4 + y // 4) * 9 + index * 13) % 256), axis=-1).astype(np.uint8)
        split = "gallery" if index < 5 else "test"
        relative = f"original/{split}/cat/{index}.png"
        source = config.resolve_data_path(relative)
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(png(Image.fromarray(rgb)))
        rgba = Image.fromarray(rgb).convert("RGBA")
        alpha = np.where((x - 256) ** 2 + (y - 256) ** 2 < 230 ** 2, 255, 0).astype(np.uint8)
        rgba.putalpha(Image.fromarray(alpha))
        row = {field: "" for field in REQUIRED_COLUMNS}
        row.update(relative_path=relative, species_name="cat", split=split, group_id=f"g{index}", quality_status="approved")
        destination = service.cutout_path(row)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(png(rgba))
        rows.append(row)
    manifest = service.original_config.default_manifest_path
    with manifest.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(REQUIRED_COLUMNS))
        writer.writeheader(); writer.writerows(rows)
    return service, rows


def test_native512_retains_pixels_and_separates_config_ids(app_config):
    repository = Repository(app_config)
    repository.create_schema()
    baseline = repository.ensure_baseline_bundle()
    config = app_config.for_profile(NATIVE512_BUNDLE_NAME)
    native_repository = Repository(replace(config, db_path=app_config.db_path))
    native = native_repository.ensure_baseline_bundle()
    rgb = np.random.default_rng(8).integers(0, 256, (512, 512, 3), dtype=np.uint8)
    payload = png(Image.fromarray(rgb))
    image = preprocess_image(payload, preprocess_version=config.preprocess_version)
    assert np.array_equal(image.rgb, rgb)
    features = extract_features(image, native)
    assert (features.hsv.size, features.hog.size, features.lbp.size) == (128, 34596, 160)
    assert np.isclose(np.linalg.norm(features.hog), 1)
    assert set(native.config_ids.values()).isdisjoint(baseline.config_ids.values())
    assert native.hog.parameters["input_size"] == [512, 512]
    old = extract_features(preprocess_image(payload), baseline)
    with pytest.raises(AppError) as error:
        compare_features(features, old, Weights())
    assert error.value.code == "CONFIG_MISMATCH"


def test_model_progress_reader_ignores_partial_append(tmp_path):
    path = tmp_path / "progress.jsonl"
    path.write_text('{"completed": 1}\n{"completed":', encoding="utf-8")
    assert read_model_progress(path) == {"completed": 1}
    path.write_text('{"completed": 1}\n{"completed": 2}\n', encoding="utf-8")
    assert read_model_progress(path) == {"completed": 2}


def test_lbp_uses_bottom_of_512_image():
    plain = np.full((512, 512, 3), 128, np.uint8)
    changed = plain.copy()
    changed[384:, 384:] = np.random.default_rng(2).integers(0, 256, (128, 128, 3), dtype=np.uint8)
    left, right = extract_lbp(plain).reshape(16, 10), extract_lbp(changed).reshape(16, 10)
    assert np.allclose(right.sum(axis=1), 1 / 16)
    assert np.array_equal(left[0], right[0])
    assert not np.array_equal(left[-1], right[-1])


def test_separate_databases_with_same_numeric_ids_cannot_mix_preprocessing(app_config):
    service, rows = dataset(app_config, 1)
    left = Repository(service.original_config); left.create_schema()
    right = Repository(service.config); right.create_schema()
    left_bundle, right_bundle = left.ensure_baseline_bundle(), right.ensure_baseline_bundle()
    assert left_bundle.config_ids == right_bundle.config_ids
    raw = service.original_config.resolve_data_path(rows[0]["relative_path"]).read_bytes()
    mask = service.cutout_path(rows[0]).read_bytes()
    a = extract_features(preprocess_image(raw, preprocess_version=left_bundle.preprocess_version), left_bundle)
    b = extract_features(preprocess_image(mask, preprocess_version=right_bundle.preprocess_version), right_bundle)
    with pytest.raises(AppError) as error:
        compare_features(a, b, Weights())
    assert error.value.code == "CONFIG_MISMATCH"


def test_native_import_reuses_source_without_duplicate_png(app_config):
    service, rows = dataset(app_config, 2)
    config = service.original_config
    repository = Repository(config); repository.create_schema()
    counts = []
    result = IngestionService(config, repository).import_manifest(config.default_manifest_path,
                                                                 progress=lambda *args: counts.append(args))
    assert result.created == 2 and not result.failed
    assert counts[-1][:2] == (2, 2)
    records = repository.audit_image_records()
    assert all(row["width"] == row["height"] == 512 for row in records)
    assert all(row["processed_path"] == row["original_path"] for row in records)
    assert not list((config.data_root / "processed" / config.bundle_name).rglob("*.png"))


def test_background512_review_import_and_search_are_consistent(app_config):
    service, rows = dataset(app_config)
    config = service.config
    imported = run_import(config, service.original_config.default_manifest_path, service.cutouts, config.default_manifest_path)
    assert (imported["created"], imported["database_vectors"], imported["approved_candidates"]) == (6, 18, 0)
    service.review(list(range(5)), "approved")
    repeated = run_import(config, service.original_config.default_manifest_path, service.cutouts, config.default_manifest_path)
    assert repeated["created"] == 0 and repeated["skipped"] == 6 and repeated["approved_candidates"] == 5
    repository = Repository(config)
    response = SearchService(config, repository).search(SearchRequest(service.cutout_path(rows[-1]).read_bytes(), bundle_name=config.bundle_name))
    assert response.processed_query.rgb.shape == (512, 512, 3)
    assert len(set(item.image_id for item in response.items)) == 5
    assert all(response.items[index].scores.total >= response.items[index + 1].scores.total for index in range(4))
    stored = repository.audit_image_records()
    assert all(row["width"] == row["height"] == 512 for row in stored)
    assert repository.dataset_integrity()["integrity"] == "ok"
    with config.default_manifest_path.open(encoding="utf-8-sig", newline="") as stream:
        assert sum(row["quality_status"] == "approved" for row in csv.DictReader(stream)) == 5
    service.review([0], "rejected")
    assert len(repository.load_candidates(repository.ensure_baseline_bundle()).candidates) == 4


def test_review_rejects_unimported_or_invalid_ids_without_partial_change(app_config):
    service, _ = dataset(app_config, 2)
    with pytest.raises(ValueError, match="before"):
        service.review([0], "approved")
    run_import(service.config, service.original_config.default_manifest_path, service.cutouts, service.config.default_manifest_path)
    with pytest.raises(ValueError):
        service.review([0, 999], "approved")
    assert all(row["quality_status"] == "pending" for row in Repository(service.config).audit_image_records())


def test_corrected_mask_keeps_history_input_and_replaces_one_active_version(app_config):
    service, rows = dataset(app_config)
    config = service.config
    run_import(config, service.original_config.default_manifest_path, service.cutouts, config.default_manifest_path, reviewed=True)
    repository = Repository(config)
    old = repository.audit_image_records()[0]
    immutable = config.resolve_data_path(old["original_path"]).read_bytes()
    previous_preview = service.catalog()["items"][0]["mask_url"]
    cutout = service.cutout_path(rows[0])
    with Image.open(cutout) as source:
        corrected = source.copy()
    r, g, b, alpha = corrected.getpixel((256, 256))
    corrected.putpixel((256, 256), (r, g, b, 128))
    cutout.write_bytes(png(corrected))
    assert service.catalog()["items"][0]["quality_status"] == "not_imported"
    assert service.catalog()["items"][0]["mask_url"] != previous_preview
    report = run_import(config, service.original_config.default_manifest_path, service.cutouts, config.default_manifest_path)
    assert (report["created"], report["skipped"], report["approved_candidates"]) == (1, 5, 4)
    assert config.resolve_data_path(old["original_path"]).read_bytes() == immutable
    versions = [row for row in repository.audit_image_records() if row["group_id"] == rows[0]["group_id"]]
    assert len(versions) == 2 and sum(row["active"] for row in versions) == 1
    service.review([0], "approved")
    assert len(repository.load_candidates(repository.ensure_baseline_bundle()).candidates) == 5


def test_processing_api_starts_once_cancels_and_rejects_unsafe_requests(app_config, monkeypatch):
    service, _ = dataset(app_config, 1)
    jobs = ProcessingJobs(service)
    entered = threading.Event()
    def slow_job(action, limit, update, cancelled, job_id):
        entered.set()
        if cancelled.wait(5):
            raise ProcessingCancelled()
        raise AssertionError("Job should have been cancelled")
    monkeypatch.setattr(service, "run", slow_job)
    monkeypatch.setattr(web, "processing_jobs", lambda: jobs)
    with TestClient(web.app) as client:
        assert client.get("/api/processing?offset=-1").status_code == 422
        assert client.post("/api/processing", json={"action": "pipeline", "limit": -1}).status_code == 422
        assert client.get("/api/processing/preview/0/original").status_code == 200
        assert client.get("/api/processing/preview/0/secret").status_code == 422
        assert client.post("/api/processing", json={"action": "pipeline", "limit": 1}).status_code == 202
        assert entered.wait(2)
        assert client.post("/api/processing", json={"action": "pipeline"}).status_code == 409
        assert client.post("/api/processing/review", json={"source_ids": [0], "quality_status": "approved"}).status_code == 409
        assert client.post("/api/processing/cancel", json={}).status_code == 200
    jobs._worker.join(timeout=3)
    assert jobs.latest()["status"] == "cancelled"
    assert ProcessingJobs(service).latest()["status"] == "cancelled"


def test_background512_http_auto_segments_raw_query_and_keeps_profile(app_config, monkeypatch):
    service, rows = dataset(app_config)
    run_import(service.config, service.original_config.default_manifest_path, service.cutouts, service.config.default_manifest_path, reviewed=True)
    repository = Repository(service.config)
    search = SearchService(service.config, repository)
    monkeypatch.setattr(web, "services_for_profile", lambda profile: (service.config, repository, search))
    cutout = service.cutout_path(rows[-1]).read_bytes()
    calls = []
    def segment(payload, crop):
        calls.append(payload)
        return cutout
    monkeypatch.setattr(service, "query_cutout", segment)
    monkeypatch.setattr(web, "processing_jobs", lambda: ProcessingJobs(service))
    with TestClient(web.app) as client:
        url = "/api/search?profile=background512-white-v1"
        raw = service.config.resolve_data_path(rows[-1]["relative_path"]).read_bytes()
        result = client.post(url, files={"image": ("raw.png", raw, "image/png")})
        assert result.status_code == 200, result.text
        assert len(calls) == 1
        assert result.json()["query"]["dimensions"] == {"hsv": 128, "hog": 34596, "lbp": 160}
        with Image.open(BytesIO(__import__('base64').b64decode(result.json()["query"]["rgb"].split(',')[1]))) as image:
            assert image.size == (512, 512)
        ready = client.post(url, files={"image": ("cutout.png", cutout, "image/png")})
        assert ready.status_code == 200 and len(calls) == 1
        assert [row["image_id"] for row in result.json()["items"]] == [row["image_id"] for row in ready.json()["items"]]
