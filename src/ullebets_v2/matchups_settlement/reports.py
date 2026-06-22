from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def build_matchup_settlement_parity_rows(
    *,
    source_workflow: str,
    score_docs: list[dict[str, Any]],
    league_avg_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    total_docs = len(score_docs) + len(league_avg_docs)
    if total_docs == 0:
        return [
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": ["matchup collections", "teamstats", "RapidAPI fallback"],
                    "old_outputs": ["enriched matchup outcomes"],
                    "v2_job": "settle_matchups_outputs.py",
                    "v2_outputs": ["matchups_score_v2", "matchups_league_avg_v2", "audit_reports"],
                    "smoke_test": "dry-run on an empty snapshot date window",
                    "parity_proof": "treat empty matchup windows as a clean no-op while preserving settled output schemas",
                },
                counts_old={"entry_count": 0, "resolved_count": 0},
                counts_v2={"entry_count": 0, "resolved_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    all_docs = [*score_docs, *league_avg_docs]
    resolved_count = sum(1 for row in all_docs if row.get("outcome_status") == "resolved")
    unresolved_count = sum(1 for row in all_docs if row.get("outcome_status") != "resolved")
    parity_status = "matched" if resolved_count > 0 else "mismatch"
    blocking_issues = ["no_matchup_rows_resolved"] if resolved_count == 0 else []
    audit_risks = ["unresolved_matchup_outcomes_present"] if unresolved_count else []
    return [
        build_parity_report_row(
            workflow_entry={
                "old_workflow": source_workflow,
                "old_inputs": ["matchup collections", "teamstats", "RapidAPI fallback"],
                "old_outputs": ["enriched matchup outcomes"],
                "v2_job": "settle_matchups_outputs.py",
                "v2_outputs": ["matchups_score_v2", "matchups_league_avg_v2", "audit_reports"],
                "smoke_test": "dry-run against canonical matchup rows and canonical actuals",
                "parity_proof": "V2 enriches matchup rows from canonical match stats instead of fallback-first settlement, and marks unresolved rows explicitly instead of silently leaving them ambiguous",
            },
            counts_old={
                "entry_count": total_docs,
                "resolved_count": resolved_count,
            },
            counts_v2={
                "entry_count": total_docs,
                "resolved_count": resolved_count,
                "outcome_status_counts": _count_by(all_docs, "outcome_status"),
                "score_collection_count": len(score_docs),
                "league_avg_collection_count": len(league_avg_docs),
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=audit_risks,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_matchup_settlement_audit_rows(
    *,
    source_workflow: str,
    score_docs: list[dict[str, Any]],
    league_avg_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    all_docs = [*score_docs, *league_avg_docs]
    if not all_docs:
        return [
            build_audit_report_row(
                audit_type="matchup_settlement",
                scope_key=source_workflow,
                status="ok",
                metrics={"entry_count": 0, "resolved_count": 0},
                findings=["no_matchup_rows_available_for_settlement"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    findings: list[str] = []
    if any(row.get("outcome_status") == "pending_result" for row in all_docs):
        findings.append("pending_results_present")
    if any(row.get("outcome_status") == "missing_actual" for row in all_docs):
        findings.append("missing_actuals_present")
    status = "ok" if not findings else "warn"
    return [
        build_audit_report_row(
            audit_type="matchup_settlement",
            scope_key=source_workflow,
            status=status,
            metrics={
                "entry_count": len(all_docs),
                "resolved_count": sum(1 for row in all_docs if row.get("outcome_status") == "resolved"),
                "top_50_resolved_count": sum(1 for row in all_docs if row.get("is_top_50") and row.get("outcome_status") == "resolved"),
                "score_collection_count": len(score_docs),
                "league_avg_collection_count": len(league_avg_docs),
                "outcome_status_counts": _count_by(all_docs, "outcome_status"),
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_matchup_settlement_health_rows(
    *,
    score_docs: list[dict[str, Any]],
    league_avg_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    all_docs = [*score_docs, *league_avg_docs]
    if not all_docs:
        return [
            build_health_report_row(
                job_name="settle_matchups_outputs",
                status="ok",
                summary="No matchup rows were available for settlement.",
                metrics={"entry_count": 0, "resolved_count": 0},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    unresolved_count = sum(1 for row in all_docs if row.get("outcome_status") != "resolved")
    status = "ok" if unresolved_count == 0 else "warn"
    return [
        build_health_report_row(
            job_name="settle_matchups_outputs",
            status=status,
            summary=(
                "Matchup rows were enriched with authoritative actual values."
                if status == "ok"
                else "Matchup enrichment completed with unresolved rows."
            ),
            metrics={
                "entry_count": len(all_docs),
                "resolved_count": sum(1 for row in all_docs if row.get("outcome_status") == "resolved"),
                "unresolved_count": unresolved_count,
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
