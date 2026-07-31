from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


def _market_side_probability(frame: pd.DataFrame) -> pd.Series:
    over_probability = pd.to_numeric(
        frame["market_fair_probability_over"],
        errors="coerce",
    )
    return pd.Series(
        np.where(
            frame["direction"].eq("over"),
            over_probability,
            1.0 - over_probability,
        ),
        index=frame.index,
        dtype=float,
    )


def apply_market_probability_blend(
    predictions: pd.DataFrame,
    *,
    alpha: float,
) -> pd.DataFrame:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be between zero and one")
    blended = predictions.copy()
    market_probability = _market_side_probability(blended)
    model_probability = pd.to_numeric(
        blended["predicted_win_probability"],
        errors="coerce",
    )
    blended["market_side_probability"] = market_probability
    blended["blend_alpha"] = float(alpha)
    blended["blended_win_probability"] = (
        market_probability
        + float(alpha) * (model_probability - market_probability)
    )
    blended["blended_expected_roi_units"] = (
        blended["blended_win_probability"]
        * pd.to_numeric(blended["offered_odds"], errors="coerce")
        - 1.0
    )
    return blended


def select_blended_policy_bets(
    predictions: pd.DataFrame,
    *,
    minimum_ev: float,
    maximum_ev: float | None,
    maximum_bets_per_match: int | None,
) -> pd.DataFrame:
    selected = predictions[
        predictions["blended_expected_roi_units"].gt(minimum_ev)
    ].copy()
    if maximum_ev is not None:
        selected = selected[
            selected["blended_expected_roi_units"].lt(maximum_ev)
        ].copy()
    if selected.empty:
        return selected

    model_sort = (
        ["model_name"]
        if "model_name" in selected.columns
        else []
    )
    selected = selected.sort_values(
        model_sort
        + ["sample_key", "blended_expected_roi_units"],
        ascending=[True] * len(model_sort) + [True, False],
    ).drop_duplicates(
        subset=model_sort + ["sample_key"],
        keep="first",
    )
    if maximum_bets_per_match is not None:
        if maximum_bets_per_match <= 0:
            raise ValueError(
                "maximum_bets_per_match must be positive"
            )
        selected = (
            selected.sort_values(
                [
                    *model_sort,
                    "exposure_match_id",
                    "blended_expected_roi_units",
                    "sample_key",
                ],
                ascending=(
                    [True] * len(model_sort)
                    + [True, False, True]
                ),
            )
            .groupby(
                model_sort + ["exposure_match_id"],
                sort=False,
                group_keys=False,
            )
            .head(maximum_bets_per_match)
        )
    return selected.reset_index(drop=True)


def _market_level_rows(predictions: pd.DataFrame) -> pd.DataFrame:
    market_rows = predictions.sort_values(
        ["test_start", "sample_key", "direction"]
    ).drop_duplicates(
        ["test_start", "sample_key"],
        keep="first",
    )
    return market_rows[
        market_rows["is_over_win"].notna()
        & market_rows["predicted_over_probability"].notna()
        & market_rows["market_fair_probability_over"].notna()
    ].copy()


def _select_brier_alpha(
    prior_market_rows: pd.DataFrame,
    *,
    alpha_grid: Iterable[float],
) -> tuple[float, list[dict[str, float]]]:
    actual = pd.to_numeric(
        prior_market_rows["is_over_win"],
        errors="coerce",
    )
    model = pd.to_numeric(
        prior_market_rows["predicted_over_probability"],
        errors="coerce",
    )
    market = pd.to_numeric(
        prior_market_rows["market_fair_probability_over"],
        errors="coerce",
    )
    candidates: list[dict[str, float]] = []
    for raw_alpha in alpha_grid:
        alpha = float(raw_alpha)
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha grid values must be between zero and one")
        blended = market + alpha * (model - market)
        candidates.append(
            {
                "alpha": alpha,
                "brier": float(np.mean(np.square(blended - actual))),
            }
        )
    if not candidates:
        raise ValueError("alpha_grid must not be empty")
    best = min(
        candidates,
        key=lambda row: (row["brier"], -row["alpha"]),
    )
    return float(best["alpha"]), candidates


def run_nested_brier_blend_policy(
    predictions: pd.DataFrame,
    *,
    alpha_grid: Iterable[float],
    minimum_history_windows: int,
    minimum_ev: float,
    maximum_ev: float | None,
    maximum_bets_per_match: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if minimum_history_windows < 1:
        raise ValueError("minimum_history_windows must be positive")
    frame = predictions.copy()
    windows = sorted(
        str(value)
        for value in frame["test_start"].dropna().unique()
    )
    market_rows = _market_level_rows(frame)
    selection_parts: list[pd.DataFrame] = []
    window_rows: list[dict[str, object]] = []

    for window_index, test_start in enumerate(windows):
        if window_index < minimum_history_windows:
            continue
        prior_windows = set(windows[:window_index])
        prior = market_rows[
            market_rows["test_start"].astype(str).isin(prior_windows)
        ]
        if prior.empty:
            continue
        selected_alpha, brier_candidates = _select_brier_alpha(
            prior,
            alpha_grid=alpha_grid,
        )
        current = frame[
            frame["test_start"].astype(str).eq(test_start)
        ]
        blended = apply_market_probability_blend(
            current,
            alpha=selected_alpha,
        )
        selected = select_blended_policy_bets(
            blended,
            minimum_ev=minimum_ev,
            maximum_ev=maximum_ev,
            maximum_bets_per_match=maximum_bets_per_match,
        )
        selected["policy_test_start"] = test_start
        selection_parts.append(selected)
        pnl = (
            float(
                pd.to_numeric(
                    selected["realized_roi_units"],
                    errors="coerce",
                ).sum()
            )
            if not selected.empty
            else 0.0
        )
        window_rows.append(
            {
                "test_start": test_start,
                "prior_window_count": window_index,
                "prior_prediction_rows": int(len(prior)),
                "selected_alpha": selected_alpha,
                "alpha_brier": brier_candidates,
                "bets": int(len(selected)),
                "pnl_units": pnl,
                "roi_pct": (
                    pnl / len(selected) * 100.0
                    if len(selected)
                    else 0.0
                ),
            }
        )

    selections = (
        pd.concat(selection_parts, ignore_index=True)
        if selection_parts
        else pd.DataFrame()
    )
    return selections, pd.DataFrame(window_rows)
