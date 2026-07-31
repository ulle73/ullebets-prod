from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pymongo.collection import Collection


JobStatus = str


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def build_job_run_started_doc(
    *,
    job_name: str,
    source_workflow: str,
    target_window: dict[str, Any],
    job_args: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    return {
        "run_id": uuid4().hex,
        "job_name": job_name,
        "source_workflow": source_workflow,
        "target_window": target_window,
        "job_args": job_args or {},
        "status": "running",
        "started_at": now or utc_now(),
        "finished_at": None,
        "metrics": {},
        "error": None,
    }


def build_job_run_finished_update(
    *,
    status: JobStatus,
    metrics: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    return {
        "$set": {
            "status": status,
            "finished_at": now or utc_now(),
            "metrics": metrics or {},
            "error": error,
        }
    }


def inspect_job_run_health(
    *,
    job_runs: list[dict[str, Any]],
    stale_hours: int = 6,
    now: datetime | None = None,
) -> dict[str, Any]:
    effective_now = now or utc_now()
    stale_cutoff = effective_now - timedelta(hours=stale_hours)
    running_rows = [
        row
        for row in job_runs
        if row.get("status") == "running"
        and row.get("finished_at") in {None, ""}
    ]
    stale_rows = [
        row
        for row in running_rows
        if (_coerce_datetime(row.get("started_at")) or datetime.min.replace(tzinfo=UTC)) <= stale_cutoff
    ]
    stale_names: dict[str, int] = {}
    for row in stale_rows:
        job_name = str(row.get("job_name") or "unknown")
        stale_names[job_name] = stale_names.get(job_name, 0) + 1
    return {
        "status": "ok" if not stale_rows else "warn",
        "findings": [] if not stale_rows else ["stale_running_job_runs"],
        "metrics": {
            "running_job_count": len(running_rows),
            "stale_running_job_count": len(stale_rows),
            "stale_running_job_names": stale_names,
            "stale_hours_threshold": stale_hours,
            "checked_at": effective_now,
        },
        "running_rows": running_rows,
        "stale_rows": stale_rows,
    }


def reconcile_stale_job_runs(
    collection: Collection | Any,
    *,
    stale_hours: int = 6,
    now: datetime | None = None,
) -> dict[str, Any]:
    effective_now = now or utc_now()
    running_rows = list(collection.find({"status": "running"}, projection={"_id": 0}))
    health = inspect_job_run_health(
        job_runs=running_rows,
        stale_hours=stale_hours,
        now=effective_now,
    )
    reconciled_run_ids: list[str] = []
    for row in health["stale_rows"]:
        run_id = str(row.get("run_id") or "")
        if not run_id:
            continue
        metrics = dict(row.get("metrics") or {})
        metrics["reconciled_from_status"] = "running"
        metrics["reconciled_reason"] = "stale_running_job_run"
        collection.update_one(
            {"run_id": run_id},
            build_job_run_finished_update(
                status="failed",
                metrics=metrics,
                error={
                    "type": "InterruptedJobRun",
                    "message": f"Marked failed after exceeding {stale_hours} stale hours without completion.",
                },
                now=effective_now,
            ),
        )
        reconciled_run_ids.append(run_id)
    return {
        "checked_at": effective_now,
        "stale_hours_threshold": stale_hours,
        "running_job_count": len(running_rows),
        "stale_running_job_count": len(health["stale_rows"]),
        "reconciled_count": len(reconciled_run_ids),
        "reconciled_run_ids": reconciled_run_ids,
    }


def start_job_run(
    collection: Collection,
    *,
    job_name: str,
    source_workflow: str,
    target_window: dict[str, Any],
    job_args: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    doc = build_job_run_started_doc(
        job_name=job_name,
        source_workflow=source_workflow,
        target_window=target_window,
        job_args=job_args,
        now=now,
    )
    collection.insert_one(doc)
    return doc


def finish_job_run(
    collection: Collection,
    *,
    run_id: str,
    status: JobStatus,
    metrics: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> None:
    collection.update_one(
        {"run_id": run_id},
        build_job_run_finished_update(
            status=status,
            metrics=metrics,
            error=error,
            now=now,
        ),
    )


@dataclass
class JobRunContext(AbstractContextManager["JobRunContext"]):
    collection: Collection
    job_name: str
    source_workflow: str
    target_window: dict[str, Any]
    job_args: dict[str, Any]
    run_doc: dict[str, Any] | None = None

    def __enter__(self) -> "JobRunContext":
        self.run_doc = start_job_run(
            self.collection,
            job_name=self.job_name,
            source_workflow=self.source_workflow,
            target_window=self.target_window,
            job_args=self.job_args,
        )
        return self

    @property
    def run_id(self) -> str:
        if self.run_doc is None:
            raise RuntimeError("Job run has not started.")
        return str(self.run_doc["run_id"])

    def success(self, metrics: dict[str, Any] | None = None) -> None:
        finish_job_run(
            self.collection,
            run_id=self.run_id,
            status="succeeded",
            metrics=metrics,
        )

    def failure(self, error: Exception, metrics: dict[str, Any] | None = None) -> None:
        finish_job_run(
            self.collection,
            run_id=self.run_id,
            status="failed",
            metrics=metrics,
            error={
                "type": type(error).__name__,
                "message": str(error),
            },
        )

    def __exit__(self, exc_type, exc, exc_tb) -> bool:
        if exc is None:
            self.success()
            return False

        self.failure(exc)
        return False
