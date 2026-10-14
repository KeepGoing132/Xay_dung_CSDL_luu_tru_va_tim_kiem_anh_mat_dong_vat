"""Spatially weighted descriptors. The prior is geometry, not a detected face mask."""
from __future__ import annotations

import numpy as np
from skimage import color
from skimage.feature import hog, local_binary_pattern, graycoprops


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


def weighted_lbp(rgb, parameters):
    gray = np.rint(color.rgb2gray(rgb) * 255).astype(np.uint8)
    weights = spatial_weights(rgb.shape, parameters["spatial_prior"])
    parts = []
    for scale in parameters["scales"]:
        points = scale["points"]
        codes = local_binary_pattern(gray, P=points, R=scale["radius"], method=parameters["method"])
        region_parts = [np.histogram(codes[area], bins=np.arange(-.5, points+2.5),
                                     weights=weights[area])[0]
                        for area in regions(rgb.shape, parameters["grid"])]
        vector = np.concatenate(region_parts)
        parts.append(vector / vector.sum())
    return np.concatenate(parts) / len(parts)


def weighted_color_moments(rgb, parameters):
    weights = spatial_weights(rgb.shape, parameters["spatial_prior"])
    parts = []
    for area in regions(rgb.shape, parameters["grid"]):
        pixels = rgb[area].reshape(-1, 3).astype(np.float64) / 255
        mass = weights[area].ravel()
        mass /= mass.sum()
        average = np.sum(pixels * mass[:, None], axis=0)
        centered = pixels - average
        std = np.sqrt(np.sum(centered**2 * mass[:, None], axis=0))
        third = np.cbrt(np.sum(centered**3 * mass[:, None], axis=0))
        parts.append(np.stack((average, std, (third+1)/2), axis=1).ravel())
    return np.concatenate(parts)


def weighted_glcm_matrix(gray, weights, parameters):
    levels = parameters["levels"]
    quantized = (gray.astype(np.uint16) * levels // 256).astype(np.uint8)
    distances, angles = parameters["distances"], np.deg2rad(parameters["angles_degrees"])
    matrix = np.zeros((levels, levels, len(distances), len(angles)), dtype=np.float64)
    h, w = gray.shape
    for di, distance in enumerate(distances):
        for ai, angle in enumerate(angles):
            dy, dx = int(np.rint(distance*np.sin(angle))), int(np.rint(distance*np.cos(angle)))
            a = (slice(max(0, -dy), min(h, h-dy)), slice(max(0, -dx), min(w, w-dx)))
            b = (slice(max(0, dy), min(h, h+dy)), slice(max(0, dx), min(w, w+dx)))
            codes = quantized[a].astype(np.int64)*levels + quantized[b]
            mass = np.sqrt(weights[a]*weights[b])
            counts = np.bincount(codes.ravel(), weights=mass.ravel(), minlength=levels**2).reshape(levels, levels)
            if parameters["symmetric"]:
                counts += counts.T.copy()
            matrix[:, :, di, ai] = counts / counts.sum()
    return matrix


def weighted_glcm(rgb, parameters):
    gray = np.rint(color.rgb2gray(rgb)*255).astype(np.uint8)
    matrix = weighted_glcm_matrix(gray, spatial_weights(rgb.shape, parameters["spatial_prior"]), parameters)
    parts = []
    for prop in parameters["properties"]:
        values = graycoprops(matrix, prop)
        if prop == "contrast":
            values /= (parameters["levels"]-1)**2
        elif prop == "dissimilarity":
            values /= parameters["levels"]-1
        elif prop == "correlation":
            values = (values+1)/2
        parts.append(values.ravel())
    return np.concatenate(parts)
