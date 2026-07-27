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


def _to_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def _normalize_scope(scope: str | None) -> str:
    value = str(scope or "").lower()
    return "all" if value in {"all", "total"} else value


def _normalize_tracking_doc(row: dict[str, Any]) -> dict[str, Any]:
    bet = row.get("bet") if isinstance(row.get("bet"), dict) else {}
    tracking_key = row.get("tracking_key") or row.get("selection_key") or row.get("trackingKey")
    saved_odds = (
        _to_float(row.get("saved_odds"))
        or _to_float(row.get("selected_odds"))
        or _to_float(bet.get("odds"))
    )
    saved_at = (
        row.get("saved_at")
        or row.get("snapshot_time")
        or row.get("savedOddsObservedAt")
        or row.get("createdAt")
    )
    source_match_id = row.get("source_match_id") or row.get("matchId")
    match_key = row.get("match_key")
    if match_key is None and source_match_id is not None:
        match_key = f"sofascore:{source_match_id}"
    return {
        "tracking_key": tracking_key,
        "selection_key": row.get("selection_key") or tracking_key,
        "prediction_key": row.get("prediction_key"),
        "parent_prediction_key": row.get("parent_prediction_key"),
        "analysis_key": row.get("analysis_key"),
        "run_id": row.get("run_id"),
        "export_mode": row.get("export_mode"),
        "prediction_type": row.get("prediction_type"),
        "bet_key": row.get("bet_key") or row.get("trackingKey"),
        "match_key": match_key,
        "source_match_id": source_match_id,
        "offer_key": row.get("offer_key"),
        "event_id": row.get("event_id"),
        "league_key": row.get("league_key"),
        "league_name": row.get("league_name") or row.get("leagueName"),
        "home_team_name": row.get("home_team_name") or row.get("homeTeamName") or bet.get("homeTeam"),
        "away_team_name": row.get("away_team_name") or row.get("awayTeamName") or bet.get("awayTeam"),
        "stat_key": row.get("stat_key") or bet.get("statKey"),
        "period": row.get("period") or bet.get("period"),
        "scope": row.get("scope") or bet.get("scope"),
        "direction": row.get("direction") or bet.get("direction"),
        "line_value": row.get("line_value") if row.get("line_value") is not None else bet.get("line"),
        "saved_odds": saved_odds,
        "saved_at": saved_at,
        "match_start_time": row.get("match_start_time") or row.get("eventTimestampMs"),
        "invalid_for_model": bool(row.get("invalid_for_model")),
        "tracking_source": "forward_bets_v2" if row.get("saved_at") is not None or row.get("prediction_key") is not None else "model_snapshots",
        "strategy_score": row.get("strategy_score") or row.get("strategyScore"),
        "primary_ev": row.get("primary_ev") or row.get("primaryEv"),
        "headline": row.get("headline"),
    }


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
    tracked_bet_docs: list[dict[str, Any]],
    closing_line_docs: list[dict[str, Any]],
    refreshed_at: datetime,
) -> list[dict[str, Any]]:
    by_offer_key, by_tuple = _closing_lookup(closing_line_docs)
    docs: list[dict[str, Any]] = []
    for raw_row in tracked_bet_docs:
        tracked = _normalize_tracking_doc(raw_row)
        saved_odds = _to_float(tracked.get("saved_odds"))
        line_value = _to_float(tracked.get("line_value"))
        saved_at = _to_datetime(tracked.get("saved_at"))
        match_start_time = _to_datetime(tracked.get("match_start_time"))
        invalid_snapshot_timing = bool(tracked.get("invalid_for_model"))
        if saved_at is not None and match_start_time is not None and saved_at >= match_start_time:
            invalid_snapshot_timing = True
        closing = None
        offer_key = str(tracked.get("offer_key") or "")
        if offer_key:
            closing = by_offer_key.get(offer_key)
        if closing is None and line_value is not None:
            closing = by_tuple.get(
                (
                    str(tracked.get("match_key") or ""),
                    str(tracked.get("stat_key") or ""),
                    str(tracked.get("period") or ""),
                    _normalize_scope(tracked.get("scope")),
                    line_value,
                )
            )

        direction = "under" if str(tracked.get("direction") or "").lower() == "under" else "over"
        opening_odds = None
        latest_odds = None
        closing_odds = None
        if closing is not None:
            opening_odds = _to_float(
                closing.get("opening_under_odds") if direction == "under" else closing.get("opening_over_odds")
            )
            latest_odds = _to_float(
                closing.get("latest_under_odds") if direction == "under" else closing.get("latest_over_odds")
            )
            closing_odds = _to_float(
                closing.get("closing_under_odds") if direction == "under" else closing.get("closing_over_odds")
            )

        clv_status = "tracked"
        if invalid_snapshot_timing:
            clv_status = "invalid_snapshot_timing"
        elif closing is None:
            clv_status = "missing_closing_line"
        elif saved_odds is None or closing_odds is None or closing_odds <= 1 or saved_odds <= 1:
            clv_status = "missing_selected_odds"

        clv_pct = None
        implied_edge_delta = None
        beat_closing_line = None
        if clv_status == "tracked":
            clv_pct = round(((saved_odds / closing_odds) - 1.0) * 100, 1)
            implied_edge_delta = round(((1.0 / closing_odds) - (1.0 / saved_odds)) * 100, 2)
            beat_closing_line = saved_odds > closing_odds

        price_history: list[dict[str, Any]] = []
        for history_row in list(closing.get("price_history") or []) if closing else []:
            odds = _to_float(history_row.get("under_odds") if direction == "under" else history_row.get("over_odds"))
            price_history.append(
                {
                    "snapshot_label": history_row.get("snapshot_label"),
                    "observed_at": history_row.get("snapshot_time"),
                    "odds": odds,
                    "source_workflow": history_row.get("source_workflow"),
                }
            )

        docs.append(
            {
                "tracking_key": tracked["tracking_key"],
                "selection_key": tracked["selection_key"],
                "prediction_key": tracked.get("prediction_key"),
                "parent_prediction_key": tracked.get("parent_prediction_key"),
                "analysis_key": tracked.get("analysis_key"),
                "run_id": tracked.get("run_id"),
                "export_mode": tracked.get("export_mode"),
                "prediction_type": tracked.get("prediction_type"),
                "tracking_source": tracked.get("tracking_source"),
                "bet_key": tracked.get("bet_key"),
                "match_key": tracked.get("match_key"),
                "source_match_id": tracked.get("source_match_id"),
                "offer_key": tracked.get("offer_key"),
                "closing_key": closing.get("closing_key") if closing else None,
                "event_id": tracked.get("event_id"),
                "league_key": tracked.get("league_key"),
                "league_name": tracked.get("league_name"),
                "home_team_name": tracked.get("home_team_name"),
                "away_team_name": tracked.get("away_team_name"),
                "stat_key": tracked.get("stat_key"),
                "period": tracked.get("period"),
                "scope": tracked.get("scope"),
                "direction": direction,
                "line_value": tracked.get("line_value"),
                "saved_odds": saved_odds,
                "selected_odds": saved_odds,
                "saved_at": tracked.get("saved_at"),
                "snapshot_time": tracked.get("saved_at"),
                "match_start_time": tracked.get("match_start_time"),
                "invalid_for_model": invalid_snapshot_timing,
                "opening_snapshot_label": closing.get("opening_snapshot_label") if closing else None,
                "opening_snapshot_time": closing.get("opening_snapshot_time") if closing else None,
                "opening_odds": opening_odds,
                "latest_snapshot_label": closing.get("latest_snapshot_label") if closing else None,
                "latest_snapshot_time": closing.get("latest_snapshot_time") if closing else None,
                "latest_observed_odds": latest_odds,
                "closing_snapshot_time": closing.get("closing_snapshot_time") if closing else None,
                "closing_snapshot_label": closing.get("closing_snapshot_label") if closing else None,
                "closing_odds": closing_odds,
                "opening_observed_at": closing.get("opening_snapshot_time") if closing else None,
                "latest_observed_at": closing.get("latest_snapshot_time") if closing else None,
                "closing_observed_at": closing.get("closing_snapshot_time") if closing else None,
                "price_history": price_history,
                "prematch_observation_count": closing.get("prematch_observation_count") if closing else 0,
                "clv_pct": clv_pct,
                "implied_edge_delta": implied_edge_delta,
                "beat_closing_line": beat_closing_line,
                "clv_status": clv_status,
                "refreshed_at": refreshed_at,
            }
        )
    return docs


def load_forward_bet_docs(database: Any) -> list[dict[str, Any]]:
    return list(database["forward_bets_v2"].find({}, projection={"_id": 0}))


def load_model_snapshot_docs(database: Any) -> list[dict[str, Any]]:
    return list(database["model_snapshots"].find({}, projection={"_id": 0}))


def load_closing_line_docs(database: Any) -> list[dict[str, Any]]:
    return list(database["closing_lines_v2"].find({}, projection={"_id": 0}))


def run_clv_tracking_refresh(
    *,
    tracked_bet_docs: list[dict[str, Any]] | None = None,
    model_snapshot_docs: list[dict[str, Any]] | None = None,
    closing_line_docs: list[dict[str, Any]] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    refreshed_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = refreshed_at or utc_now()
    tracked_rows = tracked_bet_docs if tracked_bet_docs is not None else model_snapshot_docs
    if tracked_rows is None:
        if database is not None:
            tracked_rows = load_forward_bet_docs(database)
            if not tracked_rows:
                tracked_rows = load_model_snapshot_docs(database)
        else:
            tracked_rows = []
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
        tracked_bet_docs=tracked_rows,
        closing_line_docs=closing_lines,
        refreshed_at=timestamp,
    )
    report_date = timestamp.date().isoformat()
    parity_rows = build_clv_tracking_parity_rows(
        tracked_bet_docs=tracked_rows,
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
        "tracked_bets": len(tracked_rows),
        "model_snapshots": len(tracked_rows),
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
        target_window={"tracked_bet_count": len(tracked_rows), "refreshed_at": timestamp.isoformat()},
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
