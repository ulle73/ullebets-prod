from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.forward_exposures import (
    canonicalize_forward_bet_docs,
    forward_selection_family,
)
from ullebets_v2.clv_tracking.service import build_clv_tracking_docs, load_closing_line_docs
from ullebets_v2.forward_timing import evaluate_forward_timing
from ullebets_v2.forward_results.persistence import persist_forward_result_records
from ullebets_v2.forward_results.reports import (
    build_forward_result_audit_rows,
    build_forward_result_health_rows,
    build_forward_result_parity_rows,
)
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.settlement.service import FORWARD_BET_SELECTION_SOURCE, build_settled_docs, load_match_stats_docs
from ullebets_v2.storage.collections import CLV_TRACKING, FORWARD_BETS, SETTLED_BETS


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


def _result_loop_key(row: dict[str, Any]) -> str:
    for field_name in ("prediction_key", "selection_key", "tracking_key", "offer_key"):
        value = row.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    match_key = str(row.get("match_key") or "missing-match")
    stat_key = str(row.get("stat_key") or "missing-stat")
    period = str(row.get("period") or "missing-period")
    scope = str(row.get("scope") or "missing-scope")
    line_value = str(row.get("line_value") or "missing-line")
    direction = str(row.get("direction") or "over")
    return "|".join(["forward_result", match_key, stat_key, scope, period, line_value, direction])


def _build_lookup(rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        for field_name in key_fields:
            value = row.get(field_name)
            if isinstance(value, str) and value.strip() and value not in lookup:
                lookup[value] = row
    return lookup


def _merge_by_key(
    *,
    base_rows: list[dict[str, Any]],
    overlay_rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in base_rows + overlay_rows:
        key = None
        for field_name in key_fields:
            value = row.get(field_name)
            if isinstance(value, str) and value.strip():
                key = value
                break
        if key is None:
            key = _result_loop_key(row)
        merged[key] = row
    return list(merged.values())


def _result_status(
    *,
    settlement_status: str,
    event_started: bool,
    actual_source_status: str | None,
) -> tuple[str, str]:
    if settlement_status == "settled":
        return "settled", "settled"
    if settlement_status == "pending_result":
        return ("pending", actual_source_status or "missing_match_result_source") if event_started else ("open", "match-not-started")
    if settlement_status == "missing_actual":
        return "unresolved", actual_source_status or "missing_actual_source_row"
    if settlement_status == "rule_error":
        return "unresolved", "rule_error"
    if settlement_status == "missing_settlement_record":
        return ("pending", "settlement_not_run") if event_started else ("open", "match-not-started")
    return "unresolved", settlement_status or "unknown"


def load_forward_bet_docs(database: Any) -> list[dict[str, Any]]:
    return list(database[FORWARD_BETS].find({}, projection={"_id": 0}))


def load_clv_tracking_docs(database: Any) -> list[dict[str, Any]]:
    docs = list(database[CLV_TRACKING].find({}, projection={"_id": 0}))
    return [
        row
        for row in docs
        if row.get("tracking_source") == FORWARD_BETS or row.get("prediction_key") is not None
    ]


def load_forward_settled_docs(database: Any) -> list[dict[str, Any]]:
    docs = list(database[SETTLED_BETS].find({}, projection={"_id": 0}))
    return [
        row
        for row in docs
        if row.get("selection_source") == FORWARD_BET_SELECTION_SOURCE or row.get("prediction_key") is not None
    ]


def build_forward_result_docs(
    *,
    forward_bet_docs: list[dict[str, Any]],
    clv_tracking_docs: list[dict[str, Any]],
    settled_bet_docs: list[dict[str, Any]],
    refreshed_at: datetime,
) -> list[dict[str, Any]]:
    clv_lookup = _build_lookup(clv_tracking_docs, ("clv_key", "prediction_key", "selection_key", "tracking_key"))
    settlement_lookup = _build_lookup(settled_bet_docs, ("prediction_key", "selection_key", "tracking_key", "settlement_key"))
    docs: list[dict[str, Any]] = []

    for row in forward_bet_docs:
        result_loop_key = _result_loop_key(row)
        timing = evaluate_forward_timing(row)
        match_start_time = timing["match_start_time"]
        clv_row = None
        for field_name in ("prediction_key", "selection_key", "tracking_key"):
            value = row.get(field_name)
            if isinstance(value, str) and value.strip():
                clv_row = clv_lookup.get(value)
                if clv_row is not None:
                    break
        settled_row = None
        for field_name in ("prediction_key", "selection_key", "tracking_key"):
            value = row.get(field_name)
            if isinstance(value, str) and value.strip():
                settled_row = settlement_lookup.get(value)
                if settled_row is not None:
                    break

        clv_status = str(clv_row.get("clv_status") or "missing_clv_tracking_record") if clv_row else "missing_clv_tracking_record"
        settlement_status = (
            str(settled_row.get("settlement_status") or "missing_settlement_record")
            if settled_row
            else "missing_settlement_record"
        )
        timing_status = str(timing["timing_status"])
        odds_captured_after_start = timing_status in {
            "invalid_after_start",
            "snapshot_at_or_after_match_start",
        }
        event_started = match_start_time is not None and refreshed_at >= match_start_time
        result_loop_status, status_reason = _result_status(
            settlement_status=settlement_status,
            event_started=event_started,
            actual_source_status=str(settled_row.get("actual_source_status") or "") if settled_row else None,
        )
        if not timing["valid_for_performance"]:
            result_loop_status = "excluded"
            status_reason = timing_status

        tracked_closing_odds = _to_float(clv_row.get("closing_odds")) if clv_row else None
        docs.append(
            {
                "result_loop_key": result_loop_key,
                "prediction_key": row.get("prediction_key"),
                "parent_prediction_key": row.get("parent_prediction_key"),
                "analysis_key": row.get("analysis_key"),
                "run_id": row.get("run_id"),
                "export_mode": row.get("export_mode"),
                "prediction_type": row.get("prediction_type"),
                "model_id": row.get("model_id"),
                "model_status": row.get("model_status"),
                "selection_policy_id": row.get("selection_policy_id"),
                "selection_policy_status": row.get(
                    "selection_policy_status"
                ),
                "selection_policy_registry_id": row.get(
                    "selection_policy_registry_id"
                ),
                "selection_family": forward_selection_family(row),
                "canonical_exposure_key": row.get(
                    "canonical_exposure_key"
                ) or row.get("exposure_key"),
                "canonical_evaluation_key": row.get(
                    "canonical_evaluation_key"
                ),
                "selection_granularity": row.get(
                    "selection_granularity"
                ),
                "snapshot_key": row.get("snapshot_key"),
                "snapshot_label": row.get("snapshot_label"),
                "snapshot_type": row.get("snapshot_type"),
                "selection_key": row.get("selection_key"),
                "tracking_key": row.get("tracking_key"),
                "match_key": row.get("match_key"),
                "source_match_id": row.get("source_match_id"),
                "offer_key": row.get("offer_key"),
                "home_team_name": row.get("home_team_name"),
                "away_team_name": row.get("away_team_name"),
                "league_name": row.get("league_name"),
                "headline": row.get("headline"),
                "stat_key": row.get("stat_key"),
                "period": row.get("period"),
                "scope": row.get("scope"),
                "direction": row.get("direction"),
                "line_value": row.get("line_value"),
                "predicted_win_probability": row.get(
                    "predicted_win_probability"
                ),
                "expected_roi_units": row.get("expected_roi_units"),
                "saved_odds": _to_float(row.get("saved_odds")),
                "saved_at": row.get("odds_snapshot_time")
                or row.get("saved_at"),
                "odds_snapshot_time": row.get("odds_snapshot_time"),
                "prediction_created_at": row.get(
                    "prediction_created_at"
                ),
                "match_start_time": row.get("match_start_time"),
                "event_started": event_started,
                "timing_contract": timing["timing_contract"],
                "timing_status": timing_status,
                "odds_captured_after_start": odds_captured_after_start,
                "invalid_for_model": not timing["valid_for_performance"]
                or clv_status == "invalid_snapshot_timing",
                "valid_for_performance": timing[
                    "valid_for_performance"
                ],
                "clv_key": clv_row.get("clv_key") if clv_row else None,
                "tracking_source": clv_row.get("tracking_source") if clv_row else row.get("tracking_source"),
                "closing_key": clv_row.get("closing_key") if clv_row else None,
                "opening_snapshot_label": clv_row.get("opening_snapshot_label") if clv_row else None,
                "opening_snapshot_time": clv_row.get("opening_snapshot_time") if clv_row else None,
                "opening_odds": _to_float(clv_row.get("opening_odds")) if clv_row else None,
                "latest_snapshot_label": clv_row.get("latest_snapshot_label") if clv_row else None,
                "latest_snapshot_time": clv_row.get("latest_snapshot_time") if clv_row else None,
                "latest_observed_odds": _to_float(clv_row.get("latest_observed_odds")) if clv_row else None,
                "closing_snapshot_label": clv_row.get("closing_snapshot_label") if clv_row else None,
                "closing_snapshot_time": clv_row.get("closing_snapshot_time") if clv_row else None,
                "closing_quality": clv_row.get("closing_quality") if clv_row else None,
                "closing_age_minutes": clv_row.get("closing_age_minutes") if clv_row else None,
                "official_clv": clv_row.get("official_clv") if clv_row else False,
                "clv_basis": clv_row.get("clv_basis") if clv_row else None,
                "closing_odds": tracked_closing_odds,
                "clv_pct": _to_float(clv_row.get("clv_pct")) if clv_row else None,
                "implied_edge_delta": _to_float(clv_row.get("implied_edge_delta")) if clv_row else None,
                "beat_closing_line": clv_row.get("beat_closing_line") if clv_row else None,
                "clv_status": clv_status,
                "closing_line_available": tracked_closing_odds is not None,
                "prematch_observation_count": int(clv_row.get("prematch_observation_count") or 0) if clv_row else 0,
                "price_history": list(clv_row.get("price_history") or []) if clv_row else [],
                "settlement_key": settled_row.get("settlement_key") if settled_row else None,
                "selection_source": settled_row.get("selection_source") if settled_row else FORWARD_BET_SELECTION_SOURCE,
                "source_collection": settled_row.get("source_collection") if settled_row else FORWARD_BETS,
                "settlement_status": settlement_status,
                "actual_value": settled_row.get("actual_value") if settled_row else None,
                "home_value": settled_row.get("home_value") if settled_row else None,
                "away_value": settled_row.get("away_value") if settled_row else None,
                "settlement_result": (
                    settled_row.get("settlement_result")
                    if settled_row and timing["valid_for_performance"]
                    else None
                ),
                "win": (
                    settled_row.get("win")
                    if settled_row and timing["valid_for_performance"]
                    else None
                ),
                "roi_units": (
                    _to_float(settled_row.get("roi_units"))
                    if settled_row and timing["valid_for_performance"]
                    else None
                ),
                "pnl_units": (
                    _to_float(settled_row.get("pnl_units"))
                    if settled_row and timing["valid_for_performance"]
                    else None
                ),
                "stake_units": _to_float(settled_row.get("stake_units") if settled_row else row.get("stake_units")) or 1.0,
                "actual_source": settled_row.get("actual_source") if settled_row else None,
                "actual_source_status": settled_row.get("actual_source_status") if settled_row else None,
                "settled_at": settled_row.get("settled_at") if settled_row else None,
                "result_loop_status": result_loop_status,
                "status_reason": status_reason,
                "refreshed_at": refreshed_at,
            }
        )
    return sorted(docs, key=lambda row: (str(row.get("match_start_time") or ""), str(row.get("result_loop_key") or "")))


def run_forward_result_refresh(
    *,
    forward_bet_docs: list[dict[str, Any]] | None = None,
    clv_tracking_docs: list[dict[str, Any]] | None = None,
    closing_line_docs: list[dict[str, Any]] | None = None,
    settled_bet_docs: list[dict[str, Any]] | None = None,
    match_stats_canonical: list[dict[str, Any]] | None = None,
    match_results_canonical: list[dict[str, Any]] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    refreshed_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = refreshed_at or utc_now()
    tracked_rows = forward_bet_docs
    if tracked_rows is None:
        tracked_rows = load_forward_bet_docs(database) if database is not None else []
    tracked_rows, exposure_audit = canonicalize_forward_bet_docs(tracked_rows)

    clv_rows = clv_tracking_docs
    if clv_rows is None:
        clv_rows = load_clv_tracking_docs(database) if database is not None else []
    ephemeral_clv_rows: list[dict[str, Any]] = []
    if len(clv_rows) < len(tracked_rows):
        closing_lines = closing_line_docs
        if closing_lines is None:
            closing_lines = load_closing_line_docs(database) if database is not None else []
        if closing_lines:
            ephemeral_clv_rows = build_clv_tracking_docs(
                tracked_bet_docs=tracked_rows,
                closing_line_docs=closing_lines,
                refreshed_at=timestamp,
            )
            clv_rows = _merge_by_key(
                base_rows=ephemeral_clv_rows,
                overlay_rows=clv_rows,
                key_fields=("clv_key", "prediction_key", "selection_key", "tracking_key"),
            )

    settled_rows = settled_bet_docs
    if settled_rows is None:
        settled_rows = load_forward_settled_docs(database) if database is not None else []
    ephemeral_settled_rows: list[dict[str, Any]] = []
    if len(settled_rows) < len(tracked_rows):
        stats = match_stats_canonical
        results = match_results_canonical
        if (stats is None or results is None) and database is not None:
            loaded_stats, loaded_results = load_match_stats_docs(
                database,
                [str(row.get("match_key")) for row in tracked_rows if row.get("match_key") is not None],
            )
            stats = loaded_stats if stats is None else stats
            results = loaded_results if results is None else results
        if stats is not None and results is not None:
            ephemeral_settled_rows = build_settled_docs(
                selection_docs=tracked_rows,
                match_stats_canonical=stats,
                match_results_canonical=results,
                selection_source=FORWARD_BET_SELECTION_SOURCE,
                settled_at=timestamp,
            )
            settled_rows = _merge_by_key(
                base_rows=ephemeral_settled_rows,
                overlay_rows=settled_rows,
                key_fields=("settlement_key", "prediction_key", "selection_key", "tracking_key"),
            )

    result_docs = build_forward_result_docs(
        forward_bet_docs=tracked_rows,
        clv_tracking_docs=clv_rows,
        settled_bet_docs=settled_rows,
        refreshed_at=timestamp,
    )
    report_date = timestamp.date().isoformat()
    parity_rows = build_forward_result_parity_rows(
        forward_bet_docs=tracked_rows,
        result_docs=result_docs,
        report_date=report_date,
    )
    audit_rows = build_forward_result_audit_rows(
        result_docs=result_docs,
        report_date=report_date,
    )
    health_rows = build_forward_result_health_rows(
        result_docs=result_docs,
        report_date=report_date,
    )
    settled_rows_only = [row for row in result_docs if row.get("result_loop_status") == "settled"]
    clv_tracked_rows = [
        row
        for row in result_docs
        if row.get("clv_status") == "tracked"
        and (
            row.get("official_clv") is True
            or row.get("closing_snapshot_label") == "T_MINUS_10M"
            or row.get("closing_quality") == "t10"
        )
    ]
    clv_fallback_rows = [
        row for row in result_docs if row.get("clv_status") == "tracked_fallback_t30"
    ]
    pnl_units = round(sum(_to_float(row.get("pnl_units")) or 0.0 for row in settled_rows_only), 2)
    performance_rows = [
        row for row in result_docs if row.get("valid_for_performance")
    ]
    total_stake_units = sum(
        _to_float(row.get("stake_units")) or 1.0
        for row in performance_rows
    )
    settled_stake_units = sum(_to_float(row.get("stake_units")) or 1.0 for row in settled_rows_only)
    wins = sum(1 for row in settled_rows_only if row.get("settlement_result") == "win")
    summary: dict[str, Any] = {
        "job": "refresh_forward_results",
        "refreshed_at": timestamp.isoformat(),
        "forward_bets": len(tracked_rows),
        "forward_exposure_audit": exposure_audit,
        "clv_tracking_rows": len(clv_rows),
        "settled_bets": len(settled_rows),
        "forward_results": len(result_docs),
        "ephemeral_clv_rows": len(ephemeral_clv_rows),
        "ephemeral_settled_rows": len(ephemeral_settled_rows),
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
            status: sum(1 for row in result_docs if row.get("result_loop_status") == status)
            for status in sorted({row.get("result_loop_status") for row in result_docs})
        },
        "clv_status_counts": {
            status: sum(1 for row in result_docs if row.get("clv_status") == status)
            for status in sorted({row.get("clv_status") for row in result_docs})
        },
        "settlement_status_counts": {
            status: sum(1 for row in result_docs if row.get("settlement_status") == status)
            for status in sorted({row.get("settlement_status") for row in result_docs})
        },
        "timing_status_counts": {
            status: sum(1 for row in result_docs if row.get("timing_status") == status)
            for status in sorted({row.get("timing_status") for row in result_docs})
        },
        "beat_close_count": sum(1 for row in clv_tracked_rows if row.get("beat_closing_line") is True),
        "fallback_t30_clv_count": len(clv_fallback_rows),
        "avg_clv_pct": round(sum(_to_float(row.get("clv_pct")) or 0.0 for row in clv_tracked_rows) / len(clv_tracked_rows), 2)
        if clv_tracked_rows
        else None,
        "avg_fallback_t30_clv_pct": round(
            sum(_to_float(row.get("clv_pct")) or 0.0 for row in clv_fallback_rows)
            / len(clv_fallback_rows),
            2,
        )
        if clv_fallback_rows
        else None,
        "settled_count": len(settled_rows_only),
        "win_rate_pct": round((wins / len(settled_rows_only)) * 100) if settled_rows_only else 0,
        "pnl_units": pnl_units,
        "roi_pct_all_tracked": round((pnl_units / total_stake_units) * 100, 1) if total_stake_units else 0.0,
        "roi_pct_settled_only": round((pnl_units / settled_stake_units) * 100, 1) if settled_stake_units else 0.0,
        "result_docs": result_docs,
    }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="refresh_forward_results",
        source_workflow="result-loop-bets",
        target_window={"forward_bet_count": len(tracked_rows), "refreshed_at": timestamp.isoformat()},
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {key: value for key, value in summary.items() if key != "result_docs"}
    try:
        persistence_metrics = persist_forward_result_records(
            database,
            result_docs=result_docs,
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
