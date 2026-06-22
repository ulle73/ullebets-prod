from __future__ import annotations

from typing import Any


def persist_analysis_records(
    database: Any,
    *,
    analysis_run_doc: dict[str, Any],
    analysis_candidate_docs: list[dict[str, Any]],
    analysis_snapshot_doc: dict[str, Any] | None,
    parity_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    health_rows: list[dict[str, Any]],
) -> dict[str, int]:
    run_result = database["analysis_runs_v2"].update_one(
        {"run_id": analysis_run_doc["run_id"]},
        {"$set": analysis_run_doc},
        upsert=True,
    )
    run_upserts = 1 if run_result.upserted_id is not None else 0

    candidate_upserts = 0
    for row in analysis_candidate_docs:
        result = database["analysis_candidates_v2"].update_one(
            {"candidate_key": row["candidate_key"]},
            {"$set": row},
            upsert=True,
        )
        candidate_upserts += 1 if result.upserted_id is not None else 0

    snapshot_upserts = 0
    if analysis_snapshot_doc:
        result = database["analysis_snapshots_v2"].update_one(
            {"analysis_key": analysis_snapshot_doc["analysis_key"]},
            {"$set": analysis_snapshot_doc},
            upsert=True,
        )
        snapshot_upserts = 1 if result.upserted_id is not None else 0

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
        "analysis_run_upserts": run_upserts,
        "analysis_candidate_upserts": candidate_upserts,
        "analysis_snapshot_upserts": snapshot_upserts,
        "parity_upserts": parity_upserts,
        "audit_upserts": audit_upserts,
        "health_upserts": health_upserts,
    }
