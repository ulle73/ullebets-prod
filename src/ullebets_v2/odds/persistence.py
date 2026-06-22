from __future__ import annotations

from typing import Any


def persist_odds_records(
    database: Any,
    *,
    raw_docs: list[dict[str, Any]],
    event_link_docs: list[dict[str, Any]],
    market_offer_docs: list[dict[str, Any]],
    parity_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    health_rows: list[dict[str, Any]],
) -> dict[str, int]:
    raw_upserts = 0
    for row in raw_docs:
        result = database["raw_odds_kambi"].update_one(
            {"raw_key": row["raw_key"]},
            {"$set": row},
            upsert=True,
        )
        raw_upserts += 1 if result.upserted_id is not None else 0

    event_link_upserts = 0
    for row in event_link_docs:
        result = database["unibet_event_links"].update_one(
            {"event_id": row["event_id"]},
            {"$set": row},
            upsert=True,
        )
        event_link_upserts += 1 if result.upserted_id is not None else 0

    market_offer_upserts = 0
    for row in market_offer_docs:
        result = database["market_offers"].update_one(
            {"offer_key": row["offer_key"]},
            {"$set": row},
            upsert=True,
        )
        market_offer_upserts += 1 if result.upserted_id is not None else 0

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
        "raw_upserts": raw_upserts,
        "event_link_upserts": event_link_upserts,
        "market_offer_upserts": market_offer_upserts,
        "parity_upserts": parity_upserts,
        "audit_upserts": audit_upserts,
        "health_upserts": health_upserts,
    }
