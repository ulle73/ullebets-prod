from __future__ import annotations

from dataclasses import dataclass
import math

from scipy.stats import nbinom, poisson


@dataclass(frozen=True)
class LineProbabilities:
    win: float
    push: float
    loss: float


def poisson_line_probabilities(
    *,
    mean: float,
    line: float,
    direction: str,
) -> LineProbabilities:
    if not math.isfinite(mean) or mean < 0:
        raise ValueError("mean must be a finite non-negative number")
    if not math.isfinite(line) or line < 0:
        raise ValueError("line must be a finite non-negative number")
    normalized_direction = direction.lower()
    if normalized_direction not in {"over", "under"}:
        raise ValueError("direction must be over or under")

    integer_line = float(line).is_integer()
    boundary = int(line)
    push = float(poisson.pmf(boundary, mean)) if integer_line else 0.0

    if normalized_direction == "over":
        win_floor = boundary if integer_line else math.floor(line)
        win = float(poisson.sf(win_floor, mean))
        loss = float(poisson.cdf(boundary - 1, mean)) if integer_line else 1.0 - win
    else:
        win_ceiling = boundary - 1 if integer_line else math.floor(line)
        win = float(poisson.cdf(win_ceiling, mean))
        loss = float(poisson.sf(boundary, mean)) if integer_line else 1.0 - win

    return LineProbabilities(win=win, push=push, loss=loss)


def negative_binomial_line_probabilities(
    *,
    mean: float,
    dispersion: float,
    line: float,
    direction: str,
) -> LineProbabilities:
    if not math.isfinite(mean) or mean < 0:
        raise ValueError("mean must be a finite non-negative number")
    if not math.isfinite(dispersion) or dispersion <= 0:
        raise ValueError("dispersion must be a finite positive number")
    if not math.isfinite(line) or line < 0:
        raise ValueError("line must be a finite non-negative number")
    normalized_direction = direction.lower()
    if normalized_direction not in {"over", "under"}:
        raise ValueError("direction must be over or under")
    if mean == 0:
        actual = 0.0
        if math.isclose(actual, line, rel_tol=0.0, abs_tol=1e-12):
            return LineProbabilities(win=0.0, push=1.0, loss=0.0)
        won = actual > line if normalized_direction == "over" else actual < line
        return LineProbabilities(
            win=1.0 if won else 0.0,
            push=0.0,
            loss=0.0 if won else 1.0,
        )

    success_probability = dispersion / (dispersion + mean)
    integer_line = float(line).is_integer()
    boundary = int(line)
    push = (
        float(nbinom.pmf(boundary, dispersion, success_probability))
        if integer_line
        else 0.0
    )

    if normalized_direction == "over":
        win_floor = boundary if integer_line else math.floor(line)
        win = float(nbinom.sf(win_floor, dispersion, success_probability))
        loss = (
            float(nbinom.cdf(boundary - 1, dispersion, success_probability))
            if integer_line
            else 1.0 - win
        )
    else:
        win_ceiling = boundary - 1 if integer_line else math.floor(line)
        win = float(nbinom.cdf(win_ceiling, dispersion, success_probability))
        loss = (
            float(nbinom.sf(boundary, dispersion, success_probability))
            if integer_line
            else 1.0 - win
        )
    return LineProbabilities(win=win, push=push, loss=loss)


def expected_roi(
    *,
    win_probability: float,
    push_probability: float,
    decimal_odds: float,
) -> float:
    if not 0.0 <= win_probability <= 1.0:
        raise ValueError("win_probability must be between zero and one")
    if not 0.0 <= push_probability <= 1.0:
        raise ValueError("push_probability must be between zero and one")
    if win_probability + push_probability > 1.0 + 1e-12:
        raise ValueError("win and push probabilities cannot exceed one")
    if not math.isfinite(decimal_odds) or decimal_odds <= 1.0:
        raise ValueError("decimal_odds must be greater than one")

    loss_probability = max(0.0, 1.0 - win_probability - push_probability)
    return win_probability * (decimal_odds - 1.0) - loss_probability
