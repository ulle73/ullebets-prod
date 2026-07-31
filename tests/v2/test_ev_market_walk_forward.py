from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ullebets_v2.ev_model.market_walk_forward import (
    MarketWalkForwardConfig,
    run_market_classifier_walk_forward,
    select_market_classifier_bets,
)


def test_market_selection_can_reject_implausibly_large_model_edges() -> None:
    predictions = pd.DataFrame(
        [
            {
                "model_name": "logistic_market",
                "sample_key": "accepted",
                "direction": "over",
                "expected_roi_units": 0.24,
            },
            {
                "model_name": "logistic_market",
                "sample_key": "rejected",
                "direction": "over",
                "expected_roi_units": 0.26,
            },
        ]
    )

    selected = select_market_classifier_bets(
        predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )

    assert selected["sample_key"].tolist() == ["accepted"]


def test_market_walk_forward_is_chronological_and_deduplicated() -> None:
    start = date(2026, 1, 1)
    rows = []
    for offset in range(60):
        match_date = start + timedelta(days=offset)
        rows.append(
            {
                "sample_key": f"match-{offset}|cornerKicks|ALL|total",
                "exposure_match_id": f"match-{offset}",
                "match_date": match_date.isoformat(),
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 10.5,
                "over_odds": 2.1,
                "under_odds": 1.8,
                "market_fair_probability_over": 0.46,
                "history_role_expected_10": 11.0,
                "is_over_win": float(offset % 2 == 0),
                "over_settlement_result": (
                    "win" if offset % 2 == 0 else "loss"
                ),
                "under_settlement_result": (
                    "loss" if offset % 2 == 0 else "win"
                ),
                "over_realized_roi_units": (
                    1.1 if offset % 2 == 0 else -1.0
                ),
                "under_realized_roi_units": (
                    -1.0 if offset % 2 == 0 else 0.8
                ),
                "training_weight": 1.0,
            }
        )

    predictions, summaries = run_market_classifier_walk_forward(
        pd.DataFrame(rows),
        MarketWalkForwardConfig(
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
    assert not predictions.duplicated(
        subset=["model_name", "sample_key", "direction"]
    ).any()
    assert not summaries.empty
