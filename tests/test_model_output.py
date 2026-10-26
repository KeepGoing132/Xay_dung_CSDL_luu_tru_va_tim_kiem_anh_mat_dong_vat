import sys
from types import SimpleNamespace

from PIL import Image
import pytest

from animal_face_model.remove_background import process_image
from backend.src.background_import import build_manifest
from test_four_pipeline import sources as dataset


def test_model_publishes_complete_png_without_replacing_existing_files(tmp_path, monkeypatch):
    source, destination = tmp_path / "source.png", tmp_path / "cutout.png"
    Image.new("RGB", (16, 16), (12, 34, 56)).save(source)
    original = source.read_bytes()
    def remove(rgb, **kwargs):
        image = rgb.convert("RGBA")
        image.putpixel((0, 0), (12, 34, 56, 0))
        return image
    monkeypatch.setitem(sys.modules, "rembg", SimpleNamespace(remove=remove))
    report = process_image(source, destination, object())
    with Image.open(destination) as image:
        image.load()
        assert image.mode == "RGBA" and image.size == (16, 16)
        assert image.convert("RGB").tobytes() == Image.open(source).tobytes()
    assert report["alpha_range"] == [0, 255]
    before = destination.read_bytes()
    with pytest.raises(FileExistsError):
        process_image(source, destination, object())
    assert destination.read_bytes() == before and source.read_bytes() == original
    assert not list(tmp_path.glob("*.part"))


def test_gallery_calibration_does_not_read_incomplete_query_masks(app_config):
    service, rows = dataset(app_config)
    service.cutout_path(rows[-1]).write_bytes(b"incomplete PNG being written")
    _, selected, missing = build_manifest(service.config, service.config.source_manifest_path,
                                          service.cutouts, source_splits={"gallery"})
    assert len(selected) == 5 and not missing
    assert all(row["split"] == "gallery" for row in selected)
    with pytest.raises(ValueError, match="Invalid cutout"):
        build_manifest(service.config, service.config.source_manifest_path, service.cutouts)


def test_codebook_and_calibration_keep_per_image_quality_and_ignore_test_masks(app_config, monkeypatch):
    import csv
    import backend.src.calibration_preparation as calibration
    import backend.src.dataset_preparation as preparation
    from scripts.prepare_dataset import prepare_codebook_only

    service, rows = dataset(app_config)
    service.cutout_path(rows[-1]).unlink()
    rows[-1]['split'] = 'test'
    rows[4]['group_id'] = rows[3]['group_id']
    rows[4]['quality_status'] = 'rejected'
    with app_config.source_manifest_path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    selected = []
    def codebook(config, specs, gallery, workers):
        selected.extend(gallery)
        return {'n_images_sampled': len(gallery), 'n_descriptors': 40, 'settings': {'clusters': 32}}
    monkeypatch.setattr(calibration, 'prepare_codebook', codebook)
    assert prepare_codebook_only(app_config)['gallery_rows'] == 4
    assert all(row['quality_status'] == 'approved' and row['split'] == 'gallery' for row in selected)
    def fit(config, masks, workers):
        assert workers == 4
        return masks
    monkeypatch.setattr(preparation, 'prepare_calibration', fit)
    masks = preparation.prepare_manifest_calibration(app_config)
    assert len(masks) == 5
    assert masks[3]['quality_status'] == 'approved'
    assert masks[4]['quality_status'] == 'rejected'


def test_fatal_provider_failure_stops_without_counting_pending_images_as_success(tmp_path, monkeypatch):
    import json
    import animal_face_model.remove_background as model
    source=tmp_path/'sources';source.mkdir()
    for name in ('a.png','b.png'):Image.new('RGB',(16,16),(12,34,56)).save(source/name)
    output=tmp_path/'masks';progress=tmp_path/'progress.jsonl'
    def fail(*args):raise RuntimeError('out of memory in provider')
    monkeypatch.setattr(model,'create_session',fail)
    monkeypatch.setattr(model,'version',lambda name:'test')
    monkeypatch.setitem(sys.modules,'onnxruntime',SimpleNamespace(__version__='test'))
    monkeypatch.setattr(sys,'argv',['remove_background.py','--input',str(source),'--output',str(output),
        '--provider','cpu','--progress-file',str(progress)])
    assert model.main()==1
    report=json.loads(next(output.glob('processing-*.json')).read_text(encoding='utf-8'))
    assert (report['succeeded'],report['failed'],report['pending'])==(0,1,1)
    assert report['fatal_provider_error'] and len(progress.read_text().splitlines())==1


def test_invalid_opaque_masks_are_failed_not_successful(tmp_path, monkeypatch):
    import json
    import animal_face_model.remove_background as model
    source=tmp_path/'sources';source.mkdir()
    for name in ('a.png','b.png'):Image.new('RGB',(16,16),(12,34,56)).save(source/name)
    output=tmp_path/'masks'
    monkeypatch.setattr(model,'create_session',lambda *args:object())
    monkeypatch.setattr(model,'version',lambda name:'test')
    monkeypatch.setitem(sys.modules,'onnxruntime',SimpleNamespace(__version__='test'))
    monkeypatch.setitem(sys.modules,'rembg',SimpleNamespace(remove=lambda rgb,**kwargs:rgb.convert('RGBA')))
    monkeypatch.setattr(sys,'argv',['remove_background.py','--input',str(source),'--output',str(output),'--provider','cpu'])
    assert model.main()==1
    report=json.loads(next(output.glob('processing-*.json')).read_text(encoding='utf-8'))
    assert (report['succeeded'],report['failed'],report['pending'])==(0,2,0)
