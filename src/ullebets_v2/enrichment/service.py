from __future__ import annotations

from pathlib import Path
from typing import Any

from ullebets_v2.enrichment.live import (
    EnrichmentSourceConfig,
    Transport,
    build_live_match_enrichment_source_rows,
)
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


def _run_match_enrichment_pipeline(
    *,
    source_rows: list[dict[str, Any]],
    expected_matches: list[dict[str, Any]] | None,
    support_docs: dict[str, Any],
    source_workflow: str,
    job_args: dict[str, Any],
    target_window: dict[str, Any],
    database: Any | None,
    dry_run: bool,
    extra_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    docs = build_match_enrichment_documents(
        source_rows=source_rows,
        support_docs=support_docs,
    )
    parity_rows = build_match_enrichment_parity_rows(
        source_workflow=source_workflow,
        source_rows=source_rows,
        expected_matches=expected_matches,
        canonical_match_results=docs["match_results"],
    )
    audit_rows = build_match_enrichment_audit_rows(
        source_workflow=source_workflow,
        source_rows=source_rows,
        expected_matches=expected_matches,
        raw_match_statistics=docs["raw_match_statistics"],
        raw_incidents=docs["raw_incidents"],
        raw_shotmaps=docs["raw_shotmaps"],
        raw_results=docs["raw_results"],
        canonical_match_results=docs["match_results"],
        canonical_match_stats=docs["match_stats_canonical"],
    )

    summary: dict[str, Any] = {
        "job": "ingest_match_enrichment",
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
    if extra_summary:
        summary.update(extra_summary)

    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    job_collection = database["job_runs"]
    run_doc = build_job_run_started_doc(
        job_name="ingest_match_enrichment",
        source_workflow=source_workflow,
        target_window=target_window,
        job_args=job_args,
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
    return _run_match_enrichment_pipeline(
        source_rows=source_rows,
        expected_matches=None,
        support_docs=support_docs,
        source_workflow=source_workflow,
        job_args={"dry_run": False, "mode": "replay"},
        target_window={"dates": dates or [], "mode": "replay"},
        database=database,
        dry_run=dry_run,
        extra_summary={"dates": dates or [], "mode": "replay"},
    )


def run_live_match_enrichment_window(
    *,
    targets: list[dict[str, Any]],
    support_docs: dict[str, Any],
    source_workflow: str,
    source_config: EnrichmentSourceConfig,
    database: Any | None = None,
    dry_run: bool = False,
    transport: Transport | None = None,
) -> dict[str, Any]:
    live_result = build_live_match_enrichment_source_rows(
        targets=targets,
        source_config=source_config,
        transport=transport,
    )
    return _run_match_enrichment_pipeline(
        source_rows=live_result["source_rows"],
        expected_matches=targets,
        support_docs=support_docs,
        source_workflow=source_workflow,
        job_args={"dry_run": False, "mode": "live"},
        target_window={"target_matches": len(targets), "mode": "live"},
        database=database,
        dry_run=dry_run,
        extra_summary={
            "mode": "live",
            "target_matches": len(targets),
            "dates": sorted({str(row.get("source_date") or "") for row in targets}),
            "errors": sum(1 for row in live_result["match_rows"] if row.get("error")),
            "matched_targets": len(live_result["source_rows"]),
            "match_rows": live_result["match_rows"],
        },
    )
