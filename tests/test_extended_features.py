from dataclasses import replace
from hashlib import sha256
import csv
import json
import threading

import numpy as np
import pytest
from starlette.testclient import TestClient

from backend import app as web
from backend.src.config import EXPANDED512_BUNDLE_NAME, EXTRA_FEATURE_SPECS, default_weights_for
from backend.src.features import extract_color_moments, extract_features, extract_glcm, extract_hsv, extract_spatial_hsv
from backend.src.ingestion import IngestionService
from backend.src.models import SearchRequest, Weights
from backend.src.preprocessing import preprocess_image
from backend.src.repository import Repository
from backend.src.search_service import SearchService
from backend.src.similarity import compare_features
from test_native512_processing import dataset, png
from test_repository_search import insert_gallery, make_png
from PIL import Image


def test_spatial_color_distinguishes_equal_global_histograms():
    left = np.zeros((512, 512, 3), dtype=np.uint8)
    left[:256] = [255, 0, 0]
    left[256:] = [0, 0, 255]
    right = left[::-1].copy()
    assert np.array_equal(extract_hsv(left), extract_hsv(right))
    parameters = EXTRA_FEATURE_SPECS["spatial_hsv"]["parameters"]
    a, b = extract_spatial_hsv(left, parameters), extract_spatial_hsv(right, parameters)
    assert a.shape == (512,) and np.isclose(a.sum(), 1)
    assert np.minimum(a, b).sum() == 0


def test_constant_color_moments_have_independent_expected_values():
    rgb = np.full((512, 512, 3), [255, 0, 128], dtype=np.uint8)
    vector = extract_color_moments(rgb, EXTRA_FEATURE_SPECS["color_moments"]["parameters"])
    expected = np.tile([1, 0, .5, 0, 0, .5, 128 / 255, 0, .5], 4)
    np.testing.assert_allclose(vector, expected, atol=1e-5)


def test_constant_glcm_and_checkerboard_have_different_contrast():
    parameters = EXTRA_FEATURE_SPECS["glcm"]["parameters"]
    zero = extract_glcm(np.zeros((512, 512, 3), dtype=np.uint8), parameters)
    np.testing.assert_allclose(zero[:16], 0)
    np.testing.assert_allclose(zero[16:], 1)
    y, x = np.mgrid[:512, :512]
    rgb = np.repeat((((x + y) % 2) * 255).astype(np.uint8)[..., None], 3, axis=2)
    check = extract_glcm(rgb, parameters)
    assert check[0] == pytest.approx(1)
    assert check.shape == (48,) and np.isfinite(check).all()


def test_expanded_roundtrip_http_and_legacy_isolation(app_config, monkeypatch):
    source_service, _ = dataset(app_config)
    config = app_config.for_profile(EXPANDED512_BUNDLE_NAME)
    repo = Repository(config)
    repo.create_schema()
    imported = IngestionService(config, repo).import_manifest(config.default_manifest_path)
    assert imported.created == 6 and imported.failed == 0
    assert repo.dataset_integrity()["vector_count"] == 36
    bundle = repo.ensure_baseline_bundle()
    loaded = repo.load_candidates(bundle)
    assert len(loaded.candidates) == 5 and not loaded.rejected
    query = source_service.config.resolve_data_path(source_service.sources()[-1]["relative_path"]).read_bytes()
    features = extract_features(preprocess_image(query, preprocess_version=config.preprocess_version), bundle)
    assert sum(v.size for v in features.vectors.values()) == 35480
    weights = Weights.from_dict(default_weights_for(config.bundle_name))
    self_scores = compare_features(features, features, weights)
    assert self_scores.total == pytest.approx(1)
    native = Repository(config.for_profile("native512-v1"))
    native.create_schema()
    old = extract_features(preprocess_image(query, preprocess_version=config.preprocess_version), native.ensure_baseline_bundle())
    with pytest.raises(Exception, match="CONFIG_MISMATCH"):
        compare_features(features, old, weights)
    service = SearchService(config, repo)
    monkeypatch.setattr(web, "services", lambda: (config, repo, service))
    with TestClient(web.app) as client:
        page = client.get("/")
        assert page.status_code == 200 and 'id="glcm-weight"' in page.text
        assert "6 đặc trưng · 512×512" in page.text and "Xuất kết quả JSON" in page.text
        result = client.post("/api/search", files={"image": ("query.png", query, "image/png")})
        assert result.status_code == 200, result.text
        body = result.json()
        assert len(body["items"]) == len({row["image_id"] for row in body["items"]}) == 5
        for row in body["items"]:
            assert set(row["scores"]) == set(bundle.configs) | {"total"}
            assert sum(row["contributions"].values()) == pytest.approx(row["scores"]["total"])
        saved = client.get(f'/api/history/{body["query_id"]}').json()
        assert saved["items"][0]["scores"] == body["items"][0]["scores"]
        assert body["timings"]["request_ms"] >= body["timings"]["processing_ms"]
    again = IngestionService(config, repo).import_manifest(config.default_manifest_path)
    assert again.created == 0 and again.skipped == 6


@pytest.mark.parametrize("fault", ["missing", "corrupt", "different_pixels", "missing_vector"])
def test_gallery_health_and_search_reject_bad_inputs(app_config, monkeypatch, fault):
    repo = Repository(app_config)
    repo.create_schema()
    insert_gallery(repo, app_config, 5)
    path = app_config.resolve_data_path("processed/gallery/cat/0.png")
    if fault == "missing":
        path.rename(path.with_suffix(".hidden"))
    elif fault == "corrupt":
        path.write_bytes(b"broken png")
    elif fault == "different_pixels":
        Image.new("RGB", (128, 128), "red").save(path)
    else:
        with repo.connect() as connection:
            connection.execute("DELETE FROM image_features WHERE image_id=1 AND config_id=1")
            connection.commit()
    service = SearchService(app_config, repo)
    monkeypatch.setattr(web, "services", lambda: (app_config, repo, service))
    with TestClient(web.app) as client:
        stats = client.get("/api/dashboard").json()["stats"]
        assert stats["approved_gallery"] == 5 and stats["valid_candidates"] == 4
        assert not stats["gallery_ready"]
        assert stats["rejected_candidates"][0]["image_id"] == 1
        result = client.post("/api/search", files={"image": ("q.png", make_png((10, 20, 30)), "image/png")})
        assert result.status_code == 422 and result.json()["error"]["code"] == "INSUFFICIENT_GALLERY"
        assert result.json()["error"]["details"]["rejected"][0]["image_id"] == 1
    assert repo.dashboard_stats()["searches"] == 0


def test_limited_import_preserves_other_manifest_rows(app_config):
    service, _ = dataset(app_config, 6)
    first = service.run("extract_features", 1, lambda **_: None, threading.Event(), "first")
    assert first["import"]["created"] == first["import"]["total"] == 1
    all_rows = service.run("extract_features", None, lambda **_: None, threading.Event(), "all")
    assert all_rows["import"]["created"] == 5
    limited = service.run("extract_features", 1, lambda **_: None, threading.Event(), "limited")
    assert limited["import"]["total"] == limited["import"]["skipped"] == 1
    with service.config.default_manifest_path.open(encoding="utf-8-sig", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 6


def test_migration4_preserves_old_features_and_history(app_config):
    migration = app_config.migration_path.parent / "004_extended_features.sql"
    disabled = migration.with_suffix(".disabled")
    migration.rename(disabled)
    repo = Repository(app_config)
    repo.create_schema()
    insert_gallery(repo, app_config, 5)
    before_images = repo.audit_image_records()
    before_vectors = repo.audit_feature_records()
    with repo.connect() as connection:
        connection.execute("INSERT INTO search_queries(query_id,query_path,query_sha256,search_config_json,candidate_count,duration_ms,timings_json) VALUES (1,'query.png',?,'{}',5,0,'{}')", ("a" * 64,))
        connection.executemany("INSERT INTO search_results VALUES (1,?,?,.5,.5,.5,.5)", [(i, i) for i in range(1, 6)])
        connection.commit()
    disabled.rename(migration)
    repo.create_schema()
    repo.create_schema()
    assert repo.audit_image_records() == before_images
    assert repo.audit_feature_records() == before_vectors
    assert len(repo.get_search_items(1)) == 5
    assert repo.dataset_integrity()["foreign_key_errors"] == []
    with repo.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("SELECT extra_scores_json FROM search_results").fetchone()[0] == "{}"


def test_stale_or_invalid_validation_weights_are_explained(app_config):
    repo = Repository(app_config)
    repo.create_schema()
    bundle = repo.ensure_baseline_bundle()
    service = SearchService(app_config, repo)
    folder = app_config.result_directory("evaluation")
    folder.mkdir(parents=True)
    (folder / "selected_weights.json").write_text("[]", encoding="utf-8")
    presets, warning = service.weight_presets(bundle)
    assert len(presets) == 5 and "validation" in warning
