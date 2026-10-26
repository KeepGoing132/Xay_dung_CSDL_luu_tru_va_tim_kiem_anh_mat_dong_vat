"""Gabor đa hướng/đa tần số theo vùng; không còn Haar và histogram cạnh của cấu hình cũ."""
from functools import lru_cache
import numpy as np
from scipy.signal import fftconvolve
from skimage import color, filters, transform
from .spatial_features import regions, spatial_weights

def _gray(rgb, parameters):
    size = parameters["analysis_size"]
    return transform.resize(color.rgb2gray(rgb), (size, size), order=1,
                            mode="reflect", anti_aliasing=True, preserve_range=True)

def _weighted_statistics(values, weights):
    mass = weights / weights.sum()
    mean = float(np.sum(values * mass))
    return mean, float(np.sqrt(np.sum((values - mean)**2 * mass)))

@lru_cache(maxsize=64)
def _gabor_kernel(frequency, angle, bandwidth, n_stds):
    kernel = filters.gabor_kernel(frequency, theta=np.deg2rad(angle),
                                  bandwidth=bandwidth, n_stds=n_stds)
    # Remove DC response, normalize complex L1 mass, then cache read-only kernels.
    kernel = kernel - kernel.mean()
    kernel /= np.abs(kernel).sum()
    kernel.flags.writeable = False
    return kernel

def extract_gabor(rgb, parameters):
    gray = _gray(rgb, parameters)
    weights = spatial_weights(gray.shape, parameters["spatial_prior"])
    result = []
    for frequency in parameters["frequencies"]:
        for angle in parameters["angles_degrees"]:
            kernel = _gabor_kernel(frequency, angle, parameters["bandwidth"], parameters["n_stds"])
            py, px = (value // 2 for value in kernel.shape)
            padded = np.pad(gray, ((py, py), (px, px)), mode=parameters["boundary"])
            magnitude = np.abs(fftconvolve(padded, kernel, mode="valid"))
            for area in regions(gray.shape, parameters["grid"]):
                result.extend(_weighted_statistics(magnitude[area], weights[area]))
    return np.clip(np.asarray(result), 0., 1.)
