from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ullebets_v2.enrichment.service import run_match_enrichment_window
from ullebets_v2.fixtures.service import run_fixture_ingest_window
from ullebets_v2.jobs.job_runs import finish_job_run, start_job_run
from ullebets_v2.teamprofiles.service import run_teamprofile_build
from ullebets_v2.verification.service import run_match_enrichment_verification


def _normalize_dates(dates: list[str]) -> list[str]:
    normalized = [str(value) for value in dates if str(value).strip()]
    unique_dates = list(dict.fromkeys(normalized))
    if not unique_dates:
        raise ValueError("At least one date is required for historical Phase A backfill.")
    return unique_dates


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _default_profile_date(dates: list[str]) -> str:
    latest = max(_parse_date(value) for value in dates)
    return (latest + timedelta(days=1)).date().isoformat()


def _default_verification_from_date(dates: list[str]) -> str:
    earliest = min(_parse_date(value) for value in dates)
    return earliest.date().isoformat()


def _build_parent_metrics(
    *,
    summary: dict[str, Any],
    steps_completed: list[str],
) -> dict[str, Any]:
    fixture_summary = summary.get("fixture_summary") or {}
    enrichment_summary = summary.get("enrichment_summary") or {}
    verification_summary = summary.get("verification_summary") or {}
    teamprofile_summary = summary.get("teamprofile_summary") or {}
    return {
        "steps_completed": len(steps_completed),
        "step_names": steps_completed,
        "fixture_processed_dates": fixture_summary.get("processed_dates", 0),
        "fixture_canonical_docs": fixture_summary.get("canonical_docs", 0),
        "fixture_missing_dates": len(fixture_summary.get("missing_dates") or []),
        "enrichment_match_results_canonical": enrichment_summary.get("match_results_canonical", 0),
        "enrichment_match_stats_canonical": enrichment_summary.get("match_stats_canonical", 0),
        "verification_audit_reports": verification_summary.get("audit_reports", 0),
        "verification_health_reports": verification_summary.get("health_reports", 0),
        "teamprofiles": teamprofile_summary.get("teamprofiles", 0),
    }


def run_historical_phase_a_backfill(
    *,
    dates: list[str],
    support_docs: dict[str, Any],
    old_payloads_by_date: dict[str, dict[str, Any]],
    fixture_source_dir: Path,
    fixture_source_paths_by_date: dict[str, Path] | None = None,
    teamstats_source_dir: Path,
    legacy_teamstats_database: Any | None,
    database: Any | None = None,
    dry_run: bool = False,
    source_workflow: str = "historical-phase-a-backfill",
    fixture_workflow: str = "import-fixtures-rolling.yml",
    enrichment_workflow: str = "update-teamstats-and-teamprofiles.yml",
    verification_workflow: str = "verify-teamstats-db.yml",
    teamprofile_workflow: str = "update-teamstats-and-teamprofiles.yml",
    verification_from_date: str | None = None,
    profile_date: str | None = None,
    stale_hours: int = 36,
) -> dict[str, Any]:
    normalized_dates = _normalize_dates(dates)
    effective_verification_from_date = verification_from_date or _default_verification_from_date(normalized_dates)
    effective_profile_date = profile_date or _default_profile_date(normalized_dates)

    summary: dict[str, Any] = {
        "job": "historical_phase_a_backfill",
        "mode": "replay",
        "dates": normalized_dates,
        "verification_from_date": effective_verification_from_date,
        "profile_date": effective_profile_date,
        "fixture_source_dir": str(fixture_source_dir),
        "teamstats_source_dir": str(teamstats_source_dir),
        "steps_completed": [],
    }
    steps_completed: list[str] = []

    run_id: str | None = None
    if not dry_run:
        if database is None:
            raise RuntimeError("database is required when dry_run is False.")
        run_doc = start_job_run(
            database["job_runs"],
            job_name="historical_phase_a_backfill",
            source_workflow=source_workflow,
            target_window={
                "dates": normalized_dates,
                "from_date": effective_verification_from_date,
                "profile_date": effective_profile_date,
                "mode": "replay",
            },
            job_args={
                "dry_run": False,
                "stale_hours": stale_hours,
                "fixture_workflow": fixture_workflow,
                "enrichment_workflow": enrichment_workflow,
                "verification_workflow": verification_workflow,
                "teamprofile_workflow": teamprofile_workflow,
            },
        )
        run_id = str(run_doc["run_id"])

    try:
        fixture_summary = run_fixture_ingest_window(
            mode="replay",
            dates=normalized_dates,
            support_docs=support_docs,
            source_workflow=fixture_workflow,
            old_payloads_by_date=old_payloads_by_date,
            source_dir=fixture_source_dir,
            replay_source_paths_by_date=fixture_source_paths_by_date,
            database=database,
            dry_run=dry_run,
        )
        steps_completed.append("fixtures")
        summary["fixture_summary"] = fixture_summary
        summary["steps_completed"] = list(steps_completed)

        enrichment_summary = run_match_enrichment_window(
            source_dir=teamstats_source_dir,
            support_docs=support_docs,
            source_workflow=enrichment_workflow,
            dates=normalized_dates,
            legacy_teamstats_database=legacy_teamstats_database,
            database=database,
            dry_run=dry_run,
        )
        steps_completed.append("enrichment")
        summary["enrichment_summary"] = enrichment_summary
        summary["steps_completed"] = list(steps_completed)

        verification_summary = run_match_enrichment_verification(
            source_workflow=verification_workflow,
            from_date=effective_verification_from_date,
            stale_hours=stale_hours,
            database=database,
            dry_run=dry_run,
        )
        steps_completed.append("verification")
        summary["verification_summary"] = verification_summary
        summary["steps_completed"] = list(steps_completed)

        teamprofile_summary = run_teamprofile_build(
            source_workflow=teamprofile_workflow,
            support_docs=support_docs,
            profile_date=effective_profile_date,
            database=database,
            dry_run=dry_run,
        )
        steps_completed.append("teamprofiles")
        summary["teamprofile_summary"] = teamprofile_summary
        summary["steps_completed"] = list(steps_completed)

        if run_id is not None and database is not None:
            finish_job_run(
                database["job_runs"],
                run_id=run_id,
                status="succeeded",
                metrics=_build_parent_metrics(summary=summary, steps_completed=steps_completed),
            )
        return summary
    except Exception as exc:
        if run_id is not None and database is not None:
            finish_job_run(
                database["job_runs"],
                run_id=run_id,
                status="failed",
                metrics=_build_parent_metrics(summary=summary, steps_completed=steps_completed),
                error={"type": type(exc).__name__, "message": str(exc)},
            )
        raise
