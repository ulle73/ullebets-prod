from datetime import UTC, datetime

import pandas as pd

from ullebets_v2.market_bias.bootstrap import _time, build_bootstrap_candidates


def test_bootstrap_parses_unix_seconds_and_milliseconds() -> None:
    expected = datetime(2026, 8, 20, 12, tzinfo=UTC)
    seconds = expected.timestamp()

    assert _time(seconds) == expected
    assert _time(seconds * 1000) == expected


def test_bootstrap_accepts_only_exact_safe_prematch_mappings(tmp_path) -> None:
    snapshots = pd.DataFrame([
        {"match_id": "m1", "snapshot_fetched_at": "2026-08-20T10:00:00Z", "snapshot_type": "T_MINUS_30M", "bet_key": "b1", "stat_key": "cornerKicks", "period": "ALL", "scope": "home", "direction": "over", "line_value": 10.5, "odds_decimal": 1.98, "is_primary_modeled_stat": True},
        {"match_id": "m2", "snapshot_fetched_at": "2026-08-20T13:00:00Z", "snapshot_type": "T_MINUS_30M", "bet_key": "b2", "stat_key": "cornerKicks", "period": "ALL", "scope": "home", "direction": "over", "line_value": 10.5, "odds_decimal": 1.98, "is_primary_modeled_stat": True},
    ])
    lines = pd.DataFrame([
        {"match_id": "m1", "bet_key":"b1", "stat_key":"cornerKicks", "period":"ALL", "scope":"home", "direction":"over", "line_value":10.5, "league_name": "League", "home_team_name": "Home", "away_team_name": "Away", "home_team_id": "h1", "away_team_id": "a1", "kickoff_ts": "2026-08-20T12:00:00Z", "actual_value": 11.0, "has_authoritative_teamstats_outcome": True},
        {"match_id": "m2", "bet_key":"b2", "stat_key":"cornerKicks", "period":"ALL", "scope":"home", "direction":"over", "line_value":10.5, "league_name": "League", "home_team_name": "Ambiguous", "away_team_name": "Away", "home_team_id": None, "away_team_id": "a1", "kickoff_ts": "2026-08-20T12:00:00Z", "actual_value": 11.0, "has_authoritative_teamstats_outcome": True},
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


def test_bootstrap_joins_each_snapshot_to_its_exact_market_line(tmp_path) -> None:
    snapshots = pd.DataFrame([
        {"match_id":"m1","bet_key":"corners-over","snapshot_fetched_at":"2026-08-20T10:00:00Z","snapshot_type":"T_MINUS_30M","stat_key":"cornerKicks","period":"ALL","scope":"home","direction":"over","line_value":10.5,"odds_decimal":1.98,"is_primary_modeled_stat":True},
        {"match_id":"m1","bet_key":"shots-over","snapshot_fetched_at":"2026-08-20T10:00:00Z","snapshot_type":"T_MINUS_30M","stat_key":"totalShots","period":"ALL","scope":"home","direction":"over","line_value":20.5,"odds_decimal":1.98,"is_primary_modeled_stat":True},
    ])
    kickoff_epoch = datetime(2026, 8, 20, 12, tzinfo=UTC).timestamp()
    lines = pd.DataFrame([{**row, "league_name":"LaLiga", "home_team_name":"Home", "away_team_name":"Away", "home_team_id":"h", "away_team_id":"a", "kickoff_ts":kickoff_epoch, "actual_value":11.0 if row["stat_key"] == "cornerKicks" else 22.0, "has_authoritative_teamstats_outcome":True} for row in snapshots.to_dict("records")])
    for name, frame in {"market_snapshots":snapshots,"market_lines":lines,"matches":pd.DataFrame([{"match_id":"m1"}])}.items(): frame.to_parquet(tmp_path / f"{name}.parquet")
    support={"teams":[{"team_key":"h","league_key":"la","team_id":"h","team_name":"Home"},{"team_key":"a","league_key":"la","team_id":"a","team_name":"Away"}],"leagues":[{"league_key":"la","league_name":"La Liga","unibet_lookup_slugs":["LaLiga"]}]}
    candidates, _ = build_bootstrap_candidates(tmp_path, support_docs=support, as_of=datetime(2026,8,21,tzinfo=UTC), run_id="r")
    assert {doc["actual_value"] for candidate in candidates for doc in candidate.observation_docs} == {11.0,22.0}


def test_bootstrap_uses_unique_configured_aliases_and_contextual_snapshot_identity(tmp_path) -> None:
    snapshots = pd.DataFrame([
        {"match_id":"m1","bet_key":"corners-over","snapshot_fetched_at":"2026-08-20T10:00:00Z","snapshot_type":"T_MINUS_30M","stat_key":"cornerKicks","period":"ALL","scope":"home","direction":"over","line_value":10.5,"odds_decimal":1.98,"is_primary_modeled_stat":True},
        {"match_id":"m1","bet_key":"shots-over","snapshot_fetched_at":"2026-08-20T10:00:00Z","snapshot_type":"T_MINUS_30M","stat_key":"totalShots","period":"ALL","scope":"home","direction":"over","line_value":10.5,"odds_decimal":1.98,"is_primary_modeled_stat":True},
    ])
    lines = pd.DataFrame([
        {**row, "league_name":"League", "home_team_name":"Home Source", "away_team_name":"Away Source", "home_team_id":None, "away_team_id":None, "kickoff_ts":"2026-08-20T12:00:00Z", "actual_value":11.0, "has_authoritative_teamstats_outcome":True}
        for row in snapshots.to_dict("records")
    ])
    for name, frame in {"market_snapshots":snapshots,"market_lines":lines,"matches":pd.DataFrame([{"match_id":"m1"}])}.items():
        frame.to_parquet(tmp_path / f"{name}.parquet")
    support = {
        "teams": [
            {"team_key":"home","league_key":"league","team_name":"Home", "aliases":["Home Source"]},
            {"team_key":"away","league_key":"league","team_name":"Away", "team_aliases":["Away Source"]},
        ],
        "leagues": [{"league_key":"league", "league_name":"League"}],
    }

    candidates, audit = build_bootstrap_candidates(tmp_path, support_docs=support, as_of=datetime(2026,8,21,tzinfo=UTC), run_id="r")
    snapshot_keys = {doc["snapshot_key"] for candidate in candidates for doc in candidate.observation_docs}

    assert audit["mapping_method_counts"]["configured_alias"] == 4
    assert len(snapshot_keys) == 2


def test_bootstrap_duplicate_line_selection_is_independent_of_parquet_row_order(tmp_path) -> None:
    snapshot = {
        "match_id": "m1", "bet_key": "b1", "snapshot_fetched_at": "2026-08-20T10:00:00Z",
        "snapshot_type": "T_MINUS_30M", "stat_key": "cornerKicks", "period": "ALL",
        "scope": "home", "direction": "over", "line_value": 10.5, "odds_decimal": 1.98,
        "is_primary_modeled_stat": True,
    }
    base_line = {
        **snapshot, "league_name": "League", "home_team_name": "Home", "away_team_name": "Away",
        "home_team_id": "h", "away_team_id": "a", "kickoff_ts": "2026-08-20T12:00:00Z",
        "teamstats_saved_at": "2026-08-20T15:00:00Z", "actual_value": 11.0,
        "has_authoritative_teamstats_outcome": True,
    }
    support = {
        "teams": [
            {"team_key": "home", "league_key": "league", "team_id": "h", "team_name": "Home"},
            {"team_key": "away", "league_key": "league", "team_id": "a", "team_name": "Away"},
        ],
        "leagues": [{"league_key": "league", "league_name": "League"}],
    }

    def source_hash(rows: list[dict]) -> str:
        pd.DataFrame([snapshot]).to_parquet(tmp_path / "market_snapshots.parquet")
        pd.DataFrame(rows).to_parquet(tmp_path / "market_lines.parquet")
        pd.DataFrame([{"match_id": "m1"}]).to_parquet(tmp_path / "matches.parquet")
        candidates, _ = build_bootstrap_candidates(
            tmp_path,
            support_docs=support,
            as_of=datetime(2026, 8, 21, tzinfo=UTC),
            run_id="r",
        )
        return candidates[0].observation_docs[0]["source_payload_hash"]

    older = {**base_line, "generated_at": "2026-08-19T10:00:00Z", "league_name": "Old label"}
    newer = {**base_line, "generated_at": "2026-08-20T10:00:00Z"}

    assert source_hash([older, newer]) == source_hash([newer, older])


def test_bootstrap_duplicate_snapshot_prices_choose_nearest_even_odds(tmp_path) -> None:
    snapshots = pd.DataFrame([
        {"match_id": "m1", "bet_key": "over-high", "snapshot_fetched_at": "2026-08-20T10:00:00Z", "snapshot_type": "T_MINUS_30M", "stat_key": "cornerKicks", "period": "ALL", "scope": "home", "direction": "over", "line_value": 10.5, "odds_decimal": 2.28, "is_primary_modeled_stat": True},
        {"match_id": "m1", "bet_key": "over-even", "snapshot_fetched_at": "2026-08-20T10:00:00Z", "snapshot_type": "T_MINUS_30M", "stat_key": "cornerKicks", "period": "ALL", "scope": "home", "direction": "over", "line_value": 10.5, "odds_decimal": 2.00, "is_primary_modeled_stat": True},
        {"match_id": "m1", "bet_key": "under-low", "snapshot_fetched_at": "2026-08-20T10:00:00Z", "snapshot_type": "T_MINUS_30M", "stat_key": "cornerKicks", "period": "ALL", "scope": "home", "direction": "under", "line_value": 10.5, "odds_decimal": 1.72, "is_primary_modeled_stat": True},
        {"match_id": "m1", "bet_key": "under-even", "snapshot_fetched_at": "2026-08-20T10:00:00Z", "snapshot_type": "T_MINUS_30M", "stat_key": "cornerKicks", "period": "ALL", "scope": "home", "direction": "under", "line_value": 10.5, "odds_decimal": 1.95, "is_primary_modeled_stat": True},
    ])
    line_base = {"match_id": "m1", "stat_key": "cornerKicks", "period": "ALL", "scope": "home", "line_value": 10.5, "league_name": "League", "home_team_name": "Home", "away_team_name": "Away", "home_team_id": "h", "away_team_id": "a", "kickoff_ts": "2026-08-20T12:00:00Z", "teamstats_saved_at": "2026-08-20T15:00:00Z", "generated_at": "2026-08-20T16:00:00Z", "actual_value": 11.0, "has_authoritative_teamstats_outcome": True}
    lines = pd.DataFrame([{**line_base, "bet_key": row["bet_key"], "direction": row["direction"]} for row in snapshots.to_dict("records")])
    snapshots.to_parquet(tmp_path / "market_snapshots.parquet")
    lines.to_parquet(tmp_path / "market_lines.parquet")
    pd.DataFrame([{"match_id": "m1"}]).to_parquet(tmp_path / "matches.parquet")
    support = {"teams": [{"team_key": "home", "league_key": "league", "team_id": "h", "team_name": "Home"}, {"team_key": "away", "league_key": "league", "team_id": "a", "team_name": "Away"}], "leagues": [{"league_key": "league", "league_name": "League"}]}

    candidates, _ = build_bootstrap_candidates(tmp_path, support_docs=support, as_of=datetime(2026, 8, 21, tzinfo=UTC), run_id="r")
    observation = candidates[0].observation_docs[0]

    assert observation["over_odds"] == 2.00
    assert observation["under_odds"] == 1.95
