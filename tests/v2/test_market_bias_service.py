from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from ullebets_v2.market_bias.persistence import (
    MARKET_BIAS_BULK_WRITE_BATCH_SIZE,
    ImmutableMarketBiasConflict,
    persist_observations,
    persist_profiles,
)
from ullebets_v2.market_bias.reports import (
    MARKET_BIAS_AUDIT_METRICS,
    build_market_bias_audit_rows,
    build_market_bias_health_rows,
)
from ullebets_v2.market_bias.service import MarketBiasCandidate, run_market_bias_refresh


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict] = []
        self.write_count = 0
        self.find_queries: list[dict] = []
        self.find_one_queries: list[dict] = []

    def find_one(self, query: dict, projection: dict | None = None):  # noqa: ARG002
        self.find_one_queries.append(query)
        return next((dict(doc) for doc in self.docs if all(doc.get(key) == value for key, value in query.items())), None)

    def find(self, query: dict | None = None, projection: dict | None = None):  # noqa: ARG002
        query = query or {}
        self.find_queries.append(query)
        observation_keys = query.get("observation_key")
        if isinstance(observation_keys, dict) and "$in" in observation_keys:
            return [dict(doc) for doc in self.docs if doc.get("observation_key") in observation_keys["$in"]]
        if "$or" in query:
            return [
                dict(doc)
                for doc in self.docs
                if any(all(doc.get(key) == value for key, value in clause.items()) for clause in query["$or"])
            ]
        return [dict(doc) for doc in self.docs if all(doc.get(key) == value for key, value in query.items())]

    def insert_one(self, doc: dict) -> None:
        self.write_count += 1
        self.docs.append(dict(doc))

    def update_one(self, query: dict, update: dict, upsert: bool = False):
        self.write_count += 1
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                doc.update(update.get("$set", {}))
                return SimpleNamespace(upserted_id=None)
        if not upsert:
            raise AssertionError(f"missing document for {query}")
        doc = {**query, **update.get("$set", {})}
        self.docs.append(doc)
        return SimpleNamespace(upserted_id="inserted")


class FakeDatabase(dict):
    def __missing__(self, key: str) -> FakeCollection:
        collection = FakeCollection()
        self[key] = collection
        return collection


class BulkFakeCollection(FakeCollection):
    def __init__(self) -> None:
        super().__init__()
        self.bulk_batch_sizes: list[int] = []

    def bulk_write(self, operations: list[object], ordered: bool) -> None:
        assert ordered is False
        self.bulk_batch_sizes.append(len(operations))
        for operation in operations:
            self.insert_one(operation._doc)  # type: ignore[attr-defined]


def _observation(index: int = 0) -> dict:
    kickoff = datetime(2026, 8, 20, 18, 0, tzinfo=UTC) - timedelta(days=index)
    return {
        "observation_key": f"observation-{index}",
        "match_key": f"match-{index}",
        "source_match_id": f"source-{index}",
        "league_key": "league-1",
        "team_key": "team-1",
        "venue_context": "home",
        "market_scope": "home",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "line_value": 10.5,
        "over_odds": 1.98,
        "under_odds": 1.92,
        "actual_value": 11.0,
        "residual_value": 0.5,
        "line_result": "over",
        "snapshot_key": f"snapshot-{index}",
        "snapshot_label": "T_MINUS_30M",
        "snapshot_time": kickoff - timedelta(minutes=30),
        "match_start_time": kickoff,
        "minutes_to_kickoff": 30.0,
        "outcome_available_at": kickoff + timedelta(hours=3),
        "source_kind": "v2_forward",
        "source_record_key": f"canonical:{index}",
        "source_payload_hash": f"payload-{index}",
        "line_selection_method": "latest_valid_prematch_near_even_over",
        "method_version": "main_line_residual_v1",
        "created_at": kickoff + timedelta(hours=3),
        "run_id": "candidate-run",
    }


def test_persist_observations_is_idempotent_and_rejects_immutable_conflicts() -> None:
    database = FakeDatabase()
    observation = _observation()

    inserted = persist_observations(database, [observation])
    replayed = persist_observations(database, [observation])

    assert inserted == {"observation_inserts": 1, "observation_replays": 0}
    assert replayed == {"observation_inserts": 0, "observation_replays": 1}
    changed = {**observation, "actual_value": 12.0, "source_payload_hash": "changed"}
    with pytest.raises(ImmutableMarketBiasConflict):
        persist_observations(database, [changed])


def test_persist_observations_uses_bounded_unordered_bulk_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    database = FakeDatabase()
    collection = BulkFakeCollection()
    database["market_bias_observations"] = collection
    monkeypatch.setattr("ullebets_v2.market_bias.persistence.MARKET_BIAS_BULK_WRITE_BATCH_SIZE", 2)

    metrics = persist_observations(database, [_observation(index) for index in range(5)])

    assert MARKET_BIAS_BULK_WRITE_BATCH_SIZE > 0
    assert metrics["observation_inserts"] == 5
    assert collection.bulk_batch_sizes == [2, 2, 1]


def test_persist_observations_batch_reads_replays_and_conflicts_without_find_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = FakeDatabase()
    collection = BulkFakeCollection()
    collection.docs.append(_observation(0))
    database["market_bias_observations"] = collection
    monkeypatch.setattr(
        "ullebets_v2.market_bias.persistence.MARKET_BIAS_EXISTING_LOOKUP_BATCH_SIZE",
        2,
    )

    metrics = persist_observations(database, [_observation(index) for index in range(3)])

    assert metrics == {"observation_inserts": 2, "observation_replays": 1}
    assert [len(query["observation_key"]["$in"]) for query in collection.find_queries] == [2, 1]
    assert collection.find_one_queries == []
    with pytest.raises(ImmutableMarketBiasConflict):
        persist_observations(database, [{**_observation(0), "actual_value": 99.0}])


def test_persist_profiles_upserts_by_profile_key() -> None:
    database = FakeDatabase()
    profile = {"profile_key": "profile-1", "direction": "neutral"}

    assert persist_profiles(database, [profile]) == {"profile_upserts": 1}
    assert persist_profiles(database, [{**profile, "direction": "over"}]) == {"profile_upserts": 0}
    assert database["market_bias_profiles"].docs == [{"profile_key": "profile-1", "direction": "over"}]


def test_market_bias_reports_expose_all_required_audit_metrics() -> None:
    metrics = {
        "timing_rejection_count": 1,
        "missing_actual_count": 2,
        "unmatched_identity_count": 3,
        "invalid_row_count": 4,
        "duplicate_observation_key_count": 5,
        "source_hash_conflict_count": 6,
        "qualifying_line_failure_count": 7,
        "counts_by_stat": {"cornerKicks": 1},
        "counts_by_scope": {"home": 1},
        "counts_by_period": {"ALL": 1},
        "counts_by_league": {"league-1": 1},
        "counts_by_snapshot_label": {"T_MINUS_30M": 1},
    }
    audit = build_market_bias_audit_rows(source_workflow="test.yml", metrics=metrics, report_date="2026-08-21")
    health = build_market_bias_health_rows(metrics=metrics, report_date="2026-08-21")

    assert set(MARKET_BIAS_AUDIT_METRICS).issubset(audit[0]["metrics"])
    assert audit[0]["metrics"] == metrics
    assert health[0]["job_name"] == "refresh_market_bias"


def test_run_market_bias_refresh_returns_documents_in_dry_run_without_writes() -> None:
    database = FakeDatabase()
    summary = run_market_bias_refresh(
        source_workflow="test.yml",
        source_kind="v2_forward",
        candidates=[MarketBiasCandidate(observation_docs=tuple(_observation(index) for index in range(6)))],
        as_of=datetime(2026, 8, 21, 18, 0, tzinfo=UTC),
        profile_date="2026-08-21",
        database=database,
        dry_run=True,
    )

    assert len(summary["observation_docs"]) == 6
    assert len(summary["profile_docs"]) == 1
    assert summary["audit_rows"] and summary["health_rows"]
    assert all(collection.write_count == 0 for collection in database.values())


def test_run_market_bias_refresh_merges_existing_history_without_dry_run_writes() -> None:
    database = FakeDatabase()
    existing = [_observation(index) for index in range(1, 7)]
    database["market_bias_observations"].docs.extend(existing)

    summary = run_market_bias_refresh(
        source_workflow="test.yml",
        source_kind="v2_forward",
        candidates=[MarketBiasCandidate(observation_docs=(_observation(7),))],
        as_of=datetime(2026, 8, 21, 18, 0, tzinfo=UTC),
        profile_date="2026-08-21",
        database=database,
        dry_run=True,
    )

    assert summary["profile_docs"][0]["sample_size"] == 7
    assert len(summary["observation_docs"]) == 1
    assert all(collection.write_count == 0 for collection in database.values())


def test_existing_history_queries_are_bounded_to_cosmos_safe_context_batches() -> None:
    database = FakeDatabase()
    database["market_bias_observations"].docs.append({**_observation(999), "team_key": "unrelated"})
    incoming = tuple(
        {**_observation(index), "team_key": f"team-{index}"}
        for index in range(101)
    )

    run_market_bias_refresh(
        source_workflow="test.yml",
        source_kind="v2_forward",
        candidates=[MarketBiasCandidate(observation_docs=incoming)],
        as_of=datetime(2026, 8, 21, 18, 0, tzinfo=UTC),
        profile_date="2026-08-21",
        database=database,
        dry_run=True,
    )

    queries = database["market_bias_observations"].find_queries
    assert len(queries) == 2
    assert all(len(query["$or"]) <= 100 for query in queries)


def test_empty_existing_history_skips_all_context_queries() -> None:
    database = FakeDatabase()

    run_market_bias_refresh(
        source_workflow="test.yml",
        source_kind="v2_forward",
        candidates=[MarketBiasCandidate(observation_docs=tuple(_observation(index) for index in range(101)))],
        as_of=datetime(2026, 8, 21, 18, 0, tzinfo=UTC),
        profile_date="2026-08-21",
        database=database,
        dry_run=True,
    )

    collection = database["market_bias_observations"]
    assert collection.find_one_queries == [{}]
    assert collection.find_queries == []


def test_metrics_only_candidate_keeps_rejection_audit_without_counting_as_source_row() -> None:
    database = FakeDatabase()

    summary = run_market_bias_refresh(
        source_workflow="test.yml",
        source_kind="v2_forward",
        candidates=[
            MarketBiasCandidate(
                observation_docs=(),
                metrics={
                    "timing_rejection_count": 2,
                    "missing_actual_count": 1,
                    "missing_result_availability_count": 1,
                },
            )
        ],
        as_of=datetime(2026, 8, 21, 18, 0, tzinfo=UTC),
        profile_date="2026-08-21",
        database=database,
        dry_run=True,
    )

    assert summary["source_row_count"] == 0
    assert summary["timing_rejection_count"] == 2
    assert summary["missing_actual_count"] == 1
    assert summary["health_rows"][0]["status"] == "warn"
    assert all(collection.write_count == 0 for collection in database.values())


def test_run_market_bias_refresh_persists_one_job_run_lifecycle() -> None:
    database = FakeDatabase()
    summary = run_market_bias_refresh(
        source_workflow="test.yml",
        source_kind="v2_forward",
        candidates=[MarketBiasCandidate(observation_docs=tuple(_observation(index) for index in range(6)))],
        as_of=datetime(2026, 8, 21, 18, 0, tzinfo=UTC),
        profile_date="2026-08-21",
        database=database,
        dry_run=False,
    )

    assert summary["observation_inserts"] == 6
    assert summary["profile_upserts"] == 1
    assert len(database["job_runs"].docs) == 1
    assert database["job_runs"].docs[0]["status"] == "succeeded"
    run_id = database["job_runs"].docs[0]["run_id"]
    assert {row["run_id"] for row in database["market_bias_observations"].docs} == {run_id}
    assert {row["run_id"] for row in database["market_bias_profiles"].docs} == {run_id}


def test_write_mode_marks_job_run_failed_when_interrupted(monkeypatch: pytest.MonkeyPatch) -> None:
    database = FakeDatabase()
    monkeypatch.setattr(
        "ullebets_v2.market_bias.service._run_refresh",
        lambda **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        run_market_bias_refresh(
            source_workflow="test.yml",
            source_kind="v2_forward",
            candidates=[MarketBiasCandidate(observation_docs=(_observation(),))],
            as_of=datetime(2026, 8, 21, 18, 0, tzinfo=UTC),
            profile_date="2026-08-21",
            database=database,
            dry_run=False,
        )

    assert database["job_runs"].docs[0]["status"] == "failed"
    assert database["job_runs"].docs[0]["error"]["type"] == "KeyboardInterrupt"
