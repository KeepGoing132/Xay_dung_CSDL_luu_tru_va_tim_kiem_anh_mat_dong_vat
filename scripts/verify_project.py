"""Audit the current four-descriptor configuration and preserved source dataset."""
from pathlib import Path
from collections import Counter
import argparse
import ast
import csv
from hashlib import sha256
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.src.config import AppConfig,FEATURE_KEYS,feature_specs_for,PROFILE_SETTINGS
from backend.src.errors import AppError
from backend.src.repository import Repository


def verify(config):
    path=config.data_root/'dataset512-left/manifest.csv'
    with path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
    inventory_path=config.data_root/'dataset512-left/inventory.csv'
    with inventory_path.open(encoding='utf-8-sig',newline='') as stream:
        inventory=list(csv.DictReader(stream))
    expected_rows=sum(int(row['selected_count']) for row in inventory)
    if len(rows)!=expected_rows:raise ValueError(f'Manifest has {len(rows)} rows, inventory totals {expected_rows}')
    if len(rows)<500:raise ValueError(f'Fewer than 500 selected sources: {len(rows)}')
    minimums={row['species_name']:int(row['minimum_total']) for row in inventory}
    counts={}
    for row in rows:counts[row['species_name']]=counts.get(row['species_name'],0)+1
    if counts!={row['species_name']:int(row['selected_count']) for row in inventory}:
        raise ValueError(f'Per-species counts differ from inventory: {counts}')
    below=sorted(name for name in counts if counts[name]<minimums.get(name,0))
    if below:raise ValueError(f'Species below the declared minimum: {below}')
    seen=set();groups={};pixels=set()
    for row in rows:
        relative=row['data_relative_path'];image=config.resolve_data_path(relative)
        if not image.is_relative_to(config.source_root.resolve()) or relative in seen:
            raise ValueError(f'Unsafe or duplicate source: {relative}')
        seen.add(relative)
        if sha256(image.read_bytes()).hexdigest()!=row['file_sha256']:
            raise ValueError(f'Source checksum mismatch: {relative}')
        from PIL import Image
        with Image.open(image) as im:
            if im.mode!='RGB' or im.size!=(512,512):raise ValueError(f'Invalid RGB512: {relative}')
            digest=sha256(im.tobytes()).hexdigest()
        if digest!=row['pixel_sha256'] or digest in pixels:raise ValueError(f'Pixel checksum/duplicate: {relative}')
        pixels.add(digest)
        if not row['source_url']:raise ValueError(f'Missing source: {relative}')
        groups.setdefault(row['group_id'],set()).add(row['split'])
    if any(len(v)>1 for v in groups.values()):raise ValueError('Source group crosses splits')
    with config.source_manifest_path.open(encoding='utf-8-sig',newline='') as stream:runtime=list(csv.DictReader(stream))
    if len(runtime)!=len(rows) or {r['relative_path'] for r in runtime}!=seen:
        raise ValueError('Runtime source manifest differs from selected dataset')
    source_by_path={row['data_relative_path']:row for row in rows}
    for row in runtime:
        source=source_by_path[row['relative_path']]
        for key in ('species_name','split','group_id','quality_status','source_url','file_sha256','pixel_sha256'):
            expected='validation' if config.pca_components and key=='split' and source[key]=='test' else source[key]
            if row[key]!=expected:raise ValueError(f'Runtime {key} differs: {row["relative_path"]}')
        if config.pca_components and row.get('mask_split')!=source['split']:
            raise ValueError(f'Runtime mask provenance differs: {row["relative_path"]}')
    if any(r[k] for r in runtime for k in ('crop_x','crop_y','crop_size')):raise ValueError('Already-cropped source must not be cropped twice')
    specs=feature_specs_for(config.bundle_name);assert set(specs)==set(FEATURE_KEYS)
    report={'configuration':config.bundle_name,'groups':list(FEATURE_KEYS),'dimensions':sum(s['dimension'] for s in specs.values()),
            'source_images_verified':len(rows),'source_urls':sum(bool(r['source_url']) for r in rows),
            'splits':dict(Counter(r['split'] for r in runtime)),'valid_gallery':0,'acceptance_ready':False}
    if config.db_path.exists():
        repo=Repository(config);report['database']=repo.dataset_integrity()
        records=repo.audit_image_records()
        # A re-import may retain retired history rows for the same mask path.
        current={}
        for row in records:
            path=row['original_path']
            if path not in current or row['image_id']>current[path]['image_id']:current[path]=row
        report['mask_review']=dict(Counter(row['quality_status'] for row in current.values()))
        errors=[]
        if report['database']['integrity']!='ok' or report['database']['foreign_key_errors']:
            errors.append('Database integrity or foreign-key check failed')
        if any(row['split']!='gallery' for row in records):errors.append('Non-gallery image stored in database')
        if config.default_manifest_path.exists():
            with config.default_manifest_path.open(encoding='utf-8-sig',newline='') as stream:
                imported=list(csv.DictReader(stream))
            by_path={row['relative_path']:row for row in imported}
            if len(by_path)!=len(imported):errors.append('Duplicate imported mask paths')
            if set(by_path)!=set(current):errors.append('Import manifest and database paths differ')
            for row in current.values():
                path=row['original_path'];mask=config.resolve_data_path(path)
                if not mask.is_file() or sha256(mask.read_bytes()).hexdigest()!=row['original_sha256']:
                    errors.append(f'Missing or changed mask: {path}')
                imported_row=by_path.get(path)
                if imported_row:
                    for key in ('split','group_id','quality_status'):
                        if imported_row[key]!=row[key]:errors.append(f'Import manifest {key} differs: {path}')
        elif records:errors.append('Import manifest missing for stored gallery')
        report['synchronization_errors']=errors
        try:
            loaded=repo.load_candidates(repo.ensure_bundle())
            report.update(valid_gallery=len(loaded.candidates),rejected=[r.__dict__ for r in loaded.rejected],
                          acceptance_ready=len(loaded.candidates)>=500 and not loaded.rejected and not errors)
        except AppError as exc:report['setup_error']={'code':exc.code,'message':exc.message}
    else:report['setup_error']={'code':'DATABASE_NOT_PREPARED'}
    for directory in ('backend','scripts','tests'):
        for path in (config.project_root/directory).rglob('*.py'):ast.parse(path.read_text(encoding='utf-8-sig'))
    for path in (config.project_root/'animal_face_model').glob('*.py'):ast.parse(path.read_text(encoding='utf-8-sig'))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=list(PROFILE_SETTINGS))
    parser.add_argument('--require-ready',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();report=verify(AppConfig.default(args.profile))
    content=json.dumps(report,ensure_ascii=True,indent=2);print(content)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(content,encoding='utf-8')
    if report.get('synchronization_errors'):raise SystemExit(1)
    if args.require_ready and not report['acceptance_ready']:raise SystemExit(1)


if __name__=='__main__':main()
