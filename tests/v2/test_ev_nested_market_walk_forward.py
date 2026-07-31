from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from ullebets_v2.ev_model.nested_market_walk_forward import (
    NestedMarketWalkForwardConfig,
    run_nested_market_walk_forward,
)


def test_nested_market_walk_forward_keeps_training_calibration_and_test_ordered() -> None:
    start = date(2026, 1, 1)
    rows = []
    for offset in range(120):
        for match_number in range(4):
            is_over = float((offset + match_number) % 2 == 0)
            rows.append(
                {
                    "sample_key": (
                        f"match-{offset}-{match_number}|"
                        "cornerKicks|ALL|total"
                    ),
                    "exposure_match_id": f"match-{offset}-{match_number}",
                    "match_date": (start + timedelta(days=offset)).isoformat(),
                    "stat_key": "cornerKicks",
                    "period": "ALL",
                    "scope": "total",
                    "line_value": 10.5,
                    "over_odds": 1.95,
                    "under_odds": 1.85,
                    "market_fair_probability_over": 0.487,
                    "history_role_expected_10": (
                        11.0 if is_over else 10.0
                    ),
                    "is_over_win": is_over,
                    "over_settlement_result": (
                        "win" if is_over else "loss"
                    ),
                    "under_settlement_result": (
                        "loss" if is_over else "win"
                    ),
                    "over_realized_roi_units": 0.95 if is_over else -1.0,
                    "under_realized_roi_units": -1.0 if is_over else 0.85,
                    "training_weight": 1.0,
                }
            )

    predictions, summaries = run_nested_market_walk_forward(
        pd.DataFrame(rows),
        NestedMarketWalkForwardConfig(
            train_window_days=90,
            calibration_window_days=20,
            test_window_days=10,
            step_days=10,
            min_model_train_rows=200,
            min_calibration_rows=60,
            min_group_calibration_rows=60,
            model_names=("logistic_market",),
            minimum_ev_thresholds=(0.0,),
        ),
    )

    assert not predictions.empty
    assert (
        pd.to_datetime(predictions["model_train_end"])
        < pd.to_datetime(predictions["calibration_start"])
    ).all()
    assert (
        pd.to_datetime(predictions["calibration_end"])
        < pd.to_datetime(predictions["match_date"])
    ).all()
    probabilities = predictions.pivot(
        index=["model_name", "sample_key"],
        columns="direction",
        values="predicted_win_probability",
    )
    assert (probabilities["over"] + probabilities["under"]).tolist() == (
        pytest.approx([1.0] * len(probabilities))
    )
    assert not summaries.empty
