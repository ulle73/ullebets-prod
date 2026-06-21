from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.support.opta import extract_opta_rows
from ullebets_v2.support.persistence import persist_support_records
from ullebets_v2.support.reports import (
    build_support_audit_rows,
    build_support_health_rows,
    build_support_parity_rows,
)
from ullebets_v2.support.schemas import build_support_documents, build_support_source_docs


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def run_support_sync(
    *,
    source_workflow: str,
    leagues_payload: dict[str, Any],
    league_urls_payload: dict[str, Any],
    source_inputs: list[Any],
    opta_payload: Any | None = None,
    league_ranking_payload: Any | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    captured_at: datetime | None = None,
    source_version: str = "v2-support-sync",
) -> dict[str, Any]:
    now = captured_at or utc_now()
    old_support_docs = build_support_documents(
        leagues=leagues_payload,
        league_urls=league_urls_payload,
        ranking_rows=[],
        captured_at=now,
        source_version=source_version,
    )
    v2_support_docs = build_support_documents(
        leagues=leagues_payload,
        league_urls=league_urls_payload,
        ranking_rows=league_ranking_payload if isinstance(league_ranking_payload, list) else [],
        opta_rows=extract_opta_rows(opta_payload),
        captured_at=now,
        source_version=source_version,
    )
    source_docs = build_support_source_docs(
        source_payloads=[
            {
                "source_name": source.source_name,
                "source_kind": source.source_kind,
                "source_locator": source.source_locator,
                "payload": source.payload,
            }
            for source in source_inputs
        ],
        captured_at=now,
        source_version=source_version,
    )
    v2_support_docs["sources"] = source_docs
    parity_rows = build_support_parity_rows(
        source_workflow=source_workflow,
        old_support_docs=old_support_docs,
        v2_support_docs=v2_support_docs,
    )
    audit_rows = build_support_audit_rows(
        source_workflow=source_workflow,
        source_inputs=source_inputs,
        support_docs=v2_support_docs,
    )
    health_rows = build_support_health_rows(
        source_workflow=source_workflow,
        source_inputs=source_inputs,
        support_docs=v2_support_docs,
    )

    summary: dict[str, Any] = {
        "job": "sync_support_data",
        "captured_at": now.isoformat(),
        "support_sources": len(source_docs),
        "support_leagues": len(v2_support_docs["leagues"]),
        "support_teams": len(v2_support_docs["teams"]),
        "support_rankings": len(v2_support_docs["rankings"]),
        "parity_reports": len(parity_rows),
        "audit_reports": len(audit_rows),
        "health_reports": len(health_rows),
        "source_errors": {
            source.source_name: source.error
            for source in source_inputs
            if getattr(source, "error", None)
        },
        "opta_match_method_counts": {
            method: sum(1 for row in v2_support_docs["teams"] if row.get("opta_match_method") == method)
            for method in sorted(
                {
                    row.get("opta_match_method")
                    for row in v2_support_docs["teams"]
                    if row.get("opta_match_method")
                }
            )
        },
        "parity_status_counts": {
            status: sum(1 for row in parity_rows if row["parity_status"] == status)
            for status in sorted({row["parity_status"] for row in parity_rows})
        },
        "audit_status_counts": {
            status: sum(1 for row in audit_rows if row["status"] == status)
            for status in sorted({row["status"] for row in audit_rows})
        },
        "health_status_counts": {
            status: sum(1 for row in health_rows if row["status"] == status)
            for status in sorted({row["status"] for row in health_rows})
        },
    }

    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    job_collection = database["job_runs"]
    run_doc = build_job_run_started_doc(
        job_name="sync_support_data",
        source_workflow=source_workflow,
        target_window={"captured_at": now.isoformat()},
        job_args={"dry_run": False},
    )
    job_collection.insert_one(run_doc)
    try:
        metrics = persist_support_records(
            database,
            source_docs=source_docs,
            support_docs=v2_support_docs,
            parity_rows=parity_rows,
            audit_rows=audit_rows,
            health_rows=health_rows,
        )
        job_collection.update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics={**metrics, **summary},
            ),
        )
    except Exception as exc:
        job_collection.update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="failed",
                metrics=summary,
                error={"type": type(exc).__name__, "message": str(exc)},
            ),
        )
        raise

    return summary
