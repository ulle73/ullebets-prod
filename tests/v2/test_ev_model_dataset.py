from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.dataset import prepare_modeling_frame


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "exposure_match_id": "match-1",
        "match_date": "2026-01-10",
        "stat_key": "cornerKicks",
        "scope": "total",
        "period": "ALL",
        "line_value": 10.5,
        "actual_value": 12.0,
        "over_odds": 1.9,
        "under_odds": 1.9,
        "is_model_eligible_segment": True,
        "is_canonical_line": True,
        "is_strictly_prematch_odds": True,
        "latest_snapshot_minutes_before_kickoff": 120.0,
    }
    row.update(overrides)
    return row


def test_modeling_frame_keeps_only_verified_unique_prematch_rows() -> None:
    frame = pd.DataFrame(
        [
            _row(),
            _row(latest_snapshot_minutes_before_kickoff=300.0),
            _row(exposure_match_id="match-2", stat_key="fouls"),
            _row(exposure_match_id="match-3", is_strictly_prematch_odds=False),
            _row(exposure_match_id="match-4", actual_value=None),
            _row(exposure_match_id="match-5", is_canonical_line=False),
        ]
    )

    prepared, audit = prepare_modeling_frame(frame)

    assert prepared["exposure_match_id"].tolist() == ["match-1"]
    assert prepared["sample_key"].tolist() == ["match-1|cornerKicks|ALL|total"]
    assert prepared.iloc[0]["latest_snapshot_minutes_before_kickoff"] == 120.0
    assert audit.input_rows == 6
    assert audit.output_rows == 1
    assert audit.duplicate_rows_removed == 1


def test_modeling_frame_requires_audited_timing_status() -> None:
    frame = pd.DataFrame([_row()]).drop(columns=["is_strictly_prematch_odds"])

    with pytest.raises(ValueError, match="is_strictly_prematch_odds"):
        prepare_modeling_frame(frame)


def test_over_only_markets_do_not_require_under_odds() -> None:
    frame = pd.DataFrame(
        [
            _row(
                stat_key="shotsOnGoal",
                scope="home",
                under_odds=None,
            )
        ]
    )

    prepared, _ = prepare_modeling_frame(frame)

    assert len(prepared) == 1
