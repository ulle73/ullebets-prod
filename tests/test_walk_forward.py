import pandas as pd

from ullebets_v1.backtest.metrics import roi_units
from ullebets_v1.backtest.walk_forward import _selection_from_lambda


def test_roi_units_handles_win_loss_push():
    assert roi_units("win", 2.0) == 1.0
    assert roi_units("loss", 2.0) == -1.0
    assert roi_units("push", 2.0) == 0.0


def test_selection_from_lambda_preserves_snapshot_metadata():
    frame = pd.DataFrame(
        [
            {
                "exposure_match_id": "m1",
                "match_id": "m1",
                "match_date": "2026-01-03",
                "league_name": "Premier League",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 8.5,
                "over_odds": 1.9,
                "under_odds": 2.1,
                "over_result": "win",
                "under_result": "loss",
                "over_clv_pct": 0.03,
                "under_clv_pct": -0.01,
                "model_lambda": 12.0,
                "effective_odds_source": "latest_snapshot",
                "latest_snapshot_type": "closing",
                "latest_snapshot_minutes_before_kickoff": 90.0,
                "has_latest_prematch_snapshot": True,
                "prematch_snapshot_count": 4,
            }
        ]
    )

    selections = _selection_from_lambda(frame, "model_lambda", threshold=0.0)

    assert len(selections) == 1
    row = selections.iloc[0]
    assert row["effective_odds_source"] == "latest_snapshot"
    assert row["latest_snapshot_type"] == "closing"
    assert row["latest_snapshot_minutes_before_kickoff"] == 90.0
    assert bool(row["has_latest_prematch_snapshot"]) is True
    assert row["prematch_snapshot_count"] == 4


def test_selection_from_lambda_dedupes_by_exposure_match_id_not_raw_match_id():
    frame = pd.DataFrame(
        [
            {
                "exposure_match_id": "ts1",
                "match_id": None,
                "resolved_teamstats_match_id": "ts1",
                "match_date": "2026-01-03",
                "league_name": "Premier League",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 8.5,
                "over_odds": 2.2,
                "under_odds": 1.7,
                "over_result": "win",
                "under_result": "loss",
                "over_clv_pct": 0.03,
                "under_clv_pct": -0.01,
                "model_lambda": 12.0,
            },
            {
                "exposure_match_id": "ts2",
                "match_id": None,
                "resolved_teamstats_match_id": "ts2",
                "match_date": "2026-01-03",
                "league_name": "Premier League",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 8.5,
                "over_odds": 2.15,
                "under_odds": 1.72,
                "over_result": "win",
                "under_result": "loss",
                "over_clv_pct": 0.02,
                "under_clv_pct": -0.01,
                "model_lambda": 12.0,
            },
        ]
    )

    selections = _selection_from_lambda(frame, "model_lambda", threshold=0.0)

    assert len(selections) == 2
    assert set(selections["exposure_match_id"]) == {"ts1", "ts2"}
