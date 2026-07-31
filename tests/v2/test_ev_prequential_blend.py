from __future__ import annotations

import pandas as pd

from ullebets_v2.ev_model.prequential_blend import (
    build_prequential_blend_predictions,
)


def _side_rows(
    *,
    model_name: str,
    over_probabilities: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    outcomes = [1.0, 0.0, 1.0]
    for index, (probability, outcome) in enumerate(
        zip(over_probabilities, outcomes, strict=True)
    ):
        test_start = (
            pd.Timestamp("2026-01-01")
            + pd.Timedelta(days=index * 14)
        ).date().isoformat()
        test_end = (
            pd.Timestamp(test_start) + pd.Timedelta(days=13)
        ).date().isoformat()
        for direction, side_probability in (
            ("over", probability),
            ("under", 1.0 - probability),
        ):
            won = (
                outcome == 1.0
                if direction == "over"
                else outcome == 0.0
            )
            rows.append(
                {
                    "side_key": f"m{index}|{direction}",
                    "sample_key": f"m{index}",
                    "exposure_match_id": f"m{index}",
                    "direction": direction,
                    "test_start": test_start,
                    "test_end": test_end,
                    "model_name": model_name,
                    "predicted_win_probability": side_probability,
                    "predicted_over_probability": probability,
                    "is_over_win": outcome,
                    "offered_odds": 2.0,
                    "settlement_result": (
                        "win" if won else "loss"
                    ),
                    "realized_roi_units": (
                        1.0 if won else -1.0
                    ),
                }
            )
    return pd.DataFrame(rows)


def test_prequential_blend_uses_only_completed_prior_windows() -> None:
    reference = _side_rows(
        model_name="reference",
        over_probabilities=[0.50, 0.50, 0.50],
    )
    challenger = _side_rows(
        model_name="challenger",
        over_probabilities=[0.90, 0.10, 0.90],
    )

    predictions, decisions = build_prequential_blend_predictions(
        reference,
        challenger,
        challenger_weights=(0.0, 1.0),
        cold_start_weight=0.0,
        model_name="prequential",
    )

    assert decisions["selected_challenger_weight"].tolist() == [
        0.0,
        1.0,
        1.0,
    ]
    assert decisions["selection_source"].tolist() == [
        "cold_start",
        "prior_outer_brier",
        "prior_outer_brier",
    ]
    second_window = predictions[
        predictions["test_start"].eq("2026-01-15")
    ]
    assert second_window["selected_challenger_weight"].eq(1.0).all()
    assert decisions.loc[1, "latest_history_test_end"] == "2026-01-14"
    assert (
        pd.to_datetime(
            decisions.loc[1:, "latest_history_test_end"]
        ).reset_index(drop=True)
        < pd.to_datetime(
            decisions.loc[1:, "test_start"]
        ).reset_index(drop=True)
    ).all()


def test_prequential_blend_prefers_reference_on_brier_tie() -> None:
    reference = _side_rows(
        model_name="reference",
        over_probabilities=[0.50, 0.50, 0.50],
    )
    challenger = reference.copy()
    challenger["model_name"] = "challenger"

    _, decisions = build_prequential_blend_predictions(
        reference,
        challenger,
        challenger_weights=(0.0, 0.1, 0.25),
        cold_start_weight=0.0,
        model_name="prequential",
    )

    assert decisions["selected_challenger_weight"].eq(0.0).all()
