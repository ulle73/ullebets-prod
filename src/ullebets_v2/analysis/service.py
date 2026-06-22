from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.analysis.persistence import persist_analysis_records
from ullebets_v2.analysis.reports import (
    build_analysis_audit_rows,
    build_analysis_health_rows,
    build_analysis_parity_rows,
)
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.model_snapshots.persistence import persist_model_snapshot_records
from ullebets_v2.model_snapshots.service import run_model_snapshot_build
from ullebets_v2.odds.persistence import persist_odds_data_records


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def build_analysis_run_key(*, date: str, strategy_id: str = "balanced", checkpoint_key: str | None = None) -> str:
    return f"{date}:{strategy_id}:{checkpoint_key or 'manual'}"


def _coerce_iso_date(value: Any, fallback: datetime) -> str:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, datetime):
        return value.date().isoformat()
    return fallback.date().isoformat()


def _select_valid_model_snapshots(model_snapshot_docs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    valid = [row for row in model_snapshot_docs if not row.get("invalid_for_model")]
    invalid_count = len(model_snapshot_docs) - len(valid)
    return valid, invalid_count


def _build_analysis_candidate_docs(
    *,
    oracle_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for row in oracle_candidates:
        selection_key = row.get("selectionKey")
        run_id = row.get("runId")
        if not selection_key or not run_id:
            continue
        docs.append(
            {
                **row,
                "candidate_key": f"{run_id}|{selection_key}",
                "selection_key": selection_key,
                "run_id": run_id,
                "run_key": row.get("runKey"),
                "match_key": row.get("matchKey"),
                "source_match_id": row.get("sourceMatchId"),
                "offer_key": row.get("offerKey"),
                "strategy_id": row.get("strategyId"),
                "strategy_label": row.get("strategyLabel"),
                "passes_strategy_filters": bool(row.get("passesStrategyFilters")),
                "is_best_bet_for_match": bool(row.get("isBestBetForMatch")),
                "proof_ready": bool((row.get("proof") or {}).get("historicalReady")),
                "updated_at": row.get("updatedAt"),
            }
        )
    return docs


def _build_analysis_run_doc(
    *,
    oracle_run: dict[str, Any],
    source_workflow: str,
    learning_profile_applied: bool,
) -> dict[str, Any]:
    return {
        **oracle_run,
        "run_id": oracle_run.get("runId"),
        "run_key": oracle_run.get("runKey"),
        "strategy_id": oracle_run.get("strategyId"),
        "strategy_label": oracle_run.get("strategyLabel"),
        "source_workflow": source_workflow,
        "learning_profile_applied": learning_profile_applied,
        "updated_at": oracle_run.get("updatedAt"),
    }


def _build_analysis_snapshot_doc(
    *,
    oracle_snapshot: dict[str, Any],
    source_workflow: str,
) -> dict[str, Any] | None:
    run_id = oracle_snapshot.get("runId")
    if not run_id:
        return None
    return {
        **oracle_snapshot,
        "analysis_key": run_id,
        "run_id": run_id,
        "run_key": oracle_snapshot.get("runKey"),
        "strategy_id": oracle_snapshot.get("strategyId"),
        "strategy_label": oracle_snapshot.get("strategyLabel"),
        "source_workflow": source_workflow,
    }


def run_auto_analysis_pipeline(
    *,
    targets: list[dict[str, Any]],
    support_docs: dict[str, Any],
    source_workflow: str,
    strategy_id: str = "balanced",
    strategy_label: str | None = None,
    run_date: str | None = None,
    checkpoint_key: str | None = None,
    checkpoint_label: str | None = None,
    checkpoint_target_days: int | None = None,
    snapshot_mode: str = "forward",
    snapshot_label: str = "CURRENT",
    analysis_oracle: Any | None = None,
    learning_profile: dict[str, Any] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    transport: Any | None = None,
    odds_oracle: Any | None = None,
    model_oracle: Any | None = None,
    fetched_at: datetime | None = None,
) -> dict[str, Any]:
    captured_at = fetched_at or utc_now()
    effective_run_date = _coerce_iso_date(run_date, captured_at)
    learning_profile_applied = bool(learning_profile)
    model_summary = run_model_snapshot_build(
        targets=targets,
        support_docs=support_docs,
        source_workflow=source_workflow,
        snapshot_mode=snapshot_mode,
        snapshot_label=snapshot_label,
        database=None,
        dry_run=True,
        transport=transport,
        odds_oracle=odds_oracle,
        model_oracle=model_oracle,
        fetched_at=captured_at,
        return_documents=True,
    )
    documents = model_summary.get("documents", {})
    model_snapshot_docs: list[dict[str, Any]] = documents.get("model_snapshot_docs", [])
    valid_model_snapshots, invalid_snapshot_count = _select_valid_model_snapshots(model_snapshot_docs)

    run_key = build_analysis_run_key(
        date=effective_run_date,
        strategy_id=strategy_id,
        checkpoint_key=checkpoint_key,
    )
    run_meta = {
        "runId": run_key,
        "runKey": run_key,
        "date": effective_run_date,
        "strategyId": strategy_id,
        "strategyLabel": strategy_label or strategy_id,
        "source": source_workflow,
        "checkpointKey": checkpoint_key,
        "checkpointLabel": checkpoint_label,
        "checkpointTargetDays": checkpoint_target_days,
        "createdAt": captured_at.isoformat(),
    }

    oracle_error_count = 0
    if valid_model_snapshots and analysis_oracle is None:
        raise RuntimeError("analysis_oracle is required when valid model snapshot rows are present.")

    if valid_model_snapshots:
        oracle_payload = analysis_oracle.rank_model_snapshots(
            model_snapshot_docs=valid_model_snapshots,
            run_meta=run_meta,
            learning_profile=learning_profile,
        )
        oracle_run = oracle_payload.get("run", {})
        oracle_candidates = oracle_payload.get("candidates", [])
        oracle_shortlist = oracle_payload.get("shortlist", [])
        oracle_snapshot = oracle_payload.get("snapshot", {})
    else:
        oracle_run = {
            "runId": run_key,
            "runKey": run_key,
            "date": effective_run_date,
            "strategyId": strategy_id,
            "strategyLabel": strategy_label or strategy_id,
            "source": source_workflow,
            "checkpointKey": checkpoint_key,
            "checkpointLabel": checkpoint_label,
            "checkpointTargetDays": checkpoint_target_days,
            "analyzedMatches": len({str(target.get("match_key")) for target in targets}),
            "marketCount": 0,
            "candidateCount": 0,
            "qualifyingCandidateCount": 0,
            "shortlistCount": 0,
            "provenCount": 0,
            "createdAt": captured_at,
            "updatedAt": captured_at,
        }
        oracle_candidates = []
        oracle_shortlist = []
        oracle_snapshot = {
            "runId": run_key,
            "runKey": run_key,
            "date": effective_run_date,
            "strategyId": strategy_id,
            "strategyLabel": strategy_label or strategy_id,
            "checkpointKey": checkpoint_key,
            "checkpointLabel": checkpoint_label,
            "checkpointTargetDays": checkpoint_target_days,
            "analyzedMatches": len({str(target.get("match_key")) for target in targets}),
            "shortlist": [],
            "createdAt": captured_at,
        }

    analysis_candidate_docs = _build_analysis_candidate_docs(
        oracle_candidates=oracle_candidates,
    )
    shortlist_selection_keys = {
        str(row.get("selection_key"))
        for row in analysis_candidate_docs
        if row.get("is_best_bet_for_match")
    }
    shortlist_docs = [
        row
        for row in analysis_candidate_docs
        if str(row.get("selection_key")) in shortlist_selection_keys
    ]
    analysis_run_doc = _build_analysis_run_doc(
        oracle_run=oracle_run,
        source_workflow=source_workflow,
        learning_profile_applied=learning_profile_applied,
    )
    analysis_snapshot_doc = _build_analysis_snapshot_doc(
        oracle_snapshot=oracle_snapshot,
        source_workflow=source_workflow,
    )

    report_date = captured_at.date().isoformat()
    parity_rows = build_analysis_parity_rows(
        source_workflow=source_workflow,
        target_matches=targets,
        model_snapshot_docs=model_snapshot_docs,
        analysis_candidate_docs=analysis_candidate_docs,
        shortlist_docs=shortlist_docs,
        oracle_error_count=oracle_error_count,
        report_date=report_date,
    )
    audit_rows = build_analysis_audit_rows(
        source_workflow=source_workflow,
        target_matches=targets,
        model_snapshot_docs=model_snapshot_docs,
        analysis_candidate_docs=analysis_candidate_docs,
        shortlist_docs=shortlist_docs,
        learning_profile_applied=learning_profile_applied,
        oracle_error_count=oracle_error_count,
        report_date=report_date,
    )
    health_rows = build_analysis_health_rows(
        target_matches=targets,
        analysis_candidate_docs=analysis_candidate_docs,
        shortlist_docs=shortlist_docs,
        oracle_error_count=oracle_error_count,
        report_date=report_date,
    )

    summary: dict[str, Any] = {
        "job": "run_auto_analysis",
        "captured_at": captured_at.isoformat(),
        "run_id": analysis_run_doc.get("run_id"),
        "run_key": analysis_run_doc.get("run_key"),
        "target_matches": len(targets),
        "matched_events": model_summary.get("matched_events", 0),
        "raw_docs": len(documents.get("raw_docs", [])),
        "event_links": len(documents.get("event_link_docs", [])),
        "market_offers": len(documents.get("market_offer_docs", [])),
        "model_snapshots": len(model_snapshot_docs),
        "valid_model_snapshots": len(valid_model_snapshots),
        "invalid_model_snapshots": invalid_snapshot_count,
        "analysis_candidates": len(analysis_candidate_docs),
        "qualifying_candidates": sum(1 for row in analysis_candidate_docs if row.get("passes_strategy_filters")),
        "analysis_shortlist": len(shortlist_docs),
        "learning_profile_applied": learning_profile_applied,
        "parity_reports": len(parity_rows),
        "audit_reports": len(audit_rows),
        "health_reports": len(health_rows),
        "oracle_error_count": oracle_error_count,
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
        "analysis_snapshot": analysis_snapshot_doc,
        "analysis_candidate_docs": analysis_candidate_docs,
    }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="run_auto_analysis",
        source_workflow=source_workflow,
        target_window={
            "run_date": effective_run_date,
            "strategy_id": strategy_id,
            "checkpoint_key": checkpoint_key,
            "target_match_count": len(targets),
        },
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {
        key: value
        for key, value in summary.items()
        if key not in {"analysis_run", "analysis_snapshot", "analysis_candidate_docs"}
    }
    try:
        odds_metrics = persist_odds_data_records(
            database,
            raw_docs=documents.get("raw_docs", []),
            event_link_docs=documents.get("event_link_docs", []),
            market_offer_docs=documents.get("market_offer_docs", []),
        )
        model_metrics = persist_model_snapshot_records(
            database,
            model_snapshot_docs=model_snapshot_docs,
            parity_rows=documents.get("parity_rows", []),
            audit_rows=documents.get("audit_rows", []),
            health_rows=documents.get("health_rows", []),
        )
        analysis_metrics = persist_analysis_records(
            database,
            analysis_run_doc=analysis_run_doc,
            analysis_candidate_docs=analysis_candidate_docs,
            analysis_snapshot_doc=analysis_snapshot_doc,
            parity_rows=parity_rows,
            audit_rows=audit_rows,
            health_rows=health_rows,
        )
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics={**odds_metrics, **model_metrics, **analysis_metrics, **job_metrics},
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
