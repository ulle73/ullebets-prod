from __future__ import annotations

from typing import Any

from ullebets_v2.parity.reports import (
    build_audit_report_row,
    build_health_report_row,
    build_parity_report_row,
)
from ullebets_v2.support.schemas import stable_json_hash


def _league_identity_rows(league_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "league_key": row["league_key"],
                "league_name": row["league_name"],
                "league_id": row.get("league_id"),
                "season_id": row.get("season_id"),
                "category_id": row.get("category_id"),
                "country": row.get("country"),
                "unibet_base_url": row.get("unibet_base_url"),
                "unibet_country_slug": row.get("unibet_country_slug"),
                "unibet_league_slug": row.get("unibet_league_slug"),
                "unibet_lookup_slugs": row.get("unibet_lookup_slugs", []),
            }
            for row in league_docs
        ],
        key=lambda row: row["league_key"],
    )


def _team_identity_rows(team_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "team_key": row["team_key"],
                "league_key": row["league_key"],
                "team_id": row.get("team_id"),
                "team_name": row.get("team_name"),
                "team_slug": row.get("team_slug"),
            }
            for row in team_docs
        ],
        key=lambda row: row["team_key"],
    )


def build_support_parity_rows(
    *,
    source_workflow: str,
    old_support_docs: dict[str, Any],
    v2_support_docs: dict[str, Any],
) -> list[dict[str, Any]]:
    old_leagues = old_support_docs["leagues"]
    old_teams = old_support_docs["teams"]
    v2_leagues = v2_support_docs["leagues"]
    v2_teams = v2_support_docs["teams"]

    counts_old = {
        "league_count": len(old_leagues),
        "team_count": len(old_teams),
        "league_url_count": sum(1 for row in old_leagues if row.get("unibet_base_url")),
        "opta_id_count": sum(1 for row in old_teams if row.get("opta_id") is not None),
        "opta_rank_count": sum(1 for row in old_teams if row.get("opta_rank") is not None),
        "opta_rating_count": sum(1 for row in old_teams if row.get("opta_rating") is not None),
        "league_identity_hash": stable_json_hash(_league_identity_rows(old_leagues)),
        "team_identity_hash": stable_json_hash(_team_identity_rows(old_teams)),
    }
    counts_v2 = {
        "league_count": len(v2_leagues),
        "team_count": len(v2_teams),
        "league_url_count": sum(1 for row in v2_leagues if row.get("unibet_base_url")),
        "opta_id_count": sum(1 for row in v2_teams if row.get("opta_id") is not None),
        "opta_rank_count": sum(1 for row in v2_teams if row.get("opta_rank") is not None),
        "opta_rating_count": sum(1 for row in v2_teams if row.get("opta_rating") is not None),
        "league_identity_hash": stable_json_hash(_league_identity_rows(v2_leagues)),
        "team_identity_hash": stable_json_hash(_team_identity_rows(v2_teams)),
    }

    matched = (
        counts_old["league_count"] == counts_v2["league_count"]
        and counts_old["team_count"] == counts_v2["team_count"]
        and counts_old["league_url_count"] == counts_v2["league_url_count"]
        and counts_old["league_identity_hash"] == counts_v2["league_identity_hash"]
        and counts_old["team_identity_hash"] == counts_v2["team_identity_hash"]
    )
    parity_status = "matched" if matched else "mismatch"

    return [
        build_parity_report_row(
            workflow_entry={
                "old_workflow": source_workflow,
                "old_inputs": [
                    "data/leagues-and-teams.json",
                    "data/unibetLeagueUrls.json",
                    "Opta power rankings",
                ],
                "old_outputs": ["leagues-and-teams.json"],
                "v2_job": "sync_support_data.py",
                "v2_outputs": [
                    "support_sources",
                    "support_leagues",
                    "support_teams",
                    "support_rankings",
                ],
                "smoke_test": "dry-run support sync against old repo support files and remote ranking sources",
                "parity_proof": "compare league/team identity coverage and unibet url coverage against old support files",
            },
            counts_old=counts_old,
            counts_v2=counts_v2,
            parity_status=parity_status,
            blocking_issues=[] if matched else ["support_identity_parity_mismatch"],
            audit_risks=[],
        )
    ]


def build_support_audit_rows(
    *,
    source_workflow: str,
    source_inputs: list[Any],
    support_docs: dict[str, Any],
) -> list[dict[str, Any]]:
    source_errors = [
        {
            "source_name": source.source_name,
            "error": source.error,
        }
        for source in source_inputs
        if getattr(source, "error", None)
    ]
    team_docs = support_docs["teams"]
    ranking_docs = support_docs["rankings"]
    unmatched_opta = [row["team_key"] for row in team_docs if row.get("opta_source_status") == "unmatched"]
    ranking_unmatched = [row["league_key"] for row in ranking_docs if not row.get("matched_support_league")]

    status = "ok"
    findings: list[str] = []
    if source_errors:
        status = "warn"
        findings.extend(f"source_error:{row['source_name']}" for row in source_errors)
    if unmatched_opta:
        status = "warn"
        findings.append(f"unmatched_opta_teams:{len(unmatched_opta)}")
    if not ranking_docs:
        status = "warn"
        findings.append("missing_league_ranking_rows")
    if ranking_unmatched:
        status = "warn"
        findings.append(f"unmatched_league_ranking_rows:{len(ranking_unmatched)}")

    return [
        build_audit_report_row(
            audit_type="support_sync",
            scope_key=source_workflow,
            status=status,
            metrics={
                "source_count": len(source_inputs),
                "source_error_count": len(source_errors),
                "league_count": len(support_docs["leagues"]),
                "team_count": len(team_docs),
                "league_url_count": sum(1 for row in support_docs["leagues"] if row.get("unibet_base_url")),
                "opta_matched_team_count": sum(1 for row in team_docs if row.get("opta_source_status") == "matched"),
                "opta_unmatched_team_count": len(unmatched_opta),
                "ranking_count": len(ranking_docs),
                "ranking_unmatched_count": len(ranking_unmatched),
            },
            findings=findings,
        )
    ]


def build_support_health_rows(
    *,
    source_workflow: str,
    source_inputs: list[Any],
    support_docs: dict[str, Any],
) -> list[dict[str, Any]]:
    source_errors = sum(1 for source in source_inputs if getattr(source, "error", None))
    ranking_count = len(support_docs["rankings"])
    unmatched_opta = sum(1 for row in support_docs["teams"] if row.get("opta_source_status") == "unmatched")
    status = "ok" if source_errors == 0 and ranking_count > 0 and unmatched_opta == 0 else "warn"
    summary = (
        "Support sync sources loaded and normalized."
        if status == "ok"
        else "Support sync completed with missing source coverage or unmatched support rows."
    )
    return [
        build_health_report_row(
            job_name="sync_support_data",
            status=status,
            summary=summary,
            metrics={
                "source_error_count": source_errors,
                "ranking_count": ranking_count,
                "unmatched_opta_team_count": unmatched_opta,
            },
        )
    ]
