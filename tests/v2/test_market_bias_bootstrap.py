from datetime import UTC, datetime

import pandas as pd

from ullebets_v2.market_bias.bootstrap import build_bootstrap_candidates


def test_bootstrap_accepts_only_exact_safe_prematch_mappings(tmp_path) -> None:
    snapshots = pd.DataFrame([
        {"match_id": "m1", "snapshot_fetched_at": "2026-08-20T10:00:00Z", "snapshot_type": "T_MINUS_30M", "bet_key": "b1", "stat_key": "cornerKicks", "period": "ALL", "scope": "home", "direction": "over", "line_value": 10.5, "odds_decimal": 1.98, "is_primary_modeled_stat": True},
        {"match_id": "m2", "snapshot_fetched_at": "2026-08-20T13:00:00Z", "snapshot_type": "T_MINUS_30M", "bet_key": "b2", "stat_key": "cornerKicks", "period": "ALL", "scope": "home", "direction": "over", "line_value": 10.5, "odds_decimal": 1.98, "is_primary_modeled_stat": True},
    ])
    lines = pd.DataFrame([
        {"match_id": "m1", "league_name": "League", "home_team_name": "Home", "away_team_name": "Away", "home_team_id": "h1", "away_team_id": "a1", "kickoff_ts": "2026-08-20T12:00:00Z", "actual_value": 11.0, "has_authoritative_teamstats_outcome": True},
        {"match_id": "m2", "league_name": "League", "home_team_name": "Ambiguous", "away_team_name": "Away", "home_team_id": None, "away_team_id": "a1", "kickoff_ts": "2026-08-20T12:00:00Z", "actual_value": 11.0, "has_authoritative_teamstats_outcome": True},
    ])
    matches = pd.DataFrame([{"match_id": "m1"}, {"match_id": "m2"}])
    for name, frame in {"market_snapshots": snapshots, "market_lines": lines, "matches": matches}.items():
        frame.to_parquet(tmp_path / f"{name}.parquet")
    support = {"teams": [{"team_key": "home-key", "league_key": "league-key", "source_team_id": "h1", "team_name": "Home"}, {"team_key": "away-key", "league_key": "league-key", "source_team_id": "a1", "team_name": "Away"}, {"team_key": "amb-1", "league_key": "league-key", "team_name": "Ambiguous"}, {"team_key": "amb-2", "league_key": "league-key", "team_name": "Ambiguous"}], "leagues": [{"league_key": "league-key", "league_name": "League"}]}

    candidates, audit = build_bootstrap_candidates(tmp_path, support_docs=support, as_of=datetime(2026, 8, 21, tzinfo=UTC), run_id="run")

    assert len(candidates) == 1
    assert candidates[0].observation_docs[0]["team_key"] == "home-key"
    assert audit["accepted_observation_count"] == 1
    assert audit["ambiguous_identity_count"] == 1
