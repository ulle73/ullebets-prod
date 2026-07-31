from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row
from ullebets_v2.parity.workflow_matrix import WORKFLOW_PARITY_MATRIX


CLOSING_WORKFLOW = "run-unibet-closing.yml"


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _workflow_entry(old_workflow: str) -> dict[str, Any]:
    matching_entry = next(
        (
            entry
            for entry in WORKFLOW_PARITY_MATRIX
            if entry["old_workflow"] == old_workflow
        ),
        None,
    )
    if matching_entry is not None:
        return matching_entry
    return next(
        entry
        for entry in WORKFLOW_PARITY_MATRIX
        if entry["old_workflow"] == CLOSING_WORKFLOW
    )


def build_closing_parity_rows(
    *,
    source_workflow: str,
    target_matches: list[dict[str, Any]],
    due_targets: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    market_snapshot_docs: list[dict[str, Any]],
    closing_line_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    gap_rows = [row for row in match_rows if row.get("checkpoint_capture_gap")]
    source_error_count = sum(1 for row in match_rows if row.get("error"))
    if not target_matches:
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
    if not due_targets and not gap_rows:
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

    matched_event_count = sum(
        1 for row in match_rows if row.get("v2_event_id") and not row.get("checkpoint_capture_gap")
    )
    error_count = sum(1 for row in match_rows if row.get("error"))
    invalid_for_model_count = sum(1 for row in market_snapshot_docs if row.get("invalid_for_model"))
    offerless_match_count = sum(
        1
        for row in match_rows
        if row.get("v2_event_id") and int(row.get("v2_offer_count") or 0) == 0 and not row.get("checkpoint_capture_gap")
    )
    gap_count = len(gap_rows)
    parity_status = "matched" if error_count == 0 and invalid_for_model_count == 0 and source_error_count == 0 else "mismatch"
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
                "checkpoint_gap_count": gap_count,
                "source_error_count": source_error_count,
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=audit_risks
            + [
                f"historical_policy_gap:{row.get('match_key')}:{row.get('requested_checkpoint_key')}"
                for row in gap_rows
            ],
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_closing_audit_rows(
    *,
    source_workflow: str,
    target_matches: list[dict[str, Any]],
    due_targets: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    market_snapshot_docs: list[dict[str, Any]],
    closing_line_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    gap_rows = [row for row in match_rows if row.get("checkpoint_capture_gap")]
    source_errors = [row for row in match_rows if row.get("error")]
    if not target_matches:
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
    if not due_targets and not gap_rows:
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

    matched_event_count = sum(
        1 for row in match_rows if row.get("v2_event_id") and not row.get("checkpoint_capture_gap")
    )
    unmatched_match_count = max(0, len(due_targets) - matched_event_count)
    invalid_for_model_count = sum(1 for row in market_snapshot_docs if row.get("invalid_for_model"))
    offerless_match_count = sum(
        1
        for row in match_rows
        if row.get("v2_event_id") and int(row.get("v2_offer_count") or 0) == 0 and not row.get("checkpoint_capture_gap")
    )
    findings: list[str] = []
    if unmatched_match_count:
        findings.append("due_matches_without_event_mapping")
    if offerless_match_count:
        findings.append("matched_events_without_stat_offers")
    if invalid_for_model_count:
        findings.append("post_start_snapshots_excluded")
    if source_errors:
        findings.extend(f"source_error:{row['match_key']}" for row in source_errors)
    if gap_rows:
        findings.extend(
            f"historical_policy_gap:{row.get('match_key')}:{row.get('requested_checkpoint_key')}"
            for row in gap_rows
        )
    status = "ok" if unmatched_match_count == 0 and offerless_match_count == 0 and invalid_for_model_count == 0 and not source_errors else "warn"
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
                "checkpoint_gap_count": len(gap_rows),
                "source_error_count": len(source_errors),
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_closing_health_rows(
    *,
    target_matches: list[dict[str, Any]],
    due_targets: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    market_snapshot_docs: list[dict[str, Any]],
    closing_line_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    gap_count = sum(1 for row in match_rows if row.get("checkpoint_capture_gap"))
    if not target_matches:
        return [
            build_health_report_row(
                job_name="capture_closing_snapshots",
                status="ok",
                summary="No due closing targets inside the T_MINUS_10M window.",
                metrics={"due_match_count": 0, "closing_line_count": 0},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]
    if not due_targets and gap_count == 0:
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
    invalid_for_model_count = sum(1 for row in market_snapshot_docs if row.get("invalid_for_model"))
    status = "ok" if error_count == 0 and invalid_for_model_count == 0 else "warn"
    return [
        build_health_report_row(
            job_name="capture_closing_snapshots",
            status=status,
            summary=(
                "Closing capture completed with strict prematch filtering."
                if status == "ok"
                else "Closing capture completed with ingest errors or invalid post-start snapshots."
            ),
            metrics={
                "due_match_count": len(due_targets),
                "matched_event_count": sum(
                    1
                    for row in match_rows
                    if row.get("v2_event_id") and not row.get("checkpoint_capture_gap")
                ),
                "closing_line_count": len(closing_line_docs),
                "invalid_for_model_count": invalid_for_model_count,
                "historical_policy_gap_count": gap_count,
                "checkpoint_gap_count": gap_count,
                "error_count": error_count,
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
