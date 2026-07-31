from __future__ import annotations

import math

from scipy.optimize import brentq

from ullebets_v2.ev_model.probabilities import poisson_line_probabilities


def fair_over_probability(
    *,
    over_odds: float,
    under_odds: float | None,
) -> float:
    if not math.isfinite(over_odds) or over_odds <= 1.0:
        raise ValueError("over_odds must be greater than one")
    implied_over = 1.0 / over_odds
    if under_odds is None or not math.isfinite(under_odds):
        return implied_over
    if under_odds <= 1.0:
        raise ValueError("under_odds must be greater than one")
    implied_under = 1.0 / under_odds
    return implied_over / (implied_over + implied_under)


def infer_poisson_mean(
    *,
    line: float,
    win_probability: float,
    direction: str,
) -> float:
    if not 0.0 < win_probability < 1.0:
        raise ValueError("win_probability must be strictly between zero and one")

    def objective(mean: float) -> float:
        return (
            poisson_line_probabilities(
                mean=mean,
                line=line,
                direction=direction,
            ).win
            - win_probability
        )

    upper_bound = max(100.0, line * 5.0 + 50.0)
    return float(brentq(objective, 1e-9, upper_bound, xtol=1e-10))
