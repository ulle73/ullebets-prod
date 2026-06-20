import pandas as pd

from ullebets_v1.reporting.diagnostics import build_model_diagnostics


def test_build_model_diagnostics_computes_one_pick_per_match_summary():
    feature_frame = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "effective_odds_source": "latest_snapshot",
                "latest_snapshot_type": "closing",
                "latest_snapshot_minutes_before_kickoff": 90.0,
            }
        ]
    )
    selections = pd.DataFrame(
        [
            {
                "strategy": "poisson_model",
                "match_id": "m1",
                "league_name": "Premier League",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "selected_odds": 2.0,
                "expected_roi_units": 0.4,
                "realized_roi_units": 1.0,
                "selected_clv_pct": None,
                "latest_snapshot_minutes_before_kickoff": 90.0,
            },
            {
                "strategy": "poisson_model",
                "match_id": "m1",
                "league_name": "Premier League",
                "stat_key": "cornerKicks",
                "period": "1ST",
                "scope": "home",
                "selected_odds": 2.1,
                "expected_roi_units": 0.2,
                "realized_roi_units": -1.0,
                "selected_clv_pct": None,
                "latest_snapshot_minutes_before_kickoff": 120.0,
            },
        ]
    )

    diagnostics = build_model_diagnostics(feature_frame, selections)

    assert diagnostics["selection_summary"]["overall_by_strategy"]["poisson_model"]["bets"] == 2
    assert diagnostics["selection_summary"]["one_pick_per_match_by_strategy"]["poisson_model"]["bets"] == 1
