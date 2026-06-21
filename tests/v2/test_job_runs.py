from datetime import UTC, datetime

from ullebets_v2.jobs.job_runs import (
    build_job_run_finished_update,
    build_job_run_started_doc,
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
