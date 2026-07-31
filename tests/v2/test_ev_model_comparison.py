from __future__ import annotations

import pandas as pd

from ullebets_v2.ev_model.model_comparison import (
    build_paired_strategy_comparison,
)


def test_paired_comparison_tracks_overlap_and_model_quality() -> None:
    reference = pd.DataFrame(
        [
            {
                "side_key": "common",
                "exposure_match_id": "m1",
                "realized_roi_units": -1.0,
            },
            {
                "side_key": "reference-only",
                "exposure_match_id": "m2",
                "realized_roi_units": -1.0,
            },
        ]
    )
    challenger = pd.DataFrame(
        [
            {
                "side_key": "common",
                "exposure_match_id": "m1",
                "realized_roi_units": -1.0,
            },
            {
                "side_key": "challenger-only",
                "exposure_match_id": "m3",
                "realized_roi_units": 1.0,
            },
        ]
    )
    reference_predictions = pd.DataFrame(
        [
            {
                "side_key": "s1",
                "predicted_win_probability": 0.40,
                "settlement_result": "win",
            },
            {
                "side_key": "s2",
                "predicted_win_probability": 0.60,
                "settlement_result": "loss",
            },
        ]
    )
    challenger_predictions = pd.DataFrame(
        [
            {
                "side_key": "s1",
                "predicted_win_probability": 0.70,
                "settlement_result": "win",
            },
            {
                "side_key": "s2",
                "predicted_win_probability": 0.30,
                "settlement_result": "loss",
            },
        ]
    )

    report = build_paired_strategy_comparison(
        reference_selections=reference,
        challenger_selections=challenger,
        reference_predictions=reference_predictions,
        challenger_predictions=challenger_predictions,
        bootstrap_iterations=2_000,
        random_seed=17,
    )

    assert report["selection_overlap"] == {
        "common": 1,
        "reference_only": 1,
        "challenger_only": 1,
    }
    assert report["challenger_unique"]["roi_pct"] == 100.0
    assert report["paired_bootstrap"]["match_clusters"] == 3
    assert (
        report["paired_bootstrap"][
            "probability_challenger_superior"
        ]
        > 0.5
    )
    assert (
        report["prediction_quality"]["challenger_brier"]
        < report["prediction_quality"]["reference_brier"]
    )
