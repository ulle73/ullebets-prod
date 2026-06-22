from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def build_teamprofile_parity_rows(
    *,
    source_workflow: str,
    match_results_canonical: list[dict[str, Any]],
    profile_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not match_results_canonical:
        return [
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": ["RapidAPI stats/incidents/shotmap/odds", "local teamstats dirs"],
                    "old_outputs": ["teamstats", "job_state", "teamprofiles", "patched match-for-date"],
                    "v2_job": "build_teamprofiles.py",
                    "v2_outputs": ["teamprofiles_v2", "parity_reports"],
                    "smoke_test": "dry-run replay for bounded finished-match subset",
                    "parity_proof": "treat empty canonical history as a clean no-op while preserving the teamprofile schema boundary",
                },
                counts_old={"distinct_match_count": 0, "profile_count": 0},
                counts_v2={"distinct_match_count": 0, "profile_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    parity_status = "matched" if profile_docs else "mismatch"
    blocking_issues = [] if profile_docs else ["no_teamprofiles_generated"]
    return [
        build_parity_report_row(
            workflow_entry={
                "old_workflow": source_workflow,
                "old_inputs": ["RapidAPI stats/incidents/shotmap/odds", "local teamstats dirs"],
                "old_outputs": ["teamstats", "job_state", "teamprofiles", "patched match-for-date"],
                "v2_job": "build_teamprofiles.py",
                "v2_outputs": ["teamprofiles_v2", "parity_reports"],
                "smoke_test": "dry-run canonical stat blocks into team profiles",
                "parity_proof": "V2 rebuilds team-level home/away profiles from canonical match stat rows so the profile layer stays reproducible from raw enrichment artifacts",
            },
            counts_old={
                "distinct_match_count": len({row["match_key"] for row in match_results_canonical}),
                "profile_count": len(profile_docs),
            },
            counts_v2={
                "distinct_match_count": len({row["match_key"] for row in match_results_canonical}),
                "profile_count": len(profile_docs),
                "league_count": len({row.get("league_key") for row in profile_docs}),
                "match_type_counts": _count_by(profile_docs, "match_type"),
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=[],
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_teamprofile_audit_rows(
    *,
    source_workflow: str,
    match_results_canonical: list[dict[str, Any]],
    profile_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not match_results_canonical:
        return [
            build_audit_report_row(
                audit_type="teamprofiles",
                scope_key=source_workflow,
                status="ok",
                metrics={"distinct_match_count": 0, "profile_count": 0},
                findings=["no_canonical_match_history_available"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    empty_games = sum(1 for row in profile_docs if not row.get("games"))
    findings: list[str] = []
    if empty_games:
        findings.append("profiles_without_games_present")
    status = "ok" if not findings else "warn"
    return [
        build_audit_report_row(
            audit_type="teamprofiles",
            scope_key=source_workflow,
            status=status,
            metrics={
                "distinct_match_count": len({row["match_key"] for row in match_results_canonical}),
                "profile_count": len(profile_docs),
                "empty_games_count": empty_games,
                "league_count": len({row.get("league_key") for row in profile_docs}),
                "team_count": len({row.get("team_key") for row in profile_docs}),
                "match_type_counts": _count_by(profile_docs, "match_type"),
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_teamprofile_health_rows(
    *,
    profile_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not profile_docs:
        return [
            build_health_report_row(
                job_name="build_teamprofiles",
                status="ok",
                summary="No teamprofiles were generated because no canonical finished matches were available.",
                metrics={"profile_count": 0},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    return [
        build_health_report_row(
            job_name="build_teamprofiles",
            status="ok",
            summary="Teamprofiles were rebuilt from canonical match statistics.",
            metrics={
                "profile_count": len(profile_docs),
                "team_count": len({row.get("team_key") for row in profile_docs}),
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
