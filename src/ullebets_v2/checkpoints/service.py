from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.checkpoints.persistence import persist_checkpoint_records
from ullebets_v2.checkpoints.policy import build_snapshot_timing_fields, pick_due_checkpoint
from ullebets_v2.checkpoints.reports import (
    build_checkpoint_audit_rows,
    build_checkpoint_health_rows,
    build_checkpoint_parity_rows,
)
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.odds.oracle import OriginalJsOracle
from ullebets_v2.odds.persistence import persist_odds_data_records
from ullebets_v2.odds.service import run_unibet_odds_ingest


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _serialize_target_window(now: datetime, checkpoint_filter: str | None) -> dict[str, Any]:
    payload = {"captured_at": now.isoformat()}
    if checkpoint_filter:
        payload["checkpoint_filter"] = checkpoint_filter
    return payload


def build_existing_snapshot_map(snapshot_docs: list[dict[str, Any]] | None = None) -> dict[str, list[dict[str, Any]]]:
    mapped: dict[str, list[dict[str, Any]]] = {}
    for row in snapshot_docs or []:
        match_key = row.get("match_key")
        if not match_key:
            continue
        mapped.setdefault(str(match_key), []).append(row)
    return mapped


def load_existing_snapshot_docs(database: Any, match_keys: list[str]) -> list[dict[str, Any]]:
    if not match_keys:
        return []
    return list(
        database["market_snapshots"].find(
            {"match_key": {"$in": [str(match_key) for match_key in match_keys]}},
            projection={"_id": 0},
        )
    )


def select_due_checkpoint_targets(
    *,
    targets: list[dict[str, Any]],
    now: datetime | None = None,
    existing_snapshot_docs: list[dict[str, Any]] | None = None,
    checkpoint_filter: str | None = None,
) -> list[dict[str, Any]]:
    current_time = now or utc_now()
    existing_by_match = build_existing_snapshot_map(existing_snapshot_docs)
    due_targets: list[dict[str, Any]] = []
    for target in targets:
        match_key = str(target["match_key"])
        checkpoint = pick_due_checkpoint(
            match_start=target.get("start_time"),
            now=current_time,
            snapshots=existing_by_match.get(match_key, []),
            checkpoint_filter=checkpoint_filter,
        )
        if checkpoint is None:
            continue
        timing = build_snapshot_timing_fields(
            match_start=target.get("start_time"),
            snapshot_time=current_time,
            checkpoint_key=checkpoint.key,
        )
        due_targets.append(
            {
                **target,
                "checkpoint_key": checkpoint.key,
                "checkpoint_label": checkpoint.label,
                "checkpoint_snapshot_type": checkpoint.snapshot_type,
                "checkpoint_target_days": checkpoint.target_days,
                "minutes_to_kickoff": timing["minutes_to_kickoff"],
            }
        )
    return sorted(due_targets, key=lambda row: row.get("start_time") or current_time)


def build_market_snapshot_docs(
    *,
    due_targets: list[dict[str, Any]],
    market_offer_docs: list[dict[str, Any]],
    snapshot_time: datetime,
    source_workflow: str,
) -> list[dict[str, Any]]:
    target_by_match_key = {str(row["match_key"]): row for row in due_targets}
    docs: list[dict[str, Any]] = []
    for offer in market_offer_docs:
        match_key = str(offer["match_key"])
        target = target_by_match_key.get(match_key)
        if target is None:
            continue
        timing = build_snapshot_timing_fields(
            match_start=target.get("start_time"),
            snapshot_time=snapshot_time,
            checkpoint_key=target.get("checkpoint_key"),
            minutes_to_kickoff=target.get("minutes_to_kickoff"),
        )
        snapshot_label = str(target["checkpoint_key"])
        snapshot_key = "|".join([match_key, str(offer["offer_key"]), snapshot_label])
        docs.append(
            {
                "snapshot_key": snapshot_key,
                "match_key": match_key,
                "offer_key": offer["offer_key"],
                "event_id": offer.get("event_id"),
                "league_key": offer.get("league_key"),
                "league_name": offer.get("league_name"),
                "home_team_name": offer.get("home_team_name"),
                "away_team_name": offer.get("away_team_name"),
                "stat_key": offer.get("stat_key"),
                "scope": offer.get("scope"),
                "period": offer.get("period"),
                "line": offer.get("line"),
                "over_odds": offer.get("over_odds"),
                "under_odds": offer.get("under_odds"),
                "source_provider": offer.get("source_provider"),
                "raw_payload_hash": offer.get("raw_payload_hash"),
                "snapshot_label": snapshot_label,
                "snapshot_type": target.get("checkpoint_snapshot_type"),
                "target_days": target.get("checkpoint_target_days"),
                "snapshot_time": timing["snapshot_time"],
                "snapshot_time_source": "job_captured_at",
                "match_start_time": timing["match_start_time"],
                "match_start_time_source": "fixture_target.start_time",
                "minutes_to_kickoff": timing["minutes_to_kickoff"],
                "horizon_days": timing["horizon_days"],
                "invalid_for_model": timing["invalid_for_model"],
                "source_workflow": source_workflow,
                "capture_mode": "checkpoint",
                "captured_at": snapshot_time,
            }
        )
    return docs


def run_checkpoint_capture(
    *,
    targets: list[dict[str, Any]],
    support_docs: dict[str, Any],
    source_workflow: str,
    database: Any | None = None,
    dry_run: bool = False,
    existing_snapshot_docs: list[dict[str, Any]] | None = None,
    checkpoint_filter: str | None = None,
    transport: Any | None = None,
    oracle: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    captured_at = now or utc_now()
    snapshots = existing_snapshot_docs
    if snapshots is None and database is not None:
        snapshots = load_existing_snapshot_docs(database, [str(target["match_key"]) for target in targets])
    due_targets = select_due_checkpoint_targets(
        targets=targets,
        now=captured_at,
        existing_snapshot_docs=snapshots,
        checkpoint_filter=checkpoint_filter,
    )

    odds_summary = run_unibet_odds_ingest(
        targets=due_targets,
        support_docs=support_docs,
        source_workflow=source_workflow,
        dry_run=True,
        transport=transport,
        oracle=oracle,
        fetched_at=captured_at,
        return_documents=True,
    )
    documents = odds_summary.get("documents", {})
    market_snapshot_docs = build_market_snapshot_docs(
        due_targets=due_targets,
        market_offer_docs=documents.get("market_offer_docs", []),
        snapshot_time=captured_at,
        source_workflow=source_workflow,
    )
    report_date = captured_at.date().isoformat()
    parity_rows = build_checkpoint_parity_rows(
        source_workflow=source_workflow,
        due_targets=due_targets,
        market_snapshot_docs=market_snapshot_docs,
        report_date=report_date,
    )
    audit_rows = build_checkpoint_audit_rows(
        source_workflow=source_workflow,
        due_targets=due_targets,
        match_rows=odds_summary["match_rows"],
        market_snapshot_docs=market_snapshot_docs,
        report_date=report_date,
    )
    health_rows = build_checkpoint_health_rows(
        due_targets=due_targets,
        market_snapshot_docs=market_snapshot_docs,
        error_count=odds_summary["errors"],
        report_date=report_date,
    )

    summary: dict[str, Any] = {
        "job": "capture_odds_checkpoints",
        "captured_at": captured_at.isoformat(),
        "target_matches": len(targets),
        "due_matches": len(due_targets),
        "checkpoint_counts": {
            key: sum(1 for row in due_targets if row.get("checkpoint_key") == key)
            for key in sorted({row.get("checkpoint_key") for row in due_targets})
        },
        "raw_docs": len(documents.get("raw_docs", [])),
        "event_links": len(documents.get("event_link_docs", [])),
        "market_offers": len(documents.get("market_offer_docs", [])),
        "market_snapshots": len(market_snapshot_docs),
        "parity_reports": len(parity_rows),
        "audit_reports": len(audit_rows),
        "health_reports": len(health_rows),
        "matched_events": odds_summary["matched_events"],
        "errors": odds_summary["errors"],
        "invalid_for_model_rows": sum(1 for row in market_snapshot_docs if row.get("invalid_for_model")),
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
        "due_targets": due_targets,
        "match_rows": odds_summary["match_rows"],
    }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="capture_odds_checkpoints",
        source_workflow=source_workflow,
        target_window=_serialize_target_window(captured_at, checkpoint_filter),
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {key: value for key, value in summary.items() if key not in {"due_targets", "match_rows"}}
    try:
        odds_metrics = persist_odds_data_records(
            database,
            raw_docs=documents.get("raw_docs", []),
            event_link_docs=documents.get("event_link_docs", []),
            market_offer_docs=documents.get("market_offer_docs", []),
        )
        checkpoint_metrics = persist_checkpoint_records(
            database,
            market_snapshot_docs=market_snapshot_docs,
            parity_rows=parity_rows,
            audit_rows=audit_rows,
            health_rows=health_rows,
        )
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics={**odds_metrics, **checkpoint_metrics, **job_metrics},
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
