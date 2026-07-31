from __future__ import annotations

import numpy as np
import pytest

from ullebets_v2.ev_model.dispersion import estimate_nb_dispersion


def test_dispersion_estimator_detects_variance_above_poisson() -> None:
    actual = np.array([0.0, 10.0] * 50)
    predicted_mean = np.full(100, 5.0)

    dispersion = estimate_nb_dispersion(actual, predicted_mean)

    assert dispersion == pytest.approx(1.25)


def test_dispersion_estimator_uses_poisson_limit_when_not_overdispersed() -> None:
    actual = np.full(100, 5.0)
    predicted_mean = np.full(100, 5.0)

    dispersion = estimate_nb_dispersion(actual, predicted_mean)

    assert dispersion == 1_000_000.0
