from __future__ import annotations

from typing import Any


def persist_fixture_records(
    database: Any,
    *,
    raw_fixture_docs: list[dict[str, Any]],
    canonical_fixture_docs: list[dict[str, Any]],
    source_link_docs: list[dict[str, Any]],
    parity_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
) -> dict[str, int]:
    raw_upserts = 0
    for raw_doc in raw_fixture_docs:
        result = database["raw_fixtures"].update_one(
            {"payload_hash": raw_doc["payload_hash"]},
            {"$set": raw_doc},
            upsert=True,
        )
        raw_upserts += 1 if result.upserted_id is not None else 0

    canonical_upserts = 0
    for canonical_doc in canonical_fixture_docs:
        result = database["fixtures_canonical"].update_one(
            {"match_key": canonical_doc["match_key"]},
            {"$set": canonical_doc},
            upsert=True,
        )
        canonical_upserts += 1 if result.upserted_id is not None else 0

    source_link_upserts = 0
    for source_link_doc in source_link_docs:
        result = database["fixture_source_links"].update_one(
            {"link_key": source_link_doc["link_key"]},
            {"$set": source_link_doc},
            upsert=True,
        )
        source_link_upserts += 1 if result.upserted_id is not None else 0

    parity_upserts = 0
    for row in parity_rows:
        result = database["parity_reports"].update_one(
            {
                "old_workflow": row["old_workflow"],
                "report_date": row["report_date"],
            },
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

    return {
        "raw_upserts": raw_upserts,
        "canonical_upserts": canonical_upserts,
        "source_link_upserts": source_link_upserts,
        "parity_upserts": parity_upserts,
        "audit_upserts": audit_upserts,
    }
