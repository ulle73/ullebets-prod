from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.partial_pooling import (
    build_prequential_partial_pooling_predictions,
)


def _prediction_rows(
    *,
    probability_column: str,
    probabilities: list[float],
    outcomes: list[float],
    windows: list[str],
    stat_key: str = "cornerKicks",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sample_key": [
                f"{stat_key}-{index}"
                for index in range(len(probabilities))
            ],
            "stat_key": [stat_key] * len(probabilities),
            "test_start": windows,
            "is_over_win": outcomes,
            probability_column: probabilities,
        }
    )


def test_prequential_pooling_uses_only_completed_prior_windows() -> None:
    windows = (
        ["2026-01-01"] * 4
        + ["2026-01-15"] * 2
        + ["2026-01-29"] * 2
    )
    outcomes = [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0]
    global_rows = _prediction_rows(
        probability_column="predicted_over_probability",
        probabilities=[0.1, 0.1, 0.9, 0.9, 0.9, 0.9, 0.1, 0.1],
        outcomes=outcomes,
        windows=windows,
    )
    local_rows = _prediction_rows(
        probability_column="predicted_over_probability",
        probabilities=[0.9, 0.9, 0.1, 0.1, 0.1, 0.1, 0.9, 0.9],
        outcomes=outcomes,
        windows=windows,
    )

    predictions, audit = (
        build_prequential_partial_pooling_predictions(
            global_rows,
            local_rows,
            candidate_local_weights=(0.0, 0.5, 1.0),
            min_prior_markets=4,
        )
    )

    by_window = audit.set_index("test_start")
    assert by_window.loc["2026-01-01", "local_weight"] == 0.0
    assert by_window.loc["2026-01-15", "local_weight"] == 1.0
    assert by_window.loc["2026-01-29", "local_weight"] == 1.0
    assert by_window.loc["2026-01-15", "prior_markets"] == 4
    assert by_window.loc["2026-01-29", "prior_markets"] == 6

    changed_current_outcomes = global_rows.copy()
    changed_current_outcomes.loc[
        changed_current_outcomes["test_start"].eq("2026-01-15"),
        "is_over_win",
    ] = 1.0
    changed_local = local_rows.copy()
    changed_local["is_over_win"] = changed_current_outcomes[
        "is_over_win"
    ]
    _, changed_audit = (
        build_prequential_partial_pooling_predictions(
            changed_current_outcomes,
            changed_local,
            candidate_local_weights=(0.0, 0.5, 1.0),
            min_prior_markets=4,
        )
    )
    changed_by_window = changed_audit.set_index("test_start")
    assert (
        changed_by_window.loc["2026-01-15", "local_weight"]
        == by_window.loc["2026-01-15", "local_weight"]
    )
    assert predictions.loc[
        predictions["test_start"].eq("2026-01-15"),
        "predicted_over_probability",
    ].tolist() == pytest.approx([0.1, 0.1])


def test_prequential_pooling_falls_back_when_local_prediction_is_missing() -> None:
    global_rows = _prediction_rows(
        probability_column="predicted_over_probability",
        probabilities=[0.4, 0.6],
        outcomes=[0.0, 1.0],
        windows=["2026-01-01", "2026-01-15"],
    )
    local_rows = _prediction_rows(
        probability_column="predicted_over_probability",
        probabilities=[0.3],
        outcomes=[0.0],
        windows=["2026-01-01"],
    )

    predictions, audit = (
        build_prequential_partial_pooling_predictions(
            global_rows,
            local_rows,
            min_prior_markets=1,
        )
    )

    missing = predictions.loc[
        predictions["sample_key"].eq("cornerKicks-1")
    ].iloc[0]
    assert missing["predicted_over_probability"] == pytest.approx(0.6)
    assert missing["local_weight"] == 0.0
    assert missing["partial_pooling_source"] == "missing_local_fallback"
    assert audit["missing_local_markets"].sum() == 1
