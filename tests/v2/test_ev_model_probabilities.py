from __future__ import annotations

from math import exp, factorial

import pytest

from ullebets_v2.ev_model.probabilities import (
    expected_roi,
    negative_binomial_line_probabilities,
    poisson_line_probabilities,
)


def test_half_line_has_no_push_probability() -> None:
    probabilities = poisson_line_probabilities(mean=10.0, line=10.5, direction="over")

    assert probabilities.push == 0.0
    assert probabilities.win + probabilities.loss == pytest.approx(1.0)


def test_integer_line_keeps_push_separate_from_win_and_loss() -> None:
    probabilities = poisson_line_probabilities(mean=10.0, line=10.0, direction="over")
    expected_push = exp(-10.0) * (10.0**10) / factorial(10)

    assert probabilities.push == pytest.approx(expected_push)
    assert probabilities.win + probabilities.push + probabilities.loss == pytest.approx(1.0)


def test_expected_roi_treats_push_as_zero_profit() -> None:
    roi = expected_roi(win_probability=0.50, push_probability=0.10, decimal_odds=1.90)

    assert roi == pytest.approx(0.05)


def test_negative_binomial_probabilities_preserve_all_outcomes() -> None:
    probabilities = negative_binomial_line_probabilities(
        mean=10.0,
        dispersion=4.0,
        line=10.0,
        direction="under",
    )

    assert probabilities.win + probabilities.push + probabilities.loss == pytest.approx(1.0)
    assert probabilities.push > 0.0


def test_large_negative_binomial_dispersion_approaches_poisson() -> None:
    poisson_probabilities = poisson_line_probabilities(
        mean=8.0,
        line=8.5,
        direction="over",
    )
    negative_binomial_probabilities = negative_binomial_line_probabilities(
        mean=8.0,
        dispersion=1_000_000.0,
        line=8.5,
        direction="over",
    )

    assert negative_binomial_probabilities.win == pytest.approx(
        poisson_probabilities.win,
        abs=1e-5,
    )
