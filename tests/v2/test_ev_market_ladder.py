from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.market_ladder import (
    LADDER_FEATURE_COLUMNS,
    LADDER_MODEL_FEATURE_COLUMNS,
    build_snapshot_ladder_features,
    transform_ladder_features_for_model,
)


def _market_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sample_key": "m1|cornerKicks|ALL|total",
                "exposure_match_id": "m1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 10.5,
                "over_odds": 1.90,
                "under_odds": 1.90,
                "market_fair_probability_over": 0.50,
                "market_anchor_lambda": 11.17,
                "odds_snapshot_time": "2026-01-02T12:00:00Z",
                "match_start_time": "2026-01-02T18:00:00Z",
            }
        ]
    )


def _snapshot(
    line: float,
    direction: str,
    odds: float,
    *,
    fetched_at: str = "2026-01-02T12:00:00Z",
) -> dict[str, object]:
    return {
        "match_id": "m1",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "total",
        "snapshot_fetched_at": fetched_at,
        "line_value": line,
        "direction": direction,
        "odds_decimal": odds,
        "is_primary_modeled_stat": True,
    }


def _ladder() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _snapshot(9.5, "over", 1.50),
            _snapshot(9.5, "under", 2.40),
            _snapshot(10.5, "over", 1.90),
            _snapshot(10.5, "under", 1.90),
            _snapshot(11.5, "over", 2.40),
            _snapshot(11.5, "under", 1.50),
        ]
    )


def test_ladder_features_use_leave_current_line_out_consensus() -> None:
    raw, audit = build_snapshot_ladder_features(
        _market_frame(),
        _ladder(),
    )
    model = transform_ladder_features_for_model(raw)

    assert tuple(raw.columns) == LADDER_FEATURE_COLUMNS
    assert tuple(model.columns) == LADDER_MODEL_FEATURE_COLUMNS
    assert raw.loc[0, "ladder_line_count"] == 3
    assert raw.loc[0, "ladder_line_span"] == 2.0
    assert pd.notna(raw.loc[0, "ladder_other_anchor_median"])
    assert pd.notna(
        raw.loc[
            0,
            "ladder_current_probability_minus_neighbor_consensus",
        ]
    )
    assert audit["rows_with_usable_leave_current_out_ladder"] == 1
    assert audit["current_line_price_alignment_rows"] == 1


def test_ladder_features_ignore_future_snapshot_ladders() -> None:
    future = _ladder().copy()
    future["snapshot_fetched_at"] = "2026-01-02T13:00:00Z"
    future["line_value"] += 5.0
    snapshots = pd.concat([_ladder(), future], ignore_index=True)

    raw, audit = build_snapshot_ladder_features(
        _market_frame(),
        snapshots,
    )

    assert raw.loc[0, "ladder_line_count"] == 3
    assert raw.loc[0, "ladder_line_span"] == 2.0
    assert audit["future_snapshot_ladders_excluded"] == 1
    assert audit["future_snapshot_ladders_used"] == 0


def test_ladder_features_fail_closed_when_current_price_does_not_align() -> None:
    frame = _market_frame()
    frame.loc[0, "over_odds"] = 1.91

    raw, audit = build_snapshot_ladder_features(
        frame,
        _ladder(),
    )

    assert raw.loc[0, "ladder_line_count"] == 3
    assert pd.isna(
        raw.loc[0, "ladder_current_anchor_minus_other_median"]
    )
    assert audit["current_line_price_alignment_rows"] == 0
    assert audit["rows_with_usable_leave_current_out_ladder"] == 0


def test_ladder_features_reject_post_start_model_snapshot() -> None:
    frame = _market_frame()
    frame.loc[0, "odds_snapshot_time"] = frame.loc[0, "match_start_time"]

    with pytest.raises(ValueError, match="strictly before kickoff"):
        build_snapshot_ladder_features(frame, _ladder())
