from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd

from ullebets_v2.ev_model.probabilities import (
    expected_roi,
    negative_binomial_line_probabilities,
    poisson_line_probabilities,
)


def _settle(actual: float, line: float, direction: str) -> tuple[str, float]:
    if math.isclose(actual, line, rel_tol=0.0, abs_tol=1e-9):
        return "push", 0.0
    won = actual > line if direction == "over" else actual < line
    return ("win", 1.0) if won else ("loss", -1.0)


def score_market_rows(
    frame: pd.DataFrame,
    *,
    predicted_means: Iterable[float],
    minimum_ev: float,
    distribution: str = "poisson",
    dispersions: Iterable[float] | None = None,
) -> pd.DataFrame:
    means = list(predicted_means)
    if len(means) != len(frame):
        raise ValueError("predicted_means must match the frame length")
    if distribution not in {"poisson", "negative_binomial"}:
        raise ValueError("distribution must be poisson or negative_binomial")
    dispersion_values = (
        list(dispersions)
        if dispersions is not None
        else [math.nan] * len(frame)
    )
    if len(dispersion_values) != len(frame):
        raise ValueError("dispersions must match the frame length")

    selections: list[dict] = []
    for row, mean, dispersion in zip(
        frame.itertuples(index=False),
        means,
        dispersion_values,
        strict=True,
    ):
        if not math.isfinite(float(mean)) or float(mean) < 0:
            continue
        line = float(row.line_value)
        candidates: list[tuple[str, float, float, float, float]] = []
        for direction, odds_value in (
            ("over", getattr(row, "over_odds", None)),
            ("under", getattr(row, "under_odds", None)),
        ):
            if odds_value is None or pd.isna(odds_value):
                continue
            if distribution == "negative_binomial":
                probabilities = negative_binomial_line_probabilities(
                    mean=float(mean),
                    dispersion=float(dispersion),
                    line=line,
                    direction=direction,
                )
            else:
                probabilities = poisson_line_probabilities(
                    mean=float(mean),
                    line=line,
                    direction=direction,
                )
            ev = expected_roi(
                win_probability=probabilities.win,
                push_probability=probabilities.push,
                decimal_odds=float(odds_value),
            )
            candidates.append(
                (
                    direction,
                    float(odds_value),
                    probabilities.win,
                    probabilities.push,
                    ev,
                )
            )
        if not candidates:
            continue
        direction, odds, win_probability, push_probability, ev = max(
            candidates,
            key=lambda candidate: candidate[-1],
        )
        if ev <= minimum_ev:
            continue

        settlement_result, unit_sign = _settle(
            float(row.actual_value),
            line,
            direction,
        )
        realized_roi_units = (
            odds - 1.0
            if unit_sign > 0
            else unit_sign
        )
        selections.append(
            {
                "sample_key": row.sample_key,
                "exposure_match_id": row.exposure_match_id,
                "match_date": row.match_date,
                "stat_key": row.stat_key,
                "period": row.period,
                "scope": row.scope,
                "line_value": line,
                "direction": direction,
                "selected_odds": odds,
                "predicted_mean": float(mean),
                "predicted_win_probability": win_probability,
                "predicted_push_probability": push_probability,
                "expected_roi_units": ev,
                "distribution": distribution,
                "dispersion": (
                    float(dispersion)
                    if distribution == "negative_binomial"
                    else None
                ),
                "actual_value": float(row.actual_value),
                "settlement_result": settlement_result,
                "realized_roi_units": realized_roi_units,
            }
        )
    return pd.DataFrame(selections)
