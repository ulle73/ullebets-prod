import pandas as pd

from ullebets_v1.audit.odds_timing import (
    AT_OR_AFTER_START_STATUS,
    PRE_MATCH_STATUS,
    annotate_backtest_timing,
    build_backtest_timing_summary,
)


def test_annotate_backtest_timing_enforces_required_side_prematch_rules():
    kickoff_m1 = int(pd.Timestamp("2026-01-01T20:00:00Z").timestamp())
    kickoff_m2 = int(pd.Timestamp("2026-01-02T15:00:00Z").timestamp())
    features = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "resolved_teamstats_match_id": "m1",
                "match_date": "2026-01-01",
                "league_name": "Premier League",
                "home_team_name": "Home",
                "away_team_name": "Away",
                "period": "ALL",
                "scope": "home",
                "stat_key": "shotsOnGoal",
                "line_value": 4.5,
                "market_side_policy": "over_only",
                "actual_value": 5.0,
                "is_model_eligible_segment": True,
                "is_canonical_line": True,
            },
            {
                "match_id": "m2",
                "resolved_teamstats_match_id": "m2",
                "match_date": "2026-01-02",
                "league_name": "Premier League",
                "home_team_name": "Home2",
                "away_team_name": "Away2",
                "period": "ALL",
                "scope": "total",
                "stat_key": "cornerKicks",
                "line_value": 9.5,
                "market_side_policy": "two_sided",
                "actual_value": 10.0,
                "is_model_eligible_segment": True,
                "is_canonical_line": True,
            },
        ]
    )
    market_lines = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "resolved_teamstats_match_id": "m1",
                "match_date": "2026-01-01",
                "league_name": "Premier League",
                "home_team_name": "Home",
                "away_team_name": "Away",
                "period": "ALL",
                "scope": "home",
                "stat_key": "shotsOnGoal",
                "line_value": 4.5,
                "direction": "over",
                "latest_snapshot_fetched_at": "2025-12-31T18:00:00Z",
                "updated_at": None,
                "generated_at": "2025-12-31T10:00:00Z",
                "kickoff_ts": kickoff_m1,
            },
            {
                "match_id": "m2",
                "resolved_teamstats_match_id": "m2",
                "match_date": "2026-01-02",
                "league_name": "Premier League",
                "home_team_name": "Home2",
                "away_team_name": "Away2",
                "period": "ALL",
                "scope": "total",
                "stat_key": "cornerKicks",
                "line_value": 9.5,
                "direction": "over",
                "latest_snapshot_fetched_at": "2026-01-02T14:00:00Z",
                "updated_at": None,
                "generated_at": "2026-01-02T10:00:00Z",
                "kickoff_ts": kickoff_m2,
            },
            {
                "match_id": "m2",
                "resolved_teamstats_match_id": "m2",
                "match_date": "2026-01-02",
                "league_name": "Premier League",
                "home_team_name": "Home2",
                "away_team_name": "Away2",
                "period": "ALL",
                "scope": "total",
                "stat_key": "cornerKicks",
                "line_value": 9.5,
                "direction": "under",
                "latest_snapshot_fetched_at": None,
                "updated_at": "2026-01-02T16:05:00Z",
                "generated_at": "2026-01-02T11:00:00Z",
                "kickoff_ts": kickoff_m2,
            },
        ]
    )

    audited = annotate_backtest_timing(features, market_lines)

    shots = audited[audited["match_id"] == "m1"].iloc[0]
    assert shots["odds_timing_status"] == PRE_MATCH_STATUS
    assert bool(shots["is_strictly_prematch_odds"]) is True
    assert shots["over_snapshot_time_source"] == "unibet-backtest snapshots.snapshot_fetched_at"

    corners = audited[audited["match_id"] == "m2"].iloc[0]
    assert corners["under_odds_timing_status"] == AT_OR_AFTER_START_STATUS
    assert corners["odds_timing_status"] == AT_OR_AFTER_START_STATUS
    assert bool(corners["is_strictly_prematch_odds"]) is False
    assert bool(corners["timing_leakage_risk"]) is True

    summary = build_backtest_timing_summary(audited)
    assert summary["total_tested_odds_rows"] == 3
    assert summary["rows_before_matchstart"] == 2
    assert summary["rows_at_or_after_matchstart"] == 1
