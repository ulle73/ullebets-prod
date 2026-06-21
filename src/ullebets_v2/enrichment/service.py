from __future__ import annotations

from pathlib import Path
from typing import Any

from ullebets_v2.enrichment.persistence import persist_enrichment_records
from ullebets_v2.enrichment.replay import build_match_enrichment_documents, build_teamstats_source_rows
from ullebets_v2.enrichment.reports import build_match_enrichment_audit_rows, build_match_enrichment_parity_rows
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc


def filter_source_rows_by_dates(source_rows: list[dict[str, Any]], dates: list[str] | None) -> list[dict[str, Any]]:
    if not dates:
        return source_rows
    allowed = set(dates)
    filtered: list[dict[str, Any]] = []
    for row in source_rows:
        matches = [match for match in row["matches"] if str(match.get("date")) in allowed]
        if matches:
            filtered.append({**row, "matches": matches})
    return filtered


def run_match_enrichment_window(
    *,
    source_dir: Path,
    support_docs: dict[str, Any],
    source_workflow: str,
    dates: list[str] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    source_rows = filter_source_rows_by_dates(build_teamstats_source_rows(source_dir), dates)
    docs = build_match_enrichment_documents(
        source_rows=source_rows,
        support_docs=support_docs,
    )
    parity_rows = build_match_enrichment_parity_rows(
        source_workflow=source_workflow,
        source_rows=source_rows,
        canonical_match_results=docs["match_results"],
    )
    audit_rows = build_match_enrichment_audit_rows(
        source_workflow=source_workflow,
        source_rows=source_rows,
        raw_match_statistics=docs["raw_match_statistics"],
        raw_incidents=docs["raw_incidents"],
        raw_shotmaps=docs["raw_shotmaps"],
        raw_results=docs["raw_results"],
        canonical_match_results=docs["match_results"],
        canonical_match_stats=docs["match_stats_canonical"],
    )

    summary: dict[str, Any] = {
        "job": "ingest_match_enrichment",
        "dates": dates or [],
        "source_files": len(source_rows),
        "raw_match_statistics": len(docs["raw_match_statistics"]),
        "raw_incidents": len(docs["raw_incidents"]),
        "raw_shotmaps": len(docs["raw_shotmaps"]),
        "raw_results": len(docs["raw_results"]),
        "match_results_canonical": len(docs["match_results"]),
        "match_stats_canonical": len(docs["match_stats_canonical"]),
        "parity_reports": len(parity_rows),
        "audit_reports": len(audit_rows),
        "parity_status_counts": {
            status: sum(1 for row in parity_rows if row["parity_status"] == status)
            for status in sorted({row["parity_status"] for row in parity_rows})
        },
        "audit_status_counts": {
            status: sum(1 for row in audit_rows if row["status"] == status)
            for status in sorted({row["status"] for row in audit_rows})
        },
    }

    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    job_collection = database["job_runs"]
    run_doc = build_job_run_started_doc(
        job_name="ingest_match_enrichment",
        source_workflow=source_workflow,
        target_window={"dates": dates or []},
        job_args={"dry_run": False},
    )
    job_collection.insert_one(run_doc)
    try:
        metrics = persist_enrichment_records(
            database,
            raw_match_statistics=docs["raw_match_statistics"],
            raw_incidents=docs["raw_incidents"],
            raw_shotmaps=docs["raw_shotmaps"],
            raw_results=docs["raw_results"],
            match_stats_canonical=docs["match_stats_canonical"],
            match_results=docs["match_results"],
            parity_rows=parity_rows,
            audit_rows=audit_rows,
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
