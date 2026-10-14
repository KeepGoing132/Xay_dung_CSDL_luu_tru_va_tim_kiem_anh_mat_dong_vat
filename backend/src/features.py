from __future__ import annotations

import numpy as np
from skimage import color
from skimage.feature import hog, local_binary_pattern, graycomatrix, graycoprops

from .errors import invalid
from .config import FEATURE_SPECS, preprocessing_size
from .models import BundleConfig, FeatureBundle, ProcessedImage
from .refined_features import weighted_hsv, weighted_hog, weighted_lbp, weighted_color_moments, weighted_glcm


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


def extract_hsv(rgb: np.ndarray, parameters: dict | None = None) -> np.ndarray:
    parameters = parameters or FEATURE_SPECS["hsv"]["parameters"]
    if "spatial_prior" in parameters:
        return weighted_hsv(rgb, parameters)
    hsv = color.rgb2hsv(rgb.astype(np.float32) / 255.0)
    vector, _ = np.histogramdd(
        hsv.reshape(-1, 3),
        bins=tuple(parameters["bins"]),
        range=tuple(tuple(value) for value in parameters["ranges"]),
    )
    vector = vector.astype(np.float64).ravel(order="C")
    total = float(vector.sum())
    if total <= 0:
        raise invalid("INVALID_VECTOR", "Histogram HSV rỗng")
    return vector / total


def extract_hog(rgb: np.ndarray, *, visualize: bool = False, parameters: dict | None = None):
    parameters = parameters or FEATURE_SPECS["hog"]["parameters"]
    if "scales" in parameters:
        return weighted_hog(rgb, parameters, visualize)
    gray = color.rgb2gray(rgb)
    result = hog(
        gray,
        orientations=parameters["orientations"],
        pixels_per_cell=tuple(parameters["pixels_per_cell"]),
        cells_per_block=tuple(parameters["cells_per_block"]),
        block_norm=parameters["block_norm"],
        transform_sqrt=parameters["transform_sqrt"],
        feature_vector=True,
        visualize=visualize,
    )
    if visualize:
        vector, image = result
    else:
        vector, image = result, None
    vector = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(vector))
    if norm > parameters["epsilon"]:
        vector = vector / norm
    else:
        vector = np.zeros_like(vector)
    return (vector, image) if visualize else vector


def lbp_code_image(rgb: np.ndarray, parameters: dict | None = None) -> np.ndarray:
    parameters = parameters or FEATURE_SPECS["lbp"]["parameters"]
    if "scales" in parameters:
        parameters = {**parameters, **parameters["scales"][0]}
    gray = np.rint(color.rgb2gray(rgb) * 255.0).astype(np.uint8)
    return local_binary_pattern(gray, P=parameters["points"], R=parameters["radius"], method=parameters["method"])


def extract_lbp(rgb: np.ndarray, parameters: dict | None = None) -> np.ndarray:
    parameters = parameters or FEATURE_SPECS["lbp"]["parameters"]
    if "scales" in parameters:
        return weighted_lbp(rgb, parameters)
    codes = lbp_code_image(rgb, parameters)
    region_vectors: list[np.ndarray] = []
    edges = np.arange(-0.5, parameters["points"] + 2.5, 1.0)
    grid_rows, grid_columns = parameters["grid"]
    height, width = codes.shape
    for row in range(grid_rows):
        for col in range(grid_columns):
            region = codes[row * height // grid_rows : (row + 1) * height // grid_rows,
                           col * width // grid_columns : (col + 1) * width // grid_columns]
            hist, _ = np.histogram(region, bins=edges)
            hist = hist.astype(np.float64)
            total = float(hist.sum())
            if total <= 0:
                raise invalid("INVALID_VECTOR", "Histogram LBP vùng rỗng", row=row, col=col)
            region_vectors.append(hist / total)
    vector = np.concatenate(region_vectors)
    return vector / float(vector.sum())


def _regions(rgb: np.ndarray, grid):
    height, width = rgb.shape[:2]
    for row in range(grid[0]):
        for col in range(grid[1]):
            yield rgb[row * height // grid[0]:(row + 1) * height // grid[0],
                      col * width // grid[1]:(col + 1) * width // grid[1]]


def extract_spatial_hsv(rgb: np.ndarray, parameters: dict) -> np.ndarray:
    if "spatial_prior" in parameters:
        return weighted_hsv(rgb, parameters, spatial=True)
    vectors = [extract_hsv(region, parameters) for region in _regions(rgb, parameters["grid"])]
    return np.concatenate(vectors) / len(vectors)


def extract_color_moments(rgb: np.ndarray, parameters: dict) -> np.ndarray:
    if "spatial_prior" in parameters:
        return weighted_color_moments(rgb, parameters)
    vectors = []
    for region in _regions(rgb, parameters["grid"]):
        pixels = region.reshape(-1, 3).astype(np.float64) / 255.0
        means = pixels.mean(axis=0)
        centered = pixels - means
        stds = np.sqrt(np.mean(centered ** 2, axis=0))
        third = np.cbrt(np.mean(centered ** 3, axis=0))
        # Region-major, channel-major, then mean/std/mapped third moment.
        vectors.append(np.stack((means, stds, (third + 1.0) / 2.0), axis=1).ravel())
    return np.concatenate(vectors)


def extract_glcm(rgb: np.ndarray, parameters: dict) -> np.ndarray:
    if "spatial_prior" in parameters:
        return weighted_glcm(rgb, parameters)
    levels = parameters["levels"]
    gray = np.rint(color.rgb2gray(rgb) * 255.0).astype(np.uint8)
    quantized = (gray.astype(np.uint16) * levels // 256).astype(np.uint8)
    matrix = graycomatrix(quantized, parameters["distances"],
                         np.deg2rad(parameters["angles_degrees"]), levels=levels,
                         symmetric=parameters["symmetric"], normed=parameters["normed"])
    vectors = []
    for prop in parameters["properties"]:
        values = graycoprops(matrix, prop)
        if prop == "contrast":
            values = values / (levels - 1) ** 2
        elif prop == "dissimilarity":
            values = values / (levels - 1)
        elif prop == "correlation":
            values = (values + 1.0) / 2.0
        vectors.append(values.ravel())
    return np.concatenate(vectors)


EXTRA_EXTRACTORS = {"spatial_hsv": extract_spatial_hsv, "color_moments": extract_color_moments,
                    "glcm": extract_glcm}


def extract_features(image: ProcessedImage, config: BundleConfig) -> FeatureBundle:
    _validate_input(image, config)
    hsv = extract_hsv(image.rgb, config.hsv.parameters)
    hog_vector = extract_hog(image.rgb, parameters=config.hog.parameters)
    lbp = extract_lbp(image.rgb, config.lbp.parameters)
    warnings: list[str] = []
    if float(np.linalg.norm(hog_vector)) <= 1e-12:
        warnings.append("zero_gradient")

    extras = {name: EXTRA_EXTRACTORS[name](image.rgb, spec.parameters) for name, spec in config.extras.items()}
    vectors = {"hsv": hsv, "hog": hog_vector, "lbp": lbp, **extras}
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
        if not np.isfinite(vector).all() or (vector < -1e-12).any():
            raise invalid("INVALID_VECTOR", "Vector chứa giá trị không hữu hạn hoặc âm", feature=name)
        if config.configs[name].parameters.get("normalization") == "bounded" and (vector > 1 + 1e-12).any():
            raise invalid("INVALID_VECTOR", "Vector vượt miền chuẩn hóa [0,1]", feature=name)
    return FeatureBundle(
        hsv=hsv,
        hog=hog_vector,
        lbp=lbp,
        config_ids=config.config_ids,
        warnings=tuple(warnings),
        preprocess_version=image.preprocess_version,
        extras=extras,
        similarities={name: spec.parameters["similarity"] for name, spec in config.configs.items() if "similarity" in spec.parameters},
        config_signature=config.signature,
    )

