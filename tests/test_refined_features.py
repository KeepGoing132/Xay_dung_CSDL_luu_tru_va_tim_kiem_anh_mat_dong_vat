from copy import deepcopy
from dataclasses import replace
import json

import numpy as np
import pytest
from PIL import Image
from starlette.testclient import TestClient

from backend import app as web
from backend.src.calibration import calibration_path, fit_calibration
from backend.src.config import AppConfig, REFINED512_BUNDLE_NAME, feature_specs_for
from backend.src.errors import AppError
from backend.src.features import extract_features, extract_hsv, extract_color_moments
from backend.src.ingestion import IngestionService
from backend.src.models import Weights
from backend.src.preprocessing import preprocess_image
from backend.src.refined_features import spatial_weights, weighted_glcm_matrix
from backend.src.repository import Repository
from backend.src.search_service import SearchService
from backend.src.similarity import calibrated_similarity, compare_features
from scripts.prepare_refined_profile import descriptor_bundle, prepare_calibration
from test_native512_processing import dataset, png


def specs_for(config):
    return feature_specs_for(REFINED512_BUNDLE_NAME, config.preprocess_version)


def test_runtime_default_is_refined_and_explicit_profiles_remain_available(monkeypatch):
    monkeypatch.delenv("CBIR_PROFILE", raising=False)
    assert AppConfig.default().bundle_name == REFINED512_BUNDLE_NAME
    monkeypatch.setenv("CBIR_PROFILE", "expanded512-v1")
    assert AppConfig.default().bundle_name == "expanded512-v1"
    assert AppConfig.default("native512-v1").bundle_name == "native512-v1"


def test_prior_reduces_corner_color_influence_without_removing_ears(app_config):
    config = app_config.for_profile(REFINED512_BUNDLE_NAME)
    parameters = specs_for(config)["hsv"]["parameters"]
    weights = spatial_weights((512, 512), parameters["spatial_prior"])
    assert weights.min() >= .15 and weights.max() <= 1
    assert weights[256, 256] > 6*weights[0, 0]
    image = np.full((512, 512, 3), 128, dtype=np.uint8)
    center, corner = image.copy(), image.copy()
    center[224:288, 224:288] = [255, 0, 0]
    corner[:64, :64] = [255, 0, 0]
    base = extract_hsv(image, parameters)
    center_distance = 1-np.minimum(base, extract_hsv(center, parameters)).sum()
    corner_distance = 1-np.minimum(base, extract_hsv(corner, parameters)).sum()
    assert center_distance > 4*corner_distance > 0


def test_weighted_glcm_matches_independent_pair_counts():
    gray = np.array([[0, 255, 0], [255, 255, 0]], dtype=np.uint8)
    weights = np.array([[1., 4., 9.], [1., 1., 1.]])
    params = {"levels": 2, "distances": [1], "angles_degrees": [0], "symmetric": True}
    matrix = weighted_glcm_matrix(gray, weights, params)[:, :, 0, 0]
    # Horizontal pairs: 0->1 mass2; 1->0 mass6; 1->1 mass1; 1->0 mass1.
    np.testing.assert_allclose(matrix, np.array([[0., 9.], [9., 2.]])/20)


def test_refined_constant_image_vectors_and_multiscale_dimensions(app_config):
    config = app_config.for_profile(REFINED512_BUNDLE_NAME)
    specs = specs_for(config)
    bundle = descriptor_bundle(config, specs)
    image = preprocess_image(png(Image.new("RGB", (512, 512), (128, 128, 128))), preprocess_version=config.preprocess_version)
    features = extract_features(image, bundle)
    assert {key: len(value) for key, value in features.vectors.items()} == {
        "hsv": 128, "hog": 9864, "lbp": 864, "spatial_hsv": 512, "color_moments": 36, "glcm": 40}
    assert sum(v.size for v in features.vectors.values()) == 11444
    assert np.count_nonzero(features.hog) == 0 and "zero_gradient" in features.warnings
    assert np.isclose(features.hsv.sum(), 1) and np.isclose(features.lbp.sum(), 1)
    assert np.isclose(features.extras["spatial_hsv"].sum(), 1)
    np.testing.assert_allclose(features.extras["glcm"][:16], 0)
    np.testing.assert_allclose(features.extras["glcm"][16:], 1)
    moments = extract_color_moments(image.rgb, specs["color_moments"]["parameters"])
    np.testing.assert_allclose(moments, np.tile([128/255, 0, .5], 12), atol=1e-6)


def test_calibration_is_deterministic_and_scales_median_distance_to_half():
    specs = {"hsv": {"dimension": 2, "parameters": {"similarity": {"metric": "intersection_exp", "scale": 1}}},
             "glcm": {"dimension": 2, "parameters": {"similarity": {"metric": "standardized_l1_exp", "scale": 1}}}}
    arrays = {"hsv": [[1., 0.], [.5, .5], [0., 1.]], "glcm": [[0., .2], [.2, .2], [.4, .2]]}
    a = fit_calibration(arrays, specs)
    assert a == fit_calibration(arrays, specs) and a["n_pairs"] == 3
    metric = a["metrics"]["hsv"]
    assert metric["scale"] == .5
    assert calibrated_similarity(np.array([1., 0.]), np.array([.5, .5]), metric) == pytest.approx(.5)
    assert calibrated_similarity(np.array([1., 0.]), np.array([1., 0.]), metric) == 1
    assert a["metrics"]["glcm"]["coordinate_scales"] == pytest.approx([.2, .02])


def test_calibrated_zero_hog_still_rejects_mismatched_dimensions():
    metric = {"metric": "cosine_exp", "scale": .2}
    assert calibrated_similarity(np.zeros(2), np.ones(2), metric) == 0
    with pytest.raises(AppError, match="CONFIG_MISMATCH"):
        calibrated_similarity(np.zeros(1), np.ones(2), metric)
    with pytest.raises(AppError, match="INVALID_VECTOR"):
        calibrated_similarity(np.zeros(2), np.array([np.nan, 1]), metric)


def test_refined_import_calibration_query_history_and_preview(app_config, monkeypatch):
    _, rows = dataset(app_config)
    config = app_config.for_profile(REFINED512_BUNDLE_NAME)
    artifact = prepare_calibration(config, rows, minimum_gallery=5)
    assert artifact["n_gallery"] == 5
    assert all("/gallery/" in row["path"] for row in artifact["source_records"])
    # Changing labels and non-gallery image pixels must not alter the frozen fit.
    relabeled = [{**row, "species_name": "anything"} for row in rows]
    query_path = config.resolve_data_path(rows[-1]["relative_path"])
    query = query_path.read_bytes()
    query_path.write_bytes(png(Image.new("RGB", (512, 512), "green")))
    assert prepare_calibration(config, relabeled, minimum_gallery=5) == artifact
    query_path.write_bytes(query)
    repo = Repository(config)
    repo.create_schema()
    summary = IngestionService(config, repo).import_rows(rows)
    assert summary.created == 6 and summary.failed == 0
    bundle = repo.ensure_baseline_bundle()
    loaded = repo.load_candidates(bundle)
    assert len(loaded.candidates) == 5 and not loaded.rejected
    service = SearchService(config, repo)
    monkeypatch.setattr(web, "services", lambda: (config, repo, service))
    with TestClient(web.app) as client:
        page = client.get("/")
        assert page.status_code == 200 and "6 đặc trưng cải tiến" in page.text
        result = client.post("/api/search", files={"image": ("q.png", query, "image/png")})
        assert result.status_code == 200, result.text
        body = result.json()
        assert len({item["image_id"] for item in body["items"]}) == 5
        assert body["query"]["dimensions"]["hog"] == 9864
        assert body["query"]["spatial_prior"].startswith("data:image/png")
        assert "R=1, 2, 3" in body["query"]["preview_notes"]["lbp"]
        for item in body["items"]:
            assert sum(item["contributions"].values()) == pytest.approx(item["scores"]["total"])
        history = client.get(f'/api/history/{body["query_id"]}').json()
        assert [r["scores"] for r in history["items"]] == [r["scores"] for r in body["items"]]
    reference = loaded.candidates[0].features
    with pytest.raises(AppError, match="CONFIG_MISMATCH"):
        compare_features(reference, replace(reference, config_signature="another-config"), Weights())
    # A changed gallery or algorithm cannot silently reuse the calibration.
    changed = deepcopy(rows); changed[0]["crop_size"] = "500"; changed[0]["crop_x"] = changed[0]["crop_y"] = "0"
    with pytest.raises(ValueError, match="Gallery changed"):
        prepare_calibration(config, changed, minimum_gallery=5)
    altered = deepcopy(artifact); altered["metrics"]["hsv"]["scale"] *= 2
    calibration_path(config).write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(AppError, match="CONFIG_CONFLICT"):
        repo.ensure_baseline_bundle()
    damaged = deepcopy(artifact); damaged["metrics"]["hsv"]["scale"] = 0
    calibration_path(config).write_text(json.dumps(damaged), encoding="utf-8")
    with pytest.raises(AppError, match="CONFIG_MISMATCH"):
        repo.ensure_baseline_bundle()


def test_refined_refuses_missing_calibration_before_registering_configs(app_config):
    config = app_config.for_profile(REFINED512_BUNDLE_NAME)
    repo = Repository(config); repo.create_schema()
    with pytest.raises(AppError, match="CONFIG_MISMATCH"):
        repo.ensure_baseline_bundle()
    assert repo.registered_configs() == []
