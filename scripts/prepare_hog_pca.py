"""Fit HOG PCA on gallery, select dimension on the former test used as validation, and build a separate profile."""
from pathlib import Path
import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
import csv
import json
import shutil
import sys
from statistics import mean, median
from time import perf_counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig, BUNDLE_NAME, PCA_PROFILES, FEATURE_KEYS, feature_specs_for, default_weights_for
from backend.src.pca import PCAModel, fit_pca, save_pca, with_pca_specs
from backend.src.codebook import with_codebook_specs
from backend.src.calibration import canonical_hash, calibration_path, fit_calibration
from backend.src.calibration_preparation import descriptor_bundle
from backend.src.features import extract_features
from backend.src.models import FeatureBundle, Weights, Candidate
from backend.src.processing_service import DatasetProcessingService
from backend.src.preprocessing import preprocess_image
from backend.src.repository import Repository
from backend.src.similarity import rank_candidates
from scripts.evaluate import validate_query_split, write_csv
from scripts.prepare_dataset import prepare_sources


def read_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_frozen_json(path, value):
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != value:
            raise ValueError(f'Frozen artifact changed: {path}; create another profile')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)


def feature_bundle(vectors, bundle):
    return FeatureBundle.from_vectors(vectors, config_ids=bundle.config_ids,
        preprocess_version=bundle.preprocess_version, config_signature=bundle.signature,
        similarities={k:s.parameters['similarity'] for k,s in bundle.configs.items()})


def evaluate_vectors(candidates, queries, bundle, config):
    rows=[];latencies=[]
    weights=Weights.from_dict(default_weights_for(config.bundle_name))
    for index,(source,vectors) in enumerate(queries):
        start=perf_counter()
        query=feature_bundle(vectors,bundle)
        results=rank_candidates(query,candidates,weights)
        latency=(perf_counter()-start)*1000
        latencies.append(latency)
        hits=[item.species_name==source['species_name'] for item in results]
        rows.append({'query':source['relative_path'],'species':source['species_name'],
            'p5':sum(hits)/5,'top1':int(hits[0]),'top5':int(any(hits)),'rank_ms':latency,
            'result_ids':json.dumps([item.image_id for item in results])})
    per_species={name:mean(r['p5'] for r in rows if r['species']==name) for name in sorted({r['species'] for r in rows})}
    arrays=[vector for c in candidates for vector in c.features.vectors.values()]
    return {'profile':config.bundle_name,'hog_dimension':bundle.hog.dimension,
        'total_dimension':sum(s.dimension for s in bundle.configs.values()),
        'p5':mean(r['p5'] for r in rows),'top1':mean(r['top1'] for r in rows),'top5':mean(r['top5'] for r in rows),
        'rank_median_ms':median(latencies),'rank_p95_ms':float(np.percentile(latencies,95)),
        'gallery_vector_bytes':sum(a.nbytes for a in arrays),'per_species_p5':per_species},rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-p5-loss',type=float,default=.01,
                        help='Maximum validation P@5 loss allowed relative to baseline (default .01)')
    args=parser.parse_args()
    if not 0<=args.max_p5_loss<=.1:parser.error('max-p5-loss must be in [0,.1]')
    base=AppConfig.default(BUNDLE_NAME);repo=Repository(base);bundle=repo.ensure_bundle()
    loaded=repo.load_candidates(bundle)
    if len(loaded.candidates)<500 or loaded.rejected:raise ValueError('Prepare at least 500 valid baseline gallery images first')
    fingerprint=repo.gallery_fingerprint(bundle)
    records={r['image_id']:r for r in repo.audit_image_records()}
    sources=read_rows(base.source_manifest_path)
    validation=[{**r,'split':'validation','mask_split':r['split']} for r in sources if r['split']=='test']
    validate_query_split(validation,list(records.values()))
    out=base.data_root/'evaluation/hog-pca-selection-v1';out.mkdir(parents=True,exist_ok=True)
    matrices={key:np.stack([c.features.vectors[key] for c in loaded.candidates]) for key in FEATURE_KEYS}
    provenance={'baseline_profile':BUNDLE_NAME,'baseline_signature':bundle.signature,
        'source_split':'gallery','n_gallery':len(loaded.candidates),
        'hog_vectors_sha256':sha256(np.ascontiguousarray(matrices['hog']).tobytes()).hexdigest(),
        'gallery_images_sha256':canonical_hash(sorted(records[c.image_id]['original_sha256'] for c in loaded.candidates))}
    print('Fitting PCA on',len(loaded.candidates),'gallery rows only',flush=True)
    fitted=fit_pca(matrices['hog'],max(PCA_PROFILES.values()))
    cache=out/'baseline_validation_vectors.npz';cache_meta=out/'baseline_validation_vectors.json'
    query_signature={'baseline_signature':bundle.signature,
        'source_manifest_sha256':sha256(base.source_manifest_path.read_bytes()).hexdigest(),
        'query_source_sha256':[sha256(base.resolve_data_path(r['relative_path']).read_bytes()).hexdigest() for r in validation]}
    queries=[]
    if cache.exists() and cache_meta.exists() and json.loads(cache_meta.read_text())==query_signature:
        with np.load(cache,allow_pickle=False) as data:
            for index,row in enumerate(validation):queries.append((row,{k:data[k][index].copy() for k in FEATURE_KEYS}))
        print('Reusing verified validation descriptors',flush=True)
    else:
        processing=DatasetProcessingService(base)
        gallery_pixels={records[c.image_id]['processed_sha256'] for c in loaded.candidates}
        for index,row in enumerate(validation,1):
            payload=base.resolve_data_path(row['relative_path']).read_bytes()
            mask=processing.query_cutout(payload)
            image=preprocess_image(mask,preprocess_version=base.preprocess_version)
            if image.pixel_sha256 in gallery_pixels:raise ValueError('Validation query pixels overlap gallery')
            values=extract_features(image,bundle).vectors
            queries.append((row,values))
            if index%10==0:print(f'Validation descriptors {index}/{len(validation)}',flush=True)
        np.savez(cache,**{k:np.stack([v[k] for _,v in queries]) for k in FEATURE_KEYS})
        cache_meta.write_text(json.dumps(query_signature),encoding='utf-8')
    summary,rows=evaluate_vectors(loaded.candidates,queries,bundle,base)
    metrics=[summary];write_csv(out/'queries_baseline.csv',rows)
    print('Baseline',summary['p5'],flush=True)
    prepared={}
    base_calibration=json.loads(calibration_path(base).read_text(encoding='utf-8'))
    by_path={records[c.image_id]['original_path']:i for i,c in enumerate(loaded.candidates)}
    fit_order=[by_path[r['path']] for r in base_calibration['source_records']]
    if len(fit_order)!=len(loaded.candidates) or len(set(fit_order))!=len(fit_order):
        raise ValueError('Frozen calibration gallery differs from active gallery')
    for profile,n in PCA_PROFILES.items():
        config=base.for_profile(profile)
        model=PCAModel(fitted.mean,fitted.components[:n],fitted.explained_variance_ratio[:n])
        metadata=save_pca(config,model,provenance)
        specs=with_pca_specs(config,with_codebook_specs(config,feature_specs_for(profile)))
        model=descriptor_bundle(config,specs).hog.projection
        gallery={**matrices,'hog':model.transform(matrices['hog'])}
        calibration=fit_calibration({k:a[fit_order] for k,a in gallery.items()},specs,profile=profile)
        # Hold all three unaffected metrics fixed for a fair HOG-only comparison.
        for key in FEATURE_KEYS:
            if key!='hog':calibration['metrics'][key]=base_calibration['metrics'][key]
        calibration.update(gallery_source_sha256=base_calibration['gallery_source_sha256'],
            source_records=base_calibration['source_records'],preprocessing_version=base.preprocess_version,
            note='Gallery-only PCA/calibration; former test is validation. Four other descriptor metrics unchanged.')
        write_frozen_json(calibration_path(config),calibration)
        from backend.src.calibration import calibrated_specs
        calibrated=calibrated_specs(config,specs)
        trial=descriptor_bundle(config,calibrated)
        candidates=tuple(Candidate(c.image_id,c.processed_path,c.species_name,
            feature_bundle({k:a[i] for k,a in gallery.items()},trial)) for i,c in enumerate(loaded.candidates))
        trial_queries=[(row,{**v,'hog':model.transform(v['hog'])}) for row,v in queries]
        result,rows=evaluate_vectors(candidates,trial_queries,trial,config)
        result['explained_variance_retained']=metadata['explained_variance_ratio_sum']
        result['pca_model_bytes']=(config.data_root/'calibration'/profile/'hog_pca.npz').stat().st_size
        metrics.append(result);write_csv(out/f'queries_pca{n}.csv',rows)
        prepared[profile]=(config,candidates)
        print(profile,'P@5',result['p5'],'Top1',result['top1'],'rank ms',result['rank_median_ms'],flush=True)
    eligible=[m for m in metrics[1:] if m['p5']>=metrics[0]['p5']-args.max_p5_loss-1e-12 and m['top1']>=metrics[0]['top1']-.02-1e-12]
    if not eligible:
        (out/'comparison.json').write_text(json.dumps({'metrics':metrics,'selected':None,'note':'Baseline retained: no PCA candidate meets quality limits'},indent=2),encoding='utf-8')
        raise SystemExit('No PCA candidate meets the validation quality limits; baseline retained')
    chosen=min(eligible,key=lambda m:m['hog_dimension'])
    config,candidates=prepared[chosen['profile']]
    if repo.gallery_fingerprint(bundle)!=fingerprint:raise ValueError('Gallery changed during validation; rerun')
    config.ensure_runtime_dirs();prepare_sources(config)
    compressed=Repository(config);compressed.create_schema();actual_bundle=compressed.ensure_bundle()
    # Rebind trial IDs/signatures to the real config IDs in the new database.
    features={c.image_id:feature_bundle(c.features.vectors,actual_bundle) for c in candidates}
    print('Building separate compressed database',config.db_path.name,flush=True)
    compressed.copy_gallery_vectors(repo,features,actual_bundle)
    if config.default_manifest_path.exists():
        if config.default_manifest_path.read_bytes()!=base.default_manifest_path.read_bytes():
            raise ValueError('Existing compressed import manifest differs; do not overwrite review decisions')
    else:shutil.copyfile(base.default_manifest_path,config.default_manifest_path)
    final=compressed.load_candidates(actual_bundle)
    if len(final.candidates)!=len(loaded.candidates) or final.rejected:raise ValueError('Compressed gallery verification failed')
    report={'selected':chosen['profile'],'selection_split':'validation','validation_queries':len(validation),
        'independent_test_queries':0,'selection_rule':{'max_p5_loss':args.max_p5_loss,'max_top1_loss':.02,'tie':'smallest dimension'},
        'metrics':metrics,'source_provenance':provenance,'integrity':compressed.dataset_integrity(),
        'database_bytes':{'baseline':base.db_path.stat().st_size,'compressed':config.db_path.stat().st_size},
        'note':'Validation dimension selection only; no independent test claim. Original profile and all image files preserved.'}
    (out/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    columns=list(dict.fromkeys(key for row in metrics for key in row))
    write_csv(out/'comparison.csv',[{k:json.dumps(m[k]) if isinstance(m.get(k),dict) else m.get(k,'') for k in columns} for m in metrics])
    print(json.dumps(report,ensure_ascii=True,indent=2),flush=True)


if __name__=='__main__':main()
