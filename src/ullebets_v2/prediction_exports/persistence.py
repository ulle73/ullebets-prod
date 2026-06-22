from __future__ import annotations

from typing import Any


def persist_prediction_export_records(
    database: Any,
    *,
    prediction_export_docs: list[dict[str, Any]],
    forward_bet_docs: list[dict[str, Any]],
    parity_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    health_rows: list[dict[str, Any]],
) -> dict[str, int]:
    export_upserts = 0
    for row in prediction_export_docs:
        result = database["prediction_exports_v2"].update_one(
            {"prediction_key": row["prediction_key"]},
            {"$set": row},
            upsert=True,
        )
        export_upserts += 1 if result.upserted_id is not None else 0

    forward_bet_upserts = 0
    for row in forward_bet_docs:
        result = database["forward_bets_v2"].update_one(
            {"prediction_key": row["prediction_key"]},
            {"$set": row},
            upsert=True,
        )
        forward_bet_upserts += 1 if result.upserted_id is not None else 0

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
        "prediction_export_upserts": export_upserts,
        "forward_bet_upserts": forward_bet_upserts,
        "parity_upserts": parity_upserts,
        "audit_upserts": audit_upserts,
        "health_upserts": health_upserts,
    }
