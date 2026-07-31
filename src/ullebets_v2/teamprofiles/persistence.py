from __future__ import annotations

from typing import Any

from ullebets_v2.storage.collections import TEAMPROFILES


def persist_teamprofile_records(
    database: Any,
    *,
    profile_docs: list[dict[str, Any]],
    parity_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    health_rows: list[dict[str, Any]],
    replace_profile_date: str | None = None,
) -> dict[str, int]:
    profile_upserts = 0
    for row in profile_docs:
        result = database[TEAMPROFILES].update_one(
            {"profile_key": row["profile_key"]},
            {"$set": row},
            upsert=True,
        )
        profile_upserts += 1 if result.upserted_id is not None else 0

    deleted_profiles = 0
    if replace_profile_date and profile_docs:
        keep_profile_keys = [str(row["profile_key"]) for row in profile_docs if row.get("profile_key")]
        delete_result = database[TEAMPROFILES].delete_many(
            {
                "profile_date": replace_profile_date,
                "profile_key": {"$nin": keep_profile_keys},
            }
        )
        deleted_profiles = int(getattr(delete_result, "deleted_count", 0) or 0)

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
        "teamprofile_upserts": profile_upserts,
        "teamprofile_deleted": deleted_profiles,
        "parity_upserts": parity_upserts,
        "audit_upserts": audit_upserts,
        "health_upserts": health_upserts,
    }
