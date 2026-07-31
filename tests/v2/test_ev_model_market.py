from __future__ import annotations

import pytest

from ullebets_v2.ev_model.market import (
    fair_over_probability,
    infer_poisson_mean,
)
from ullebets_v2.ev_model.probabilities import poisson_line_probabilities


def test_two_sided_market_probability_removes_overround() -> None:
    probability = fair_over_probability(over_odds=1.80, under_odds=2.00)

    assert probability == pytest.approx((1 / 1.80) / ((1 / 1.80) + (1 / 2.00)))


def test_over_only_market_uses_break_even_probability() -> None:
    probability = fair_over_probability(over_odds=2.00, under_odds=None)

    assert probability == pytest.approx(0.50)


def test_market_probability_can_be_inverted_to_poisson_mean() -> None:
    probability = poisson_line_probabilities(
        mean=10.0,
        line=10.5,
        direction="over",
    ).win

    inferred = infer_poisson_mean(
        line=10.5,
        win_probability=probability,
        direction="over",
    )

    assert inferred == pytest.approx(10.0, abs=1e-6)
