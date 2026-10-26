from dataclasses import replace
import json

import numpy as np
import pytest

from backend.src.config import feature_specs_for
from backend.src.errors import AppError
from backend.src.pca import PCAModel, fit_pca, save_pca, with_pca_specs, attach_projection
from backend.src.calibration_preparation import descriptor_bundle
from backend.src.preprocessing import preprocess_image
from backend.src.features import extract_features
from backend.src.repository import Repository
from PIL import Image
from io import BytesIO


def test_pca_matches_svd_subspace_and_preserves_zero_gradient():
    values=np.random.default_rng(7).normal(size=(25,12))
    model=fit_pca(values,5)
    _,singular,basis=np.linalg.svd(values-values.mean(axis=0),full_matrices=False)
    np.testing.assert_allclose(model.components.T@model.components,basis[:5].T@basis[:5],atol=1e-10)
    np.testing.assert_allclose(model.explained_variance_ratio,singular[:5]**2/np.sum(singular**2),atol=1e-12)
    np.testing.assert_allclose(model.components@model.components.T,np.eye(5),atol=1e-10)
    batch=model.transform(values[:3])
    np.testing.assert_allclose(batch,np.stack([model.transform(row) for row in values[:3]]),atol=1e-12)
    np.testing.assert_allclose(np.linalg.norm(batch,axis=1),1)
    assert (batch<0).any()
    assert not model.transform(np.zeros(12)).any()
    with pytest.raises(ValueError):fit_pca(values,25)
    with pytest.raises(AppError):model.transform(np.ones(13))


def test_pca_artifact_is_gallery_only_frozen_and_checksum_verified(app_config):
    config=app_config.for_profile('foreground4-hogpca128-v1')
    model=PCAModel(np.full(9864,.001),np.eye(128,9864),np.full(128,1/128))
    provenance={'source_split':'gallery','n_gallery':781,'hog_vectors_sha256':'frozen'}
    with pytest.raises(AppError):with_pca_specs(config,feature_specs_for(config.bundle_name))
    with pytest.raises(ValueError):save_pca(config,model,{**provenance,'source_split':'validation'})
    save_pca(config,model,provenance)
    specs=with_pca_specs(config,feature_specs_for(config.bundle_name))
    bundle=descriptor_bundle(config,specs)
    assert bundle.hog.projection is not None and bundle.hog.dimension==128
    assert bundle.hog.parameters['signed_values'] and bundle.hog.parameters['similarity']['metric']=='cosine_signed_exp'
    vector=bundle.hog.projection.transform(np.linspace(0,.02,9864))
    Repository._validate_vector(vector,bundle.hog)
    assert bundle.signature!=descriptor_bundle(config,feature_specs_for(config.bundle_name)).signature
    save_pca(config,model,provenance)
    with pytest.raises(ValueError):save_pca(config,model,{**provenance,'hog_vectors_sha256':'changed'})
    binary=config.data_root/'calibration'/config.bundle_name/'hog_pca.npz'
    binary.write_bytes(b'broken')
    with pytest.raises(AppError,match='PCA'):with_pca_specs(config,feature_specs_for(config.bundle_name))


def test_extract_features_projects_hog_and_keeps_three_other_dimensions(app_config,monkeypatch):
    config=app_config.for_profile('foreground4-hogpca128-v1')
    specs=feature_specs_for(config.bundle_name)
    bundle=descriptor_bundle(config,specs)
    groups=dict(bundle.configs)
    groups['hog']=replace(bundle.hog,projection=PCAModel(np.full(9864,.001),np.eye(128,9864),np.full(128,1/128)))
    bundle=replace(bundle,configs=groups)
    import backend.src.features as feature_module
    for key in ('spatial_hsv','rootsift_vlad','gabor'):
        dimension=specs[key]['dimension']
        monkeypatch.setitem(feature_module.EXTRA_EXTRACTORS,key,lambda rgb,parameters,d=dimension:np.full(d,1/d))
    image=Image.fromarray(np.random.default_rng(3).integers(0,256,(512,512,3),dtype=np.uint8)).convert('RGBA')
    image.putpixel((0,0),(0,0,0,0))
    stream=BytesIO();image.save(stream,format='PNG')
    result=extract_features(preprocess_image(stream.getvalue()),bundle)
    assert {k:len(v) for k,v in result.vectors.items()}==dict(hog=128,spatial_hsv=512,rootsift_vlad=4096,gabor=96)
    assert np.linalg.norm(result.vectors['hog'])==pytest.approx(1)
    with pytest.raises(AppError,match='PCA'):
        extract_features(preprocess_image(stream.getvalue()),descriptor_bundle(config,specs))
