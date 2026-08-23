from __future__ import annotations

from typing import Any

from pymongo import UpdateOne

from ullebets_v2.fixtures.dates import fixture_date_stockholm


def backfill_fixture_date_stockholm(
    database: Any,
    *,
    batch_size: int = 200,
    dry_run: bool = False,
) -> dict[str, int]:
    """Populate the rebuildable product-date derivative without changing source provenance."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    collection = database["fixtures_canonical"]
    summary = {
        "scanned": 0,
        "eligible": 0,
        "would_update": 0,
        "updated": 0,
        "already_correct": 0,
        "missing_start_time": 0,
        "missing_match_key": 0,
    }
    operations: list[UpdateOne] = []

    def flush() -> None:
        if not operations:
            return
        if not dry_run:
            collection.bulk_write(operations, ordered=False)
            summary["updated"] += len(operations)
        operations.clear()

    for row in collection.find(
        {},
        projection={"_id": 0, "match_key": 1, "start_time": 1, "fixture_date_stockholm": 1},
    ):
        summary["scanned"] += 1
        match_key = row.get("match_key")
        if not match_key:
            summary["missing_match_key"] += 1
            continue
        derived_date = fixture_date_stockholm(row.get("start_time"))
        if derived_date is None:
            summary["missing_start_time"] += 1
            continue
        summary["eligible"] += 1
        if row.get("fixture_date_stockholm") == derived_date:
            summary["already_correct"] += 1
            continue
        summary["would_update"] += 1
        operations.append(
            UpdateOne(
                {"match_key": str(match_key)},
                {"$set": {"fixture_date_stockholm": derived_date}},
            )
        )
        if len(operations) >= batch_size:
            flush()
    flush()
    return summary


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
