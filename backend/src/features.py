"""The four descriptors used by both gallery and query."""
import numpy as np
from .errors import invalid
from .config import FEATURE_SPECS, preprocessing_size
from .models import BundleConfig, FeatureBundle, ProcessedImage
from .rootsift import extract_rootsift_vlad
from .spatial_features import weighted_hog, weighted_hsv
from .texture_features import extract_gabor

def _validate_input(image: ProcessedImage, config: BundleConfig) -> None:
    size = preprocessing_size(config.preprocess_version)
    if image.rgb.shape != (size, size, 3) or image.rgb.dtype != np.uint8:
        raise invalid(
            "INVALID_IMAGE",
            f"Extractor chỉ nhận RGB uint8 {size}x{size}",
            shape=list(image.rgb.shape),
            dtype=str(image.rgb.dtype),
        )
    if image.preprocess_version != config.preprocess_version:
        raise invalid(
            "CONFIG_MISMATCH",
            "Phiên bản tiền xử lý không khớp bundle",
            image_version=image.preprocess_version,
            bundle_version=config.preprocess_version,
        )

def extract_hog(rgb, *, visualize=False, parameters=None):
    return weighted_hog(rgb, parameters or FEATURE_SPECS["hog"]["parameters"], visualize)

def extract_spatial_hsv(rgb, parameters=None):
    return weighted_hsv(rgb, parameters or FEATURE_SPECS["spatial_hsv"]["parameters"], spatial=True)

EXTRA_EXTRACTORS = {"spatial_hsv": extract_spatial_hsv, "gabor": extract_gabor,
                    "rootsift_vlad": extract_rootsift_vlad}

def extract_features(image: ProcessedImage, config: BundleConfig) -> FeatureBundle:
    _validate_input(image, config)
    vectors: dict[str, np.ndarray] = {}
    for name, spec in config.configs.items():
        if name == "hog":
            vectors["hog"] = extract_hog(image.rgb, parameters=spec.parameters)
            if spec.parameters.get('pca'):
                if spec.projection is None:
                    raise invalid('CONFIG_MISMATCH', 'Thiếu mô hình PCA cho HOG')
                vectors['hog'] = spec.projection.transform(vectors['hog'])
        else:
            vectors[name] = EXTRA_EXTRACTORS[name](image.rgb, spec.parameters)
    warnings: list[str] = []
    if float(np.linalg.norm(vectors["hog"])) <= 1e-12:
        warnings.append("zero_gradient")
    if "rootsift_vlad" in vectors and float(np.linalg.norm(vectors["rootsift_vlad"])) <= 1e-12:
        warnings.append("flat_root_sift")

    expected = {name: spec.dimension for name, spec in config.configs.items()}
    for name, vector in vectors.items():
        if vector.shape != (expected[name],):
            raise invalid(
                "INVALID_VECTOR",
                "Số chiều vector không đúng cấu hình",
                feature=name,
                actual=int(vector.size),
                expected=expected[name],
            )
        signed = bool(config.configs[name].parameters.get("signed_values"))
        if not np.isfinite(vector).all() or (not signed and (vector < -1e-12).any()):
            raise invalid("INVALID_VECTOR", "Vector chứa giá trị không hữu hạn hoặc âm", feature=name)
        if config.configs[name].parameters.get("normalization") == "bounded" and (vector > 1 + 1e-12).any():
            raise invalid("INVALID_VECTOR", "Vector vượt miền chuẩn hóa [0,1]", feature=name)
    return FeatureBundle.from_vectors(
        vectors,
        config_ids=config.config_ids,
        warnings=tuple(warnings),
        preprocess_version=image.preprocess_version,
        similarities={name: spec.parameters["similarity"] for name, spec in config.configs.items() if "similarity" in spec.parameters},
        config_signature=config.signature,
    )
