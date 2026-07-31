from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from ullebets_v2.ev_model.nested_regularization import (
    NestedRegularizationConfig,
    _with_recency_weight,
    run_nested_regularization_walk_forward,
    train_nested_regularization_candidate,
)


def test_nested_regularization_selects_c_before_outer_test() -> None:
    start = date(2026, 1, 1)
    rows: list[dict[str, object]] = []
    for offset in range(130):
        for match_number in range(4):
            signal = float((offset + match_number) % 7) - 3.0
            is_over = float(signal > 0.0)
            rows.append(
                {
                    "sample_key": (
                        f"match-{offset}-{match_number}|"
                        "cornerKicks|ALL|total"
                    ),
                    "exposure_match_id": (
                        f"match-{offset}-{match_number}"
                    ),
                    "match_date": (
                        start + timedelta(days=offset)
                    ).isoformat(),
                    "stat_key": "cornerKicks",
                    "period": "ALL",
                    "scope": "total",
                    "line_value": 10.5,
                    "over_odds": 1.95,
                    "under_odds": 1.85,
                    "market_fair_probability_over": 0.487,
                    "history_role_expected_10": signal,
                    "is_over_win": is_over,
                    "over_settlement_result": (
                        "win" if is_over else "loss"
                    ),
                    "under_settlement_result": (
                        "loss" if is_over else "win"
                    ),
                    "over_realized_roi_units": (
                        0.95 if is_over else -1.0
                    ),
                    "under_realized_roi_units": (
                        -1.0 if is_over else 0.85
                    ),
                    "training_weight": 1.0,
                }
            )

    predictions, windows = run_nested_regularization_walk_forward(
        pd.DataFrame(rows),
        NestedRegularizationConfig(
            train_window_days=90,
            validation_window_days=20,
            test_window_days=10,
            step_days=10,
            min_model_train_rows=200,
            min_validation_rows=60,
            c_grid=(0.01, 0.25),
            recency_half_life_days=45.0,
        ),
    )

    assert not predictions.empty
    assert not windows.empty
    assert set(windows["selected_logistic_c"]).issubset(
        {0.01, 0.25}
    )
    assert (
        pd.to_datetime(windows["inner_train_end"])
        < pd.to_datetime(windows["validation_start"])
    ).all()
    assert (
        pd.to_datetime(windows["validation_end"])
        < pd.to_datetime(windows["test_start"])
    ).all()
    probabilities = predictions.pivot(
        index=["model_name", "sample_key"],
        columns="direction",
        values="predicted_win_probability",
    )
    assert (
        probabilities["over"] + probabilities["under"]
    ).tolist() == pytest.approx([1.0] * len(probabilities))
    assert np.isfinite(
        predictions["expected_roi_units"].to_numpy(dtype=float)
    ).all()


def test_nested_regularization_falls_back_without_validation_coverage() -> None:
    start = date(2026, 1, 1)
    rows: list[dict[str, object]] = []
    for offset in range(110):
        for match_number in range(4):
            is_over = float((offset + match_number) % 2 == 0)
            rows.append(
                {
                    "sample_key": (
                        f"match-{offset}-{match_number}|"
                        "cornerKicks|ALL|total"
                    ),
                    "exposure_match_id": (
                        f"match-{offset}-{match_number}"
                    ),
                    "match_date": (
                        start + timedelta(days=offset)
                    ).isoformat(),
                    "stat_key": "cornerKicks",
                    "period": "ALL",
                    "scope": "total",
                    "line_value": 10.5,
                    "over_odds": 1.95,
                    "under_odds": 1.85,
                    "market_fair_probability_over": 0.487,
                    "history_role_expected_10": float(match_number),
                    "is_over_win": is_over,
                    "over_settlement_result": (
                        "win" if is_over else "loss"
                    ),
                    "under_settlement_result": (
                        "loss" if is_over else "win"
                    ),
                    "over_realized_roi_units": (
                        0.95 if is_over else -1.0
                    ),
                    "under_realized_roi_units": (
                        -1.0 if is_over else 0.85
                    ),
                    "training_weight": 1.0,
                }
            )

    predictions, windows = run_nested_regularization_walk_forward(
        pd.DataFrame(rows),
        NestedRegularizationConfig(
            train_window_days=90,
            validation_window_days=20,
            test_window_days=10,
            step_days=10,
            min_model_train_rows=200,
            min_validation_rows=10_000,
            c_grid=(0.01, 0.25),
            default_logistic_c=0.25,
        ),
    )

    assert not predictions.empty
    assert set(windows["selection_source"]) == {
        "default_insufficient_validation"
    }
    assert set(windows["selected_logistic_c"]) == {0.25}


def test_nested_regularization_candidate_refits_selected_c_on_full_window() -> None:
    start = date(2026, 1, 1)
    rows: list[dict[str, object]] = []
    for offset in range(110):
        for match_number in range(4):
            signal = float((offset + match_number) % 5) - 2.0
            rows.append(
                {
                    "sample_key": (
                        f"match-{offset}-{match_number}|"
                        "cornerKicks|ALL|total"
                    ),
                    "exposure_match_id": (
                        f"match-{offset}-{match_number}"
                    ),
                    "match_date": (
                        start + timedelta(days=offset)
                    ).isoformat(),
                    "stat_key": "cornerKicks",
                    "period": "ALL",
                    "scope": "total",
                    "line_value": 10.5,
                    "over_odds": 1.95,
                    "under_odds": 1.85,
                    "market_fair_probability_over": 0.487,
                    "history_role_expected_10": signal,
                    "is_over_win": float(signal > 0.0),
                    "training_weight": 1.0,
                }
            )
    frame = pd.DataFrame(rows)
    cutoff = start + timedelta(days=110)

    result = train_nested_regularization_candidate(
        frame,
        cutoff_date=cutoff,
        config=NestedRegularizationConfig(
            min_model_train_rows=200,
            min_validation_rows=60,
            c_grid=(0.01, 0.25),
        ),
    )

    assert result.bundle.training_end == (
        cutoff - timedelta(days=1)
    ).isoformat()
    assert result.bundle.training_rows == 90 * 4
    assert result.selected_logistic_c in {0.01, 0.25}
    assert result.selection_source == "inner_temporal_validation"
    assert (
        result.bundle.model.pipeline.named_steps["model"].C
        == result.selected_logistic_c
    )


def test_stat_balance_uses_only_training_frame_counts() -> None:
    frame = pd.DataFrame(
        {
            "_match_day": pd.to_datetime(
                ["2026-01-10"] * 10
            ),
            "stat_key": (
                ["cornerKicks"] * 8
                + ["shotsOnGoal"] * 2
            ),
            "training_weight": [1.0] * 10,
        }
    )

    balanced = _with_recency_weight(
        frame,
        reference_day=pd.Timestamp("2026-01-10"),
        half_life_days=45.0,
        stat_balance_power=1.0,
    )
    totals = balanced.groupby("stat_key")[
        "training_weight"
    ].sum()

    assert totals["cornerKicks"] == pytest.approx(
        totals["shotsOnGoal"]
    )
    assert balanced["training_weight"].mean() == pytest.approx(
        1.0
    )


def test_stat_balance_rejects_invalid_power() -> None:
    frame = pd.DataFrame(
        {
            "_match_day": pd.to_datetime(["2026-01-10"]),
            "stat_key": ["cornerKicks"],
            "training_weight": [1.0],
        }
    )

    with pytest.raises(
        ValueError,
        match="stat_balance_power",
    ):
        _with_recency_weight(
            frame,
            reference_day=pd.Timestamp("2026-01-10"),
            half_life_days=45.0,
            stat_balance_power=1.1,
        )


def test_walk_forward_honors_explicit_evaluation_start_date() -> None:
    start = date(2026, 1, 1)
    rows: list[dict[str, object]] = []
    for offset in range(80):
        for match_number in range(4):
            rows.append(
                {
                    "sample_key": (
                        f"match-{offset}-{match_number}|"
                        "cornerKicks|ALL|total"
                    ),
                    "exposure_match_id": (
                        f"match-{offset}-{match_number}"
                    ),
                    "match_date": (
                        start + timedelta(days=offset)
                    ).isoformat(),
                    "stat_key": "cornerKicks",
                    "period": "ALL",
                    "scope": "total",
                    "line_value": 10.5,
                    "over_odds": 1.95,
                    "under_odds": 1.85,
                    "market_fair_probability_over": 0.487,
                    "history_role_expected_10": float(
                        match_number
                    ),
                    "is_over_win": float(
                        (offset + match_number) % 2 == 0
                    ),
                    "training_weight": 1.0,
                }
            )
    evaluation_start = start + timedelta(days=50)

    predictions, windows = run_nested_regularization_walk_forward(
        pd.DataFrame(rows),
        NestedRegularizationConfig(
            train_window_days=30,
            validation_window_days=10,
            test_window_days=10,
            step_days=10,
            min_model_train_rows=100,
            min_validation_rows=20,
            c_grid=(0.01,),
            evaluation_start_date=evaluation_start.isoformat(),
        ),
    )

    assert not predictions.empty
    assert windows["test_start"].min() == evaluation_start.isoformat()
