from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row
from ullebets_v2.parity.workflow_matrix import WORKFLOW_PARITY_MATRIX


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _workflow_entry(old_workflow: str) -> dict[str, Any]:
    return next(
        entry
        for entry in WORKFLOW_PARITY_MATRIX
        if entry["old_workflow"] == old_workflow
    )


def build_closing_parity_rows(
    *,
    source_workflow: str,
    due_targets: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    market_snapshot_docs: list[dict[str, Any]],
    closing_line_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not due_targets:
        return [
            build_parity_report_row(
                workflow_entry=_workflow_entry(source_workflow),
                counts_old={"due_match_count": 0, "closing_line_count": 0},
                counts_v2={"due_match_count": 0, "market_snapshot_count": 0, "closing_line_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    matched_event_count = sum(1 for row in match_rows if row.get("v2_event_id"))
    error_count = sum(1 for row in match_rows if row.get("error"))
    invalid_for_model_count = sum(1 for row in market_snapshot_docs if row.get("invalid_for_model"))
    offerless_match_count = sum(
        1 for row in match_rows if row.get("v2_event_id") and int(row.get("v2_offer_count") or 0) == 0
    )
    parity_status = "matched" if error_count == 0 and invalid_for_model_count == 0 else "mismatch"
    blocking_issues: list[str] = []
    audit_risks: list[str] = []
    if error_count:
        blocking_issues.append("closing_ingest_errors_present")
    if invalid_for_model_count:
        blocking_issues.append("post_start_snapshot_rows_present")
        audit_risks.append("timing_leakage_risk")
    if offerless_match_count:
        audit_risks.append("matched_events_without_offers")

    return [
        build_parity_report_row(
            workflow_entry=_workflow_entry(source_workflow),
            counts_old={
                "due_match_count": len(due_targets),
            },
            counts_v2={
                "due_match_count": len(due_targets),
                "matched_event_count": matched_event_count,
                "market_snapshot_count": len(market_snapshot_docs),
                "closing_line_count": len(closing_line_docs),
                "offerless_match_count": offerless_match_count,
                "invalid_for_model_count": invalid_for_model_count,
                "error_count": error_count,
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=audit_risks,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_closing_audit_rows(
    *,
    source_workflow: str,
    due_targets: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    market_snapshot_docs: list[dict[str, Any]],
    closing_line_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not due_targets:
        return [
            build_audit_report_row(
                audit_type="closing_capture",
                scope_key=source_workflow,
                status="ok",
                metrics={"due_match_count": 0, "market_snapshot_count": 0, "closing_line_count": 0},
                findings=["no_due_closing_targets"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    matched_event_count = sum(1 for row in match_rows if row.get("v2_event_id"))
    unmatched_match_count = len(due_targets) - matched_event_count
    invalid_for_model_count = sum(1 for row in market_snapshot_docs if row.get("invalid_for_model"))
    offerless_match_count = sum(
        1 for row in match_rows if row.get("v2_event_id") and int(row.get("v2_offer_count") or 0) == 0
    )
    findings: list[str] = []
    if unmatched_match_count:
        findings.append("due_matches_without_event_mapping")
    if offerless_match_count:
        findings.append("matched_events_without_stat_offers")
    if invalid_for_model_count:
        findings.append("post_start_snapshots_excluded")
    status = "ok" if not findings else "warn"
    valid_snapshots = sum(1 for row in market_snapshot_docs if not row.get("invalid_for_model"))
    return [
        build_audit_report_row(
            audit_type="closing_capture",
            scope_key=source_workflow,
            status=status,
            metrics={
                "due_match_count": len(due_targets),
                "matched_event_count": matched_event_count,
                "unmatched_match_count": unmatched_match_count,
                "market_snapshot_count": len(market_snapshot_docs),
                "valid_market_snapshot_count": valid_snapshots,
                "closing_line_count": len(closing_line_docs),
                "offerless_match_count": offerless_match_count,
                "invalid_for_model_count": invalid_for_model_count,
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_closing_health_rows(
    *,
    due_targets: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    closing_line_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not due_targets:
        return [
            build_health_report_row(
                job_name="capture_closing_snapshots",
                status="ok",
                summary="No due closing targets inside the T_MINUS_10M window.",
                metrics={"due_match_count": 0, "closing_line_count": 0},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    error_count = sum(1 for row in match_rows if row.get("error"))
    status = "ok" if error_count == 0 else "warn"
    return [
        build_health_report_row(
            job_name="capture_closing_snapshots",
            status=status,
            summary=(
                "Closing capture completed with strict prematch filtering."
                if status == "ok"
                else "Closing capture completed with ingest errors."
            ),
            metrics={
                "due_match_count": len(due_targets),
                "matched_event_count": sum(1 for row in match_rows if row.get("v2_event_id")),
                "closing_line_count": len(closing_line_docs),
                "error_count": error_count,
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
