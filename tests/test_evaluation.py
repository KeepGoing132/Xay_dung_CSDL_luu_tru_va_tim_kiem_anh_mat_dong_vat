from dataclasses import replace

import pytest

from backend.src.config import EXPANDED512_BUNDLE_NAME
from backend.src.ingestion import IngestionService
from backend.src.models import Weights
from backend.src.repository import Repository
from scripts.evaluate import evaluate_runs, validate_query_split
from test_native512_processing import dataset
from scripts.score_judgments import visual_metrics


def test_evaluation_rejects_empty_split_and_leakage():
    with pytest.raises(ValueError, match="empty"):
        validate_query_split([], [])
    row = {"group_id": "same", "relative_path": "query.png", "quality_status": "approved"}
    record = {"group_id": "same", "original_path": "gallery.png", "split": "gallery"}
    with pytest.raises(ValueError, match="overlaps"):
        validate_query_split([row], [record])


def test_visual_metrics_use_grades_and_reject_unjudged_pairs():
    results = [{"run_id": "run", "query_key": "q", "rank": str(i), "image_id": str(i), "error": ""} for i in range(1, 6)]
    judgments = [{"query_key": "q", "image_id": str(i), "rater": "reviewer1", "shape_grade": "2" if i <= 3 else "0",
                  "color_grade": "1", "texture_grade": "1"} for i in range(1, 6)]
    report = visual_metrics(results, judgments)
    assert report["metrics"][0]["visual_p5_all"] == .6
    assert report["n_raters"] == 1
    with pytest.raises(ValueError, match="Missing judgments"):
        visual_metrics(results, judgments[:-1])


def test_evaluation_six_scores_and_failed_query_denominator(app_config):
    service, rows = dataset(app_config, 6)
    config = app_config.for_profile(EXPANDED512_BUNDLE_NAME)
    repo = Repository(config)
    repo.create_schema()
    assert IngestionService(config, repo).import_manifest(config.default_manifest_path).failed == 0
    bundle = repo.ensure_baseline_bundle()
    candidates = repo.load_candidates(bundle).candidates
    missing = {**rows[-1], "relative_path": "missing.png", "group_id": "missing"}
    per_query, metrics = evaluate_runs([rows[-1], missing], {"all": Weights.from_dict({key: 1 for key in bundle.configs})},
                                      config, bundle, candidates)
    assert len(per_query) == 6 and metrics[0]["n_failed"] == 1
    assert metrics[0]["mean_same_species_p5"] == 1
    assert metrics[0]["mean_all_known_p5"] == .5
    with pytest.raises(ValueError, match="overlap gallery"):
        evaluate_runs([rows[0]], {"hog": Weights(0, 1, 0)}, config, bundle, candidates,
                      {repo.audit_image_records()[0]["processed_sha256"]})
