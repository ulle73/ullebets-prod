from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.checkpoints.persistence import persist_checkpoint_records
from ullebets_v2.checkpoints.policy import (
    V2_ODDS_CHECKPOINTS,
    build_snapshot_timing_fields,
    classify_checkpoint_by_minutes,
    pick_due_checkpoint,
)
from ullebets_v2.checkpoints.reports import (
    build_checkpoint_audit_rows,
    build_checkpoint_health_rows,
    build_checkpoint_parity_rows,
)
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.odds.oracle import OriginalJsOracle
from ullebets_v2.odds.persistence import persist_odds_data_records
from ullebets_v2.odds.service import (
    _build_legacy_event_link_doc,
    _build_legacy_tuples,
    _build_market_offer_docs,
    _find_legacy_backtest_doc,
    _parse_match_time,
    run_unibet_odds_ingest,
)
from ullebets_v2.support.schemas import stable_json_hash


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


def _checkpoint_order(checkpoint_key: str | None) -> int:
    for index, checkpoint in enumerate(V2_ODDS_CHECKPOINTS):
        if checkpoint.key == checkpoint_key:
            return index
    return len(V2_ODDS_CHECKPOINTS)


def _build_replay_snapshot_raw_doc(
    *,
    match: dict[str, Any],
    legacy_doc: dict[str, Any],
    snapshot: dict[str, Any],
    checkpoint_key: str,
) -> dict[str, Any]:
    snapshot_time = _parse_match_time(snapshot.get("fetchedAt")) or utc_now()
    payload = {
        "eventId": legacy_doc.get("eventId"),
        "matchId": legacy_doc.get("matchId"),
        "matchDate": legacy_doc.get("matchDate"),
        "league": legacy_doc.get("league"),
        "homeTeam": legacy_doc.get("homeTeam"),
        "awayTeam": legacy_doc.get("awayTeam"),
        "url": legacy_doc.get("url"),
        "snapshot": snapshot,
    }
    payload_hash = stable_json_hash(payload)
    event_id = legacy_doc.get("eventId")
    return {
        "raw_key": "|".join(
            [
                "legacy_unibet_snapshot",
                str(event_id) if event_id is not None else "",
                str(match["match_key"]),
                checkpoint_key,
                snapshot_time.isoformat(),
                payload_hash,
            ]
        ),
        "payload_hash": payload_hash,
        "payload_kind": "legacy_unibet_snapshot",
        "source_provider": "legacy_unibet_backtest",
        "source_url": legacy_doc.get("url"),
        "fetched_at": snapshot_time,
        "match_key": match["match_key"],
        "event_id": str(event_id) if event_id is not None else None,
        "league_key": match.get("league_key"),
        "league_name": match.get("league_name"),
        "match_start_time": match.get("start_time"),
        "payload": payload,
        "bet_offer_count": len(snapshot.get("lines") or []),
    }


def select_replay_checkpoint_targets(
    *,
    targets: list[dict[str, Any]],
    legacy_backtest_database: Any,
    existing_snapshot_docs: list[dict[str, Any]] | None = None,
    checkpoint_filter: str | None = None,
) -> dict[str, Any]:
    existing_by_match = build_existing_snapshot_map(existing_snapshot_docs)
    due_targets: list[dict[str, Any]] = []
    match_rows: list[dict[str, Any]] = []
    raw_docs: list[dict[str, Any]] = []
    event_link_docs: list[dict[str, Any]] = []
    market_offer_docs: list[dict[str, Any]] = []

    expected_checkpoints = [
        checkpoint for checkpoint in V2_ODDS_CHECKPOINTS if checkpoint_filter in {None, checkpoint.key}
    ]

    for target in targets:
        match = dict(target)
        legacy_doc = _find_legacy_backtest_doc(
            legacy_backtest_database=legacy_backtest_database,
            match=match,
        )
        if legacy_doc is None:
            for checkpoint in expected_checkpoints:
                match_rows.append(
                    {
                        "match_key": match["match_key"],
                        "checkpoint_key": checkpoint.key,
                        "requested_checkpoint_key": checkpoint.key,
                        "v2_event_id": None,
                        "v2_offer_count": 0,
                        "historical_source_checked": True,
                        "historical_source_found": False,
                        "historical_event_id": None,
                        "checkpoint_capture_gap": True,
                        "error": None,
                    }
                )
            continue

        event_id = legacy_doc.get("eventId")
        event_id_str = str(event_id) if event_id is not None else None
        match_start_time = _parse_match_time(match.get("start_time"))
        selected_by_checkpoint: dict[str, dict[str, Any]] = {}
        for snapshot in list(legacy_doc.get("snapshots") or []):
            if not isinstance(snapshot, dict):
                continue
            snapshot_time = _parse_match_time(snapshot.get("fetchedAt"))
            if snapshot_time is None or match_start_time is None or snapshot_time >= match_start_time:
                continue
            minutes_to_kickoff = round((match_start_time - snapshot_time).total_seconds() / 60)
            checkpoint = classify_checkpoint_by_minutes(
                minutes_to_kickoff=minutes_to_kickoff,
                checkpoint_filter=checkpoint_filter,
            )
            if checkpoint is None:
                continue
            if checkpoint.key in {
                row.get("snapshot_label")
                for row in existing_by_match.get(str(match["match_key"]), [])
            }:
                continue
            current = selected_by_checkpoint.get(checkpoint.key)
            if current is None or snapshot_time > current["snapshot_time"]:
                selected_by_checkpoint[checkpoint.key] = {
                    "checkpoint": checkpoint,
                    "snapshot": snapshot,
                    "snapshot_time": snapshot_time,
                    "minutes_to_kickoff": minutes_to_kickoff,
                }

        if selected_by_checkpoint:
            event_link_docs.append(
                _build_legacy_event_link_doc(
                    match=match,
                    legacy_doc=legacy_doc,
                    imported_at=max(
                        selection["snapshot_time"] for selection in selected_by_checkpoint.values()
                    ),
                )
            )

        selected_keys = set(selected_by_checkpoint)
        for checkpoint in expected_checkpoints:
            selection = selected_by_checkpoint.get(checkpoint.key)
            if selection is None:
                match_rows.append(
                    {
                        "match_key": match["match_key"],
                        "checkpoint_key": checkpoint.key,
                        "requested_checkpoint_key": checkpoint.key,
                        "v2_event_id": event_id_str,
                        "v2_offer_count": 0,
                        "historical_source_checked": True,
                        "historical_source_found": True,
                        "historical_event_id": event_id_str,
                        "checkpoint_capture_gap": True,
                        "historical_snapshot_count": len(legacy_doc.get("snapshots") or []),
                        "error": None,
                    }
                )
                continue

            snapshot = selection["snapshot"]
            snapshot_time = selection["snapshot_time"]
            tuples = _build_legacy_tuples(list(snapshot.get("lines") or []))
            raw_doc = _build_replay_snapshot_raw_doc(
                match=match,
                legacy_doc=legacy_doc,
                snapshot=snapshot,
                checkpoint_key=checkpoint.key,
            )
            offer_docs = _build_market_offer_docs(
                match=match,
                event_id=event_id_str,
                tuples=tuples,
                raw_payload_hash=raw_doc["payload_hash"],
                fetched_at=snapshot_time,
            )
            due_targets.append(
                {
                    **match,
                    "checkpoint_key": checkpoint.key,
                    "checkpoint_label": checkpoint.label,
                    "checkpoint_snapshot_type": checkpoint.snapshot_type,
                    "checkpoint_target_days": checkpoint.target_days,
                    "minutes_to_kickoff": selection["minutes_to_kickoff"],
                    "_selected_market_offer_docs": offer_docs,
                    "_snapshot_time_override": snapshot_time,
                    "_snapshot_time_source_override": "legacy_snapshot.fetchedAt",
                    "_capture_mode_override": "checkpoint_replay",
                }
            )
            raw_docs.append(raw_doc)
            market_offer_docs.extend(offer_docs)
            match_rows.append(
                {
                    "match_key": match["match_key"],
                    "checkpoint_key": checkpoint.key,
                    "requested_checkpoint_key": checkpoint.key,
                    "v2_event_id": event_id_str,
                    "v2_offer_count": len(tuples),
                    "historical_source_checked": True,
                    "historical_source_found": True,
                    "historical_event_id": event_id_str,
                    "historical_snapshot_count": len(legacy_doc.get("snapshots") or []),
                    "checkpoint_capture_gap": False,
                    "selected_snapshot_time": snapshot_time,
                    "error": None,
                }
            )

    due_targets.sort(
        key=lambda row: (
            row.get("start_time") or utc_now(),
            _checkpoint_order(str(row.get("checkpoint_key") or "")),
            str(row.get("match_key") or ""),
        )
    )
    match_rows.sort(
        key=lambda row: (
            str(row.get("match_key") or ""),
            _checkpoint_order(str(row.get("requested_checkpoint_key") or row.get("checkpoint_key") or "")),
        )
    )
    return {
        "due_targets": due_targets,
        "match_rows": match_rows,
        "raw_docs": raw_docs,
        "event_link_docs": event_link_docs,
        "market_offer_docs": market_offer_docs,
    }


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
    docs: list[dict[str, Any]] = []
    offers_by_match_key: dict[str, list[dict[str, Any]]] = {}
    for offer in market_offer_docs:
        offers_by_match_key.setdefault(str(offer["match_key"]), []).append(offer)

    for target in due_targets:
        match_key = str(target["match_key"])
        offers = target.get("_selected_market_offer_docs")
        if not isinstance(offers, list):
            offers = offers_by_match_key.get(match_key, [])
        effective_snapshot_time = target.get("_snapshot_time_override")
        if not isinstance(effective_snapshot_time, datetime):
            effective_snapshot_time = snapshot_time
        timing = build_snapshot_timing_fields(
            match_start=target.get("start_time"),
            snapshot_time=effective_snapshot_time,
            checkpoint_key=target.get("checkpoint_key"),
            minutes_to_kickoff=target.get("minutes_to_kickoff"),
        )
        for offer in offers:
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
                    "snapshot_time_source": str(
                        target.get("_snapshot_time_source_override") or "job_captured_at"
                    ),
                    "match_start_time": timing["match_start_time"],
                    "match_start_time_source": "fixture_target.start_time",
                    "minutes_to_kickoff": timing["minutes_to_kickoff"],
                    "horizon_days": timing["horizon_days"],
                    "invalid_for_model": timing["invalid_for_model"],
                    "source_workflow": source_workflow,
                    "capture_mode": str(target.get("_capture_mode_override") or "checkpoint"),
                    "captured_at": timing["snapshot_time"],
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
    legacy_backtest_database: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    captured_at = now or utc_now()
    snapshots = existing_snapshot_docs
    if snapshots is None and database is not None:
        snapshots = load_existing_snapshot_docs(database, [str(target["match_key"]) for target in targets])
    if legacy_backtest_database is not None:
        replay = select_replay_checkpoint_targets(
            targets=targets,
            legacy_backtest_database=legacy_backtest_database,
            existing_snapshot_docs=snapshots,
            checkpoint_filter=checkpoint_filter,
        )
        due_targets = replay["due_targets"]
        match_rows = replay["match_rows"]
        documents = {
            "raw_docs": replay["raw_docs"],
            "event_link_docs": replay["event_link_docs"],
            "market_offer_docs": replay["market_offer_docs"],
        }
        errors = sum(1 for row in match_rows if row.get("error"))
        matched_events = len({row["match_key"] for row in match_rows if row.get("v2_event_id")})
    else:
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
        match_rows = odds_summary["match_rows"]
        errors = odds_summary["errors"]
        matched_events = odds_summary["matched_events"]
    market_snapshot_docs = build_market_snapshot_docs(
        due_targets=due_targets,
        market_offer_docs=documents.get("market_offer_docs", []),
        snapshot_time=captured_at,
        source_workflow=source_workflow,
    )
    report_date = captured_at.date().isoformat()
    parity_rows = build_checkpoint_parity_rows(
        source_workflow=source_workflow,
        target_matches=targets,
        due_targets=due_targets,
        match_rows=match_rows,
        market_snapshot_docs=market_snapshot_docs,
        report_date=report_date,
    )
    audit_rows = build_checkpoint_audit_rows(
        source_workflow=source_workflow,
        target_matches=targets,
        due_targets=due_targets,
        match_rows=match_rows,
        market_snapshot_docs=market_snapshot_docs,
        report_date=report_date,
    )
    health_rows = build_checkpoint_health_rows(
        target_matches=targets,
        due_targets=due_targets,
        match_rows=match_rows,
        market_snapshot_docs=market_snapshot_docs,
        error_count=errors,
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
        "matched_events": matched_events,
        "errors": errors,
        "invalid_for_model_rows": sum(1 for row in market_snapshot_docs if row.get("invalid_for_model")),
        "checkpoint_gap_count": sum(1 for row in match_rows if row.get("checkpoint_capture_gap")),
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
        "match_rows": match_rows,
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
