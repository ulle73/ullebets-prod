from __future__ import annotations

from typing import Any


def persist_support_records(
    database: Any,
    *,
    source_docs: list[dict[str, Any]],
    support_docs: dict[str, Any],
    parity_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    health_rows: list[dict[str, Any]],
) -> dict[str, int]:
    source_upserts = 0
    for row in source_docs:
        result = database["support_sources"].update_one(
            {"source_key": row["source_key"]},
            {"$set": row},
            upsert=True,
        )
        source_upserts += 1 if result.upserted_id is not None else 0

    league_upserts = 0
    for row in support_docs["leagues"]:
        result = database["support_leagues"].update_one(
            {"league_key": row["league_key"]},
            {"$set": row},
            upsert=True,
        )
        league_upserts += 1 if result.upserted_id is not None else 0

    team_upserts = 0
    for row in support_docs["teams"]:
        result = database["support_teams"].update_one(
            {"team_key": row["team_key"]},
            {"$set": row},
            upsert=True,
        )
        team_upserts += 1 if result.upserted_id is not None else 0

    ranking_upserts = 0
    for row in support_docs["rankings"]:
        result = database["support_rankings"].update_one(
            {"league_key": row["league_key"], "ranking_type": row["ranking_type"]},
            {"$set": row},
            upsert=True,
        )
        ranking_upserts += 1 if result.upserted_id is not None else 0

    parity_upserts = 0
    for row in parity_rows:
        result = database["parity_reports"].update_one(
            {"old_workflow": row["old_workflow"], "report_date": row["report_date"]},
            {"$set": row},
            upsert=True,
        )
        parity_upserts += 1 if result.upserted_id is not None else 0

    audit_upserts = 0
    for row in audit_rows:
        result = database["audit_reports"].update_one(
            {
                "audit_type": row["audit_type"],
                "scope_key": row["scope_key"],
                "report_date": row["report_date"],
            },
            {"$set": row},
            upsert=True,
        )
        audit_upserts += 1 if result.upserted_id is not None else 0

    health_upserts = 0
    for row in health_rows:
        result = database["health_reports"].update_one(
            {
                "job_name": row["job_name"],
                "report_date": row["report_date"],
            },
            {"$set": row},
            upsert=True,
        )
        health_upserts += 1 if result.upserted_id is not None else 0

    return {
        "support_source_upserts": source_upserts,
        "support_league_upserts": league_upserts,
        "support_team_upserts": team_upserts,
        "support_ranking_upserts": ranking_upserts,
        "parity_upserts": parity_upserts,
        "audit_upserts": audit_upserts,
        "health_upserts": health_upserts,
    }
