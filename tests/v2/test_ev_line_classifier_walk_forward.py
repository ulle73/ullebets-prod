from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ullebets_v2.ev_model.line_walk_forward import (
    LineWalkForwardConfig,
    run_line_classifier_walk_forward,
)


def test_line_classifier_walk_forward_uses_only_prior_rows() -> None:
    start = date(2026, 1, 1)
    rows = []
    for offset in range(60):
        match_date = start + timedelta(days=offset)
        rows.append(
            {
                "sample_key": f"match-{offset}",
                "side_key": f"match-{offset}|over",
                "exposure_match_id": f"match-{offset}",
                "match_date": match_date.isoformat(),
                "stat_key": "shotsOnGoal",
                "period": "ALL",
                "scope": "home",
                "direction": "over",
                "line_value": 5.5,
                "offered_odds": 2.0,
                "market_fair_probability": 0.5,
                "history_role_expected_10": 6.0,
                "is_win": float(offset % 2 == 0),
                "settlement_result": "win" if offset % 2 == 0 else "loss",
                "realized_roi_units": 1.0 if offset % 2 == 0 else -1.0,
                "sample_weight": 1.0,
            }
        )

    predictions, summaries = run_line_classifier_walk_forward(
        pd.DataFrame(rows),
        LineWalkForwardConfig(
            train_window_days=30,
            test_window_days=10,
            step_days=10,
            min_train_rows=20,
            model_names=("market_probability",),
            minimum_ev_thresholds=(0.0,),
        ),
    )

    assert not predictions.empty
    assert (
        pd.to_datetime(predictions["train_end"])
        < pd.to_datetime(predictions["match_date"])
    ).all()
    assert predictions["side_key"].is_unique
    assert not summaries.empty
