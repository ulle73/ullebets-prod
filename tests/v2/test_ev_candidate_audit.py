from __future__ import annotations

import pandas as pd

from ullebets_v2.ev_model.candidate_audit import audit_candidate


def test_candidate_audit_detects_timing_duplicate_and_settlement_risks() -> None:
    selections = pd.DataFrame(
        [
            {
                "sample_key": "m1|cornerKicks|ALL|total",
                "side_key": "m1|cornerKicks|ALL|total|over",
                "direction": "over",
                "line_value": 10.5,
                "actual_value": 12.0,
                "settlement_result": "loss",
                "train_end": "2026-01-09",
                "match_date": "2026-01-10",
            },
            {
                "sample_key": "m1|cornerKicks|ALL|total",
                "side_key": "m1|cornerKicks|ALL|total|over",
                "direction": "over",
                "line_value": 10.5,
                "actual_value": 12.0,
                "settlement_result": "loss",
                "train_end": "2026-01-09",
                "match_date": "2026-01-10",
            },
        ]
    )
    source = pd.DataFrame(
        [
            {
                "sample_key": "m1|cornerKicks|ALL|total",
                "over_snapshot_time": "2026-01-10T15:00:00Z",
                "over_snapshot_time_source": "test.snapshot",
                "over_match_start_time": "2026-01-10T14:00:00Z",
                "over_match_start_time_source": "test.start",
                "over_clv_pct": None,
            }
        ]
    )

    report = audit_candidate(
        selections,
        source,
        feature_columns=["line_value", "actual_value"],
    )

    assert report["timing"]["at_or_after_match_start"] == 2
    assert report["duplicates"]["duplicate_market_exposures"] == 1
    assert report["settlement"]["mismatches"] == 2
    assert report["features"]["forbidden_columns"] == ["actual_value"]


def test_candidate_audit_accepts_predictions_with_existing_source_columns() -> None:
    selections = pd.DataFrame(
        [
            {
                "sample_key": "m1|cornerKicks|ALL|total",
                "side_key": "m1|cornerKicks|ALL|total|under",
                "exposure_match_id": "m1",
                "direction": "under",
                "line_value": 10.5,
                "actual_value": 9.0,
                "settlement_result": "win",
                "match_date": "2026-01-10",
                "odds_snapshot_time": "2026-01-10T12:00:00Z",
                "odds_snapshot_time_source": "prediction.snapshot",
                "match_start_time": "2026-01-10T14:00:00Z",
                "match_start_time_source": "prediction.start",
            }
        ]
    )
    source = selections[
        [
            "sample_key",
            "actual_value",
            "odds_snapshot_time",
            "odds_snapshot_time_source",
            "match_start_time",
            "match_start_time_source",
        ]
    ].copy()

    report = audit_candidate(
        selections,
        source,
        feature_columns=["line_value"],
    )

    assert report["timing"]["before_match_start"] == 1
    assert report["timing"]["at_or_after_match_start"] == 0
    assert report["settlement"]["mismatches"] == 0
