from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def build_matchup_parity_rows(
    *,
    source_workflow: str,
    job_name: str,
    output_collection: str,
    target_matches: list[dict[str, Any]],
    entry_docs: list[dict[str, Any]],
    missing_matches: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not target_matches:
        return [
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": ["match-for-date", "teamprofiles"],
                    "old_outputs": [output_collection],
                    "v2_job": job_name,
                    "v2_outputs": [output_collection, "parity_reports"],
                    "smoke_test": "dry-run with empty fixture target window",
                    "parity_proof": "treat empty fixture targets as a clean no-op while preserving matchup output schemas",
                },
                counts_old={"target_match_count": 0, "entry_count": 0},
                counts_v2={"target_match_count": 0, "entry_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    parity_status = "matched" if not missing_matches else "mismatch"
    blocking_issues = ["missing_teamprofiles_for_fixture_targets"] if missing_matches else []
    return [
        build_parity_report_row(
            workflow_entry={
                "old_workflow": source_workflow,
                "old_inputs": ["match-for-date", "teamprofiles"],
                "old_outputs": [output_collection],
                "v2_job": job_name,
                "v2_outputs": [output_collection, "parity_reports"],
                "smoke_test": "dry-run matchup ranking build from canonical fixtures and V2 teamprofiles",
                "parity_proof": "V2 recreates matchup ranking rows from canonical fixture identity plus reproducible home/away teamprofiles instead of mutating legacy daily snapshot documents",
            },
            counts_old={"target_match_count": len(target_matches), "entry_count": len(entry_docs)},
            counts_v2={
                "target_match_count": len(target_matches),
                "entry_count": len(entry_docs),
                "top_50_count": sum(1 for row in entry_docs if row.get("is_top_50")),
                "scope_counts": _count_by(entry_docs, "scope"),
                "period_counts": _count_by(entry_docs, "period"),
                "stat_counts": _count_by(entry_docs, "stat_key"),
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=[],
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_matchup_audit_rows(
    *,
    audit_type: str,
    scope_key: str,
    target_matches: list[dict[str, Any]],
    entry_docs: list[dict[str, Any]],
    missing_matches: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not target_matches:
        return [
            build_audit_report_row(
                audit_type=audit_type,
                scope_key=scope_key,
                status="ok",
                metrics={"target_match_count": 0, "entry_count": 0},
                findings=["no_fixture_targets_available"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    findings: list[str] = []
    if missing_matches:
        findings.append("fixture_targets_missing_teamprofiles")
    status = "ok" if not findings else "warn"
    return [
        build_audit_report_row(
            audit_type=audit_type,
            scope_key=scope_key,
            status=status,
            metrics={
                "target_match_count": len(target_matches),
                "entry_count": len(entry_docs),
                "missing_profile_match_count": len(missing_matches),
                "scope_counts": _count_by(entry_docs, "scope"),
                "period_counts": _count_by(entry_docs, "period"),
                "stat_counts": _count_by(entry_docs, "stat_key"),
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_matchup_health_rows(
    *,
    job_name: str,
    target_matches: list[dict[str, Any]],
    entry_docs: list[dict[str, Any]],
    missing_matches: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not target_matches:
        return [
            build_health_report_row(
                job_name=job_name,
                status="ok",
                summary="No fixture targets were available for matchup ranking.",
                metrics={"target_match_count": 0, "entry_count": 0},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status = "ok" if not missing_matches else "warn"
    return [
        build_health_report_row(
            job_name=job_name,
            status=status,
            summary=(
                "Matchup ranking rows were generated."
                if status == "ok"
                else "Matchup ranking completed with missing teamprofiles for some fixture targets."
            ),
            metrics={
                "target_match_count": len(target_matches),
                "entry_count": len(entry_docs),
                "missing_profile_match_count": len(missing_matches),
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
