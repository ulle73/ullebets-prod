from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from scripts.forward_v2.resume_checkpoint_processing import pending_scopes, process_scope
from tests.v2.test_odds_ingest import FakeCollection
from ullebets_v2.checkpoints.persistence import persist_checkpoint_records


class Collection(FakeCollection):
    def find(self, query, projection=None):
        if "match_start_time" in query:
            window = query["match_start_time"]
            return [row for row in self.docs if window["$gt"] < row["match_start_time"] <= window["$lte"] and not row.get("invalid_for_model")]
        return [row for row in self.docs if row["_id"] in query["_id"]["$in"] and row["status"] == "succeeded"]

    def update_one(self, query, update, upsert=False):
        return super().update_one(query, {"$set": update.get("$setOnInsert", {})}, upsert)


def test_interruption_recovers_without_new_capture_and_new_snapshot_reopens_scope():
    now = datetime.now(UTC)
    database = {"market_snapshots": Collection(), "job_runs": Collection()}
    database["market_snapshots"].docs = [
        {"match_key": "match-1", "snapshot_key": "s1", "snapshot_label": "T_MINUS_1D", "match_start_time": now + timedelta(days=1)},
        {"match_key": "past", "snapshot_key": "old", "match_start_time": now - timedelta(seconds=1)},
    ]
    scopes = pending_scopes(database, now=now, version="v1")
    assert len(scopes) == 1
    calls = []
    def interrupted(command, **kwargs):
        calls.append(command)
        if len(calls) == 2:
            raise subprocess.TimeoutExpired(command, 900)
        return SimpleNamespace(stdout="{}", stderr="")
    with pytest.raises(subprocess.TimeoutExpired):
        process_scope(database, scopes[0], repo_root=Path.cwd(), runner=interrupted)
    assert pending_scopes(database, now=now, version="v1") == scopes
    process_scope(database, scopes[0], repo_root=Path.cwd(), runner=lambda *a, **k: SimpleNamespace(stdout="{}", stderr=""))
    assert pending_scopes(database, now=now, version="v1") == []
    database["market_snapshots"].docs.append({**database["market_snapshots"].docs[0], "snapshot_key": "s2"})
    assert len(pending_scopes(database, now=now, version="v1")) == 1


def test_oracle_error_does_not_publish_completion():
    database = {"job_runs": Collection()}
    scope = {"_id": "work-1", "match_key": "match-1", "match_start_time": datetime.now(UTC) + timedelta(hours=2), "has_t1d": False}
    with pytest.raises(RuntimeError, match="Incomplete oracle"):
        process_scope(database, scope, repo_root=Path.cwd(), runner=lambda *a, **k: SimpleNamespace(stdout='{"oracle_error_count": 1}', stderr=""))
    assert database["job_runs"].docs == []


def test_snapshot_batches_use_existing_unique_index_and_replay_is_idempotent():
    class IndexedCollection(FakeCollection):
        def bulk_write(self, operations, **kwargs):
            assert len(operations) <= 50
            assert all(tuple(op._filter) == ("match_key", "offer_key", "snapshot_label") for op in operations)
            return super().bulk_write(operations, **kwargs)
    database = {"market_snapshots": IndexedCollection()}
    docs = [{"match_key": "match-1", "offer_key": str(n), "snapshot_label": "T_MINUS_1D", "snapshot_key": f"s{n}"} for n in range(121)]
    first = persist_checkpoint_records(database, market_snapshot_docs=docs, parity_rows=[], audit_rows=[], health_rows=[])
    second = persist_checkpoint_records(database, market_snapshot_docs=docs, parity_rows=[], audit_rows=[], health_rows=[])
    assert first["market_snapshot_upserts"] == 121
    assert second["market_snapshot_upserts"] == 0
    assert len(database["market_snapshots"].docs) == 121
