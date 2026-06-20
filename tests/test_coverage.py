import pandas as pd

from ullebets_v1.normalize.coverage import build_market_line_coverage


def test_build_market_line_coverage_prefers_latest_prematch_snapshot_odds():
    market_lines = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "match_date": "2026-01-01",
                "home_team_name": "Home",
                "away_team_name": "Away",
                "bet_key": "k1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 9.5,
                "odds_decimal": 1.9,
                "settlement_result": "win",
                "actual_value": 10,
            }
        ]
    )
    market_snapshots = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "match_date": "2026-01-01",
                "bet_key": "k1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 9.5,
                "odds_decimal": 2.05,
                "snapshot_type": "closing",
                "snapshot_fetched_at": "2025-12-31T11:30:00Z",
            },
            {
                "match_id": "m1",
                "match_date": "2026-01-01",
                "bet_key": "k1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "line_value": 9.5,
                "odds_decimal": 1.95,
                "snapshot_type": "forward",
                "snapshot_fetched_at": "2025-12-30T11:30:00Z",
            },
        ]
    )
    teamstats_index = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "match_date": "2026-01-01",
                "home_team_name": "Home",
                "away_team_name": "Away",
                "kickoff_ts": 1767268800,
                "saved_at": "2026-01-01T20:00:00Z",
                "source_kind": "local_file",
                "home_team_id": "1",
                "away_team_id": "2",
            }
        ]
    )

    enriched, coverage = build_market_line_coverage(
        market_lines=market_lines,
        market_snapshots=market_snapshots,
        teamstats_index=teamstats_index,
        closing_lines=pd.DataFrame(),
        shortlist_rows=pd.DataFrame(),
        result_loop_rows=pd.DataFrame(),
    )

    assert enriched.loc[0, "has_latest_prematch_snapshot"] == True
    assert enriched.loc[0, "latest_snapshot_type"] == "closing"
    assert enriched.loc[0, "effective_odds_decimal"] == 2.05
    assert enriched.loc[0, "effective_odds_source"] == "latest_snapshot"
    assert coverage.loc[0, "has_latest_prematch_snapshot"] == True
