from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row
from ullebets_v2.storage.collections import CLV_TRACKING, FORWARD_BETS, FORWARD_RESULTS, SETTLED_BETS


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _workflow_entry() -> dict[str, Any]:
    return {
        "old_workflow": "result-loop-bets",
        "old_inputs": ["tracked forward bets", "closing-line-tracking", "canonical settlement rows"],
        "old_outputs": ["result-loop operational view"],
        "v2_job": "refresh_forward_results.py",
        "v2_outputs": [FORWARD_BETS, FORWARD_RESULTS, CLV_TRACKING, SETTLED_BETS, "audit_reports"],
        "smoke_test": "dry-run with synthetic forward bets, CLV rows, and settlement rows",
        "parity_proof": "verify one forward result row per saved forward selection, with saved odds, closing odds, CLV, settlement, ROI, and timing flags carried together without mutating source collections",
    }


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def _invalid_timing_count(timing_status_counts: dict[str, int]) -> int:
    return sum(
        count
        for status, count in timing_status_counts.items()
        if status != "prematch_valid"
    )


def build_forward_result_parity_rows(
    *,
    forward_bet_docs: list[dict[str, Any]],
    result_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not forward_bet_docs:
        return [
            build_parity_report_row(
                workflow_entry=_workflow_entry(),
                counts_old={"forward_bet_count": 0},
                counts_v2={"forward_bet_count": 0, "forward_result_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(result_docs, "result_loop_status")
    clv_status_counts = _count_by(result_docs, "clv_status")
    settlement_status_counts = _count_by(result_docs, "settlement_status")
    timing_status_counts = _count_by(result_docs, "timing_status")
    duplicate_count = len(result_docs) - len({str(row.get("result_loop_key") or "") for row in result_docs})
    source_count_mismatch = len(result_docs) != len(forward_bet_docs)
    invalid_timing_count = _invalid_timing_count(timing_status_counts)

    blocking_issues: list[str] = []
    if source_count_mismatch:
        blocking_issues.append("forward_result_count_mismatch")
    if duplicate_count:
        blocking_issues.append("duplicate_forward_result_keys")

    audit_risks: list[str] = []
    if invalid_timing_count:
        audit_risks.append("invalid_forward_timing_rows_excluded")
    if clv_status_counts.get("missing_clv_tracking_record", 0) or clv_status_counts.get("missing_closing_line", 0):
        audit_risks.append("clv_coverage_gap")
    if settlement_status_counts.get("missing_settlement_record", 0) or status_counts.get("pending", 0):
        audit_risks.append("settlement_coverage_gap")
    if status_counts.get("unresolved", 0):
        audit_risks.append("unresolved_forward_results_present")
    if timing_status_counts.get("missing_saved_at", 0) or timing_status_counts.get("missing_match_start", 0):
        audit_risks.append("timing_metadata_gap")

    return [
        build_parity_report_row(
            workflow_entry=_workflow_entry(),
            counts_old={"forward_bet_count": len(forward_bet_docs)},
            counts_v2={
                "forward_bet_count": len(forward_bet_docs),
                "forward_result_count": len(result_docs),
                "status_counts": status_counts,
                "clv_status_counts": clv_status_counts,
                "settlement_status_counts": settlement_status_counts,
                "timing_status_counts": timing_status_counts,
                "duplicate_result_loop_key_count": duplicate_count,
            },
            parity_status="matched" if not blocking_issues else "mismatch",
            blocking_issues=blocking_issues,
            audit_risks=audit_risks,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_forward_result_audit_rows(
    *,
    result_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not result_docs:
        return [
            build_audit_report_row(
                audit_type="forward_results",
                scope_key="result-loop-bets",
                status="ok",
                metrics={"forward_result_count": 0},
                findings=["no_forward_results_to_refresh"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(result_docs, "result_loop_status")
    clv_status_counts = _count_by(result_docs, "clv_status")
    settlement_status_counts = _count_by(result_docs, "settlement_status")
    timing_status_counts = _count_by(result_docs, "timing_status")
    findings: list[str] = []
    invalid_timing_count = _invalid_timing_count(timing_status_counts)
    if invalid_timing_count:
        findings.append("invalid_forward_timing_rows_excluded")
    if timing_status_counts.get("invalid_after_start", 0):
        findings.append("invalid_after_start_rows_present")
    if timing_status_counts.get("missing_saved_at", 0):
        findings.append("missing_saved_at_rows_present")
    if timing_status_counts.get("missing_match_start", 0):
        findings.append("missing_match_start_rows_present")
    if clv_status_counts.get("missing_clv_tracking_record", 0):
        findings.append("missing_clv_tracking_rows_present")
    if clv_status_counts.get("missing_closing_line", 0):
        findings.append("missing_closing_line_rows_present")
    if settlement_status_counts.get("missing_settlement_record", 0):
        findings.append("missing_settlement_rows_present")
    if status_counts.get("pending", 0):
        findings.append("pending_forward_results_present")
    if status_counts.get("unresolved", 0):
        findings.append("unresolved_forward_results_present")

    status = "warn" if findings else "ok"
    tracked_clv_rows = [row for row in result_docs if row.get("clv_status") == "tracked"]
    settled_rows = [row for row in result_docs if row.get("result_loop_status") == "settled"]
    return [
        build_audit_report_row(
            audit_type="forward_results",
            scope_key="result-loop-bets",
            status=status,
            metrics={
                "forward_result_count": len(result_docs),
                "settled_count": len(settled_rows),
                "tracked_clv_count": len(tracked_clv_rows),
                "beat_close_count": sum(1 for row in tracked_clv_rows if row.get("beat_closing_line") is True),
                "status_counts": status_counts,
                "clv_status_counts": clv_status_counts,
                "settlement_status_counts": settlement_status_counts,
                "timing_status_counts": timing_status_counts,
                "invalid_timing_count": invalid_timing_count,
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_forward_result_health_rows(
    *,
    result_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not result_docs:
        return [
            build_health_report_row(
                job_name="refresh_forward_results",
                status="ok",
                summary="No forward result rows required refresh.",
                metrics={"forward_result_count": 0},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    timing_status_counts = _count_by(result_docs, "timing_status")
    invalid_timing_count = _invalid_timing_count(timing_status_counts)
    status = "ok" if invalid_timing_count == 0 else "warn"
    return [
        build_health_report_row(
            job_name="refresh_forward_results",
            status=status,
            summary=(
                "Forward result-loop rows refreshed from forward bets, CLV, and settlement layers."
                if status == "ok"
                else "Forward result-loop refresh excluded invalid timing rows."
            ),
            metrics={
                "forward_result_count": len(result_docs),
                "settled_count": sum(1 for row in result_docs if row.get("result_loop_status") == "settled"),
                "invalid_after_start_count": timing_status_counts.get("invalid_after_start", 0),
                "invalid_timing_count": invalid_timing_count,
                "missing_saved_at_count": timing_status_counts.get("missing_saved_at", 0),
                "missing_match_start_count": timing_status_counts.get("missing_match_start", 0),
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
