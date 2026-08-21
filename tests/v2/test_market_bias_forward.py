from datetime import UTC, datetime

from ullebets_v2.market_bias.forward import load_forward_candidates


class Collection:
    def __init__(self, rows): self.rows = rows
    def find(self, query=None, projection=None): return list(self.rows)


def test_forward_loader_uses_v2_actuals_and_result_availability_only() -> None:
    kickoff = datetime(2026, 8, 20, 18, tzinfo=UTC)
    database = {
        "fixtures_canonical": Collection([{"match_key":"m1","source_match_id":"s1","league_key":"l1","home_team_key":"h1","away_team_key":"a1","start_time":kickoff}]),
        "market_snapshots": Collection([{"match_key":"m1","snapshot_key":"x","snapshot_label":"T_MINUS_30M","snapshot_time":datetime(2026,8,20,17,30,tzinfo=UTC),"match_start_time":kickoff,"line":10.5,"over_odds":1.98,"under_odds":None,"offer_key":"o","market_scope":"home","stat_key":"cornerKicks","period":"ALL","invalid_for_model":False}]),
        "match_stats_canonical": Collection([{"match_key":"m1","stat_key":"cornerKicks","scope":"home","period":"ALL","actual_value":11.0}]),
        "match_results_canonical": Collection([{"match_key":"m1","fetched_at":datetime(2026,8,20,21,tzinfo=UTC)}]),
    }
    candidates, audit = load_forward_candidates(database, from_date="2026-08-20", to_date="2026-08-20", run_id="r")
    assert len(candidates) == 1
    assert candidates[0].observation_docs[0]["actual_value"] == 11.0
    assert candidates[0].observation_docs[0]["outcome_available_at"] == datetime(2026,8,20,21,tzinfo=UTC)
    assert audit["accepted_observation_count"] == 1
