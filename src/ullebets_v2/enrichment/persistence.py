from __future__ import annotations

from typing import Any

from pymongo import ReplaceOne


BULK_WRITE_BATCH_SIZE = 200


def persist_enrichment_records(
    database: Any,
    *,
    raw_match_statistics: list[dict[str, Any]],
    raw_incidents: list[dict[str, Any]],
    raw_shotmaps: list[dict[str, Any]],
    raw_results: list[dict[str, Any]],
    match_stats_canonical: list[dict[str, Any]],
    match_results: list[dict[str, Any]],
    parity_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
) -> dict[str, int]:
    def upsert_many(collection_name: str, docs: list[dict[str, Any]], key_fields: list[str]) -> int:
        collection = database[collection_name]
        if not docs:
            return 0

        if hasattr(collection, "bulk_write"):
            operations = [
                ReplaceOne(
                    {field: doc[field] for field in key_fields},
                    doc,
                    upsert=True,
                )
                for doc in docs
            ]
            created = 0
            for offset in range(0, len(operations), BULK_WRITE_BATCH_SIZE):
                batch = operations[offset : offset + BULK_WRITE_BATCH_SIZE]
                result = collection.bulk_write(batch, ordered=False)
                created += len(getattr(result, "upserted_ids", {}) or {})
            return created

        created = 0
        for doc in docs:
            query = {field: doc[field] for field in key_fields}
            result = collection.update_one(query, {"$set": doc}, upsert=True)
            created += 1 if result.upserted_id is not None else 0
        return created

    metrics = {
        "raw_match_statistics_upserts": upsert_many("raw_match_statistics", raw_match_statistics, ["raw_key"]),
        "raw_incidents_upserts": upsert_many("raw_incidents", raw_incidents, ["raw_key"]),
        "raw_shotmaps_upserts": upsert_many("raw_shotmaps", raw_shotmaps, ["raw_key"]),
        "raw_results_upserts": upsert_many("raw_results", raw_results, ["raw_key"]),
        "match_results_canonical_upserts": upsert_many(
            "match_results_canonical",
            match_results,
            ["match_key"],
        ),
        "match_stats_canonical_upserts": upsert_many(
            "match_stats_canonical",
            match_stats_canonical,
            ["match_key", "stat_key", "period", "scope"],
        ),
        "parity_report_upserts": upsert_many(
            "parity_reports",
            parity_rows,
            ["old_workflow", "report_date"],
        ),
        "audit_report_upserts": upsert_many(
            "audit_reports",
            audit_rows,
            ["audit_type", "scope_key", "report_date"],
        ),
    }
    return metrics
