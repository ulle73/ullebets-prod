from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.forward_exposures import canonicalize_forward_bet_docs
from ullebets_v2.forward_timing import evaluate_forward_timing
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.settlement.common import (
    build_result_lookup,
    build_stats_lookup,
    build_stat_scope_lookup,
    resolve_actual_context,
)
from ullebets_v2.settlement.persistence import persist_settlement_records
from ullebets_v2.settlement.reports import (
    build_settlement_audit_rows,
    build_settlement_health_rows,
    build_settlement_parity_rows,
)
from ullebets_v2.settlement.rules import settle_line
from ullebets_v2.storage.collections import (
    FORMULA_OBSERVATIONS,
    FORWARD_BETS,
    MODEL_SNAPSHOTS,
)

MODEL_SNAPSHOT_SELECTION_SOURCE = "model_snapshot"
FORWARD_BET_SELECTION_SOURCE = "forward_bet"
FORMULA_OBSERVATION_SELECTION_SOURCE = "formula_observation"

SETTLEMENT_CONTRACTS = {
    MODEL_SNAPSHOT_SELECTION_SOURCE: {
        "job_name": "settle_model_snapshots",
        "v2_job": "settle_model_snapshots.py",
        "summary_input_key": "model_snapshots",
        "count_key": "snapshot_count",
        "audit_type": "model_snapshot_settlement",
        "old_inputs": ["unibet-backtest lines", "teamstats results"],
        "old_outputs": ["corrected lines.actual / lines.win"],
        "smoke_test": "dry-run against synthetic and replay-derived settled rows",
        "no_target_smoke_test": "dry-run with zero model snapshots",
        "parity_proof": "apply the same over/under/push settlement rules documented in the legacy correct-unibet-backtest and result-loop flows",
        "no_target_parity_proof": "verify empty settlement windows are handled as a clean no-op",
        "no_target_finding": "no_model_snapshots_to_settle",
        "no_target_summary": "No model snapshot rows required settlement.",
        "ok_summary": "Model snapshot settlement ran with canonical over/under/push rules.",
        "warn_summary": "Model snapshot settlement encountered rule errors.",
    },
    FORWARD_BET_SELECTION_SOURCE: {
        "job_name": "settle_forward_bets",
        "v2_job": "settle_forward_bets.py",
        "summary_input_key": "forward_bets",
        "count_key": "forward_bet_count",
        "audit_type": "forward_bet_settlement",
        "old_inputs": ["forward_bets rows", "canonical match stats/results"],
        "old_outputs": ["settled forward bets"],
        "smoke_test": "dry-run against synthetic and stored forward bet rows",
        "no_target_smoke_test": "dry-run with zero forward bets",
        "parity_proof": "apply the same canonical over/under/push settlement rules used for model snapshots so forward testing cannot drift from backtest grading",
        "no_target_parity_proof": "verify empty forward settlement windows are handled as a clean no-op",
        "no_target_finding": "no_forward_bets_to_settle",
        "no_target_summary": "No forward bet rows required settlement.",
        "ok_summary": "Forward bet settlement ran with the same canonical over/under/push rules as model snapshots.",
        "warn_summary": "Forward bet settlement encountered rule errors.",
    },
}


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _selection_odds(row: dict[str, Any]) -> Any:
    selected_odds = row.get("selected_odds")
    if selected_odds is not None:
        return selected_odds
    return row.get("saved_odds")


def _selection_stake(row: dict[str, Any]) -> Any:
    return row.get("stake_units") if row.get("stake_units") is not None else 1


def _selection_settlement_key(row: dict[str, Any], *, selection_source: str) -> str:
    if selection_source == FORMULA_OBSERVATION_SELECTION_SOURCE:
        value = row.get("observation_key") or row.get("selection_key")
        if value:
            return str(value)
    if selection_source == FORWARD_BET_SELECTION_SOURCE:
        for field_name in ("prediction_key", "selection_key", "tracking_key", "offer_key"):
            value = row.get(field_name)
            if value:
                return str(value)
    for field_name in ("selection_key", "prediction_key", "tracking_key", "offer_key"):
        value = row.get(field_name)
        if value:
            return str(value)
    match_key = str(row.get("match_key") or "missing-match")
    stat_key = str(row.get("stat_key") or "missing-stat")
    period = str(row.get("period") or "missing-period")
    scope = str(row.get("scope") or "missing-scope")
    line_value = str(row.get("line_value") or "missing-line")
    direction = str(row.get("direction") or "over")
    return "|".join([selection_source, match_key, stat_key, scope, period, line_value, direction])


def _selection_source_collection(selection_source: str) -> str:
    if selection_source == FORWARD_BET_SELECTION_SOURCE:
        return FORWARD_BETS
    if selection_source == FORMULA_OBSERVATION_SELECTION_SOURCE:
        return FORMULA_OBSERVATIONS
    return MODEL_SNAPSHOTS


def build_settled_docs(
    *,
    selection_docs: list[dict[str, Any]],
    match_stats_canonical: list[dict[str, Any]],
    match_results_canonical: list[dict[str, Any]],
    selection_source: str,
    settled_at: datetime,
) -> list[dict[str, Any]]:
    result_lookup = build_result_lookup(match_results_canonical)
    stats_lookup = build_stats_lookup(match_stats_canonical)
    stat_scope_lookup = build_stat_scope_lookup(match_stats_canonical)
    settled_docs: list[dict[str, Any]] = []
    for selection in selection_docs:
        normalized_selected_odds = _selection_odds(selection)
        timing = (
            evaluate_forward_timing(selection)
            if selection_source in {
                FORWARD_BET_SELECTION_SOURCE,
                FORMULA_OBSERVATION_SELECTION_SOURCE,
            }
            else None
        )
        base_doc = {
            **selection,
            "selection_source": selection_source,
            "source_collection": _selection_source_collection(selection_source),
            "settlement_key": _selection_settlement_key(selection, selection_source=selection_source),
            "selected_odds": normalized_selected_odds,
        }
        if timing is not None:
            base_doc.update(
                {
                    "timing_contract": timing["timing_contract"],
                    "timing_status": timing["timing_status"],
                    "odds_observation_time": timing["observation_time"],
                    "valid_for_performance": timing["valid_for_performance"],
                    "invalid_for_model": not timing["valid_for_performance"],
                    "valid_for_forward_evaluation": timing[
                        "valid_for_performance"
                    ],
                }
            )
        actual_context = resolve_actual_context(
            row=selection,
            result_lookup=result_lookup,
            stats_lookup=stats_lookup,
            stat_scope_lookup=stat_scope_lookup,
        )
        if timing is not None and not timing["valid_for_performance"]:
            settled_docs.append(
                {
                    **base_doc,
                    "settlement_status": "invalid_timing",
                    "settlement_result": None,
                    "actual_value": actual_context["actual_value"],
                    "home_value": actual_context["home_value"],
                    "away_value": actual_context["away_value"],
                    "win": None,
                    "roi_units": None,
                    "pnl_units": None,
                    "stake_units": _selection_stake(selection),
                    "actual_source": actual_context["actual_source"],
                    "actual_source_status": actual_context[
                        "actual_source_status"
                    ],
                    "settled_at": settled_at,
                }
            )
            continue
        if actual_context["actual_resolution_status"] != "resolved":
            settled_docs.append(
                {
                    **base_doc,
                    "settlement_status": actual_context["actual_resolution_status"],
                    "settlement_result": None,
                    "actual_value": actual_context["actual_value"],
                    "home_value": actual_context["home_value"],
                    "away_value": actual_context["away_value"],
                    "win": None,
                    "roi_units": None,
                    "pnl_units": None,
                    "stake_units": _selection_stake(selection),
                    "actual_source": actual_context["actual_source"],
                    "actual_source_status": actual_context["actual_source_status"],
                    "settled_at": settled_at,
                }
            )
            continue

        settlement = settle_line(
            actual_value=actual_context["actual_value"],
            line_value=selection.get("line_value"),
            direction=str(selection.get("direction") or "over"),
            odds_decimal=normalized_selected_odds,
            stake_units=_selection_stake(selection),
        )
        if settlement is None:
            settled_docs.append(
                {
                    **base_doc,
                    "settlement_status": "rule_error",
                    "settlement_result": None,
                    "actual_value": actual_context["actual_value"],
                    "home_value": actual_context["home_value"],
                    "away_value": actual_context["away_value"],
                    "win": None,
                    "roi_units": None,
                    "pnl_units": None,
                    "stake_units": _selection_stake(selection),
                    "actual_source": actual_context["actual_source"],
                    "actual_source_status": "rule_error",
                    "settled_at": settled_at,
                }
            )
            continue

        settled_docs.append(
            {
                **base_doc,
                "settlement_status": "settled",
                "settlement_result": settlement["settlement_result"],
                "actual_value": actual_context["actual_value"],
                "home_value": actual_context["home_value"],
                "away_value": actual_context["away_value"],
                "win": settlement["win"],
                "roi_units": settlement["roi_units"],
                "pnl_units": settlement["pnl_units"],
                "stake_units": settlement["stake_units"],
                "actual_source": actual_context["actual_source"],
                "actual_source_status": actual_context["actual_source_status"],
                "settled_at": settled_at,
            }
        )
    return settled_docs


def load_model_snapshot_docs(database: Any) -> list[dict[str, Any]]:
    return list(database[MODEL_SNAPSHOTS].find({}, projection={"_id": 0}))


def load_forward_bet_docs(database: Any) -> list[dict[str, Any]]:
    return list(database[FORWARD_BETS].find({}, projection={"_id": 0}))


def load_match_stats_docs(database: Any, match_keys: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not match_keys:
        return [], []
    query = {"match_key": {"$in": match_keys}}
    match_stats = list(database["match_stats_canonical"].find(query, projection={"_id": 0}))
    match_results = list(database["match_results_canonical"].find(query, projection={"_id": 0}))
    return match_stats, match_results


def _load_selection_docs(database: Any, *, selection_source: str) -> list[dict[str, Any]]:
    if selection_source == FORWARD_BET_SELECTION_SOURCE:
        return load_forward_bet_docs(database)
    return load_model_snapshot_docs(database)


def _run_selection_settlement(
    *,
    source_workflow: str,
    selection_source: str,
    selection_docs: list[dict[str, Any]] | None = None,
    match_stats_canonical: list[dict[str, Any]] | None = None,
    match_results_canonical: list[dict[str, Any]] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    settled_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = settled_at or utc_now()
    contract = SETTLEMENT_CONTRACTS[selection_source]
    selections = selection_docs
    stats = match_stats_canonical
    results = match_results_canonical
    if selections is None:
        if database is None:
            selections = []
        else:
            selections = _load_selection_docs(database, selection_source=selection_source)
    exposure_audit: dict[str, int] | None = None
    if selection_source == FORWARD_BET_SELECTION_SOURCE:
        selections, exposure_audit = canonicalize_forward_bet_docs(selections)
    if stats is None or results is None:
        if database is None:
            stats = stats or []
            results = results or []
        else:
            loaded_stats, loaded_results = load_match_stats_docs(
                database,
                [str(row["match_key"]) for row in selections if row.get("match_key") is not None],
            )
            stats = loaded_stats if stats is None else stats
            results = loaded_results if results is None else results

    settled_docs = build_settled_docs(
        selection_docs=selections,
        match_stats_canonical=stats or [],
        match_results_canonical=results or [],
        selection_source=selection_source,
        settled_at=timestamp,
    )
    report_date = timestamp.date().isoformat()
    parity_rows = build_settlement_parity_rows(
        source_workflow=source_workflow,
        model_snapshot_docs=selections,
        settled_docs=settled_docs,
        report_date=report_date,
        count_key=contract["count_key"],
        audit_type_label="forward bet" if selection_source == FORWARD_BET_SELECTION_SOURCE else "model snapshot",
        plural_label="forward bets" if selection_source == FORWARD_BET_SELECTION_SOURCE else "model snapshots",
        old_inputs=contract["old_inputs"],
        old_outputs=contract["old_outputs"],
        v2_job=contract["v2_job"],
        smoke_test=contract["smoke_test"],
        no_target_smoke_test=contract["no_target_smoke_test"],
        parity_proof=contract["parity_proof"],
        no_target_parity_proof=contract["no_target_parity_proof"],
    )
    audit_rows = build_settlement_audit_rows(
        source_workflow=source_workflow,
        settled_docs=settled_docs,
        report_date=report_date,
        count_key=contract["count_key"],
        audit_type=contract["audit_type"],
        no_target_finding=contract["no_target_finding"],
    )
    health_rows = build_settlement_health_rows(
        settled_docs=settled_docs,
        report_date=report_date,
        count_key=contract["count_key"],
        job_name=contract["job_name"],
        no_target_summary=contract["no_target_summary"],
        ok_summary=contract["ok_summary"],
        warn_summary=contract["warn_summary"],
    )

    summary: dict[str, Any] = {
        "job": contract["job_name"],
        "selection_source": selection_source,
        "settled_at": timestamp.isoformat(),
        contract["summary_input_key"]: len(selections),
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
    if exposure_audit is not None:
        summary["forward_exposure_audit"] = exposure_audit
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name=contract["job_name"],
        source_workflow=source_workflow,
        target_window={
            contract["summary_input_key"]: len(selections),
            "selection_source": selection_source,
            "settled_at": timestamp.isoformat(),
        },
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
    return _run_selection_settlement(
        source_workflow=source_workflow,
        selection_source=MODEL_SNAPSHOT_SELECTION_SOURCE,
        selection_docs=model_snapshot_docs,
        match_stats_canonical=match_stats_canonical,
        match_results_canonical=match_results_canonical,
        database=database,
        dry_run=dry_run,
        settled_at=settled_at,
    )


def run_forward_bet_settlement(
    *,
    source_workflow: str,
    forward_bet_docs: list[dict[str, Any]] | None = None,
    match_stats_canonical: list[dict[str, Any]] | None = None,
    match_results_canonical: list[dict[str, Any]] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    settled_at: datetime | None = None,
) -> dict[str, Any]:
    return _run_selection_settlement(
        source_workflow=source_workflow,
        selection_source=FORWARD_BET_SELECTION_SOURCE,
        selection_docs=forward_bet_docs,
        match_stats_canonical=match_stats_canonical,
        match_results_canonical=match_results_canonical,
        database=database,
        dry_run=dry_run,
        settled_at=settled_at,
    )
