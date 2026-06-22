from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.settlement.persistence import persist_settlement_records
from ullebets_v2.settlement.reports import (
    build_settlement_audit_rows,
    build_settlement_health_rows,
    build_settlement_parity_rows,
)
from ullebets_v2.settlement.rules import settle_line


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def normalize_scope(scope: str | None) -> str:
    value = str(scope or "").lower()
    if value in {"total", "all"}:
        return "all"
    if value in {"home", "away"}:
        return value
    return value or "all"


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


def build_settled_docs(
    *,
    model_snapshot_docs: list[dict[str, Any]],
    match_stats_canonical: list[dict[str, Any]],
    match_results_canonical: list[dict[str, Any]],
    settled_at: datetime,
) -> list[dict[str, Any]]:
    stats_lookup = build_stats_lookup(match_stats_canonical)
    result_lookup = build_result_lookup(match_results_canonical)
    settled_docs: list[dict[str, Any]] = []
    for snapshot in model_snapshot_docs:
        match_key = str(snapshot.get("match_key") or "")
        result_row = result_lookup.get(match_key)
        if result_row is None:
            settled_docs.append(
                {
                    **snapshot,
                    "settlement_key": snapshot["selection_key"],
                    "settlement_status": "pending_result",
                    "settlement_result": None,
                    "actual_value": None,
                    "win": None,
                    "roi_units": None,
                    "pnl_units": None,
                    "actual_source": None,
                    "settled_at": settled_at,
                }
            )
            continue

        stat_row = stats_lookup.get(
            (
                match_key,
                str(snapshot.get("stat_key") or ""),
                str(snapshot.get("period") or ""),
                normalize_scope(snapshot.get("scope")),
            )
        )
        if stat_row is None:
            settled_docs.append(
                {
                    **snapshot,
                    "settlement_key": snapshot["selection_key"],
                    "settlement_status": "missing_actual",
                    "settlement_result": None,
                    "actual_value": None,
                    "win": None,
                    "roi_units": None,
                    "pnl_units": None,
                    "actual_source": None,
                    "settled_at": settled_at,
                }
            )
            continue

        settlement = settle_line(
            actual_value=stat_row.get("actual_value"),
            line_value=snapshot.get("line_value"),
            direction=str(snapshot.get("direction") or "over"),
            odds_decimal=snapshot.get("selected_odds"),
            stake_units=1,
        )
        if settlement is None:
            settled_docs.append(
                {
                    **snapshot,
                    "settlement_key": snapshot["selection_key"],
                    "settlement_status": "rule_error",
                    "settlement_result": None,
                    "actual_value": stat_row.get("actual_value"),
                    "win": None,
                    "roi_units": None,
                    "pnl_units": None,
                    "actual_source": f"{stat_row.get('match_key')}:{stat_row.get('stat_key')}:{stat_row.get('period')}:{stat_row.get('scope')}",
                    "settled_at": settled_at,
                }
            )
            continue

        settled_docs.append(
            {
                **snapshot,
                "settlement_key": snapshot["selection_key"],
                "settlement_status": "settled",
                "settlement_result": settlement["settlement_result"],
                "actual_value": stat_row.get("actual_value"),
                "win": settlement["win"],
                "roi_units": settlement["roi_units"],
                "pnl_units": settlement["pnl_units"],
                "stake_units": settlement["stake_units"],
                "actual_source": f"{stat_row.get('match_key')}:{stat_row.get('stat_key')}:{stat_row.get('period')}:{stat_row.get('scope')}",
                "settled_at": settled_at,
            }
        )
    return settled_docs


def load_unsettled_model_snapshot_docs(database: Any) -> list[dict[str, Any]]:
    return list(database["model_snapshots"].find({}, projection={"_id": 0}))


def load_match_stats_docs(database: Any, match_keys: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not match_keys:
        return [], []
    query = {"match_key": {"$in": match_keys}}
    match_stats = list(database["match_stats_canonical"].find(query, projection={"_id": 0}))
    match_results = list(database["match_results_canonical"].find(query, projection={"_id": 0}))
    return match_stats, match_results


def run_model_snapshot_settlement(
    *,
    source_workflow: str,
    model_snapshot_docs: list[dict[str, Any]] | None = None,
    match_stats_canonical: list[dict[str, Any]] | None = None,
    match_results_canonical: list[dict[str, Any]] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    settled_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = settled_at or utc_now()
    snapshots = model_snapshot_docs
    stats = match_stats_canonical
    results = match_results_canonical
    if snapshots is None:
        if database is None:
            snapshots = []
        else:
            snapshots = load_unsettled_model_snapshot_docs(database)
    if stats is None or results is None:
        if database is None:
            stats = stats or []
            results = results or []
        else:
            loaded_stats, loaded_results = load_match_stats_docs(database, [str(row["match_key"]) for row in snapshots])
            stats = loaded_stats if stats is None else stats
            results = loaded_results if results is None else results

    settled_docs = build_settled_docs(
        model_snapshot_docs=snapshots,
        match_stats_canonical=stats or [],
        match_results_canonical=results or [],
        settled_at=timestamp,
    )
    report_date = timestamp.date().isoformat()
    parity_rows = build_settlement_parity_rows(
        source_workflow=source_workflow,
        model_snapshot_docs=snapshots,
        settled_docs=settled_docs,
        report_date=report_date,
    )
    audit_rows = build_settlement_audit_rows(
        source_workflow=source_workflow,
        settled_docs=settled_docs,
        report_date=report_date,
    )
    health_rows = build_settlement_health_rows(
        settled_docs=settled_docs,
        report_date=report_date,
    )

    summary: dict[str, Any] = {
        "job": "settle_model_snapshots",
        "settled_at": timestamp.isoformat(),
        "model_snapshots": len(snapshots),
        "settled_bets": len(settled_docs),
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
        "status_counts": {
            status: sum(1 for row in settled_docs if row.get("settlement_status") == status)
            for status in sorted({row.get("settlement_status") for row in settled_docs})
        },
        "result_counts": {
            result: sum(1 for row in settled_docs if row.get("settlement_result") == result)
            for result in sorted({row.get("settlement_result") for row in settled_docs if row.get("settlement_result")})
        },
        "settled_docs": settled_docs,
    }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="settle_model_snapshots",
        source_workflow=source_workflow,
        target_window={"snapshot_count": len(snapshots), "settled_at": timestamp.isoformat()},
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {key: value for key, value in summary.items() if key != "settled_docs"}
    try:
        persistence_metrics = persist_settlement_records(
            database,
            settled_docs=settled_docs,
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
