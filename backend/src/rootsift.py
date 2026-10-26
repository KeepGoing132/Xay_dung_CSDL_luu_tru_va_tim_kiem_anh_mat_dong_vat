"""Dense RootSIFT descriptors pooled with VLAD, the fifth descriptor group.

Ảnh đã ở RGB 512 và đã ghép nền trắng. Descriptor được lấy trên lưới đều bên trong vùng
trọng số elliptic (không dò keypoint), ở ba mức làm mờ; mỗi descriptor 4×4 ô × 8 hướng,
chuẩn hóa L2 → cắt 0.2 → L2 rồi RootSIFT (L1 + căn). VLAD gộp descriptor theo cụm của
codebook đóng băng (gallery-only, xem codebook.py), chuẩn hóa L2 từng cụm rồi L2 toàn vector.
Mọi bước tất định, không dùng ngẫu nhiên có trạng thái.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter
from skimage import color

from .errors import invalid
from .spatial_features import spatial_weights

ORIENTATION_FULL_BINS = 36


def _gray(rgb: np.ndarray) -> np.ndarray:
    return np.asarray(color.rgb2gray(rgb), dtype=np.float64)


def sample_locations(shape: tuple[int, int], weights: np.ndarray, step: int,
                     patch: int, threshold: float) -> tuple[np.ndarray, np.ndarray]:
    """Điểm lưới đều cách biên nửa patch và nằm trong vùng trọng số, theo thứ tự hàng-cột."""
    half = patch // 2
    ys = np.arange(half, shape[0] - half + 1, step)
    xs = np.arange(half, shape[1] - half + 1, step)
    grid_y, grid_x = np.meshgrid(ys, xs, indexing="ij")
    keep = weights[grid_y, grid_x] >= threshold
    return grid_y[keep], grid_x[keep]


def _patch_offsets(patch: int) -> tuple[np.ndarray, np.ndarray]:
    half = patch // 2
    offsets = np.arange(-half, half, dtype=np.float64) + 0.5
    return np.meshgrid(offsets, offsets, indexing="xy")  # (u theo x, v theo y)


def _chunks(count: int, size: int):
    for start in range(0, count, size):
        yield slice(start, min(start + size, count))


def _descriptors_for_scale(gray: np.ndarray, rows: np.ndarray, cols: np.ndarray,
                           scale: dict, parameters: dict) -> np.ndarray:
    """Descriptor RootSIFT (N, 128) cho một mức làm mờ."""
    sigma = float(scale["sigma"])
    patch = int(scale["patch_size"])
    cell = int(scale["cell_size"])
    half = patch // 2
    cells = int(parameters["cells_per_descriptor"][0])
    bins = int(parameters["descriptor_bins"])
    blurred = gaussian_filter(gray, sigma=sigma, mode="reflect", truncate=3.0)
    grad_y, grad_x = np.gradient(blurred)
    magnitude = np.hypot(grad_x, grad_y)
    angle = np.arctan2(grad_y, grad_x) % (2 * np.pi)
    if magnitude.max() <= parameters["flat_patch_threshold"]:
        return np.zeros((0, cells * cells * bins), dtype=np.float64)

    # Hướng trội của từng điểm: histogram 36 bin trên cửa sổ nửa patch, lấy mẫu thưa.
    window = max(1, half)
    window_step = max(1, half // 4)
    window_offsets = np.arange(-window, window + 1, window_step, dtype=np.int64)
    off_u, off_v = np.meshgrid(window_offsets, window_offsets, indexing="xy")
    center_y = rows[:, None] + off_v.ravel()[None, :]
    center_x = cols[:, None] + off_u.ravel()[None, :]
    np.clip(center_y, 0, gray.shape[0] - 1, out=center_y)
    np.clip(center_x, 0, gray.shape[1] - 1, out=center_x)
    window_mass = magnitude[center_y, center_x]
    window_angle = angle[center_y, center_x]
    radius = np.hypot(off_u.ravel(), off_v.ravel())[None, :] / max(window, 1)
    window_mass = window_mass * np.exp(-0.5 * (radius * 1.5) ** 2)
    full_index = np.minimum((window_angle / (2 * np.pi) * ORIENTATION_FULL_BINS).astype(np.int64),
                            ORIENTATION_FULL_BINS - 1)
    point_index = np.repeat(np.arange(rows.size), full_index.shape[1])
    flat = point_index * ORIENTATION_FULL_BINS + full_index.ravel()
    orientation_hist = np.bincount(flat, weights=window_mass.ravel(),
                                   minlength=rows.size * ORIENTATION_FULL_BINS).reshape(rows.size, ORIENTATION_FULL_BINS)
    dominant = np.argmax(orientation_hist, axis=1)
    dominant_angle = (dominant + 0.5) * (2 * np.pi / ORIENTATION_FULL_BINS)

    off_x, off_y = _patch_offsets(patch)
    sample_x = off_x.ravel()
    sample_y = off_y.ravel()
    gaussian_window = np.exp(-0.5 * ((sample_x ** 2 + sample_y ** 2) / max(half, 1) ** 2))
    cell_x = np.clip(((sample_x + half) // cell).astype(np.int64), 0, cells - 1)
    cell_y = np.clip(((sample_y + half) // cell).astype(np.int64), 0, cells - 1)
    cell_index = cell_y * cells + cell_x

    output = []
    block = max(32, 65536 // sample_x.size)
    for span in _chunks(rows.size, block):
        cos_t = np.cos(dominant_angle[span])[:, None]
        sin_t = np.sin(dominant_angle[span])[:, None]
        position_x = np.rint(cols[span, None] + sample_x[None, :] * cos_t - sample_y[None, :] * sin_t)
        position_y = np.rint(rows[span, None] + sample_x[None, :] * sin_t + sample_y[None, :] * cos_t)
        np.clip(position_x, 0, gray.shape[1] - 1, out=position_x)
        np.clip(position_y, 0, gray.shape[0] - 1, out=position_y)
        weights = magnitude[position_y.astype(np.int64), position_x.astype(np.int64)] * gaussian_window[None, :]
        relative = (angle[position_y.astype(np.int64), position_x.astype(np.int64)]
                    - dominant_angle[span][:, None]) % (2 * np.pi)
        position = relative / (2 * np.pi) * bins
        lower = np.floor(position)
        fraction = position - lower
        low_bin = lower.astype(np.int64) % bins
        high_bin = (low_bin + 1) % bins
        histogram = np.zeros((position_x.shape[0], cells * cells * bins), dtype=np.float64)
        rows_index = np.repeat(np.arange(position_x.shape[0]), sample_x.size)
        width = cells * cells * bins
        low = (rows_index * width + (cell_index[None, :] * bins + low_bin).ravel())
        high = (rows_index * width + (cell_index[None, :] * bins + high_bin).ravel())
        histogram = (
            np.bincount(low, weights=(weights * (1 - fraction)).ravel(), minlength=position_x.shape[0] * width)
            + np.bincount(high, weights=(weights * fraction).ravel(), minlength=position_x.shape[0] * width)
        ).reshape(position_x.shape[0], width)
        norm = np.linalg.norm(histogram, axis=1, keepdims=True)
        usable = norm[:, 0] > parameters["flat_patch_threshold"]
        histogram = histogram[usable]
        if histogram.size:
            histogram /= np.linalg.norm(histogram, axis=1, keepdims=True)
            np.clip(histogram, None, parameters["clip"], out=histogram)
            histogram /= np.maximum(np.linalg.norm(histogram, axis=1, keepdims=True), 1e-12)
            histogram = np.sqrt(histogram / np.maximum(histogram.sum(axis=1, keepdims=True), 1e-12))
        output.append(histogram)
    return np.concatenate(output, axis=0) if output else np.zeros((0, cells * cells * bins))


def dense_rootsift(rgb: np.ndarray, parameters: dict) -> np.ndarray:
    """Toàn bộ descriptor RootSIFT của ảnh theo thứ tự mức làm mờ rồi thứ tự hàng-cột."""
    gray = _gray(rgb)
    prior = spatial_weights(gray.shape, parameters["spatial_prior"])
    descriptors = []
    for scale in parameters["scales"]:
        rows, cols = sample_locations(gray.shape, prior, int(scale["step"]),
                                      int(scale["patch_size"]), parameters["prior_threshold"])
        descriptors.append(_descriptors_for_scale(gray, rows, cols, scale, parameters))
    descriptors = [block for block in descriptors if block.size]
    if not descriptors:
        return np.zeros((0, int(parameters["descriptor_dimension"])), dtype=np.float64)
    return np.concatenate(descriptors, axis=0)


def vlad_encode(descriptors: np.ndarray, centroids: np.ndarray, *, intra_normalization: bool = True) -> np.ndarray:
    """VLAD: gán cụm gần nhất, cộng phần dư, chuẩn hóa L2 từng cụm rồi L2 toàn vector."""
    clusters, dimension = centroids.shape
    if descriptors.size == 0:
        return np.zeros(clusters * dimension, dtype=np.float64)
    if descriptors.shape[1] != dimension:
        raise invalid("CONFIG_MISMATCH", "Descriptor không khớp số chiều codebook",
                      descriptor=int(descriptors.shape[1]), codebook=dimension)
    # ||x-c||^2 = ||x||^2 - 2x·c + ||c||^2 nên argmax của x·c - ||c||^2/2 là cụm gần nhất.
    scores = descriptors @ centroids.T - 0.5 * np.sum(centroids ** 2, axis=1)[None, :]
    assignment = np.argmax(scores, axis=1)
    index = assignment[:, None] * dimension + np.arange(dimension)[None, :]
    residuals = np.bincount(index.ravel(),
                            weights=(descriptors - centroids[assignment]).ravel(),
                            minlength=clusters * dimension).reshape(clusters, dimension)
    if intra_normalization:
        norms = np.linalg.norm(residuals, axis=1, keepdims=True)
        residuals = residuals / np.maximum(norms, 1e-12)
    vector = residuals.ravel()
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 1e-12 else vector


def cluster_weights(vector: np.ndarray, clusters: int) -> np.ndarray:
    """Độ lớn phần dư theo cụm của một vector VLAD; bình phương cộng lại bằng 1."""
    return np.linalg.norm(np.asarray(vector, dtype=np.float64).reshape(clusters, -1), axis=1)


def _nearest_centroid(descriptors: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    scores = descriptors @ centroids.T - 0.5 * np.sum(centroids ** 2, axis=1)[None, :]
    return np.argmax(scores, axis=1)


def fit_codebook(descriptors: np.ndarray, clusters: int, *, seed: int, iterations: int) -> np.ndarray:
    """k-means (k-means++ khởi tạo theo seed) trên descriptor gallery; tất định với cùng đầu vào."""
    if descriptors.ndim != 2 or descriptors.shape[0] < clusters or clusters < 1:
        raise ValueError("Not enough descriptors to fit the codebook")
    rng = np.random.default_rng(seed)
    centroids = [descriptors[rng.integers(0, descriptors.shape[0])]]
    closest = np.full(descriptors.shape[0], np.inf)
    for _ in range(clusters - 1):
        distance = np.sum((descriptors - centroids[-1]) ** 2, axis=1)
        closest = np.minimum(closest, distance)
        total = float(closest.sum())
        if total <= 0:
            index = int(np.argmax(closest))  # giữ tất định khi mọi điểm đã trùng tâm
        else:
            index = int(np.searchsorted(np.cumsum(closest / total), rng.random(), side="right"))
            index = min(index, descriptors.shape[0] - 1)
        centroids.append(descriptors[index])
    centroids = np.asarray(centroids, dtype=np.float64)
    dimension = descriptors.shape[1]
    offsets = np.arange(dimension, dtype=np.int64)[None, :]
    for _ in range(iterations):
        assignment = _nearest_centroid(descriptors, centroids)
        flat = (assignment[:, None] * dimension + offsets).ravel()
        updated = np.bincount(flat, weights=descriptors.ravel(),
                              minlength=clusters * dimension).reshape(clusters, dimension)
        counts = np.bincount(assignment, minlength=clusters).astype(np.int64)
        empty = counts == 0
        if empty.any():
            distance = np.linalg.norm(descriptors - centroids[assignment], axis=1)
            for cluster in np.flatnonzero(empty):
                index = int(np.argmax(distance))
                updated[cluster] = descriptors[index]
                counts[cluster] = 1
                distance[index] = -1.0
        centroids = updated / counts[:, None]
    return centroids


def extract_rootsift_vlad(rgb: np.ndarray, parameters: dict) -> np.ndarray:
    codebook = parameters.get("vlad", {}).get("codebook_centroids")
    if codebook is None:
        raise invalid("CONFIG_MISMATCH", "Thiếu codebook VLAD đã đóng băng; chạy scripts/prepare_dataset.py",
                      path=str(parameters.get("vlad", {}).get("codebook", "")))
    centroids = np.asarray(codebook, dtype=np.float64)
    clusters, dimension = centroids.shape
    if (clusters, dimension) != (int(parameters["vlad"]["clusters"]), int(parameters["descriptor_dimension"])):
        raise invalid("CONFIG_MISMATCH", "Codebook không khớp cấu hình VLAD",
                      clusters=clusters, dimension=dimension)
    descriptors = dense_rootsift(rgb, parameters)
    return vlad_encode(descriptors, centroids,
                      intra_normalization=bool(parameters["vlad"]["intra_normalization"]))
