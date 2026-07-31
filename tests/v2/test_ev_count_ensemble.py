from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.count_ensemble import (
    blend_reference_with_count,
    gate_reference_by_count_agreement,
    merge_reference_count_predictions,
)


def _predictions() -> tuple[pd.DataFrame, pd.DataFrame]:
    reference = pd.DataFrame(
        [
            {
                "side_key": "a|over",
                "sample_key": "a",
                "direction": "over",
                "test_start": "2026-01-01",
                "test_end": "2026-01-14",
                "model_name": "reference",
                "predicted_win_probability": 0.60,
                "predicted_over_probability": 0.60,
                "offered_odds": 2.0,
                "expected_roi_units": 0.20,
            },
            {
                "side_key": "a|under",
                "sample_key": "a",
                "direction": "under",
                "test_start": "2026-01-01",
                "test_end": "2026-01-14",
                "model_name": "reference",
                "predicted_win_probability": 0.40,
                "predicted_over_probability": 0.60,
                "offered_odds": 2.0,
                "expected_roi_units": -0.20,
            },
        ]
    )
    count = pd.DataFrame(
        [
            {
                "side_key": "a|over",
                "sample_key": "a",
                "direction": "over",
                "test_start": "2026-01-01",
                "test_end": "2026-01-14",
                "model_name": "count",
                "predicted_win_probability": 0.50,
                "predicted_push_probability": 0.0,
                "expected_roi_units": 0.0,
            },
            {
                "side_key": "a|under",
                "sample_key": "a",
                "direction": "under",
                "test_start": "2026-01-01",
                "test_end": "2026-01-14",
                "model_name": "count",
                "predicted_win_probability": 0.50,
                "predicted_push_probability": 0.0,
                "expected_roi_units": 0.0,
            },
        ]
    )
    return reference, count


def test_merge_requires_exact_prediction_universe() -> None:
    reference, count = _predictions()

    merged = merge_reference_count_predictions(reference, count)

    assert len(merged) == len(reference)
    assert merged["count_predicted_win_probability"].tolist() == [0.5, 0.5]

    with pytest.raises(ValueError, match="universes do not match"):
        merge_reference_count_predictions(reference, count.iloc[:1])


def test_fixed_blend_recomputes_probability_and_ev() -> None:
    reference, count = _predictions()
    merged = merge_reference_count_predictions(reference, count)

    blended = blend_reference_with_count(
        merged,
        count_weight=0.25,
        model_name="blend",
    )

    over = blended[blended["direction"].eq("over")].iloc[0]
    assert over["predicted_win_probability"] == pytest.approx(0.575)
    assert over["expected_roi_units"] == pytest.approx(0.15)
    assert over["model_name"] == "blend"


def test_agreement_gate_keeps_only_reference_side_preferred_by_count() -> None:
    reference, count = _predictions()
    count.loc[count["direction"].eq("over"), "expected_roi_units"] = 0.03
    count.loc[count["direction"].eq("under"), "expected_roi_units"] = -0.03

    gated = gate_reference_by_count_agreement(
        reference,
        count,
        minimum_count_ev=0.0,
        model_name="agreement",
    )

    assert gated["side_key"].tolist() == ["a|over"]
    assert gated["model_name"].eq("agreement").all()
