from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.closing.service import build_closing_line_docs
from ullebets_v2.clv_tracking.persistence import persist_clv_tracking_records
from ullebets_v2.clv_tracking.reports import (
    build_clv_tracking_audit_rows,
    build_clv_tracking_health_rows,
    build_clv_tracking_parity_rows,
)
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _to_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric == numeric else None


def _normalize_scope(scope: str | None) -> str:
    value = str(scope or "").lower()
    return "all" if value in {"all", "total"} else value


def _closing_lookup(closing_line_docs: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str, str, str, float], dict[str, Any]]]:
    by_offer_key: dict[str, dict[str, Any]] = {}
    by_tuple: dict[tuple[str, str, str, str, float], dict[str, Any]] = {}
    for row in closing_line_docs:
        offer_key = str(row.get("offer_key") or "")
        if offer_key:
            by_offer_key[offer_key] = row
        line_value = _to_float(row.get("line"))
        if line_value is None:
            continue
        tuple_key = (
            str(row.get("match_key") or ""),
            str(row.get("stat_key") or ""),
            str(row.get("period") or ""),
            _normalize_scope(row.get("scope")),
            line_value,
        )
        by_tuple[tuple_key] = row
    return by_offer_key, by_tuple


def build_clv_tracking_docs(
    *,
    model_snapshot_docs: list[dict[str, Any]],
    closing_line_docs: list[dict[str, Any]],
    refreshed_at: datetime,
) -> list[dict[str, Any]]:
    by_offer_key, by_tuple = _closing_lookup(closing_line_docs)
    docs: list[dict[str, Any]] = []
    for snapshot in model_snapshot_docs:
        selected_odds = _to_float(snapshot.get("selected_odds"))
        line_value = _to_float(snapshot.get("line_value"))
        invalid_snapshot_timing = bool(snapshot.get("invalid_for_model"))
        closing = None
        offer_key = str(snapshot.get("offer_key") or "")
        if offer_key:
            closing = by_offer_key.get(offer_key)
        if closing is None and line_value is not None:
            closing = by_tuple.get(
                (
                    str(snapshot.get("match_key") or ""),
                    str(snapshot.get("stat_key") or ""),
                    str(snapshot.get("period") or ""),
                    _normalize_scope(snapshot.get("scope")),
                    line_value,
                )
            )

        direction = "under" if str(snapshot.get("direction") or "").lower() == "under" else "over"
        closing_odds = None
        if closing is not None:
            closing_odds = _to_float(
                closing.get("closing_under_odds") if direction == "under" else closing.get("closing_over_odds")
            )

        clv_status = "tracked"
        if invalid_snapshot_timing:
            clv_status = "invalid_snapshot_timing"
        elif closing is None:
            clv_status = "missing_closing_line"
        elif selected_odds is None or closing_odds is None or closing_odds <= 1 or selected_odds <= 1:
            clv_status = "missing_selected_odds"

        clv_pct = None
        implied_edge_delta = None
        beat_closing_line = None
        if clv_status == "tracked":
            clv_pct = round(((selected_odds / closing_odds) - 1.0) * 100, 1)
            implied_edge_delta = round(((1.0 / closing_odds) - (1.0 / selected_odds)) * 100, 2)
            beat_closing_line = selected_odds > closing_odds

        docs.append(
            {
                "tracking_key": snapshot["selection_key"],
                "selection_key": snapshot["selection_key"],
                "bet_key": snapshot.get("bet_key"),
                "match_key": snapshot.get("match_key"),
                "offer_key": snapshot.get("offer_key"),
                "closing_key": closing.get("closing_key") if closing else None,
                "event_id": snapshot.get("event_id"),
                "league_key": snapshot.get("league_key"),
                "league_name": snapshot.get("league_name"),
                "home_team_name": snapshot.get("home_team_name"),
                "away_team_name": snapshot.get("away_team_name"),
                "stat_key": snapshot.get("stat_key"),
                "period": snapshot.get("period"),
                "scope": snapshot.get("scope"),
                "direction": direction,
                "line_value": snapshot.get("line_value"),
                "selected_odds": selected_odds,
                "snapshot_time": snapshot.get("snapshot_time"),
                "match_start_time": snapshot.get("match_start_time"),
                "invalid_for_model": invalid_snapshot_timing,
                "closing_snapshot_time": closing.get("closing_snapshot_time") if closing else None,
                "closing_snapshot_label": closing.get("closing_snapshot_label") if closing else None,
                "closing_odds": closing_odds,
                "prematch_observation_count": closing.get("prematch_observation_count") if closing else 0,
                "clv_pct": clv_pct,
                "implied_edge_delta": implied_edge_delta,
                "beat_closing_line": beat_closing_line,
                "clv_status": clv_status,
                "refreshed_at": refreshed_at,
            }
        )
    return docs


def load_model_snapshot_docs(database: Any) -> list[dict[str, Any]]:
    return list(database["model_snapshots"].find({}, projection={"_id": 0}))


def load_closing_line_docs(database: Any) -> list[dict[str, Any]]:
    return list(database["closing_lines_v2"].find({}, projection={"_id": 0}))


def run_clv_tracking_refresh(
    *,
    model_snapshot_docs: list[dict[str, Any]] | None = None,
    closing_line_docs: list[dict[str, Any]] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    refreshed_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = refreshed_at or utc_now()
    snapshots = model_snapshot_docs if model_snapshot_docs is not None else (load_model_snapshot_docs(database) if database is not None else [])
    closing_lines = closing_line_docs
    if closing_lines is None:
        if database is not None:
            closing_lines = load_closing_line_docs(database)
        else:
            closing_lines = build_closing_line_docs(
                market_snapshot_docs=[],
                refreshed_at=timestamp,
            )

    clv_docs = build_clv_tracking_docs(
        model_snapshot_docs=snapshots,
        closing_line_docs=closing_lines,
        refreshed_at=timestamp,
    )
    report_date = timestamp.date().isoformat()
    parity_rows = build_clv_tracking_parity_rows(
        model_snapshot_docs=snapshots,
        clv_docs=clv_docs,
        report_date=report_date,
    )
    audit_rows = build_clv_tracking_audit_rows(
        clv_docs=clv_docs,
        report_date=report_date,
    )
    health_rows = build_clv_tracking_health_rows(
        clv_docs=clv_docs,
        report_date=report_date,
    )
    summary: dict[str, Any] = {
        "job": "refresh_clv_tracking",
        "refreshed_at": timestamp.isoformat(),
        "model_snapshots": len(snapshots),
        "closing_lines": len(closing_lines),
        "clv_tracking_rows": len(clv_docs),
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
            status: sum(1 for row in clv_docs if row.get("clv_status") == status)
            for status in sorted({row.get("clv_status") for row in clv_docs})
        },
        "clv_docs": clv_docs,
    }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="refresh_clv_tracking",
        source_workflow="closing-line-tracking",
        target_window={"model_snapshot_count": len(snapshots), "refreshed_at": timestamp.isoformat()},
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {key: value for key, value in summary.items() if key != "clv_docs"}
    try:
        persistence_metrics = persist_clv_tracking_records(
            database,
            clv_docs=clv_docs,
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
