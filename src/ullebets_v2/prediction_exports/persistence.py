from __future__ import annotations

from typing import Any

from ullebets_v2.forward_exposures import is_combo_leg
from ullebets_v2.storage.collections import FORWARD_BETS, PREDICTION_EXPORTS


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
        result = database[PREDICTION_EXPORTS].update_one(
            {"prediction_key": row["prediction_key"]},
            {"$set": row},
            upsert=True,
        )
        export_upserts += 1 if result.upserted_id is not None else 0

    forward_bet_upserts = 0
    forward_bet_existing = 0
    for row in forward_bet_docs:
        collection = database[FORWARD_BETS]
        existing = collection.find_one(
            {"canonical_exposure_key": row["canonical_exposure_key"]},
            projection={"_id": 0, "prediction_key": 1},
        )
        if existing is None and row.get("selection_key"):
            existing = next(
                (
                    candidate
                    for candidate in collection.find(
                        {"selection_key": row["selection_key"]},
                        projection={"_id": 0},
                    )
                    if not is_combo_leg(candidate)
                ),
                None,
            )
        if existing is not None:
            forward_bet_existing += 1
            continue
        result = collection.update_one(
            {"prediction_key": row["prediction_key"]},
            {"$setOnInsert": row},
            upsert=True,
        )
        forward_bet_upserts += 1 if result.upserted_id is not None else 0
        forward_bet_existing += 1 if result.upserted_id is None else 0

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
        "forward_bet_existing": forward_bet_existing,
        "parity_upserts": parity_upserts,
        "audit_upserts": audit_upserts,
        "health_upserts": health_upserts,
    }
