from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from .workflow_matrix import WORKFLOW_PARITY_MATRIX


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def build_parity_report_row(
    *,
    workflow_entry: dict[str, Any],
    counts_old: dict[str, Any] | None = None,
    counts_v2: dict[str, Any] | None = None,
    parity_status: str = "planned",
    blocking_issues: list[str] | None = None,
    audit_risks: list[str] | None = None,
    report_date: date | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "old_workflow": workflow_entry["old_workflow"],
        "old_inputs": workflow_entry["old_inputs"],
        "old_outputs": workflow_entry["old_outputs"],
        "v2_job": workflow_entry["v2_job"],
        "v2_outputs": workflow_entry["v2_outputs"],
        "smoke_test": workflow_entry["smoke_test"],
        "parity_proof": workflow_entry["parity_proof"],
        "counts_old": counts_old or {},
        "counts_v2": counts_v2 or {},
        "parity_status": parity_status,
        "blocking_issues": blocking_issues or [],
        "audit_risks": audit_risks or [],
        "report_date": report_date or utc_now().date(),
        "generated_at": generated_at or utc_now(),
    }


def materialize_parity_rows(
    *,
    report_date: date | None = None,
    generated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    return [
        build_parity_report_row(
            workflow_entry=entry,
            report_date=report_date,
            generated_at=generated_at,
        )
        for entry in WORKFLOW_PARITY_MATRIX
    ]


def build_audit_report_row(
    *,
    audit_type: str,
    scope_key: str,
    status: str = "planned",
    metrics: dict[str, Any] | None = None,
    findings: list[str] | None = None,
    report_date: date | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "audit_type": audit_type,
        "scope_key": scope_key,
        "status": status,
        "metrics": metrics or {},
        "findings": findings or [],
        "report_date": report_date or utc_now().date(),
        "generated_at": generated_at or utc_now(),
    }


def build_health_report_row(
    *,
    job_name: str,
    status: str,
    summary: str,
    metrics: dict[str, Any] | None = None,
    report_date: date | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "job_name": job_name,
        "status": status,
        "summary": summary,
        "metrics": metrics or {},
        "report_date": report_date or utc_now().date(),
        "generated_at": generated_at or utc_now(),
    }
