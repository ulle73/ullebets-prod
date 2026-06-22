from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)


def _load_rows(database: Any, collection_name: str) -> list[dict[str, Any]]:
    return list(database[collection_name].find({}, projection={"_id": 0}))


def _filter_by_date(rows: list[dict[str, Any]], field: str, from_date: str | None) -> list[dict[str, Any]]:
    if not from_date:
        return rows
    return [row for row in rows if str(row.get(field) or "") >= from_date]


def _latest_successful_run(job_runs: list[dict[str, Any]], job_name: str) -> dict[str, Any] | None:
    succeeded = [row for row in job_runs if row.get("job_name") == job_name and row.get("status") == "succeeded"]
    succeeded.sort(key=lambda row: row.get("finished_at") or row.get("started_at") or datetime.min.replace(tzinfo=UTC), reverse=True)
    return succeeded[0] if succeeded else None


def _build_verification_rows(
    *,
    source_workflow: str,
    from_date: str | None,
    stale_hours: int,
    match_results: list[dict[str, Any]],
    match_stats: list[dict[str, Any]],
    raw_incidents: list[dict[str, Any]],
    raw_shotmaps: list[dict[str, Any]],
    job_runs: list[dict[str, Any]],
    report_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    result_rows = _filter_by_date(match_results, "source_date", from_date)
    stat_rows = _filter_by_date(match_stats, "source_date", from_date)
    incident_rows = _filter_by_date(raw_incidents, "source_date", from_date)
    shotmap_rows = _filter_by_date(raw_shotmaps, "source_date", from_date)

    result_match_keys = {str(row.get("match_key") or "") for row in result_rows if row.get("match_key")}
    stat_match_keys = {str(row.get("match_key") or "") for row in stat_rows if row.get("match_key")}
    incident_match_keys = {str(row.get("match_key") or "") for row in incident_rows if row.get("match_key")}
    shotmap_match_keys = {str(row.get("match_key") or "") for row in shotmap_rows if row.get("match_key")}

    missing_stats = sorted(result_match_keys - stat_match_keys)
    missing_incidents = sorted(result_match_keys - incident_match_keys)
    missing_shotmaps = sorted(result_match_keys - shotmap_match_keys)
    missing_scores = sorted(
        str(row.get("match_key"))
        for row in result_rows
        if row.get("home_score") is None or row.get("away_score") is None
    )

    latest_ingest = _latest_successful_run(job_runs, "ingest_match_enrichment")
    latest_profiles = _latest_successful_run(job_runs, "build_teamprofiles")
    latest_finished = latest_ingest.get("finished_at") if latest_ingest else None
    stale_cutoff = utc_now() - timedelta(hours=stale_hours)
    stale_ingest = latest_finished is None or latest_finished < stale_cutoff

    findings: list[str] = []
    if missing_stats:
        findings.append("missing_match_stats")
    if missing_incidents:
        findings.append("missing_incidents")
    if missing_shotmaps:
        findings.append("missing_shotmaps")
    if missing_scores:
        findings.append("missing_scores")
    if stale_ingest:
        findings.append("stale_ingest_job_run")
    status = "ok" if not findings else "warn"

    metrics = {
        "from_date": from_date,
        "distinct_match_count": len(result_match_keys),
        "match_result_count": len(result_rows),
        "match_stat_row_count": len(stat_rows),
        "raw_incident_count": len(incident_rows),
        "raw_shotmap_count": len(shotmap_rows),
        "missing_stats_count": len(missing_stats),
        "missing_incidents_count": len(missing_incidents),
        "missing_shotmaps_count": len(missing_shotmaps),
        "missing_scores_count": len(missing_scores),
        "latest_ingest_finished_at": latest_finished,
        "latest_teamprofiles_finished_at": latest_profiles.get("finished_at") if latest_profiles else None,
        "stale_ingest": stale_ingest,
        "stale_hours_threshold": stale_hours,
    }
    audit_rows = [
        build_audit_report_row(
            audit_type="match_enrichment_verification",
            scope_key=f"{source_workflow}:{from_date or 'all'}",
            status=status if result_rows else "ok",
            metrics=metrics,
            findings=findings if result_rows else ["no_match_results_in_window"],
            report_date=report_date,
        )
    ]
    health_rows = [
        build_health_report_row(
            job_name="verify_match_enrichment",
            status=status if result_rows else "ok",
            summary=(
                "Match enrichment verification completed."
                if result_rows
                else "No canonical match results found for the requested window."
            ),
            metrics=metrics,
            report_date=report_date,
        )
    ]
    summary = {
        "job": "verify_match_enrichment",
        "from_date": from_date,
        "match_results": len(result_rows),
        "match_stats": len(stat_rows),
        "raw_incidents": len(incident_rows),
        "raw_shotmaps": len(shotmap_rows),
        "missing_stats": missing_stats,
        "missing_incidents": missing_incidents,
        "missing_shotmaps": missing_shotmaps,
        "missing_scores": missing_scores,
        "audit_status_counts": dict(Counter(row["status"] for row in audit_rows)),
        "health_status_counts": dict(Counter(row["status"] for row in health_rows)),
        "latest_ingest_run": latest_ingest,
        "latest_teamprofile_run": latest_profiles,
        "audit_reports": len(audit_rows),
        "health_reports": len(health_rows),
    }
    return audit_rows, health_rows, summary


def run_match_enrichment_verification(
    *,
    source_workflow: str,
    from_date: str | None = None,
    stale_hours: int = 36,
    match_results: list[dict[str, Any]] | None = None,
    match_stats: list[dict[str, Any]] | None = None,
    raw_incidents: list[dict[str, Any]] | None = None,
    raw_shotmaps: list[dict[str, Any]] | None = None,
    job_runs: list[dict[str, Any]] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    now = generated_at or utc_now()
    if any(value is None for value in (match_results, match_stats, raw_incidents, raw_shotmaps, job_runs)):
        if database is None:
            match_results = match_results or []
            match_stats = match_stats or []
            raw_incidents = raw_incidents or []
            raw_shotmaps = raw_shotmaps or []
            job_runs = job_runs or []
        else:
            match_results = _load_rows(database, "match_results_canonical") if match_results is None else match_results
            match_stats = _load_rows(database, "match_stats_canonical") if match_stats is None else match_stats
            raw_incidents = _load_rows(database, "raw_incidents") if raw_incidents is None else raw_incidents
            raw_shotmaps = _load_rows(database, "raw_shotmaps") if raw_shotmaps is None else raw_shotmaps
            job_runs = _load_rows(database, "job_runs") if job_runs is None else job_runs

    audit_rows, health_rows, summary = _build_verification_rows(
        source_workflow=source_workflow,
        from_date=from_date,
        stale_hours=stale_hours,
        match_results=match_results or [],
        match_stats=match_stats or [],
        raw_incidents=raw_incidents or [],
        raw_shotmaps=raw_shotmaps or [],
        job_runs=job_runs or [],
        report_date=now.date().isoformat(),
    )
    if dry_run:
        summary["audit_rows"] = audit_rows
        summary["health_rows"] = health_rows
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="verify_match_enrichment",
        source_workflow=source_workflow,
        target_window={"from_date": from_date},
        job_args={"dry_run": False, "stale_hours": stale_hours},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {key: value for key, value in summary.items() if key not in {"audit_rows", "health_rows"}}
    try:
        for row in audit_rows:
            database["audit_reports"].update_one(
                {"audit_type": row["audit_type"], "scope_key": row["scope_key"], "report_date": row["report_date"]},
                {"$set": row},
                upsert=True,
            )
        for row in health_rows:
            database["health_reports"].update_one(
                {"job_name": row["job_name"], "report_date": row["report_date"]},
                {"$set": row},
                upsert=True,
            )
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(status="succeeded", metrics=job_metrics),
        )
    except Exception as exc:
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="failed",
                metrics=job_metrics,
                error={"type": type(exc).__name__, "message": str(exc)},
            ),
        )
        raise
    summary["audit_rows"] = audit_rows
    summary["health_rows"] = health_rows
    return summary

