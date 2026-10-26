"""Evaluation orchestration without running the background model or a full gallery."""
import csv
import json
from types import SimpleNamespace

import pytest

from backend.src.calibration_preparation import descriptor_bundle
from backend.src.config import feature_specs_for
from backend.src.models import Weights
from backend.src.processing_service import DatasetProcessingService
from scripts import evaluate


@pytest.fixture
def evaluation_cli(app_config, monkeypatch):
    rows = [dict(relative_path=f'{split}.png', group_id=split, split=split,
                 species_name='cat', quality_status='approved') for split in ('validation', 'test')]
    with app_config.source_manifest_path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    bundle = descriptor_bundle(app_config, feature_specs_for(app_config.bundle_name))
    repository = SimpleNamespace(create_schema=lambda: None, ensure_bundle=lambda: bundle,
        load_candidates=lambda bundle: SimpleNamespace(candidates=[object()] * 500, rejected=[]),
        audit_image_records=lambda: [], gallery_fingerprint=lambda bundle: ('frozen-gallery',))
    monkeypatch.setattr(evaluate.AppConfig, 'default', lambda profile=None: app_config)
    monkeypatch.setattr(evaluate, 'Repository', lambda config: repository)
    calls = []
    def run(rows, runs, *args):
        calls.append((rows, runs))
        results = [dict(query_key=rows[0]['relative_path'], image_id=1)]
        metrics = [dict(run_id=key, mean_all_known_p5=.6, n_failed=0,
                        weights=json.dumps(weights.as_dict())) for key, weights in runs.items()]
        return results, metrics
    monkeypatch.setattr(evaluate, 'evaluate_runs', run)
    return app_config.result_directory('evaluation'), calls


def test_test_split_runs_fixed_weights_without_validation_selection(evaluation_cli, monkeypatch):
    output, calls = evaluation_cli
    monkeypatch.setattr('sys.argv', ['evaluate.py'])
    evaluate.main()
    assert calls[0][0][0]['split'] == 'test'
    assert {'ALL4_DEFAULT', 'ALL4_EQUAL'} <= set(calls[0][1])
    assert {f'ONLY_{key.upper()}' for key in feature_specs_for()} <= set(calls[0][1])
    assert not (output / 'selected_weights.json').exists()
    assert (output / 'metrics_test.csv').is_file()


def test_selected_weights_require_validation_and_matching_dataset(evaluation_cli, monkeypatch):
    output, calls = evaluation_cli
    monkeypatch.setattr('sys.argv', ['evaluate.py', '--split', 'test', '--use-selected-weights'])
    with pytest.raises(ValueError, match='validation first'):
        evaluate.main()
    monkeypatch.setattr('sys.argv', ['evaluate.py', '--split', 'validation'])
    evaluate.main()
    monkeypatch.setattr('sys.argv', ['evaluate.py', '--split', 'test', '--use-selected-weights'])
    evaluate.main()
    assert 'E_SELECTED' in calls[-1][1]
    path = output / 'selected_weights.json'
    selected = json.loads(path.read_text())
    selected['signature']['manifest_sha256'] = 'changed'
    path.write_text(json.dumps(selected))
    with pytest.raises(ValueError, match='another dataset/configuration'):
        evaluate.main()


def test_queries_sharing_a_group_read_their_own_source(app_config, monkeypatch):
    service = DatasetProcessingService(app_config)
    rows = [dict(relative_path=f'dataset512-left/images512/cat/{index}.png', group_id='same-session',
                 split='test', species_name='cat', quality_status='approved') for index in range(2)]
    for index, row in enumerate(rows):
        path = app_config.resolve_data_path(row['relative_path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes([index]))
    with app_config.source_manifest_path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    payloads = []
    def segment(self, payload, crop):
        payloads.append(payload)
        return payload
    monkeypatch.setattr(DatasetProcessingService, 'query_cutout', segment)
    monkeypatch.setattr(evaluate, 'preprocess_image', lambda *args, **kwargs: SimpleNamespace(pixel_sha256='query'))
    monkeypatch.setattr(evaluate, 'extract_features', lambda *args: None)
    monkeypatch.setattr(evaluate, 'rank_scored_candidates', lambda *args: [])
    # Also accept a custom manifest using a mask path, with exact per-image lookup.
    queries = [rows[0], {**rows[1], 'relative_path': app_config.relative_to_data(service.cutout_path(rows[1]))}]
    _, metrics = evaluate.evaluate_runs(queries, {'fixed': Weights()}, app_config, None, [])
    assert payloads == [b'\x00', b'\x01']
    assert metrics[0]['n_failed'] == 0


def test_weight_override_parser_builds_variants_and_rejects_bad_specs():
    weights = {'hog': .4, 'rootsift_vlad': .2, 'spatial_hsv': .15, 'gabor': .1}
    variants = evaluate.parse_weight_overrides('GABOR005:gabor=0.05;gabor010:gabor=0.1,hog=0.4', weights)
    assert set(variants) == {'GABOR005', 'GABOR010'}
    assert variants['GABOR005'].as_dict() == {**weights, 'gabor': .05}
    assert variants['GABOR010'].as_dict()['hog'] == .4
    for spec in ('GABOR005 gabor=0.05', 'GABOR005:khong_co=1', 'GABOR005:gabor=abc',
                 'GABOR005:gabor=0.05;GABOR005:gabor=0.1', ''):
        with pytest.raises(ValueError):
            evaluate.parse_weight_overrides(spec, weights)


def test_weight_override_runs_are_diagnostic_only(evaluation_cli, monkeypatch):
    output, calls = evaluation_cli
    monkeypatch.setattr('sys.argv', ['evaluate.py', '--split', 'test',
                                     '--weight-overrides', 'GABOR005:gabor=0.05'])
    evaluate.main()
    assert 'GABOR005' in calls[0][1]
    assert calls[0][1]['GABOR005'].as_dict()['gabor'] == 0.05
    # Biến thể quét trọng số không được tự chọn làm trọng số đã chọn.
    monkeypatch.setattr('sys.argv', ['evaluate.py', '--split', 'validation',
                                     '--weight-overrides', 'GABOR005:gabor=0.05'])
    evaluate.main()
    selected = json.loads((output / 'selected_weights.json').read_text())
    assert selected['selected_from'] != 'GABOR005'
