from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def build_settlement_parity_rows(
    *,
    source_workflow: str,
    model_snapshot_docs: list[dict[str, Any]],
    settled_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not model_snapshot_docs:
        return [
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": ["unibet-backtest lines", "teamstats results"],
                    "old_outputs": ["corrected lines.actual / lines.win"],
                    "v2_job": "settle_model_snapshots.py",
                    "v2_outputs": ["settled_bets_v2", "audit_reports"],
                    "smoke_test": "dry-run with zero model snapshots",
                    "parity_proof": "verify empty settlement windows are handled as a clean no-op",
                },
                counts_old={"snapshot_count": 0, "settled_count": 0},
                counts_v2={"snapshot_count": 0, "settled_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(settled_docs, "settlement_status")
    parity_status = "matched"
    blocking_issues: list[str] = []
    if any(status_counts.get(key, 0) for key in ("missing_actual", "rule_error")):
        parity_status = "mismatch"
        if status_counts.get("missing_actual", 0):
            blocking_issues.append("missing_actual_values_present")
        if status_counts.get("rule_error", 0):
            blocking_issues.append("rule_errors_present")

    return [
        build_parity_report_row(
            workflow_entry={
                "old_workflow": source_workflow,
                "old_inputs": ["unibet-backtest lines", "teamstats results"],
                "old_outputs": ["corrected lines.actual / lines.win"],
                "v2_job": "settle_model_snapshots.py",
                "v2_outputs": ["settled_bets_v2", "audit_reports"],
                "smoke_test": "dry-run against synthetic and replay-derived settled rows",
                "parity_proof": "apply the same over/under/push settlement rules documented in the legacy correct-unibet-backtest and result-loop flows",
            },
            counts_old={
                "snapshot_count": len(model_snapshot_docs),
                "result_bucket_counts": _count_by(settled_docs, "settlement_result"),
            },
            counts_v2={
                "snapshot_count": len(model_snapshot_docs),
                "settled_count": len(settled_docs),
                "status_counts": status_counts,
                "result_bucket_counts": _count_by(settled_docs, "settlement_result"),
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=[] if parity_status == "matched" else ["settlement_coverage_risk"],
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_settlement_audit_rows(
    *,
    source_workflow: str,
    settled_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not settled_docs:
        return [
            build_audit_report_row(
                audit_type="model_snapshot_settlement",
                scope_key=source_workflow,
                status="ok",
                metrics={"snapshot_count": 0, "settled_count": 0},
                findings=["no_model_snapshots_to_settle"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(settled_docs, "settlement_status")
    result_counts = _count_by(settled_docs, "settlement_result")
    findings: list[str] = []
    if status_counts.get("pending_result", 0):
        findings.append("pending_match_results_present")
    if status_counts.get("missing_actual", 0):
        findings.append("missing_actual_values_present")
    if status_counts.get("rule_error", 0):
        findings.append("rule_errors_present")
    status = "ok" if not findings else "warn"
    return [
        build_audit_report_row(
            audit_type="model_snapshot_settlement",
            scope_key=source_workflow,
            status=status,
            metrics={
                "snapshot_count": len(settled_docs),
                "settled_count": status_counts.get("settled", 0),
                "pending_result_count": status_counts.get("pending_result", 0),
                "missing_actual_count": status_counts.get("missing_actual", 0),
                "rule_error_count": status_counts.get("rule_error", 0),
                "invalid_for_model_count": sum(1 for row in settled_docs if row.get("invalid_for_model")),
                "result_bucket_counts": result_counts,
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_settlement_health_rows(
    *,
    settled_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not settled_docs:
        return [
            build_health_report_row(
                job_name="settle_model_snapshots",
                status="ok",
                summary="No model snapshot rows required settlement.",
                metrics={"snapshot_count": 0, "settled_count": 0},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(settled_docs, "settlement_status")
    status = "ok" if status_counts.get("rule_error", 0) == 0 else "warn"
    return [
        build_health_report_row(
            job_name="settle_model_snapshots",
            status=status,
            summary=(
                "Model snapshot settlement ran with canonical over/under/push rules."
                if status == "ok"
                else "Model snapshot settlement encountered rule errors."
            ),
            metrics={
                "snapshot_count": len(settled_docs),
                "settled_count": status_counts.get("settled", 0),
                "pending_result_count": status_counts.get("pending_result", 0),
                "missing_actual_count": status_counts.get("missing_actual", 0),
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
