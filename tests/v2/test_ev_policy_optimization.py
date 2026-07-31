from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.policy_optimization import (
    apply_market_probability_blend,
    run_nested_brier_blend_policy,
    select_blended_policy_bets,
)


def test_market_probability_blend_recomputes_side_ev() -> None:
    rows = pd.DataFrame(
        [
            {
                "direction": "over",
                "market_fair_probability_over": 0.50,
                "predicted_win_probability": 0.70,
                "offered_odds": 2.0,
            },
            {
                "direction": "under",
                "market_fair_probability_over": 0.50,
                "predicted_win_probability": 0.60,
                "offered_odds": 2.0,
            },
        ]
    )

    blended = apply_market_probability_blend(rows, alpha=0.5)

    assert blended["blended_win_probability"].tolist() == pytest.approx(
        [0.60, 0.55]
    )
    assert blended["blended_expected_roi_units"].tolist() == pytest.approx(
        [0.20, 0.10]
    )


def test_policy_selection_caps_correlated_match_exposure() -> None:
    rows = pd.DataFrame(
        [
            {
                "model_name": "logistic_market",
                "sample_key": f"sample-{index}",
                "exposure_match_id": "match-1",
                "blended_expected_roi_units": edge,
            }
            for index, edge in enumerate([0.08, 0.15, 0.12, 0.11])
        ]
    )

    selected = select_blended_policy_bets(
        rows,
        minimum_ev=0.075,
        maximum_ev=0.25,
        maximum_bets_per_match=3,
    )

    assert len(selected) == 3
    assert selected["blended_expected_roi_units"].tolist() == pytest.approx(
        [0.15, 0.12, 0.11]
    )


def test_nested_brier_blend_does_not_use_current_window_outcomes() -> None:
    rows: list[dict[str, object]] = []
    for window_index, test_start in enumerate(
        ["2026-01-01", "2026-01-15", "2026-02-01"]
    ):
        for sample_index, actual in enumerate([1.0, 0.0]):
            sample_key = f"window-{window_index}-sample-{sample_index}"
            predicted_over = 0.9 if actual == 1.0 else 0.1
            rows.append(
                {
                    "model_name": "logistic_market",
                    "sample_key": sample_key,
                    "exposure_match_id": sample_key,
                    "test_start": test_start,
                    "direction": "over",
                    "market_fair_probability_over": 0.5,
                    "predicted_over_probability": predicted_over,
                    "predicted_win_probability": predicted_over,
                    "offered_odds": 2.0,
                    "is_over_win": actual,
                    "settlement_result": (
                        "win" if actual == 1.0 else "loss"
                    ),
                    "realized_roi_units": (
                        1.0 if actual == 1.0 else -1.0
                    ),
                }
            )
    predictions = pd.DataFrame(rows)

    selected, windows = run_nested_brier_blend_policy(
        predictions,
        alpha_grid=(0.0, 0.5, 1.0),
        minimum_history_windows=2,
        minimum_ev=0.05,
        maximum_ev=0.95,
        maximum_bets_per_match=1,
    )
    changed = predictions.copy()
    changed.loc[
        changed["test_start"].eq("2026-02-01"),
        ["is_over_win", "settlement_result", "realized_roi_units"],
    ] = [0.0, "loss", -1.0]
    _, changed_windows = run_nested_brier_blend_policy(
        changed,
        alpha_grid=(0.0, 0.5, 1.0),
        minimum_history_windows=2,
        minimum_ev=0.05,
        maximum_ev=0.95,
        maximum_bets_per_match=1,
    )

    assert len(selected) == 1
    assert windows.iloc[0]["selected_alpha"] == 1.0
    assert changed_windows.iloc[0]["selected_alpha"] == 1.0
    assert windows.iloc[0]["prior_prediction_rows"] == 4
