from datetime import UTC, datetime

from ullebets_v2.market_bias.forward import load_forward_candidates


class Collection:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def find(self, query=None, projection=None):
        self.queries.append(query)
        return list(self.rows)


def _database(*, snapshot_time=None, fetched_at=None):
    kickoff = datetime(2026, 8, 20, 18, tzinfo=UTC)
    return {
        "fixtures_canonical": Collection(
            [
                {
                    "match_key": "m1",
                    "source_match_id": "s1",
                    "league_key": "l1",
                    "home_team_key": "h1",
                    "away_team_key": "a1",
                    "start_time": kickoff,
                    "source_date": "2026-08-20",
                }
            ]
        ),
        "market_snapshots": Collection(
            [
                {
                    "match_key": "m1",
                    "snapshot_key": "x",
                    "snapshot_label": "T_MINUS_30M",
                    "snapshot_time": snapshot_time or datetime(2026, 8, 20, 17, 30, tzinfo=UTC),
                    "match_start_time": kickoff,
                    "line": 10.5,
                    "over_odds": 1.98,
                    "under_odds": None,
                    "offer_key": "o",
                    "market_scope": "home",
                    "stat_key": "cornerKicks",
                    "period": "ALL",
                    "invalid_for_model": False,
                }
            ]
        ),
        "match_stats_canonical": Collection(
            [
                {
                    "match_key": "m1",
                    "stat_key": "cornerKicks",
                    "scope": "home",
                    "period": "ALL",
                    "actual_value": 11.0,
                    "_id": "ignored",
                }
            ]
        ),
        "match_results_canonical": Collection(
            [{"match_key": "m1", "fetched_at": fetched_at or datetime(2026, 8, 20, 21, tzinfo=UTC)}]
        ),
    }


def test_forward_loader_uses_bounded_v2_queries_and_result_availability() -> None:
    database = _database()
    candidates, audit = load_forward_candidates(
        database,
        from_date="2026-08-20",
        to_date="2026-08-20",
        as_of=datetime(2026, 8, 21, tzinfo=UTC),
        run_id="r",
    )

    assert len(candidates) == 1
    assert candidates[0].observation_docs[0]["actual_value"] == 11.0
    assert candidates[0].observation_docs[0]["outcome_available_at"] == datetime(2026, 8, 20, 21, tzinfo=UTC)
    assert audit["accepted_observation_count"] == 1
    assert database["fixtures_canonical"].queries == [{"source_date": {"$gte": "2026-08-20", "$lte": "2026-08-20"}}]
    for name in ("market_snapshots", "match_stats_canonical", "match_results_canonical"):
        assert database[name].queries == [{"match_key": {"$in": ["m1"]}}]


def test_forward_loader_rejects_post_start_and_unavailable_outcomes() -> None:
    database = _database(snapshot_time=datetime(2026, 8, 20, 18, tzinfo=UTC))
    candidates, audit = load_forward_candidates(
        database,
        from_date="2026-08-20",
        to_date="2026-08-20",
        as_of=datetime(2026, 8, 21, tzinfo=UTC),
        run_id="r",
    )
    assert candidates == []
    assert audit["timing_rejection_count"] == 1
    assert audit["qualifying_line_failure_count"] == 1

    unavailable = _database(fetched_at=datetime(2026, 8, 21, tzinfo=UTC))
    candidates, audit = load_forward_candidates(
        unavailable,
        from_date="2026-08-20",
        to_date="2026-08-20",
        as_of=datetime(2026, 8, 21, tzinfo=UTC),
        run_id="r",
    )
    assert candidates == []
    assert audit["missing_result_availability_count"] == 1


def test_forward_loader_is_idempotent_and_hash_ignores_mongo_id() -> None:
    database = _database()
    first, _ = load_forward_candidates(
        database,
        from_date="2026-08-20",
        to_date="2026-08-20",
        as_of=datetime(2026, 8, 21, tzinfo=UTC),
        run_id="r",
    )
    database["match_stats_canonical"].rows[0]["_id"] = "different"
    second, _ = load_forward_candidates(
        database,
        from_date="2026-08-20",
        to_date="2026-08-20",
        as_of=datetime(2026, 8, 21, tzinfo=UTC),
        run_id="r",
    )

    assert first[0].observation_docs[0]["observation_key"] == second[0].observation_docs[0]["observation_key"]
    assert first[0].observation_docs[0]["source_payload_hash"] == second[0].observation_docs[0]["source_payload_hash"]
