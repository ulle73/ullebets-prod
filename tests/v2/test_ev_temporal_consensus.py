from __future__ import annotations

import pandas as pd
import pytest

from scripts.offline_v2.run_ev_scope_temporal_consensus import (
    _agreement_selection,
    _merge_predictions,
    _with_probability,
)


def _side_rows(
    *,
    model_name: str,
    expected_by_side: dict[tuple[str, str], float],
) -> pd.DataFrame:
    rows = []
    for (sample_key, direction), expected_ev in expected_by_side.items():
        offered_odds = 2.0
        rows.append(
            {
                "sample_key": sample_key,
                "direction": direction,
                "test_start": "2026-01-01",
                "test_end": "2026-01-14",
                "model_name": model_name,
                "side_key": f"{sample_key}:{direction}",
                "stat_key": "cornerKicks",
                "scope": "away",
                "expected_roi_units": expected_ev,
                "predicted_win_probability": (
                    (expected_ev + 1.0) / offered_odds
                ),
                "predicted_over_probability": 0.5,
                "offered_odds": offered_odds,
            }
        )
    return pd.DataFrame(rows)


def test_temporal_prediction_merge_and_probability_blend() -> None:
    reference = _side_rows(
        model_name="reference",
        expected_by_side={
            ("a", "over"): 0.10,
            ("a", "under"): -0.10,
        },
    )
    short = _side_rows(
        model_name="short",
        expected_by_side={
            ("a", "over"): 0.02,
            ("a", "under"): -0.02,
        },
    )

    merged = _merge_predictions(reference, short)
    blended = _with_probability(
        merged,
        name="blend",
        probability=(
            0.75 * merged["predicted_win_probability"]
            + 0.25 * merged["short_predicted_win_probability"]
        ),
    )

    over = blended[blended["direction"].eq("over")].iloc[0]
    assert over["model_name"] == "blend"
    assert over["predicted_win_probability"] == pytest.approx(0.54)
    assert over["expected_roi_units"] == pytest.approx(0.08)


def test_temporal_agreement_gate_requires_same_preferred_side() -> None:
    reference = _side_rows(
        model_name="reference",
        expected_by_side={
            ("a", "over"): 0.10,
            ("a", "under"): -0.10,
            ("b", "over"): 0.10,
            ("b", "under"): -0.10,
        },
    )
    short = _side_rows(
        model_name="short",
        expected_by_side={
            ("a", "over"): -0.02,
            ("a", "under"): 0.12,
            ("b", "over"): 0.08,
            ("b", "under"): -0.08,
        },
    )

    all_targets, corners = _agreement_selection(
        reference,
        short,
        name="agreement",
        short_minimum_ev=0.0,
    )

    assert all_targets["side_key"].tolist() == ["b:over"]
    assert corners["side_key"].tolist() == ["b:over"]
