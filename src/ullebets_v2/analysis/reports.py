from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def build_analysis_parity_rows(
    *,
    source_workflow: str,
    target_matches: list[dict[str, Any]],
    model_snapshot_docs: list[dict[str, Any]],
    analysis_candidate_docs: list[dict[str, Any]],
    shortlist_docs: list[dict[str, Any]],
    oracle_error_count: int,
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not target_matches:
        return [
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": ["fixtures", "odds", "EV", "ranking feedback"],
                    "old_outputs": ["auto-analysis-runs", "auto-analysis-bets", "analysis-snapshots"],
                    "v2_job": "run_auto_analysis.py",
                    "v2_outputs": ["analysis_runs_v2", "analysis_candidates_v2", "analysis_snapshots_v2"],
                    "smoke_test": "dry-run on an empty target window",
                    "parity_proof": "treat no eligible auto-analysis targets as a clean no-op while keeping downstream schemas stable",
                },
                counts_old={"target_match_count": 0, "candidate_count": 0, "shortlist_count": 0},
                counts_v2={"target_match_count": 0, "candidate_count": 0, "shortlist_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    invalid_count = sum(1 for row in model_snapshot_docs if row.get("invalid_for_model"))
    parity_status = "matched" if oracle_error_count == 0 and invalid_count == 0 else "mismatch"
    blocking_issues: list[str] = []
    audit_risks: list[str] = []
    if oracle_error_count:
        blocking_issues.append("analysis_oracle_errors_present")
    if invalid_count:
        blocking_issues.append("post_start_model_rows_present")
        audit_risks.append("timing_leakage_risk")

    return [
        build_parity_report_row(
            workflow_entry={
                "old_workflow": source_workflow,
                "old_inputs": ["fixtures", "odds", "EV", "ranking feedback"],
                "old_outputs": ["auto-analysis-runs", "auto-analysis-bets", "analysis-snapshots"],
                "v2_job": "run_auto_analysis.py",
                "v2_outputs": ["analysis_runs_v2", "analysis_candidates_v2", "analysis_snapshots_v2"],
                "smoke_test": "dry-run replay or live window through unchanged JS ranking policy",
                "parity_proof": "V2 reuses the original JS ranking/filter rules on top of canonical model snapshot rows, then persists the same run/candidate/snapshot output families separately from legacy collections",
            },
            counts_old={
                "target_match_count": len(target_matches),
                "candidate_count": len(analysis_candidate_docs),
                "shortlist_count": len(shortlist_docs),
            },
            counts_v2={
                "target_match_count": len(target_matches),
                "model_snapshot_count": len(model_snapshot_docs),
                "candidate_count": len(analysis_candidate_docs),
                "qualifying_candidate_count": sum(1 for row in analysis_candidate_docs if row.get("passes_strategy_filters")),
                "shortlist_count": len(shortlist_docs),
                "strategy_counts": _count_by(analysis_candidate_docs, "strategy_id"),
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=audit_risks,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_analysis_audit_rows(
    *,
    source_workflow: str,
    target_matches: list[dict[str, Any]],
    model_snapshot_docs: list[dict[str, Any]],
    analysis_candidate_docs: list[dict[str, Any]],
    shortlist_docs: list[dict[str, Any]],
    learning_profile_applied: bool,
    oracle_error_count: int,
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not target_matches:
        return [
            build_audit_report_row(
                audit_type="auto_analysis",
                scope_key=source_workflow,
                status="ok",
                metrics={
                    "target_match_count": 0,
                    "model_snapshot_count": 0,
                    "candidate_count": 0,
                    "shortlist_count": 0,
                    "learning_profile_applied": False,
                },
                findings=["no_due_targets_in_requested_window"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    invalid_count = sum(1 for row in model_snapshot_docs if row.get("invalid_for_model"))
    findings: list[str] = []
    if invalid_count:
        findings.append("post_start_model_rows_excluded")
    if oracle_error_count:
        findings.append("analysis_oracle_errors_present")
    status = "ok" if not findings else "warn"
    return [
        build_audit_report_row(
            audit_type="auto_analysis",
            scope_key=source_workflow,
            status=status,
            metrics={
                "target_match_count": len(target_matches),
                "model_snapshot_count": len(model_snapshot_docs),
                "valid_model_snapshot_count": sum(1 for row in model_snapshot_docs if not row.get("invalid_for_model")),
                "invalid_model_snapshot_count": invalid_count,
                "candidate_count": len(analysis_candidate_docs),
                "qualifying_candidate_count": sum(1 for row in analysis_candidate_docs if row.get("passes_strategy_filters")),
                "shortlist_count": len(shortlist_docs),
                "learning_profile_applied": learning_profile_applied,
                "strategy_counts": _count_by(analysis_candidate_docs, "strategy_id"),
                "proof_ready_count": sum(1 for row in shortlist_docs if row.get("proof", {}).get("historicalReady")),
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_analysis_health_rows(
    *,
    target_matches: list[dict[str, Any]],
    analysis_candidate_docs: list[dict[str, Any]],
    shortlist_docs: list[dict[str, Any]],
    oracle_error_count: int,
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not target_matches:
        return [
            build_health_report_row(
                job_name="run_auto_analysis",
                status="ok",
                summary="No eligible auto-analysis targets were present in the requested window.",
                metrics={"target_match_count": 0, "candidate_count": 0, "shortlist_count": 0},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status = "ok" if oracle_error_count == 0 else "warn"
    return [
        build_health_report_row(
            job_name="run_auto_analysis",
            status=status,
            summary=(
                "Auto-analysis produced persisted candidate and shortlist outputs."
                if status == "ok"
                else "Auto-analysis completed with oracle errors."
            ),
            metrics={
                "target_match_count": len(target_matches),
                "candidate_count": len(analysis_candidate_docs),
                "shortlist_count": len(shortlist_docs),
                "oracle_error_count": oracle_error_count,
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
