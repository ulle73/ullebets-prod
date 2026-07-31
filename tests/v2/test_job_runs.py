from datetime import UTC, datetime

from ullebets_v2.jobs.job_runs import (
    build_job_run_finished_update,
    build_job_run_started_doc,
    inspect_job_run_health,
    reconcile_stale_job_runs,
)


def test_build_job_run_started_doc_sets_expected_fields() -> None:
    now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    doc = build_job_run_started_doc(
        job_name="sync_support_data",
        source_workflow="update-opta.yml",
        target_window={"date": "2026-06-21"},
        job_args={"mode": "full"},
        now=now,
    )

    assert doc["job_name"] == "sync_support_data"
    assert doc["source_workflow"] == "update-opta.yml"
    assert doc["target_window"] == {"date": "2026-06-21"}
    assert doc["job_args"] == {"mode": "full"}
    assert doc["status"] == "running"
    assert doc["started_at"] == now
    assert doc["finished_at"] is None
    assert "run_id" in doc


def test_build_job_run_finished_update_marks_success() -> None:
    now = datetime(2026, 6, 21, 12, 5, tzinfo=UTC)
    update = build_job_run_finished_update(
        status="succeeded",
        metrics={"upserts": 4},
        now=now,
    )

    assert update["$set"]["status"] == "succeeded"
    assert update["$set"]["finished_at"] == now
    assert update["$set"]["metrics"] == {"upserts": 4}
    assert update["$set"]["error"] is None


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = list(docs or [])

    def find(self, query: dict | None = None, projection: dict | None = None):  # noqa: ARG002
        query = query or {}
        rows: list[dict] = []
        for doc in self.docs:
            matched = True
            for key, value in query.items():
                if doc.get(key) != value:
                    matched = False
                    break
            if matched:
                rows.append(dict(doc))
        return rows

    def update_one(self, query: dict, update: dict) -> None:
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                for key, value in update.get("$set", {}).items():
                    doc[key] = value
                return
        raise AssertionError(f"document not found for query: {query}")


def test_inspect_job_run_health_flags_stale_running_rows() -> None:
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    summary = inspect_job_run_health(
        job_runs=[
            {
                "run_id": "stale-1",
                "job_name": "run_auto_analysis",
                "status": "running",
                "started_at": datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
                "finished_at": None,
            },
            {
                "run_id": "ok-1",
                "job_name": "capture_odds_checkpoints",
                "status": "succeeded",
                "started_at": datetime(2026, 7, 28, 2, 0, tzinfo=UTC),
                "finished_at": datetime(2026, 7, 28, 2, 10, tzinfo=UTC),
            },
        ],
        stale_hours=6,
        now=now,
    )

    assert summary["status"] == "warn"
    assert summary["findings"] == ["stale_running_job_runs"]
    assert summary["metrics"]["running_job_count"] == 1
    assert summary["metrics"]["stale_running_job_count"] == 1
    assert summary["metrics"]["stale_running_job_names"] == {"run_auto_analysis": 1}


def test_reconcile_stale_job_runs_marks_stale_rows_failed() -> None:
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    collection = FakeCollection(
        [
            {
                "run_id": "stale-1",
                "job_name": "run_auto_analysis",
                "status": "running",
                "started_at": datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
                "finished_at": None,
                "metrics": {"candidate_count": 3},
                "error": None,
            },
            {
                "run_id": "fresh-1",
                "job_name": "build_model_snapshots",
                "status": "running",
                "started_at": datetime(2026, 7, 28, 10, 30, tzinfo=UTC),
                "finished_at": None,
                "metrics": {},
                "error": None,
            },
        ]
    )

    summary = reconcile_stale_job_runs(
        collection,
        stale_hours=6,
        now=now,
    )

    assert summary["reconciled_count"] == 1
    assert summary["reconciled_run_ids"] == ["stale-1"]
    stale_doc = next(doc for doc in collection.docs if doc["run_id"] == "stale-1")
    fresh_doc = next(doc for doc in collection.docs if doc["run_id"] == "fresh-1")
    assert stale_doc["status"] == "failed"
    assert stale_doc["finished_at"] == now
    assert stale_doc["error"]["type"] == "InterruptedJobRun"
    assert stale_doc["metrics"]["candidate_count"] == 3
    assert fresh_doc["status"] == "running"
    assert fresh_doc["finished_at"] is None
