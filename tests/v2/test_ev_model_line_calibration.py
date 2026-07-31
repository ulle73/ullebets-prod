from __future__ import annotations

import pandas as pd

from ullebets_v2.ev_model.line_calibration import (
    build_line_probability_rows,
    select_calibrated_bets,
    sequentially_calibrate_probability_rows,
)


def test_probability_rows_preserve_over_only_market_shape() -> None:
    predictions = pd.DataFrame(
        {
            "sample_key": ["match-1|shotsOnGoal|ALL|home"],
            "exposure_match_id": ["match-1"],
            "match_date": ["2026-01-01"],
            "test_start": ["2026-01-01"],
            "model_name": ["hgb_market_residual"],
            "stat_key": ["shotsOnGoal"],
            "period": ["ALL"],
            "scope": ["home"],
            "line_value": [5.5],
            "actual_value": [7.0],
            "over_odds": [1.9],
            "under_odds": [None],
            "predicted_mean": [6.5],
            "nb_dispersion": [3.0],
        }
    )

    rows = build_line_probability_rows(predictions, distribution="negative_binomial")

    assert rows["direction"].tolist() == ["over"]


def test_sequential_calibration_never_trains_on_current_window() -> None:
    rows = []
    for window_index, window_start in enumerate(("2026-01-01", "2026-02-01")):
        for index in range(100):
            won = index % 2 == 0
            rows.append(
                {
                    "sample_key": f"{window_index}-{index}",
                    "model_name": "model",
                    "distribution": "poisson",
                    "test_start": window_start,
                    "stat_key": "cornerKicks",
                    "period": "ALL",
                    "scope": "total",
                    "direction": "over",
                    "selected_odds": 1.9,
                    "raw_win_probability": 0.8,
                    "push_probability": 0.0,
                    "settlement_result": "win" if won else "loss",
                    "realized_roi_units": 0.9 if won else -1.0,
                }
            )

    calibrated = sequentially_calibrate_probability_rows(
        pd.DataFrame(rows),
        minimum_history_rows=50,
        minimum_group_rows=50,
    )

    first = calibrated[calibrated["test_start"] == "2026-01-01"]
    second = calibrated[calibrated["test_start"] == "2026-02-01"]
    assert not first["calibration_eligible"].any()
    assert second["calibration_eligible"].all()
    assert second["calibrated_win_probability"].mean() < 0.55


def test_calibrated_selection_keeps_one_side_per_market() -> None:
    rows = pd.DataFrame(
        {
            "sample_key": ["match-1", "match-1"],
            "model_name": ["model", "model"],
            "distribution": ["poisson", "poisson"],
            "direction": ["over", "under"],
            "calibration_eligible": [True, True],
            "calibrated_expected_roi_units": [0.05, 0.12],
        }
    )

    selections = select_calibrated_bets(rows, minimum_ev=0.02)

    assert selections["direction"].tolist() == ["under"]
