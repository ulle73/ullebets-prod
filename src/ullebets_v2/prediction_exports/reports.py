from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def build_prediction_export_parity_rows(
    *,
    source_workflow: str,
    export_mode: str,
    source_candidates: list[dict[str, Any]],
    prediction_export_docs: list[dict[str, Any]],
    forward_bet_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not source_candidates:
        return [
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": ["analysis outputs", "odds", "EV"],
                    "old_outputs": ["ai-generated-bets"],
                    "v2_job": f"build_ai_bet_exports.py --mode {export_mode}",
                    "v2_outputs": ["prediction_exports_v2", "forward_bets_v2"],
                    "smoke_test": "dry-run with empty candidate set",
                    "parity_proof": "treat empty export windows as clean no-op while preserving immutable output schemas",
                },
                counts_old={"candidate_count": 0, "prediction_count": 0},
                counts_v2={"candidate_count": 0, "prediction_count": 0, "forward_bet_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    duplicate_selection_count = len(forward_bet_docs) - len({row.get("prediction_key") for row in forward_bet_docs})
    parity_status = "matched" if duplicate_selection_count == 0 else "mismatch"
    blocking_issues = ["duplicate_forward_bet_prediction_keys"] if duplicate_selection_count else []
    return [
        build_parity_report_row(
            workflow_entry={
                "old_workflow": source_workflow,
                "old_inputs": ["analysis outputs", "odds", "EV"],
                "old_outputs": ["ai-generated-bets"],
                "v2_job": f"build_ai_bet_exports.py --mode {export_mode}",
                "v2_outputs": ["prediction_exports_v2", "forward_bets_v2"],
                "smoke_test": "dry-run export build from canonical analysis outputs",
                "parity_proof": "V2 exports immutable prediction docs and separate forward bet exposures from canonical analysis rows, preserving mode-specific output counts without reusing legacy mutable documents",
            },
            counts_old={
                "candidate_count": len(source_candidates),
            },
            counts_v2={
                "candidate_count": len(source_candidates),
                "prediction_count": len(prediction_export_docs),
                "forward_bet_count": len(forward_bet_docs),
                "export_type_counts": _count_by(prediction_export_docs, "prediction_type"),
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=[],
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_prediction_export_audit_rows(
    *,
    source_workflow: str,
    export_mode: str,
    source_candidates: list[dict[str, Any]],
    prediction_export_docs: list[dict[str, Any]],
    forward_bet_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not source_candidates:
        return [
            build_audit_report_row(
                audit_type="prediction_exports",
                scope_key=f"{source_workflow}:{export_mode}",
                status="ok",
                metrics={"candidate_count": 0, "prediction_count": 0, "forward_bet_count": 0},
                findings=["no_candidates_available_for_export"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    invalid_for_model_count = sum(1 for row in forward_bet_docs if row.get("invalid_for_model"))
    findings: list[str] = []
    if invalid_for_model_count:
        findings.append("invalid_forward_bets_present")
    status = "ok" if not findings else "warn"
    return [
        build_audit_report_row(
            audit_type="prediction_exports",
            scope_key=f"{source_workflow}:{export_mode}",
            status=status,
            metrics={
                "candidate_count": len(source_candidates),
                "prediction_count": len(prediction_export_docs),
                "forward_bet_count": len(forward_bet_docs),
                "invalid_forward_bet_count": invalid_for_model_count,
                "best_bet_count": sum(1 for row in source_candidates if row.get("is_best_bet_for_match")),
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_prediction_export_health_rows(
    *,
    export_mode: str,
    prediction_export_docs: list[dict[str, Any]],
    forward_bet_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not prediction_export_docs and not forward_bet_docs:
        return [
            build_health_report_row(
                job_name="build_ai_bet_exports",
                status="ok",
                summary=f"No prediction exports were generated for mode {export_mode}.",
                metrics={"prediction_count": 0, "forward_bet_count": 0},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    return [
        build_health_report_row(
            job_name="build_ai_bet_exports",
            status="ok",
            summary=f"Prediction exports were generated for mode {export_mode}.",
            metrics={
                "prediction_count": len(prediction_export_docs),
                "forward_bet_count": len(forward_bet_docs),
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
