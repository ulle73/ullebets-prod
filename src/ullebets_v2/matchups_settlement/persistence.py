from __future__ import annotations

from typing import Any


def persist_matchup_settlement_records(
    database: Any,
    *,
    score_docs: list[dict[str, Any]],
    league_avg_docs: list[dict[str, Any]],
    parity_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    health_rows: list[dict[str, Any]],
) -> dict[str, int]:
    score_updates = 0
    for row in score_docs:
        result = database["matchups_score_v2"].update_one(
            {"entry_key": row["entry_key"]},
            {"$set": row},
            upsert=True,
        )
        score_updates += 1 if result.upserted_id is not None else 0

    league_avg_updates = 0
    for row in league_avg_docs:
        result = database["matchups_league_avg_v2"].update_one(
            {"entry_key": row["entry_key"]},
            {"$set": row},
            upsert=True,
        )
        league_avg_updates += 1 if result.upserted_id is not None else 0

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
            {"job_name": row["job_name"], "report_date": row["report_date"]},
            {"$set": row},
            upsert=True,
        )
        health_upserts += 1 if result.upserted_id is not None else 0

    return {
        "score_updates": score_updates,
        "league_avg_updates": league_avg_updates,
        "parity_upserts": parity_upserts,
        "audit_upserts": audit_upserts,
        "health_upserts": health_upserts,
    }
