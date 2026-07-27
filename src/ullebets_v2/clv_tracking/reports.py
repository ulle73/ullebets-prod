from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _workflow_entry() -> dict[str, Any]:
    return {
        "old_workflow": "closing-line-tracking",
        "old_inputs": ["result-loop tracked odds", "market observations"],
        "old_outputs": ["closing-line-tracking"],
        "v2_job": "refresh_clv_tracking.py",
        "v2_outputs": ["forward_bets_v2", "clv_tracking_v2", "audit_reports"],
        "smoke_test": "dry-run with synthetic tracked bets and canonical closing lines",
        "parity_proof": "compare saved odds, direction-specific opening/latest/closing odds, beat-close flags, and CLV percentages against the legacy closing-line-tracking semantics",
    }


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def build_clv_tracking_parity_rows(
    *,
    tracked_bet_docs: list[dict[str, Any]],
    clv_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not tracked_bet_docs:
        return [
            build_parity_report_row(
                workflow_entry=_workflow_entry(),
                counts_old={"tracked_bet_count": 0, "tracked_count": 0},
                counts_v2={"tracked_bet_count": 0, "tracked_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(clv_docs, "clv_status")
    invalid_timing_count = status_counts.get("invalid_snapshot_timing", 0)
    parity_status = "matched" if invalid_timing_count == 0 else "mismatch"
    blocking_issues = ["invalid_snapshot_timing_present"] if invalid_timing_count else []
    audit_risks: list[str] = []
    if status_counts.get("missing_closing_line", 0):
        audit_risks.append("closing_coverage_gap")
    if invalid_timing_count:
        audit_risks.append("timing_leakage_risk")
    return [
        build_parity_report_row(
            workflow_entry=_workflow_entry(),
            counts_old={"tracked_bet_count": len(tracked_bet_docs)},
            counts_v2={
                "tracked_bet_count": len(tracked_bet_docs),
                "tracked_count": len(clv_docs),
                "status_counts": status_counts,
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=audit_risks,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_clv_tracking_audit_rows(
    *,
    clv_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not clv_docs:
        return [
            build_audit_report_row(
                audit_type="clv_tracking",
                scope_key="closing-line-tracking",
                status="ok",
                metrics={"tracked_count": 0},
                findings=["no_tracked_bets_to_track"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(clv_docs, "clv_status")
    findings: list[str] = []
    if status_counts.get("missing_closing_line", 0):
        findings.append("missing_closing_lines_present")
    if status_counts.get("missing_selected_odds", 0):
        findings.append("missing_selected_or_closing_odds_present")
    if status_counts.get("invalid_snapshot_timing", 0):
        findings.append("invalid_snapshot_timing_present")
    status = "warn" if status_counts.get("invalid_snapshot_timing", 0) else "ok"
    tracked_rows = [row for row in clv_docs if row.get("clv_status") == "tracked"]
    return [
        build_audit_report_row(
            audit_type="clv_tracking",
            scope_key="closing-line-tracking",
            status=status,
            metrics={
                "tracked_count": len(clv_docs),
                "tracked_with_clv_count": len(tracked_rows),
                "beat_close_count": sum(1 for row in tracked_rows if row.get("beat_closing_line") is True),
                "status_counts": status_counts,
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_clv_tracking_health_rows(
    *,
    clv_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not clv_docs:
        return [
            build_health_report_row(
                job_name="refresh_clv_tracking",
                status="ok",
                summary="No tracked bet rows required CLV refresh.",
                metrics={"tracked_count": 0},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(clv_docs, "clv_status")
    status = "ok" if status_counts.get("invalid_snapshot_timing", 0) == 0 else "warn"
    return [
        build_health_report_row(
            job_name="refresh_clv_tracking",
            status=status,
            summary=(
                "CLV tracking refreshed from canonical closing lines."
                if status == "ok"
                else "CLV tracking found invalid snapshot timing rows."
            ),
            metrics={
                "tracked_count": len(clv_docs),
                "tracked_with_clv_count": status_counts.get("tracked", 0),
                "missing_closing_line_count": status_counts.get("missing_closing_line", 0),
                "invalid_snapshot_timing_count": status_counts.get("invalid_snapshot_timing", 0),
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
