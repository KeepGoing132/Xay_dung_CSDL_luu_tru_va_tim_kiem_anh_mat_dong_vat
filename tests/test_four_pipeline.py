from io import BytesIO
import csv
import json
from pathlib import Path
import sqlite3

import numpy as np
from PIL import Image
import pytest
from starlette.testclient import TestClient

from backend.src.calibration_preparation import descriptor_bundle, prepare_calibration
from backend.src.codebook import codebook_path, with_codebook_specs
from backend.src.config import AppConfig, BUNDLE_NAME, DEFAULT_BUNDLE_NAME, OFFICIAL_BUNDLE_NAME, OFFICIAL_DIMENSIONS, FEATURE_KEYS, SOURCE_PREPROCESS_VERSION, feature_specs_for, default_weights_for
from backend.src.errors import AppError
from backend.src.features import extract_features
from backend.src.ingestion import IngestionService
from backend.src.models import CropBox, FeatureBundle, Candidate, SearchRequest, Weights
from backend.src.preprocessing import preprocess_image
from backend.src.processing_service import DatasetProcessingService, ProcessingJobs
from backend.src.repository import Repository
from backend.src.search_service import SearchService
from backend.src.similarity import normalize_weights, compare_features, rank_candidates


def png(image):
    stream = BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


def sources(config, count=6):
    fields = ['relative_path','species_name','source_url','license_note','split','group_id',
              'crop_x','crop_y','crop_size','quality_status','review_note']
    rows = []
    service = DatasetProcessingService(config)
    for index in range(count):
        relative = f'dataset512-left/images512/cat/{index}.png'
        image = Image.fromarray(np.random.default_rng(index).integers(0,256,(512,512,3),dtype=np.uint8))
        path = config.resolve_data_path(relative)
        path.parent.mkdir(parents=True,exist_ok=True)
        image.save(path)
        row = dict.fromkeys(fields,'')
        row.update(relative_path=relative,species_name='cat',source_url='https://example.invalid/source',
                   license_note='synthetic fixture',split='gallery' if index < 5 else 'validation',
                   group_id=f'synthetic-{index}',quality_status='approved')
        mask = image.convert('RGBA')
        alpha = np.full((512,512),255,dtype=np.uint8); alpha[:30]=0
        mask.putalpha(Image.fromarray(alpha))
        target = service.cutout_path(row);target.parent.mkdir(parents=True,exist_ok=True);mask.save(target)
        rows.append(row)
    with config.source_manifest_path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    return service,rows


@pytest.fixture
def ready(app_config):
    service, rows = sources(app_config)
    masks=[{**row,'relative_path':app_config.relative_to_data(service.cutout_path(row))} for row in rows]
    prepare_calibration(app_config,masks,minimum_gallery=5)
    repo=Repository(app_config);repo.create_schema()
    summary=IngestionService(app_config,repo).import_rows(masks)
    assert summary.failed == 0,summary.errors
    return service,rows,masks,repo


def test_only_four_configuration_and_weights():
    config=AppConfig.default()
    assert config.bundle_name==OFFICIAL_BUNDLE_NAME==DEFAULT_BUNDLE_NAME=='foreground4-hogpca512-v1'
    assert config.db_path.name=='foreground4_hogpca512.db'
    specs=feature_specs_for()
    assert set(specs)==set(FEATURE_KEYS)=={'hog','spatial_hsv','rootsift_vlad','gabor'}
    assert sum(s['dimension'] for s in specs.values())==OFFICIAL_DIMENSIONS==5216
    assert specs['hog']['dimension']==512 and specs['hog']['parameters']['signed_values']
    baseline=AppConfig.default(BUNDLE_NAME)
    assert baseline.db_path.name=='foreground4.db'
    assert sum(s['dimension'] for s in feature_specs_for(BUNDLE_NAME).values())==14568
    assert specs['rootsift_vlad']['dimension']==4096 and specs['rootsift_vlad']['parameters']['vlad']['clusters']==32
    assert default_weights_for()==dict(hog=8/17,spatial_hsv=3/17,rootsift_vlad=4/17,gabor=2/17)
    for old in ['baseline-v1','foreground12-v1','refined512-v1','foreground6-v1','foreground6-v2']:
        with pytest.raises(ValueError):AppConfig.default(old)


def test_database_accepts_only_the_four_supported_feature_types(app_config):
    repo = Repository(app_config)
    repo.create_schema()
    repo.create_schema()
    with repo.connect() as db:
        for name in ('HOG', 'SPATIAL_HSV', 'ROOTSIFT_VLAD', 'GABOR'):
            db.execute("INSERT INTO feature_configs(name,feature_type,dimension,parameters_json,preprocess_version) VALUES (?,?,1,'{}','fixture')", (name, name))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO feature_configs(name,feature_type,dimension,parameters_json,preprocess_version) VALUES ('extra','UNKNOWN',1,'{}','fixture')")
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def structured_rgba(seed=7):
    array=np.random.default_rng(seed).integers(0,256,(512,512,3),dtype=np.uint8)
    array[120:400,150:360]=np.random.default_rng(seed+1).integers(40,210,(280,210,3),dtype=np.uint8)
    rgba=Image.fromarray(array).convert('RGBA');rgba.putpixel((0,0),(*rgba.getpixel((0,0))[:3],0))
    return rgba


def test_actual_four_vectors_and_blank_input(ready):
    service,rows,masks,repo=ready
    config=AppConfig.default(BUNDLE_NAME);bundle=descriptor_bundle(config,feature_specs_for(BUNDLE_NAME))
    with pytest.raises(AppError) as error:extract_features(preprocess_image(png(structured_rgba())),bundle)
    assert error.value.code=='CONFIG_MISMATCH'
    bundle=descriptor_bundle(service.config,with_codebook_specs(service.config,feature_specs_for(service.config.bundle_name)))
    result=extract_features(preprocess_image(png(structured_rgba())),bundle)
    assert {k:len(v) for k,v in result.vectors.items()}==dict(hog=9864,spatial_hsv=512,rootsift_vlad=4096,gabor=96)
    for key,vector in result.vectors.items():
        assert np.isfinite(vector).all()
        if key=='rootsift_vlad':assert (vector<0).any() and float(np.linalg.norm(vector))==pytest.approx(1)
        else:assert (vector>=0).all()
        if key == 'spatial_hsv':assert vector.sum()==pytest.approx(1)
        if key=='gabor':assert vector.max()<=1
    assert (service.config.data_root/codebook_path(service.config)).is_file()
    flat_rgba=Image.new('RGBA',(512,512),(120,80,40,255));flat_rgba.putpixel((0,0),(120,80,40,0))
    flat=extract_features(preprocess_image(png(flat_rgba)),bundle)
    assert float(np.linalg.norm(flat.vectors['rootsift_vlad']))==0 and 'flat_root_sift' in flat.warnings
    raw=preprocess_image(png(Image.new('RGB',(512,512))),preprocess_version=SOURCE_PREPROCESS_VERSION)
    with pytest.raises(AppError,match='khớp'):extract_features(raw,bundle)
    with pytest.raises(AppError) as error:preprocess_image(png(Image.new('RGB',(512,512))))
    assert error.value.code=='BACKGROUND_REQUIRED'


@pytest.mark.parametrize('mapping',[{'hog':-1},{'hog':float('nan')},{'hog':float('inf')},{}])
def test_invalid_weights(mapping):
    with pytest.raises(AppError):normalize_weights(Weights.from_dict(mapping))


def test_weights_overflow_and_unknown_groups():
    values=normalize_weights(Weights.from_dict({k:1e308 for k in FEATURE_KEYS})).as_dict()
    assert sum(values.values())==pytest.approx(1)
    with pytest.raises(AppError):Weights.from_dict({'hsv':1})


def synthetic_bundle(value,signature='same'):
    return FeatureBundle.from_vectors({k:np.array([value,1-value]) for k in FEATURE_KEYS},
        config_ids={k:i for i,k in enumerate(FEATURE_KEYS,1)},config_signature=signature,
        similarities={k:{'metric':'intersection_exp','scale':1} for k in FEATURE_KEYS})


def test_top_five_unique_ties_and_all_species():
    query=synthetic_bundle(.8)
    candidates=[Candidate(i,'path','different-species' if i==1 else 'cat',synthetic_bundle(.8)) for i in range(1,7)]
    items=rank_candidates(query,[candidates[0],*candidates],Weights())
    assert [i.image_id for i in items]==[1,2,3,4,5]
    assert items[0].species_name=='different-species'
    assert all(i.scores.total==pytest.approx(1) for i in items)
    with pytest.raises(AppError):rank_candidates(query,candidates[:4],Weights())
    with pytest.raises(AppError):compare_features(query,synthetic_bundle(.8,'other'),Weights())


def test_import_search_history_cache_and_missing_files(ready,monkeypatch):
    service,rows,masks,repo=ready
    # IngestionService.import_rows nhập đúng các hàng được đưa; chính sách chỉ-gallery nằm ở
    # run_import (xem test_import_never_stores_test_split).
    assert repo.dataset_integrity()['vector_count']==24
    monkeypatch.setattr(DatasetProcessingService,'query_cutout',lambda self,payload,crop=None:service.cutout_path(rows[-1]).read_bytes())
    search=SearchService(service.config,repo)
    response=search.search(SearchRequest(service.config.resolve_data_path(rows[-1]['relative_path']).read_bytes()))
    assert response.candidate_count==5 and len({i.image_id for i in response.items})==5
    assert set(response.query_features.vectors)==set(FEATURE_KEYS)
    stored=repo.get_search_items(response.query_id)
    assert set(stored[0]['scores'])==set(FEATURE_KEYS)|{'total'}
    loaded=search.load_gallery()[0]
    target=service.config.resolve_data_path(loaded.candidates[0].processed_path)
    payload=target.read_bytes();target.unlink()
    broken=search.load_gallery()[0]
    assert len(broken.candidates)==4 and broken.rejected[0].image_id==loaded.candidates[0].image_id
    with pytest.raises(AppError):search.search(SearchRequest(b'ignored by test stub'))
    target.write_bytes(payload)
    assert len(search.load_gallery()[0].candidates)==5
    with repo.connect() as db:
        config_id=next(iter(repo.ensure_bundle().config_ids.values()))
        db.execute("UPDATE image_features SET vector_json='[0]' WHERE image_id=1 AND config_id=?",(config_id,));db.commit()
    assert len(search.load_gallery()[0].candidates)==4


def test_pipeline_paths_unassigned_and_no_implicit_mask_approval(app_config):
    from backend.src.background_import import build_manifest,run_import
    service,rows=sources(app_config,7)
    rows[-1]['split']='unassigned'
    with app_config.source_manifest_path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    _,masks,missing=build_manifest(app_config,app_config.source_manifest_path,service.cutouts)
    assert len(masks)==6 and not missing and all(r['quality_status']=='pending' for r in masks)
    for row in masks:row['quality_status']='approved'
    prepare_calibration(app_config,masks,minimum_gallery=5)
    result=run_import(app_config,app_config.source_manifest_path,service.cutouts,app_config.default_manifest_path)
    # Ch? gallery vào CSDL: 5 ảnh gallery × 4 vector; ảnh validation không nhập.
    assert result['database_vectors']==20 and result['approved_candidates']==0
    assert len(service.sources())==7


def test_frozen_calibration_rejects_changed_gallery(ready):
    service,rows,masks,repo=ready
    masks[0]['crop_x']='0';masks[0]['crop_y']='0';masks[0]['crop_size']='500'
    with pytest.raises(ValueError,match='Gallery changed'):prepare_calibration(service.config,masks,minimum_gallery=5)


def test_query_cache_and_failure_are_explicit(app_config,monkeypatch):
    service=DatasetProcessingService(app_config)
    calls=[]
    def model(arguments,log,cancelled):
        calls.append(arguments)
        source=Path(arguments[arguments.index('--input')+1]);output=Path(arguments[arguments.index('--output')+1])
        with Image.open(source) as im:mask=im.convert('RGBA')
        mask.putpixel((0,0),(*mask.getpixel((0,0))[:3],0));output.mkdir(parents=True,exist_ok=True)
        mask.save(output/(source.name+'.png'))
    monkeypatch.setattr(service,'_model',model)
    raw=png(Image.new('RGB',(520,520),(50,100,150)))
    first=service.query_cutout(raw,CropBox(0,0,512))
    assert service.query_cutout(raw,CropBox(0,0,512))==first and len(calls)==1
    monkeypatch.setattr(service,'_model',lambda *args:(_ for _ in ()).throw(ValueError('GPU unavailable')))
    with pytest.raises(AppError) as error:service.query_cutout(png(Image.new('RGB',(512,512),(2,3,4))))
    assert error.value.code=='BACKGROUND_FAILED'


def test_web_single_config_search_and_initial_setup(ready,monkeypatch,app_config):
    import backend.app as web
    service,rows,masks,repo=ready;search=SearchService(app_config,repo)
    monkeypatch.setattr(web,'services',lambda:(app_config,repo,search))
    monkeypatch.setattr(web,'services_for_profile',lambda profile:(app_config,repo,search))
    monkeypatch.setattr(DatasetProcessingService,'query_cutout',lambda self,payload,crop=None:service.cutout_path(rows[-1]).read_bytes())
    with TestClient(web.app) as client:
        page=client.get('/');assert page.status_code==200
        assert 'profile-select' not in page.text and '12 bộ mô tả' not in page.text
        invalid=client.get('/?profile=foreground12-v1')
        assert invalid.status_code==422
        assert OFFICIAL_BUNDLE_NAME in invalid.text and '4 bộ mô tả' in invalid.text
        result=client.post('/api/search',files={'image':('query.png',b'test stub')})
        assert result.status_code==200,result.text
        assert set(result.json()['query']['dimensions'])==set(FEATURE_KEYS)
        assert len(result.json()['query']['spatial_hsv_bins'])==8
        assert client.post('/api/search',files={'image':('query.png',b'test')},data={'hsv':'1'}).status_code==422


def test_new_database_page_does_not_claim_retrieval_ready(app_config,monkeypatch):
    import backend.app as web
    repo=Repository(app_config);repo.create_schema();search=SearchService(app_config,repo)
    monkeypatch.setattr(web,'services',lambda:(app_config,repo,search))
    with TestClient(web.app) as client:
        page=client.get('/');assert page.status_code==200,page.text
        assert 'Cần chuẩn bị dữ liệu' in page.text
        stats=client.get('/api/dashboard').json()['stats']
        assert not stats['acceptance_ready'] and not stats['calibration_ready']
    with repo.connect() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO feature_configs(name,feature_type,dimension,parameters_json,preprocess_version) VALUES ('bad','HSV',1,'{}','x')")


def test_same_group_siblings_survive_import(app_config):
    """Hai ảnh khác nhau cùng group_id (nhiều crop cùng trang nguồn) phải cùng sống sót."""
    from backend.src.background_import import build_manifest,run_import
    service,rows=sources(app_config)
    rows[4]['group_id']=rows[3]['group_id']
    with app_config.source_manifest_path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    _,masks,missing=build_manifest(app_config,app_config.source_manifest_path,service.cutouts)
    assert len(masks)==6 and not missing
    for row in masks:row['quality_status']='approved'
    prepare_calibration(app_config,masks,minimum_gallery=5)
    result=run_import(app_config,app_config.source_manifest_path,service.cutouts,app_config.default_manifest_path)
    assert result['created']==5
    repo=Repository(app_config)
    with repo.connect() as db:
        active=db.execute("SELECT COUNT(*) FROM images WHERE active=1 AND quality_status='pending'").fetchone()[0]
        rejected=db.execute("SELECT COUNT(*) FROM images WHERE quality_status='rejected'").fetchone()[0]
        siblings=db.execute("SELECT group_id,COUNT(*) FROM images WHERE active=1 GROUP BY group_id HAVING COUNT(*)=2").fetchall()
    assert (active,rejected,len(siblings))==(5,0,1)
    catalog=service.catalog()
    assert catalog['imported']==5
    assert all(item['image_id'] is not None for item in catalog['items'][:5])
    service.review([3],'approved')
    with app_config.default_manifest_path.open(encoding='utf-8-sig',newline='') as stream:
        decisions={row['relative_path']:row['quality_status'] for row in csv.DictReader(stream)}
    assert decisions[app_config.relative_to_data(service.cutout_path(rows[3]))]=='approved'
    assert decisions[app_config.relative_to_data(service.cutout_path(rows[4]))]=='pending'
    catalog=service.catalog()
    assert catalog['items'][3]['quality_status']=='approved'
    assert catalog['items'][4]['quality_status']=='pending'


def test_import_never_stores_test_split(app_config):
    """Ảnh test là query đánh giá nên không được nhập đặc trưng vào CSDL."""
    from backend.src.background_import import run_import
    service,rows=sources(app_config)
    for row in rows:row['split']='test'
    with app_config.source_manifest_path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with pytest.raises(ValueError,match='No matching cutouts'):
        run_import(app_config,app_config.source_manifest_path,service.cutouts,app_config.default_manifest_path)
    repo=Repository(app_config);repo.create_schema()
    assert repo.dataset_integrity()['image_count']==0
