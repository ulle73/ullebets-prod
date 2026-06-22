from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.analysis.service import run_auto_analysis_pipeline
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.prediction_exports.combos import build_combos
from ullebets_v2.prediction_exports.persistence import persist_prediction_export_records
from ullebets_v2.prediction_exports.reports import (
    build_prediction_export_audit_rows,
    build_prediction_export_health_rows,
    build_prediction_export_parity_rows,
)
from ullebets_v2.support.schemas import stable_json_hash


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _candidate_sort_key(row: dict[str, Any]) -> tuple[float, float]:
    return float(row.get("strategy_score") or 0.0), float(row.get("primaryEv") or row.get("primary_ev") or 0.0)


def _source_candidates_for_mode(mode: str, analysis_candidate_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if mode == "combos":
        return [row for row in analysis_candidate_docs if row.get("passes_strategy_filters")]
    return [row for row in analysis_candidate_docs if row.get("is_best_bet_for_match")]


def _candidate_leg(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "selection_key": candidate.get("selection_key"),
        "match_key": candidate.get("match_key"),
        "source_match_id": candidate.get("source_match_id"),
        "offer_key": candidate.get("offer_key"),
        "home_team_name": candidate.get("homeTeamName"),
        "away_team_name": candidate.get("awayTeamName"),
        "league_name": candidate.get("leagueName"),
        "stat_key": candidate.get("bet", {}).get("statKey"),
        "scope": candidate.get("bet", {}).get("scope"),
        "period": candidate.get("bet", {}).get("period"),
        "direction": candidate.get("bet", {}).get("direction"),
        "line_value": candidate.get("bet", {}).get("line"),
        "selected_odds": candidate.get("bet", {}).get("odds"),
        "primary_ev": candidate.get("primaryEv"),
        "strategy_score": candidate.get("strategyScore"),
        "match_start_time": candidate.get("matchDate"),
        "headline": candidate.get("headline"),
    }


def _build_single_prediction_docs(
    *,
    export_mode: str,
    source_candidates: list[dict[str, Any]],
    analysis_run_doc: dict[str, Any],
    generated_at: datetime,
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for candidate in sorted(source_candidates, key=_candidate_sort_key, reverse=True):
        selection_key = candidate.get("selection_key")
        if not selection_key:
            continue
        leg = _candidate_leg(candidate)
        prediction_key = f"{analysis_run_doc['run_id']}|{export_mode}|{selection_key}"
        docs.append(
            {
                "prediction_key": prediction_key,
                "run_id": analysis_run_doc["run_id"],
                "run_key": analysis_run_doc.get("run_key"),
                "analysis_key": analysis_run_doc["run_id"],
                "export_mode": export_mode,
                "prediction_type": "single",
                "event_date": analysis_run_doc.get("date"),
                "strategy_id": analysis_run_doc.get("strategy_id"),
                "strategy_label": analysis_run_doc.get("strategy_label"),
                "source_workflow": analysis_run_doc.get("source_workflow"),
                "source_candidate_key": candidate.get("candidate_key"),
                "leg_count": 1,
                "combined_odds": leg.get("selected_odds"),
                "total_primary_ev": leg.get("primary_ev"),
                "headline": candidate.get("headline"),
                "home_team_name": candidate.get("homeTeamName"),
                "away_team_name": candidate.get("awayTeamName"),
                "league_name": candidate.get("leagueName"),
                "match_start_time": candidate.get("matchDate"),
                "legs": [leg],
                "generated_at": generated_at,
            }
        )
    return docs


def _build_combo_prediction_docs(
    *,
    export_mode: str,
    source_candidates: list[dict[str, Any]],
    analysis_run_doc: dict[str, Any],
    generated_at: datetime,
) -> list[dict[str, Any]]:
    lines = [
        {
            "selection_key": row.get("selection_key"),
            "match_key": row.get("match_key"),
            "selected_odds": row.get("bet", {}).get("odds"),
            "primary_ev": row.get("primaryEv"),
            "source_candidate_key": row.get("candidate_key"),
            "leg": _candidate_leg(row),
        }
        for row in source_candidates
        if row.get("selection_key")
    ]
    combos = build_combos(lines, legs=2, min_odds=1.8, max_odds=3.0, max_lines=100, max_combos=20)
    docs: list[dict[str, Any]] = []
    for combo in combos:
        combo_id = stable_json_hash([leg.get("selection_key") for leg in combo.get("legs", [])])
        prediction_key = f"{analysis_run_doc['run_id']}|{export_mode}|combo|{combo_id}"
        legs = [leg.get("leg") for leg in combo.get("legs", []) if isinstance(leg.get("leg"), dict)]
        if not legs:
            continue
        docs.append(
            {
                "prediction_key": prediction_key,
                "run_id": analysis_run_doc["run_id"],
                "run_key": analysis_run_doc.get("run_key"),
                "analysis_key": analysis_run_doc["run_id"],
                "export_mode": export_mode,
                "prediction_type": "combo",
                "event_date": analysis_run_doc.get("date"),
                "strategy_id": analysis_run_doc.get("strategy_id"),
                "strategy_label": analysis_run_doc.get("strategy_label"),
                "source_workflow": analysis_run_doc.get("source_workflow"),
                "leg_count": len(legs),
                "combined_odds": combo.get("combined_odds"),
                "total_primary_ev": combo.get("total_primary_ev"),
                "headline": " / ".join(str(leg.get("headline") or leg.get("selection_key")) for leg in legs),
                "home_team_name": None,
                "away_team_name": None,
                "league_name": None,
                "match_start_time": min((leg.get("match_start_time") for leg in legs if leg.get("match_start_time")), default=None),
                "legs": legs,
                "generated_at": generated_at,
            }
        )
    return docs


def build_prediction_export_docs(
    *,
    export_mode: str,
    source_candidates: list[dict[str, Any]],
    analysis_run_doc: dict[str, Any],
    generated_at: datetime,
) -> list[dict[str, Any]]:
    if export_mode == "combos":
        return _build_combo_prediction_docs(
            export_mode=export_mode,
            source_candidates=source_candidates,
            analysis_run_doc=analysis_run_doc,
            generated_at=generated_at,
        )
    return _build_single_prediction_docs(
        export_mode=export_mode,
        source_candidates=source_candidates,
        analysis_run_doc=analysis_run_doc,
        generated_at=generated_at,
    )


def build_forward_bet_docs(
    *,
    export_mode: str,
    prediction_export_docs: list[dict[str, Any]],
    generated_at: datetime,
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for export_doc in prediction_export_docs:
        for leg_index, leg in enumerate(export_doc.get("legs", []), start=1):
            prediction_key = (
                export_doc["prediction_key"]
                if export_doc.get("prediction_type") == "single"
                else f"{export_doc['prediction_key']}|leg{leg_index}"
            )
            docs.append(
                {
                    "prediction_key": prediction_key,
                    "parent_prediction_key": export_doc["prediction_key"],
                    "export_mode": export_mode,
                    "prediction_type": export_doc.get("prediction_type"),
                    "run_id": export_doc.get("run_id"),
                    "analysis_key": export_doc.get("analysis_key"),
                    "selection_key": leg.get("selection_key"),
                    "tracking_key": leg.get("selection_key"),
                    "match_key": leg.get("match_key"),
                    "source_match_id": leg.get("source_match_id"),
                    "offer_key": leg.get("offer_key"),
                    "home_team_name": leg.get("home_team_name"),
                    "away_team_name": leg.get("away_team_name"),
                    "league_name": leg.get("league_name"),
                    "stat_key": leg.get("stat_key"),
                    "scope": leg.get("scope"),
                    "period": leg.get("period"),
                    "direction": leg.get("direction"),
                    "line_value": leg.get("line_value"),
                    "saved_odds": leg.get("selected_odds"),
                    "primary_ev": leg.get("primary_ev"),
                    "strategy_score": leg.get("strategy_score"),
                    "headline": leg.get("headline"),
                    "saved_at": generated_at,
                    "match_start_time": leg.get("match_start_time"),
                    "invalid_for_model": False,
                    "leg_index": leg_index,
                    "leg_count": export_doc.get("leg_count"),
                }
            )
    return docs


def run_prediction_export_pipeline(
    *,
    export_mode: str,
    source_workflow: str,
    targets: list[dict[str, Any]] | None = None,
    support_docs: dict[str, Any] | None = None,
    analysis_run_doc: dict[str, Any] | None = None,
    analysis_candidate_docs: list[dict[str, Any]] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    strategy_id: str = "balanced",
    run_date: str | None = None,
    checkpoint_key: str | None = None,
    checkpoint_label: str | None = None,
    checkpoint_target_days: int | None = None,
    snapshot_mode: str = "forward",
    snapshot_label: str = "CURRENT",
    analysis_oracle: Any | None = None,
    transport: Any | None = None,
    odds_oracle: Any | None = None,
    model_oracle: Any | None = None,
    fetched_at: datetime | None = None,
) -> dict[str, Any]:
    generated_at = fetched_at or utc_now()
    analysis_summary: dict[str, Any] | None = None
    if analysis_run_doc is None or analysis_candidate_docs is None:
        if targets is None or support_docs is None:
            raise RuntimeError("targets and support_docs are required when analysis docs are not supplied.")
        analysis_summary = run_auto_analysis_pipeline(
            targets=targets,
            support_docs=support_docs,
            source_workflow=source_workflow,
            strategy_id=strategy_id,
            run_date=run_date,
            checkpoint_key=checkpoint_key,
            checkpoint_label=checkpoint_label,
            checkpoint_target_days=checkpoint_target_days,
            snapshot_mode=snapshot_mode,
            snapshot_label=snapshot_label,
            analysis_oracle=analysis_oracle,
            database=database if not dry_run else None,
            dry_run=dry_run,
            transport=transport,
            odds_oracle=odds_oracle,
            model_oracle=model_oracle,
            fetched_at=generated_at,
        )
        analysis_run_doc = analysis_summary.get("analysis_run")
        analysis_candidate_docs = analysis_summary.get("analysis_candidate_docs", [])

    source_candidates = _source_candidates_for_mode(export_mode, analysis_candidate_docs or [])
    prediction_export_docs = build_prediction_export_docs(
        export_mode=export_mode,
        source_candidates=source_candidates,
        analysis_run_doc=analysis_run_doc or {},
        generated_at=generated_at,
    )
    forward_bet_docs = build_forward_bet_docs(
        export_mode=export_mode,
        prediction_export_docs=prediction_export_docs,
        generated_at=generated_at,
    )
    report_date = generated_at.date().isoformat()
    parity_rows = build_prediction_export_parity_rows(
        source_workflow=source_workflow,
        export_mode=export_mode,
        source_candidates=source_candidates,
        prediction_export_docs=prediction_export_docs,
        forward_bet_docs=forward_bet_docs,
        report_date=report_date,
    )
    audit_rows = build_prediction_export_audit_rows(
        source_workflow=source_workflow,
        export_mode=export_mode,
        source_candidates=source_candidates,
        prediction_export_docs=prediction_export_docs,
        forward_bet_docs=forward_bet_docs,
        report_date=report_date,
    )
    health_rows = build_prediction_export_health_rows(
        export_mode=export_mode,
        prediction_export_docs=prediction_export_docs,
        forward_bet_docs=forward_bet_docs,
        report_date=report_date,
    )
    summary: dict[str, Any] = {
        "job": "build_ai_bet_exports",
        "generated_at": generated_at.isoformat(),
        "export_mode": export_mode,
        "analysis_candidates": len(analysis_candidate_docs or []),
        "source_candidates": len(source_candidates),
        "prediction_exports": len(prediction_export_docs),
        "forward_bets": len(forward_bet_docs),
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
        "analysis_run": analysis_run_doc,
        "prediction_export_docs": prediction_export_docs,
        "forward_bet_docs": forward_bet_docs,
    }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="build_ai_bet_exports",
        source_workflow=source_workflow,
        target_window={
            "export_mode": export_mode,
            "run_id": analysis_run_doc.get("run_id") if analysis_run_doc else None,
        },
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {
        key: value
        for key, value in summary.items()
        if key not in {"analysis_run", "prediction_export_docs", "forward_bet_docs"}
    }
    try:
        persistence_metrics = persist_prediction_export_records(
            database,
            prediction_export_docs=prediction_export_docs,
            forward_bet_docs=forward_bet_docs,
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
