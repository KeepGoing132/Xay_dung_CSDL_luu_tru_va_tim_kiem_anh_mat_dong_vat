"""Frozen, gallery-fitted HOG PCA with checksummed portable artifacts."""
from dataclasses import dataclass, replace
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
from scipy.linalg import eigh

from .errors import invalid


@dataclass(frozen=True)
class PCAModel:
    mean: np.ndarray
    components: np.ndarray
    explained_variance_ratio: np.ndarray

    def transform(self, values):
        array = np.asarray(values, dtype=np.float64)
        if array.ndim not in (1, 2) or array.shape[-1] != self.mean.size or not np.isfinite(array).all():
            raise invalid("CONFIG_MISMATCH", "Đầu vào PCA sai chiều hoặc không hữu hạn")
        batch = np.atleast_2d(array)
        result = (batch - self.mean) @ self.components.T
        # Preserve the existing zero-gradient behavior for a blank HOG input.
        result[np.linalg.norm(batch, axis=1) <= 1e-12] = 0
        result /= np.maximum(np.linalg.norm(result, axis=1, keepdims=True), 1e-12)
        return result[0] if array.ndim == 1 else result


def fit_pca(values, components):
    """Exact PCA via the sample Gram matrix; only gallery rows may be supplied."""
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or not np.isfinite(array).all() or not 0 < components < min(array.shape):
        raise ValueError("PCA needs finite gallery rows and components below sample/feature count")
    mean = array.mean(axis=0)
    centered = array - mean
    gram = centered @ centered.T
    eigenvalues, eigenvectors = eigh(gram, subset_by_index=(len(array)-components, len(array)-1))
    eigenvalues, eigenvectors = eigenvalues[::-1], eigenvectors[:, ::-1]
    tolerance = max(float(eigenvalues[0]), 1) * max(array.shape) * np.finfo(float).eps
    if eigenvalues[-1] <= tolerance:
        raise ValueError("Requested PCA dimension exceeds the numerical gallery rank")
    basis = (eigenvectors.T @ centered) / np.sqrt(eigenvalues[:, None])
    # Remove the arbitrary eigenvector sign for deterministic artifacts.
    signs = np.sign(basis[np.arange(components), np.argmax(np.abs(basis), axis=1)])
    basis *= signs[:, None]
    ratio = eigenvalues / np.sum(centered * centered)
    return PCAModel(mean, basis, ratio)


def save_pca(config, model, provenance):
    """Publish once. Existing frozen models must have the same training provenance."""
    if (provenance.get('source_split') != 'gallery' or provenance.get('n_gallery', 0) <= len(model.components)
            or len(model.components) != config.pca_components):
        raise ValueError('PCA must be fitted on gallery only, with enough rows for this profile')
    directory = config.data_root / 'calibration' / config.bundle_name
    directory.mkdir(parents=True, exist_ok=True)
    metadata_path = directory / 'hog_pca.json'
    binary = directory / 'hog_pca.npz'
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata.get('provenance') != provenance:
            raise ValueError('PCA training gallery changed; use a new profile')
        from .config import feature_specs_for
        with_pca_specs(config, feature_specs_for(config.bundle_name))
        return metadata
    with binary.open('xb') as stream:
        np.savez(stream, mean=model.mean, components=model.components,
                 explained_variance_ratio=model.explained_variance_ratio)
    metadata = {'schema_version': 1, 'profile': config.bundle_name, 'source_split': 'gallery',
        'input_dimension': model.mean.size, 'components': len(model.components), 'whiten': False,
        'normalization': 'center-project-L2', 'binary': binary.name,
        'binary_sha256': sha256(binary.read_bytes()).hexdigest(), 'provenance': provenance,
        'explained_variance_ratio_sum': float(model.explained_variance_ratio.sum())}
    with metadata_path.open('x', encoding='utf-8') as stream:
        json.dump(metadata, stream, indent=2)
    return metadata


@lru_cache(maxsize=4)
def _read_model(path, expected_sha, modified_ns, size):
    binary = Path(path)
    if sha256(binary.read_bytes()).hexdigest() != expected_sha:
        raise ValueError('PCA binary checksum mismatch')
    with np.load(binary, allow_pickle=False) as data:
        mean = np.asarray(data['mean'], dtype=np.float64)
        components = np.asarray(data['components'], dtype=np.float64)
        ratio = np.asarray(data['explained_variance_ratio'], dtype=np.float64)
    if (mean.ndim != 1 or components.ndim != 2 or components.shape[1] != mean.size
            or ratio.shape != (len(components),) or not all(np.isfinite(a).all() for a in (mean, components, ratio))):
        raise ValueError('Invalid PCA array shapes or values')
    for array in (mean, components, ratio):
        array.flags.writeable = False
    return PCAModel(mean, components, ratio)


def with_pca_specs(config, specs):
    if not config.pca_components:
        return specs
    try:
        path = config.resolve_data_path(specs['hog']['parameters']['pca']['artifact'])
        metadata = json.loads(path.read_text(encoding='utf-8'))
        if (metadata['schema_version'] != 1 or metadata['profile'] != config.bundle_name
                or metadata['source_split'] != 'gallery' or metadata['input_dimension'] != 9864
                or metadata['components'] != config.pca_components or metadata['whiten'] is not False
                or metadata['provenance']['source_split'] != 'gallery'
                or metadata['provenance']['n_gallery'] <= config.pca_components
                or metadata['binary'] != 'hog_pca.npz'):
            raise ValueError('PCA metadata does not match profile')
        binary = path.parent / metadata['binary']
        stat = binary.stat()
        model = _read_model(str(binary), metadata['binary_sha256'], stat.st_mtime_ns, stat.st_size)
        if model.components.shape != (config.pca_components, metadata['input_dimension']):
            raise ValueError('PCA dimensions do not match metadata')
        result = json.loads(json.dumps(specs))
        result['hog']['parameters']['pca'].update(binary_sha256=metadata['binary_sha256'],
            metadata_sha256=sha256(path.read_bytes()).hexdigest())
        return result
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise invalid('CONFIG_MISMATCH', 'Thiếu hoặc sai PCA HOG; chạy scripts/prepare_hog_pca.py', reason=str(exc)) from exc


def attach_projection(config, bundle):
    parameters = bundle.hog.parameters.get('pca')
    if not parameters or 'binary_sha256' not in parameters:
        return bundle
    path = config.resolve_data_path(parameters['artifact']).parent / 'hog_pca.npz'
    try:
        stat = path.stat()
        model = _read_model(str(path), parameters['binary_sha256'], stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError, KeyError) as exc:
        raise invalid('CONFIG_MISMATCH', 'Không nạp được PCA HOG', reason=str(exc)) from exc
    groups = dict(bundle.configs)
    groups['hog'] = replace(bundle.hog, projection=model)
    return replace(bundle, configs=groups)
