from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row
from ullebets_v2.storage.collections import SETTLED_BETS


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def _historical_source_gap_missing_actual_count(settled_docs: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in settled_docs
        if row.get("settlement_status") == "missing_actual"
        and row.get("actual_source_status") == "stat_not_in_canonical_source"
        and (
            row.get("legacy_actual_value") is not None
            or row.get("legacy_settlement_result") is not None
            or row.get("legacy_win") is not None
        )
    )


def _legacy_settlement_mismatch_counts(settled_docs: list[dict[str, Any]]) -> dict[str, int]:
    actual_mismatch = 0
    result_mismatch = 0
    win_mismatch = 0
    comparable = 0
    for row in settled_docs:
        legacy_actual = row.get("legacy_actual_value")
        legacy_result = row.get("legacy_settlement_result")
        legacy_win = row.get("legacy_win")
        if legacy_actual is None and legacy_result is None and legacy_win is None:
            continue

        is_historical_gap = (
            row.get("settlement_status") == "missing_actual"
            and row.get("actual_source_status") == "stat_not_in_canonical_source"
        )
        if is_historical_gap:
            continue

        row_actual = row.get("actual_value")
        row_result = row.get("settlement_result")
        row_win = row.get("win")
        row_comparable = False

        if legacy_actual is not None and row_actual is not None:
            row_comparable = True
            if row_actual != legacy_actual:
                actual_mismatch += 1
        if legacy_result is not None and row_result is not None:
            row_comparable = True
            if row_result != legacy_result:
                result_mismatch += 1
        if legacy_win is not None and row_win is not None:
            row_comparable = True
            if row_win != legacy_win:
                win_mismatch += 1

        if row_comparable:
            comparable += 1
    return {
        "legacy_comparable_count": comparable,
        "legacy_actual_mismatch_count": actual_mismatch,
        "legacy_result_mismatch_count": result_mismatch,
        "legacy_win_mismatch_count": win_mismatch,
    }


def build_settlement_parity_rows(
    *,
    source_workflow: str,
    model_snapshot_docs: list[dict[str, Any]],
    settled_docs: list[dict[str, Any]],
    report_date: str | None = None,
    count_key: str = "snapshot_count",
    audit_type_label: str = "model snapshot",
    plural_label: str = "model snapshots",
    old_inputs: list[str] | None = None,
    old_outputs: list[str] | None = None,
    v2_job: str = "settle_model_snapshots.py",
    smoke_test: str = "dry-run against synthetic and replay-derived settled rows",
    no_target_smoke_test: str = "dry-run with zero model snapshots",
    parity_proof: str = "apply the same over/under/push settlement rules documented in the legacy correct-unibet-backtest and result-loop flows",
    no_target_parity_proof: str = "verify empty settlement windows are handled as a clean no-op",
) -> list[dict[str, Any]]:
    inputs = old_inputs or ["unibet-backtest lines", "teamstats results"]
    outputs = old_outputs or ["corrected lines.actual / lines.win"]
    if not model_snapshot_docs:
        return [
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": inputs,
                    "old_outputs": outputs,
                    "v2_job": v2_job,
                    "v2_outputs": [SETTLED_BETS, "audit_reports"],
                    "smoke_test": no_target_smoke_test,
                    "parity_proof": no_target_parity_proof,
                },
                counts_old={count_key: 0, "settled_count": 0},
                counts_v2={count_key: 0, "settled_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(settled_docs, "settlement_status")
    historical_gap_count = _historical_source_gap_missing_actual_count(settled_docs)
    legacy_mismatches = _legacy_settlement_mismatch_counts(settled_docs)
    blocking_missing_actual_count = max(0, status_counts.get("missing_actual", 0) - historical_gap_count)
    parity_status = "matched"
    blocking_issues: list[str] = []
    if (
        blocking_missing_actual_count
        or status_counts.get("rule_error", 0)
        or legacy_mismatches["legacy_actual_mismatch_count"]
        or legacy_mismatches["legacy_result_mismatch_count"]
        or legacy_mismatches["legacy_win_mismatch_count"]
    ):
        parity_status = "mismatch"
        if blocking_missing_actual_count:
            blocking_issues.append("missing_actual_values_present")
        if status_counts.get("rule_error", 0):
            blocking_issues.append("rule_errors_present")
        if legacy_mismatches["legacy_actual_mismatch_count"]:
            blocking_issues.append("legacy_actual_mismatches_present")
        if legacy_mismatches["legacy_result_mismatch_count"]:
            blocking_issues.append("legacy_result_mismatches_present")
        if legacy_mismatches["legacy_win_mismatch_count"]:
            blocking_issues.append("legacy_win_mismatches_present")

    audit_risks: list[str] = []
    if historical_gap_count:
        audit_risks.append("historical_source_gap_unverified_actuals")
    if status_counts.get("pending_result", 0):
        audit_risks.append("result_coverage_gap")
    if status_counts.get("invalid_timing", 0):
        audit_risks.append("invalid_forward_timing_excluded")
    if parity_status != "matched":
        audit_risks.append("settlement_coverage_risk")

    return [
        build_parity_report_row(
            workflow_entry={
                "old_workflow": source_workflow,
                "old_inputs": inputs,
                "old_outputs": outputs,
                "v2_job": v2_job,
                "v2_outputs": [SETTLED_BETS, "audit_reports"],
                "smoke_test": smoke_test,
                "parity_proof": parity_proof,
            },
            counts_old={
                count_key: len(model_snapshot_docs),
                "result_bucket_counts": _count_by(settled_docs, "settlement_result"),
            },
            counts_v2={
                count_key: len(model_snapshot_docs),
                "settled_count": len(settled_docs),
                "status_counts": status_counts,
                "historical_source_gap_missing_actual_count": historical_gap_count,
                "blocking_missing_actual_count": blocking_missing_actual_count,
                **legacy_mismatches,
                "result_bucket_counts": _count_by(settled_docs, "settlement_result"),
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=audit_risks,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_settlement_audit_rows(
    *,
    source_workflow: str,
    settled_docs: list[dict[str, Any]],
    report_date: str | None = None,
    count_key: str = "snapshot_count",
    audit_type: str = "model_snapshot_settlement",
    no_target_finding: str = "no_model_snapshots_to_settle",
) -> list[dict[str, Any]]:
    if not settled_docs:
        return [
            build_audit_report_row(
                audit_type=audit_type,
                scope_key=source_workflow,
                status="ok",
                metrics={count_key: 0, "settled_count": 0},
                findings=[no_target_finding],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(settled_docs, "settlement_status")
    result_counts = _count_by(settled_docs, "settlement_result")
    historical_gap_count = _historical_source_gap_missing_actual_count(settled_docs)
    legacy_mismatches = _legacy_settlement_mismatch_counts(settled_docs)
    blocking_missing_actual_count = max(0, status_counts.get("missing_actual", 0) - historical_gap_count)
    findings: list[str] = []
    if status_counts.get("pending_result", 0):
        findings.append("pending_match_results_present")
    if historical_gap_count:
        findings.append("historical_source_gap_missing_actual_values_present")
    if blocking_missing_actual_count:
        findings.append("missing_actual_values_present")
    if status_counts.get("rule_error", 0):
        findings.append("rule_errors_present")
    if status_counts.get("invalid_timing", 0):
        findings.append("invalid_forward_timing_excluded")
    if legacy_mismatches["legacy_actual_mismatch_count"]:
        findings.append("legacy_actual_mismatches_present")
    if legacy_mismatches["legacy_result_mismatch_count"]:
        findings.append("legacy_result_mismatches_present")
    if legacy_mismatches["legacy_win_mismatch_count"]:
        findings.append("legacy_win_mismatches_present")
    status = "ok" if not (
        blocking_missing_actual_count
        or status_counts.get("rule_error", 0)
        or status_counts.get("invalid_timing", 0)
        or legacy_mismatches["legacy_actual_mismatch_count"]
        or legacy_mismatches["legacy_result_mismatch_count"]
        or legacy_mismatches["legacy_win_mismatch_count"]
    ) else "warn"
    return [
        build_audit_report_row(
            audit_type=audit_type,
            scope_key=source_workflow,
            status=status,
            metrics={
                count_key: len(settled_docs),
                "settled_count": status_counts.get("settled", 0),
                "pending_result_count": status_counts.get("pending_result", 0),
                "missing_actual_count": status_counts.get("missing_actual", 0),
                "historical_source_gap_missing_actual_count": historical_gap_count,
                "blocking_missing_actual_count": blocking_missing_actual_count,
                "rule_error_count": status_counts.get("rule_error", 0),
                "invalid_timing_count": status_counts.get(
                    "invalid_timing", 0
                ),
                **legacy_mismatches,
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
    count_key: str = "snapshot_count",
    job_name: str = "settle_model_snapshots",
    no_target_summary: str = "No model snapshot rows required settlement.",
    ok_summary: str = "Model snapshot settlement ran with canonical over/under/push rules.",
    warn_summary: str = "Model snapshot settlement encountered rule errors.",
) -> list[dict[str, Any]]:
    if not settled_docs:
        return [
            build_health_report_row(
                job_name=job_name,
                status="ok",
                summary=no_target_summary,
                metrics={count_key: 0, "settled_count": 0},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(settled_docs, "settlement_status")
    status = (
        "ok"
        if status_counts.get("rule_error", 0) == 0
        and status_counts.get("invalid_timing", 0) == 0
        else "warn"
    )
    return [
        build_health_report_row(
            job_name=job_name,
            status=status,
            summary=ok_summary if status == "ok" else warn_summary,
            metrics={
                count_key: len(settled_docs),
                "settled_count": status_counts.get("settled", 0),
                "pending_result_count": status_counts.get("pending_result", 0),
                "missing_actual_count": status_counts.get("missing_actual", 0),
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
