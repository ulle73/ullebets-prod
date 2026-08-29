from __future__ import annotations

from typing import Any

from pymongo import UpdateOne

from ullebets_v2.storage.collections import MATCHUPS_LEAGUE_AVG, MATCHUPS_SCORE

BULK_WRITE_BATCH_SIZE = 100


def _upsert_rows(collection: Any, rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> int:
    if not rows:
        return 0
    bulk_write = getattr(collection, "bulk_write", None)
    if not callable(bulk_write):
        upserts = 0
        for row in rows:
            result = collection.update_one({field: row[field] for field in key_fields}, {"$set": row}, upsert=True)
            upserts += 1 if result.upserted_id is not None else 0
        return upserts
    upserts = 0
    for start in range(0, len(rows), BULK_WRITE_BATCH_SIZE):
        batch = rows[start : start + BULK_WRITE_BATCH_SIZE]
        result = bulk_write([UpdateOne({field: row[field] for field in key_fields}, {"$set": row}, upsert=True) for row in batch], ordered=False)
        upserts += int(result.upserted_count)
    return upserts


def persist_matchup_settlement_records(
    database: Any,
    *,
    score_docs: list[dict[str, Any]],
    league_avg_docs: list[dict[str, Any]],
    parity_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    health_rows: list[dict[str, Any]],
) -> dict[str, int]:
    score_updates = _upsert_rows(database[MATCHUPS_SCORE], score_docs, ("entry_key",))
    league_avg_updates = _upsert_rows(database[MATCHUPS_LEAGUE_AVG], league_avg_docs, ("entry_key",))

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
