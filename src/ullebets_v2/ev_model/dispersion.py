from __future__ import annotations

import numpy as np


POISSON_LIMIT_DISPERSION = 1_000_000.0


def estimate_nb_dispersion(
    actual: np.ndarray,
    predicted_mean: np.ndarray,
) -> float:
    y = np.asarray(actual, dtype=float)
    mean = np.clip(np.asarray(predicted_mean, dtype=float), 1e-9, None)
    if y.shape != mean.shape:
        raise ValueError("actual and predicted_mean must have equal shapes")
    denominator = float(np.square(mean).sum())
    if denominator <= 0:
        return POISSON_LIMIT_DISPERSION
    alpha = float((np.square(y - mean) - y).sum()) / denominator
    if alpha <= 1e-6:
        return POISSON_LIMIT_DISPERSION
    return float(np.clip(1.0 / alpha, 0.1, POISSON_LIMIT_DISPERSION))
