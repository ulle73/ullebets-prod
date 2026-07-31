from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.market_movement import (
    MOVEMENT_FEATURE_COLUMNS,
    build_snapshot_movement_features,
    transform_movement_features_for_model,
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
                "market_overround": (2.0 / 1.90) - 1.0,
                "odds_snapshot_time": "2026-01-02T12:00:00Z",
                "match_start_time": "2026-01-02T18:00:00Z",
            }
        ]
    )


def _snapshot(
    fetched_at: str,
    line: float,
    direction: str,
    odds: float,
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


def test_movement_features_use_canonical_market_at_each_snapshot() -> None:
    snapshots = pd.DataFrame(
        [
            _snapshot("2026-01-01T12:00:00Z", 9.5, "over", 1.90),
            _snapshot("2026-01-01T12:00:00Z", 9.5, "under", 1.90),
            _snapshot("2026-01-01T12:00:00Z", 8.5, "over", 1.40),
            _snapshot("2026-01-01T12:00:00Z", 8.5, "under", 2.70),
            _snapshot("2026-01-02T12:00:00Z", 10.5, "over", 1.90),
            _snapshot("2026-01-02T12:00:00Z", 10.5, "under", 1.90),
            _snapshot("2026-01-02T12:00:00Z", 9.5, "over", 1.45),
            _snapshot("2026-01-02T12:00:00Z", 9.5, "under", 2.55),
        ]
    )

    features, audit = build_snapshot_movement_features(
        _market_frame(),
        snapshots,
    )

    assert tuple(features.columns) == MOVEMENT_FEATURE_COLUMNS
    assert features.loc[0, "movement_snapshot_observations"] == 2
    assert features.loc[0, "movement_snapshot_span_hours"] == 24.0
    assert features.loc[0, "movement_line_delta_from_open"] == 1.0
    assert features.loc[0, "movement_line_delta_from_previous"] == 1.0
    assert features.loc[0, "movement_line_changed_from_open"] == 1.0
    assert features.loc[0, "movement_anchor_delta_from_open"] > 0.0
    assert audit["rows_with_two_or_more_observations"] == 1
    assert audit["current_canonical_line_alignment_rows"] == 1


def test_movement_features_ignore_snapshots_after_row_snapshot_time() -> None:
    snapshots = pd.DataFrame(
        [
            _snapshot("2026-01-01T12:00:00Z", 9.5, "over", 1.90),
            _snapshot("2026-01-01T12:00:00Z", 9.5, "under", 1.90),
            _snapshot("2026-01-02T12:00:00Z", 10.5, "over", 1.90),
            _snapshot("2026-01-02T12:00:00Z", 10.5, "under", 1.90),
            _snapshot("2026-01-02T13:00:00Z", 11.5, "over", 1.90),
            _snapshot("2026-01-02T13:00:00Z", 11.5, "under", 1.90),
        ]
    )

    features, audit = build_snapshot_movement_features(
        _market_frame(),
        snapshots,
    )

    assert features.loc[0, "movement_snapshot_observations"] == 2
    assert features.loc[0, "movement_line_delta_from_open"] == 1.0
    assert audit["future_market_observations_excluded"] == 1
    assert audit["future_market_observations_used"] == 0


def test_movement_model_transform_compresses_outliers_without_changing_sign() -> None:
    raw = pd.DataFrame(
        {
            column: [0.0]
            for column in MOVEMENT_FEATURE_COLUMNS
        }
    )
    raw.loc[0, "movement_snapshot_observations"] = 7.0
    raw.loc[0, "movement_snapshot_span_hours"] = 168.0
    raw.loc[0, "movement_line_delta_from_open"] = -27.0
    raw.loc[0, "movement_line_changed_from_open"] = 1.0

    transformed = transform_movement_features_for_model(raw)

    assert transformed.loc[
        0, "movement_snapshot_observations_log1p"
    ] == pytest.approx(2.0794415)
    assert transformed.loc[
        0, "movement_line_delta_from_open_signed_log1p"
    ] < 0.0
    assert abs(
        transformed.loc[
            0, "movement_line_delta_from_open_signed_log1p"
        ]
    ) < 4.0
    assert transformed.loc[
        0, "movement_line_changed_from_open"
    ] == 1.0


def test_movement_features_leave_missing_history_explicit() -> None:
    features, audit = build_snapshot_movement_features(
        _market_frame(),
        pd.DataFrame(
            columns=[
                "match_id",
                "stat_key",
                "period",
                "scope",
                "snapshot_fetched_at",
                "line_value",
                "direction",
                "odds_decimal",
            ]
        ),
    )

    assert features.loc[0, "movement_snapshot_observations"] == 0
    assert pd.isna(features.loc[0, "movement_line_delta_from_open"])
    assert audit["rows_without_observations"] == 1


def test_movement_features_reject_post_start_model_snapshot() -> None:
    frame = _market_frame()
    frame.loc[0, "odds_snapshot_time"] = frame.loc[0, "match_start_time"]

    with pytest.raises(ValueError, match="strictly before kickoff"):
        build_snapshot_movement_features(frame, pd.DataFrame())
