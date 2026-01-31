from __future__ import annotations

import numpy as np
from PIL import Image


def _to_gray(img: Image.Image) -> np.ndarray:
    arr = np.asarray(img).astype(np.float32) / 255.0
    return 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]


def _sobel_edges(gray: np.ndarray) -> np.ndarray:
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
    ky = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32)

    padded = np.pad(gray, 1, mode="edge")
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)

    for y in range(gray.shape[0]):
        for x in range(gray.shape[1]):
            region = padded[y : y + 3, x : x + 3]
            gx[y, x] = np.sum(region * kx)
            gy[y, x] = np.sum(region * ky)

    mag = np.sqrt(gx ** 2 + gy ** 2)
    return mag / (mag.max() + 1e-6)


def _gram_matrix(gray: np.ndarray) -> np.ndarray:
    h, w = gray.shape
    features = gray.reshape(1, h * w)
    gram = features @ features.T / (h * w)
    return gram


def _fft_magnitude(gray: np.ndarray) -> np.ndarray:
    fft = np.fft.fft2(gray)
    mag = np.abs(fft)
    mag = np.fft.fftshift(mag)
    return mag / (mag.max() + 1e-6)


def _normalized_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.abs(a - b)))


def score_pair(input_img: Image.Image, render_img: Image.Image, weights: dict) -> dict:
    input_gray = _to_gray(input_img)
    render_gray = _to_gray(render_img)

    gram_in = _gram_matrix(input_gray)
    gram_out = _gram_matrix(render_gray)
    gram_dist = _normalized_distance(gram_in, gram_out)

    fft_in = _fft_magnitude(input_gray)
    fft_out = _fft_magnitude(render_gray)
    fft_dist = _normalized_distance(fft_in, fft_out)

    edge_in = _sobel_edges(input_gray)
    edge_out = _sobel_edges(render_gray)
    edge_dist = _normalized_distance(edge_in, edge_out)

    # Convert distances to similarity-like scores.
    gram_score = 1.0 - gram_dist
    fft_score = 1.0 - fft_dist
    edge_score = 1.0 - edge_dist

    w_fft = float(weights.get("fft", 0.4))
    w_edge = float(weights.get("edge", 0.3))
    w_gram = float(weights.get("gram", 0.3))
    total = max(w_fft + w_edge + w_gram, 1e-6)

    composite = (fft_score * w_fft + edge_score * w_edge + gram_score * w_gram) / total

    return {
        "fft": fft_score,
        "edge": edge_score,
        "gram": gram_score,
        "composite": composite,
    }
