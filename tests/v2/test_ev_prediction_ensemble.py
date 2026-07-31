from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.prediction_ensemble import (
    build_fixed_prediction_ensemble,
    gate_reference_by_multi_model_agreement,
)


def _predictions(name: str, over_probability: float) -> pd.DataFrame:
    rows = []
    for direction, probability in (
        ("over", over_probability),
        ("under", 1.0 - over_probability),
    ):
        rows.append(
            {
                "side_key": f"a|{direction}",
                "sample_key": "a",
                "direction": direction,
                "test_start": "2026-01-01",
                "test_end": "2026-01-14",
                "model_name": name,
                "predicted_win_probability": probability,
                "predicted_over_probability": over_probability,
                "offered_odds": 2.0,
                "expected_roi_units": probability * 2.0 - 1.0,
            }
        )
    return pd.DataFrame(rows)


def test_fixed_prediction_ensemble_uses_exact_shared_universe() -> None:
    reference = _predictions("reference", 0.60)
    first = _predictions("first", 0.50)
    second = _predictions("second", 0.40)

    ensemble = build_fixed_prediction_ensemble(
        {"reference": reference, "first": first, "second": second},
        weights={"reference": 0.8, "first": 0.1, "second": 0.1},
        model_name="ensemble",
    )

    over = ensemble[ensemble["direction"].eq("over")].iloc[0]
    assert over["predicted_win_probability"] == pytest.approx(0.57)
    assert over["expected_roi_units"] == pytest.approx(0.14)
    assert over["model_name"] == "ensemble"

    with pytest.raises(ValueError, match="universes do not match"):
        build_fixed_prediction_ensemble(
            {
                "reference": reference,
                "first": first.iloc[:1],
            },
            weights={"reference": 0.8, "first": 0.2},
            model_name="bad",
        )


def test_multi_model_agreement_requires_every_challenger() -> None:
    reference = _predictions("reference", 0.60)
    first = _predictions("first", 0.55)
    second = _predictions("second", 0.45)
    reference_selection = reference[
        reference["direction"].eq("over")
    ].copy()

    rejected = gate_reference_by_multi_model_agreement(
        reference_selection,
        {"first": first, "second": second},
        minimum_challenger_ev=0.0,
        model_name="agreement",
    )
    assert rejected.empty

    second = _predictions("second", 0.52)
    accepted = gate_reference_by_multi_model_agreement(
        reference_selection,
        {"first": first, "second": second},
        minimum_challenger_ev=0.0,
        model_name="agreement",
    )
    assert accepted["side_key"].tolist() == ["a|over"]
