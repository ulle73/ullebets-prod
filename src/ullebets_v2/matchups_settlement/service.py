from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.matchups_settlement.persistence import persist_matchup_settlement_records
from ullebets_v2.matchups_settlement.reports import (
    build_matchup_settlement_audit_rows,
    build_matchup_settlement_health_rows,
    build_matchup_settlement_parity_rows,
)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def normalize_scope(scope: str | None) -> str:
    value = str(scope or "").lower()
    if value in {"total", "all"}:
        return "all"
    if value in {"home", "away"}:
        return value
    return value or "all"


def _result_is_finished(result_row: dict[str, Any] | None) -> bool:
    if result_row is None:
        return False
    return result_row.get("home_score") is not None and result_row.get("away_score") is not None


def build_stats_lookup(match_stats_canonical: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in match_stats_canonical:
        key = (
            str(row.get("match_key") or ""),
            str(row.get("stat_key") or ""),
            str(row.get("period") or ""),
            normalize_scope(row.get("scope")),
        )
        lookup[key] = row
    return lookup


def build_result_lookup(match_results_canonical: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("match_key")): row
        for row in match_results_canonical
        if row.get("match_key") is not None
    }


def _resolve_outcome_fields(
    *,
    row: dict[str, Any],
    result_lookup: dict[str, dict[str, Any]],
    stats_lookup: dict[tuple[str, str, str, str], dict[str, Any]],
    resolved_at: datetime,
) -> dict[str, Any]:
    match_key = str(row.get("match_key") or "")
    stat_key = str(row.get("stat_key") or "")
    period = str(row.get("period") or "")
    scope = normalize_scope(row.get("scope"))
    result_row = result_lookup.get(match_key)
    if not _result_is_finished(result_row):
        return {
            **row,
            "outcome_status": "pending_result",
            "actual_value": None,
            "home_value": None,
            "away_value": None,
            "actual_source": None,
            "resolved_at": resolved_at,
            "outcome": None,
        }

    home_row = stats_lookup.get((match_key, stat_key, period, "home"))
    away_row = stats_lookup.get((match_key, stat_key, period, "away"))
    total_row = stats_lookup.get((match_key, stat_key, period, "all"))

    home_value = home_row.get("actual_value") if home_row else None
    away_value = away_row.get("actual_value") if away_row else None
    if scope == "home":
        actual_value = home_value
    elif scope == "away":
        actual_value = away_value
    else:
        actual_value = total_row.get("actual_value") if total_row else (
            (home_value + away_value) if isinstance(home_value, (int, float)) and isinstance(away_value, (int, float)) else None
        )

    if actual_value is None:
        return {
            **row,
            "outcome_status": "missing_actual",
            "actual_value": None,
            "home_value": home_value,
            "away_value": away_value,
            "actual_source": None,
            "resolved_at": resolved_at,
            "outcome": None,
        }

    return {
        **row,
        "outcome_status": "resolved",
        "actual_value": actual_value,
        "home_value": home_value,
        "away_value": away_value,
        "actual_source": f"{match_key}:{stat_key}:{period}",
        "resolved_at": resolved_at,
        "outcome": {
            "actualValue": actual_value,
            "homeValue": home_value,
            "awayValue": away_value,
        },
    }


def enrich_matchup_rows(
    *,
    rows: list[dict[str, Any]],
    result_lookup: dict[str, dict[str, Any]],
    stats_lookup: dict[tuple[str, str, str, str], dict[str, Any]],
    resolved_at: datetime,
) -> list[dict[str, Any]]:
    return [
        _resolve_outcome_fields(
            row=row,
            result_lookup=result_lookup,
            stats_lookup=stats_lookup,
            resolved_at=resolved_at,
        )
        for row in rows
    ]


def _load_matchup_rows(
    database: Any,
    *,
    date_from: str,
    date_to: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    query = {"snapshot_date": {"$gte": date_from, "$lte": date_to}}
    score_rows = list(database["matchups_score_v2"].find(query, projection={"_id": 0}))
    league_avg_rows = list(database["matchups_league_avg_v2"].find(query, projection={"_id": 0}))
    return score_rows, league_avg_rows


def _load_canonical_rows(
    database: Any,
    *,
    score_rows: list[dict[str, Any]],
    league_avg_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    match_keys = sorted(
        {
            str(row.get("match_key"))
            for row in [*score_rows, *league_avg_rows]
            if row.get("match_key") is not None
        }
    )
    if not match_keys:
        return [], []
    query = {"match_key": {"$in": match_keys}}
    match_stats = list(database["match_stats_canonical"].find(query, projection={"_id": 0}))
    match_results = list(database["match_results_canonical"].find(query, projection={"_id": 0}))
    return match_stats, match_results


def run_matchup_settlement(
    *,
    source_workflow: str,
    date_from: str,
    date_to: str | None = None,
    score_rows: list[dict[str, Any]] | None = None,
    league_avg_rows: list[dict[str, Any]] | None = None,
    match_stats_canonical: list[dict[str, Any]] | None = None,
    match_results_canonical: list[dict[str, Any]] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    resolved_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = resolved_at or utc_now()
    upper = date_to or date_from
    score_docs = score_rows
    league_docs = league_avg_rows
    stats_rows = match_stats_canonical
    result_rows = match_results_canonical
    if score_docs is None or league_docs is None:
        if database is None:
            score_docs = score_docs or []
            league_docs = league_docs or []
        else:
            loaded_score, loaded_league = _load_matchup_rows(database, date_from=date_from, date_to=upper)
            score_docs = loaded_score if score_docs is None else score_docs
            league_docs = loaded_league if league_docs is None else league_docs
    if stats_rows is None or result_rows is None:
        if database is None:
            stats_rows = stats_rows or []
            result_rows = result_rows or []
        else:
            loaded_stats, loaded_results = _load_canonical_rows(
                database,
                score_rows=score_docs or [],
                league_avg_rows=league_docs or [],
            )
            stats_rows = loaded_stats if stats_rows is None else stats_rows
            result_rows = loaded_results if result_rows is None else result_rows

    result_lookup = build_result_lookup(result_rows or [])
    stats_lookup = build_stats_lookup(stats_rows or [])
    settled_score_docs = enrich_matchup_rows(
        rows=score_docs or [],
        result_lookup=result_lookup,
        stats_lookup=stats_lookup,
        resolved_at=timestamp,
    )
    settled_league_avg_docs = enrich_matchup_rows(
        rows=league_docs or [],
        result_lookup=result_lookup,
        stats_lookup=stats_lookup,
        resolved_at=timestamp,
    )
    report_date = upper
    parity_rows = build_matchup_settlement_parity_rows(
        source_workflow=source_workflow,
        score_docs=settled_score_docs,
        league_avg_docs=settled_league_avg_docs,
        report_date=report_date,
    )
    audit_rows = build_matchup_settlement_audit_rows(
        source_workflow=source_workflow,
        score_docs=settled_score_docs,
        league_avg_docs=settled_league_avg_docs,
        report_date=report_date,
    )
    health_rows = build_matchup_settlement_health_rows(
        score_docs=settled_score_docs,
        league_avg_docs=settled_league_avg_docs,
        report_date=report_date,
    )

    all_docs = [*settled_score_docs, *settled_league_avg_docs]
    summary: dict[str, Any] = {
        "job": "settle_matchups_outputs",
        "resolved_at": timestamp.isoformat(),
        "date_from": date_from,
        "date_to": upper,
        "score_rows": len(settled_score_docs),
        "league_avg_rows": len(settled_league_avg_docs),
        "resolved_rows": sum(1 for row in all_docs if row.get("outcome_status") == "resolved"),
        "parity_reports": len(parity_rows),
        "audit_reports": len(audit_rows),
        "health_reports": len(health_rows),
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
        "outcome_status_counts": {
            status: sum(1 for row in all_docs if row.get("outcome_status") == status)
            for status in sorted({row.get("outcome_status") for row in all_docs})
        },
        "score_docs": settled_score_docs,
        "league_avg_docs": settled_league_avg_docs,
    }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="settle_matchups_outputs",
        source_workflow=source_workflow,
        target_window={"date_from": date_from, "date_to": upper},
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {key: value for key, value in summary.items() if key not in {"score_docs", "league_avg_docs"}}
    try:
        persistence_metrics = persist_matchup_settlement_records(
            database,
            score_docs=settled_score_docs,
            league_avg_docs=settled_league_avg_docs,
            parity_rows=parity_rows,
            audit_rows=audit_rows,
            health_rows=health_rows,
        )
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics={**persistence_metrics, **job_metrics},
            ),
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
    return summary
