"""Spatially weighted HOG and regional HSV; no detected face landmarks."""
import numpy as np
from skimage import color
from skimage.feature import hog


def spatial_weights(shape, prior):
    height, width = shape[:2]
    y, x = np.mgrid[:height, :width]
    cx, cy = prior["center"]
    rx, ry = prior["radii"]
    radius = np.sqrt((((x + .5) / width - cx) / rx) ** 2 +
                     (((y + .5) / height - cy) / ry) ** 2)
    falloff = .5 * (1 + np.cos(np.pi * np.minimum(radius, 1)))
    return prior["floor"] + (1 - prior["floor"]) * falloff

def regions(shape, grid):
    h, w = shape[:2]
    for row in range(grid[0]):
        for col in range(grid[1]):
            yield (slice(row*h//grid[0], (row+1)*h//grid[0]),
                   slice(col*w//grid[1], (col+1)*w//grid[1]))

def weighted_hsv(rgb, parameters, spatial=False):
    hsv = color.rgb2hsv(rgb.astype(np.float32) / 255.)
    weights = spatial_weights(rgb.shape, parameters["spatial_prior"])
    parts = []
    for area in regions(rgb.shape, parameters["grid"] if spatial else [1, 1]):
        hist, _ = np.histogramdd(hsv[area].reshape(-1, 3), bins=parameters["bins"],
                                range=parameters["ranges"], weights=weights[area].ravel())
        parts.append(hist.ravel())
    vector = np.concatenate(parts)
    return vector / vector.sum()

def weighted_hog(rgb, parameters, visualize=False):
    gray = color.rgb2gray(rgb)
    prior = spatial_weights(rgb.shape, parameters["spatial_prior"])
    parts, pictures = [], []
    scales = parameters["scales"]
    total_weight = sum(scale["weight"] for scale in scales)
    by, bx = parameters["cells_per_block"]
    for scale in scales:
        cy, cx = scale["pixels_per_cell"]
        result = hog(gray, orientations=parameters["orientations"], pixels_per_cell=(cy, cx),
                     cells_per_block=(by, bx), block_norm=parameters["block_norm"],
                     transform_sqrt=parameters["transform_sqrt"], feature_vector=False, visualize=visualize)
        vector, picture = result if visualize else (result, None)
        # Average the prior over each block; do not paint artificial edges onto RGB.
        block_weights = np.empty(vector.shape[:2])
        for row in range(vector.shape[0]):
            for col in range(vector.shape[1]):
                block_weights[row, col] = prior[row*cy:(row+by)*cy, col*cx:(col+bx)*cx].mean()
        vector = (vector * np.sqrt(block_weights)[..., None, None, None]).ravel()
        norm = np.linalg.norm(vector)
        if norm > parameters["epsilon"]:
            vector /= norm
        else:
            vector[:] = 0
        parts.append(vector * np.sqrt(scale["weight"] / total_weight))
        if visualize:
            pictures.append(picture * np.sqrt(prior) * scale["weight"] / total_weight)
    vector = np.concatenate(parts)
    norm = np.linalg.norm(vector)
    if norm > parameters["epsilon"]:
        vector /= norm
    return (vector, sum(pictures)) if visualize else vector
