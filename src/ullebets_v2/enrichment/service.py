from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ullebets_v2.enrichment.backfill import (
    build_canonical_match_enrichment_from_raw,
    load_enrichment_backfill_inputs,
)
from ullebets_v2.enrichment.live import (
    EnrichmentSourceConfig,
    Transport,
    build_live_match_enrichment_source_rows,
)
from ullebets_v2.enrichment.persistence import persist_enrichment_records
from ullebets_v2.enrichment.replay import (
    build_match_enrichment_documents,
    build_teamstats_source_rows,
    build_teamstats_source_rows_from_database,
)
from ullebets_v2.enrichment.reports import build_match_enrichment_audit_rows, build_match_enrichment_parity_rows
from ullebets_v2.forward_timing import to_utc_datetime
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.settlement.service import FORWARD_BET_SELECTION_SOURCE, build_settled_docs


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


def select_unresolved_forward_match_keys(
    *,
    forward_bet_docs: list[dict[str, Any]],
    match_stats_canonical: list[dict[str, Any]],
    match_results_canonical: list[dict[str, Any]],
    reference_time: datetime,
    minimum_match_age: timedelta,
) -> list[str]:
    cutoff = reference_time - minimum_match_age
    eligible_bets = []
    for row in forward_bet_docs:
        match_start_time = to_utc_datetime(row.get("match_start_time"))
        if match_start_time is None or match_start_time > cutoff:
            continue
        eligible_bets.append(row)

    settlement_rows = build_settled_docs(
        selection_docs=eligible_bets,
        match_stats_canonical=match_stats_canonical,
        match_results_canonical=match_results_canonical,
        selection_source=FORWARD_BET_SELECTION_SOURCE,
        settled_at=reference_time,
    )
    return sorted(
        {
            str(row["match_key"])
            for row in settlement_rows
            if row.get("match_key")
            and row.get("settlement_status") in {"pending_result", "missing_actual"}
        }
    )


def load_replay_source_rows(
    *,
    source_dir: Path,
    dates: list[str] | None = None,
    legacy_teamstats_database: Any | None = None,
) -> tuple[list[dict[str, Any]], str]:
    if dates and legacy_teamstats_database is not None:
        mongo_rows = build_teamstats_source_rows_from_database(
            legacy_teamstats_database,
            dates=dates,
        )
        if mongo_rows:
            return mongo_rows, "mongodb_fallback"

    file_rows = filter_source_rows_by_dates(build_teamstats_source_rows(source_dir), dates)
    if file_rows:
        return file_rows, "files"

    if legacy_teamstats_database is not None:
        mongo_rows = build_teamstats_source_rows_from_database(
            legacy_teamstats_database,
            dates=dates,
        )
        if mongo_rows:
            return mongo_rows, "mongodb_fallback"

    return file_rows, "files"


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
    legacy_teamstats_database: Any | None = None,
    database: Any | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    source_rows, replay_source = load_replay_source_rows(
        source_dir=source_dir,
        dates=dates,
        legacy_teamstats_database=legacy_teamstats_database,
    )
    return _run_match_enrichment_pipeline(
        source_rows=source_rows,
        expected_matches=None,
        support_docs=support_docs,
        source_workflow=source_workflow,
        job_args={"dry_run": False, "mode": "replay"},
        target_window={"dates": dates or [], "mode": "replay"},
        database=database,
        dry_run=dry_run,
        extra_summary={"dates": dates or [], "mode": "replay", "replay_source": replay_source},
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
            "dates": sorted(
                {
                    str(row.get("fixture_date_stockholm") or row.get("source_date") or "")
                    for row in targets
                }
            ),
            "errors": sum(1 for row in live_result["match_rows"] if row.get("error")),
            "matched_targets": len(live_result["source_rows"]),
            "match_rows": live_result["match_rows"],
        },
    )


def run_match_enrichment_backfill_from_raw(
    *,
    read_database: Any,
    source_workflow: str,
    dates: list[str] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    inputs = load_enrichment_backfill_inputs(read_database, dates=dates)
    rebuilt = build_canonical_match_enrichment_from_raw(**inputs)
    parity_rows = build_match_enrichment_parity_rows(
        source_workflow=source_workflow,
        source_rows=[],
        expected_matches=rebuilt["expected_matches"],
        canonical_match_results=rebuilt["match_results"],
    )
    audit_rows = build_match_enrichment_audit_rows(
        source_workflow=source_workflow,
        source_rows=[],
        expected_matches=rebuilt["expected_matches"],
        raw_match_statistics=inputs["raw_match_statistics"],
        raw_incidents=inputs["raw_incidents"],
        raw_shotmaps=inputs["raw_shotmaps"],
        raw_results=inputs["raw_results"],
        canonical_match_results=rebuilt["match_results"],
        canonical_match_stats=rebuilt["match_stats_canonical"],
    )
    summary: dict[str, Any] = {
        "job": "backfill_match_enrichment",
        "mode": "db",
        "dates": dates or [],
        "replay_source": "v2_raw",
        "fixture_targets": len(inputs["fixtures"]),
        "source_files": 0,
        "raw_match_statistics": len(inputs["raw_match_statistics"]),
        "raw_incidents": len(inputs["raw_incidents"]),
        "raw_shotmaps": len(inputs["raw_shotmaps"]),
        "raw_results": len(inputs["raw_results"]),
        "match_results_canonical": len(rebuilt["match_results"]),
        "match_stats_canonical": len(rebuilt["match_stats_canonical"]),
        "parity_reports": len(parity_rows),
        "audit_reports": len(audit_rows),
        "missing_fixture_context_matches": rebuilt["missing_fixture_context_matches"],
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
        job_name="backfill_match_enrichment",
        source_workflow=source_workflow,
        target_window={"dates": dates or [], "mode": "db"},
        job_args={"dry_run": False, "mode": "db"},
    )
    job_collection.insert_one(run_doc)
    try:
        metrics = persist_enrichment_records(
            database,
            raw_match_statistics=inputs["raw_match_statistics"],
            raw_incidents=inputs["raw_incidents"],
            raw_shotmaps=inputs["raw_shotmaps"],
            raw_results=inputs["raw_results"],
            match_stats_canonical=rebuilt["match_stats_canonical"],
            match_results=rebuilt["match_results"],
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
