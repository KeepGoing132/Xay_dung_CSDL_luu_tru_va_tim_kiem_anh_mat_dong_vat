"""Fresh processes must agree on defaults, including direct uvicorn imports and overrides."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('override,profile,hog,total,database', [
    (None, 'foreground4-hogpca512-v1', 512, 5216, 'foreground4_hogpca512.db'),
    ('', 'foreground4-hogpca512-v1', 512, 5216, 'foreground4_hogpca512.db'),
    ('foreground4-v1', 'foreground4-v1', 9864, 14568, 'foreground4.db'),
    ('foreground4-hogpca256-v1', 'foreground4-hogpca256-v1', 256, 4960, 'foreground4_hogpca256.db'),
])
def test_entry_points_share_default_and_explicit_override(override, profile, hog, total, database):
    env = os.environ.copy()
    env.pop('CBIR_PROFILE', None)
    if override is not None:
        env['CBIR_PROFILE'] = override
    source = '''
import inspect, json
from backend.src.config import AppConfig, OFFICIAL_BUNDLE_NAME, OFFICIAL_DIMENSIONS, feature_specs_for, feature_labels_for
from backend.src.calibration import fit_calibration
from backend import app
c = AppConfig.default()
s = feature_specs_for()
print(json.dumps(dict(profile=c.bundle_name, web=app.OFFICIAL_BUNDLE_NAME,
    constructor=AppConfig.__dataclass_fields__['bundle_name'].default,
    calibration=inspect.signature(fit_calibration).parameters['profile'].default,
    database=c.db_path.name, hog=s['hog']['dimension'],
    dimensions=sum(v['dimension'] for v in s.values()), official=OFFICIAL_DIMENSIONS,
    label=feature_labels_for()['hog'][0])))
'''
    run = subprocess.run([sys.executable, '-c', source], env=env,
                         cwd=Path(__file__).resolve().parents[1],
                         capture_output=True, text=True, encoding='utf-8', check=True)
    result = json.loads(run.stdout)
    assert all(result[key] == profile for key in ('profile', 'web', 'constructor', 'calibration'))
    assert result['database'] == database
    assert result['hog'] == hog
    assert result['dimensions'] == result['official'] == total
    if hog != 9864:
        assert result['label'] == 'HOG-PCA'
