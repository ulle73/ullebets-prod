from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ullebets_v2.ev_model.walk_forward import (
    WalkForwardExperimentConfig,
    run_count_walk_forward,
)


def test_walk_forward_predictions_only_use_prior_dates() -> None:
    start = date(2026, 1, 1)
    rows = []
    features = []
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
                "line_value": 9.5,
                "actual_value": 10.0,
                "over_odds": 2.0,
                "under_odds": 2.0,
            }
        )
        features.append(
            {
                "market_anchor_lambda": 10.0,
                "baseline_lambda": 10.0,
                "league_name_normalized": "Premier League",
                "period": "ALL",
                "scope": "total",
                "stat_key": "cornerKicks",
            }
        )

    predictions, summaries = run_count_walk_forward(
        pd.DataFrame(rows),
        pd.DataFrame(features),
        WalkForwardExperimentConfig(
            train_window_days=30,
            test_window_days=10,
            step_days=10,
            min_train_rows=20,
            model_names=("market_anchor",),
            minimum_ev_thresholds=(0.0,),
            probability_distributions=("poisson", "negative_binomial"),
        ),
    )

    assert not predictions.empty
    assert not summaries.empty
    assert (
        pd.to_datetime(predictions["train_end"])
        < pd.to_datetime(predictions["match_date"])
    ).all()
    assert predictions["sample_key"].is_unique
    assert predictions["nb_dispersion"].notna().all()
    assert set(summaries["distribution"]) == {"poisson", "negative_binomial"}
