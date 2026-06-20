from __future__ import annotations

import math


def roi_units(result: str, odds_decimal: float) -> float:
    if result == "win":
        return float(odds_decimal) - 1.0
    if result == "push":
        return 0.0
    return -1.0


def poisson_pmf(k: int, lam: float) -> float:
    if lam is None or lam < 0:
        return 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def poisson_cdf(k: int, lam: float) -> float:
    if k < 0:
        return 0.0
    total = 0.0
    for value in range(0, k + 1):
        total += poisson_pmf(value, lam)
    return min(max(total, 0.0), 1.0)


def poisson_probabilities_for_line(lam: float, line_value: float) -> tuple[float, float, float]:
    if lam is None or line_value is None:
        return 0.0, 0.0, 0.0

    integer_line = abs(line_value - round(line_value)) < 1e-9
    if integer_line:
        line_int = int(round(line_value))
        p_push = poisson_pmf(line_int, lam)
        p_over = 1.0 - poisson_cdf(line_int, lam)
        p_under = poisson_cdf(line_int - 1, lam)
    else:
        floor_line = math.floor(line_value)
        p_push = 0.0
        p_over = 1.0 - poisson_cdf(floor_line, lam)
        p_under = poisson_cdf(floor_line, lam)
    return p_over, p_under, p_push


def expected_roi_for_side(prob_win: float, prob_push: float, odds_decimal: float) -> float | None:
    if odds_decimal is None or odds_decimal <= 1:
        return None
    prob_loss = 1.0 - prob_win - prob_push
    return prob_win * (odds_decimal - 1.0) - prob_loss
