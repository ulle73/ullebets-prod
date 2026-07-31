from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from ullebets_v2.ev_model.nested_count import (
    NestedCountConfig,
    build_count_feature_frame,
    run_nested_count_walk_forward,
)


def _market_frame(days: int = 100, rows_per_day: int = 3) -> pd.DataFrame:
    start = date(2026, 1, 1)
    rows: list[dict[str, object]] = []
    for offset in range(days):
        match_day = start + timedelta(days=offset)
        kickoff = pd.Timestamp(match_day, tz="UTC") + pd.Timedelta(hours=18)
        for row_index in range(rows_per_day):
            sample_key = f"match-{offset}-{row_index}|cornerKicks|ALL|total"
            actual = float(8 + (offset + row_index) % 5)
            rows.append(
                {
                    "sample_key": sample_key,
                    "exposure_match_id": f"match-{offset}-{row_index}",
                    "match_date": match_day.isoformat(),
                    "league_name_normalized": "Premier League",
                    "period": "ALL",
                    "scope": "total",
                    "stat_key": "cornerKicks",
                    "line_value": 9.5,
                    "over_odds": 2.0,
                    "under_odds": 2.0,
                    "market_fair_probability_over": 0.5,
                    "market_anchor_lambda": 10.0,
                    "market_overround": 1.0,
                    "baseline_lambda": 10.0,
                    "snapshot_lead_hours": 24.0,
                    "history_role_expected_10": 10.0,
                    "actual_value": actual,
                    "odds_snapshot_time": kickoff - pd.Timedelta(hours=24),
                    "match_start_time": kickoff,
                    "is_over_win": float(actual > 9.5),
                    "over_settlement_result": (
                        "win" if actual > 9.5 else "loss"
                    ),
                    "under_settlement_result": (
                        "loss" if actual > 9.5 else "win"
                    ),
                    "over_realized_roi_units": (
                        1.0 if actual > 9.5 else -1.0
                    ),
                    "under_realized_roi_units": (
                        -1.0 if actual > 9.5 else 1.0
                    ),
                    "training_weight": 1.0,
                }
            )
    return pd.DataFrame(rows)


def test_count_features_exclude_outcomes_identifiers_and_timestamps() -> None:
    frame = _market_frame(days=2)

    features = build_count_feature_frame(frame)

    assert "market_anchor_lambda" in features
    assert "history_role_expected_10" in features
    assert "league_name_normalized" in features
    assert "actual_value" not in features
    assert "is_over_win" not in features
    assert "sample_key" not in features
    assert "odds_snapshot_time" not in features
    assert "match_start_time" not in features
    assert "training_weight" not in features


def test_nested_count_walk_forward_is_temporal_and_uses_validation_dispersion() -> None:
    frame = _market_frame()

    predictions, windows = run_nested_count_walk_forward(
        frame,
        NestedCountConfig(
            train_window_days=60,
            validation_window_days=14,
            test_window_days=10,
            step_days=10,
            min_model_train_rows=60,
            min_inner_train_rows=60,
            min_validation_rows=20,
            min_segment_dispersion_rows=10,
            model_name="market_anchor",
        ),
    )

    assert not predictions.empty
    assert not windows.empty
    assert predictions["side_key"].is_unique
    assert (
        pd.to_datetime(predictions["train_end"])
        < pd.to_datetime(predictions["match_date"])
    ).all()
    assert (
        pd.to_datetime(predictions["validation_end"])
        < pd.to_datetime(predictions["test_start"])
    ).all()
    assert predictions["dispersion_source"].eq(
        "inner_temporal_validation"
    ).all()
    assert predictions["nb_dispersion"].notna().all()
    assert predictions["predicted_win_probability"].between(0.0, 1.0).all()


def test_nested_count_walk_forward_rejects_post_start_snapshot() -> None:
    frame = _market_frame()
    frame.loc[0, "odds_snapshot_time"] = frame.loc[0, "match_start_time"]

    with pytest.raises(ValueError, match="strictly before kickoff"):
        run_nested_count_walk_forward(
            frame,
            NestedCountConfig(
                train_window_days=60,
                validation_window_days=14,
                min_model_train_rows=60,
                min_validation_rows=20,
                model_name="market_anchor",
            ),
        )


def test_nested_count_carries_prior_validation_dispersion_across_data_gap() -> None:
    frame = _market_frame()
    match_days = pd.to_datetime(frame["match_date"])
    gap_start = pd.Timestamp("2026-03-08")
    gap_end = pd.Timestamp("2026-03-21")
    frame = frame[~match_days.between(gap_start, gap_end)].copy()

    predictions, _ = run_nested_count_walk_forward(
        frame,
        NestedCountConfig(
            train_window_days=60,
            validation_window_days=14,
            test_window_days=10,
            step_days=10,
            min_model_train_rows=60,
            min_inner_train_rows=60,
            min_validation_rows=20,
            min_segment_dispersion_rows=10,
            model_name="market_anchor",
        ),
    )

    carried = predictions[
        predictions["dispersion_source"].eq(
            "carried_forward_prior_validation"
        )
    ]
    assert not carried.empty
    assert (
        pd.to_datetime(carried["dispersion_validation_end"])
        < pd.to_datetime(carried["test_start"])
    ).all()


def test_nested_count_walk_forward_requires_resolved_snapshot_timing() -> None:
    frame = _market_frame()
    frame.loc[0, "odds_snapshot_time"] = pd.NaT

    with pytest.raises(ValueError, match="missing timing"):
        run_nested_count_walk_forward(
            frame,
            NestedCountConfig(
                train_window_days=60,
                validation_window_days=14,
                min_model_train_rows=60,
                min_validation_rows=20,
                model_name="market_anchor",
            ),
        )
