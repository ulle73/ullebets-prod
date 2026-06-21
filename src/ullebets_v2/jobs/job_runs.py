from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pymongo.collection import Collection


JobStatus = str


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


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
