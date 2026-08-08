from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.checkpoints.service import (
    build_market_snapshot_docs,
    load_existing_snapshot_docs,
    select_replay_checkpoint_targets,
    select_due_checkpoint_targets,
)
from ullebets_v2.closing.persistence import persist_closing_records
from ullebets_v2.closing.reports import (
    build_closing_audit_rows,
    build_closing_health_rows,
    build_closing_parity_rows,
)
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.odds.persistence import persist_odds_data_records
from ullebets_v2.odds.service import run_unibet_odds_ingest


CLOSING_CAPTURE_CHECKPOINTS = ("T_MINUS_30M", "T_MINUS_10M")
PRODUCTION_CLOSING_LABELS = frozenset(CLOSING_CAPTURE_CHECKPOINTS)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


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


def build_closing_line_docs(
    *,
    market_snapshot_docs: list[dict[str, Any]],
    refreshed_at: datetime,
    restrict_match_keys: set[str] | None = None,
    eligible_closing_labels: frozenset[str] | None = PRODUCTION_CLOSING_LABELS,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in market_snapshot_docs:
        match_key = str(row.get("match_key") or "")
        offer_key = str(row.get("offer_key") or "")
        if not match_key or not offer_key:
            continue
        if restrict_match_keys is not None and match_key not in restrict_match_keys:
            continue
        grouped.setdefault(offer_key, []).append(row)

    closing_docs: list[dict[str, Any]] = []
    for offer_key, rows in grouped.items():
        normalized_rows: list[tuple[datetime, dict[str, Any], bool]] = []
        invalid_snapshot_count = 0
        for row in rows:
            snapshot_time = _to_datetime(row.get("snapshot_time"))
            match_start_time = _to_datetime(row.get("match_start_time"))
            invalid_for_model = bool(row.get("invalid_for_model"))
            if snapshot_time is not None and match_start_time is not None and snapshot_time >= match_start_time:
                invalid_for_model = True
            if invalid_for_model:
                invalid_snapshot_count += 1
            normalized_rows.append(
                (
                    snapshot_time or datetime.min.replace(tzinfo=UTC),
                    row,
                    invalid_for_model,
                )
            )

        normalized_rows.sort(key=lambda item: item[0])
        valid_rows = [row for _, row, invalid in normalized_rows if not invalid]
        if not valid_rows:
            continue

        closing_candidates = valid_rows
        if eligible_closing_labels is not None:
            closing_candidates = [
                row
                for row in valid_rows
                if str(row.get("snapshot_label") or "") in eligible_closing_labels
            ]
        if not closing_candidates:
            continue

        opening_row = valid_rows[0]
        latest_row = valid_rows[-1]
        closing_row = closing_candidates[-1]
        closing_snapshot_time = _to_datetime(closing_row.get("snapshot_time"))
        match_start_time = _to_datetime(closing_row.get("match_start_time"))
        closing_age_minutes = None
        if closing_snapshot_time is not None and match_start_time is not None:
            closing_age_minutes = round(
                (match_start_time - closing_snapshot_time).total_seconds() / 60
            )
        closing_label = str(closing_row.get("snapshot_label") or "")
        if closing_label == "T_MINUS_10M":
            closing_quality = "t10"
        elif closing_label == "T_MINUS_30M":
            closing_quality = "t30_fallback"
        else:
            closing_quality = "legacy_fallback"
        price_history = [
            {
                "snapshot_label": row.get("snapshot_label"),
                "snapshot_time": row.get("snapshot_time"),
                "over_odds": row.get("over_odds"),
                "under_odds": row.get("under_odds"),
                "source_workflow": row.get("source_workflow"),
            }
            for row in valid_rows
        ]
        closing_docs.append(
            {
                "closing_key": offer_key,
                "match_key": closing_row.get("match_key"),
                "offer_key": offer_key,
                "event_id": closing_row.get("event_id"),
                "league_key": closing_row.get("league_key"),
                "league_name": closing_row.get("league_name"),
                "home_team_name": closing_row.get("home_team_name"),
                "away_team_name": closing_row.get("away_team_name"),
                "stat_key": closing_row.get("stat_key"),
                "scope": closing_row.get("scope"),
                "period": closing_row.get("period"),
                "line": closing_row.get("line"),
                "match_start_time": closing_row.get("match_start_time"),
                "opening_snapshot_label": opening_row.get("snapshot_label"),
                "opening_snapshot_time": opening_row.get("snapshot_time"),
                "opening_over_odds": opening_row.get("over_odds"),
                "opening_under_odds": opening_row.get("under_odds"),
                "latest_snapshot_label": latest_row.get("snapshot_label"),
                "latest_snapshot_time": latest_row.get("snapshot_time"),
                "latest_over_odds": latest_row.get("over_odds"),
                "latest_under_odds": latest_row.get("under_odds"),
                "closing_snapshot_label": closing_row.get("snapshot_label"),
                "closing_snapshot_time": closing_row.get("snapshot_time"),
                "closing_over_odds": closing_row.get("over_odds"),
                "closing_under_odds": closing_row.get("under_odds"),
                "closing_quality": closing_quality,
                "closing_is_official": closing_quality == "t10",
                "closing_age_minutes": closing_age_minutes,
                "prematch_observation_count": len(valid_rows),
                "invalid_snapshot_count": invalid_snapshot_count,
                "snapshot_labels_seen": [
                    str(label)
                    for label in dict.fromkeys(row.get("snapshot_label") for row in valid_rows)
                    if label is not None
                ],
                "price_history": price_history,
                "refreshed_at": refreshed_at,
            }
        )
    return sorted(closing_docs, key=lambda row: (str(row.get("match_key") or ""), str(row.get("offer_key") or "")))


def _dedupe_snapshot_docs(snapshot_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for row in snapshot_docs:
        snapshot_key = row.get("snapshot_key")
        if not snapshot_key:
            continue
        deduped[str(snapshot_key)] = row
    return list(deduped.values())


def run_closing_capture(
    *,
    targets: list[dict[str, Any]],
    support_docs: dict[str, Any],
    source_workflow: str,
    database: Any | None = None,
    dry_run: bool = False,
    existing_snapshot_docs: list[dict[str, Any]] | None = None,
    transport: Any | None = None,
    oracle: Any | None = None,
    legacy_backtest_database: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    captured_at = now or utc_now()
    eligible_closing_labels: frozenset[str] | None = PRODUCTION_CLOSING_LABELS
    snapshots = existing_snapshot_docs
    if snapshots is None and database is not None:
        snapshots = load_existing_snapshot_docs(database, [str(target["match_key"]) for target in targets])
    if legacy_backtest_database is not None:
        eligible_closing_labels = None
        replay_due = select_replay_checkpoint_targets(
            targets=targets,
            legacy_backtest_database=legacy_backtest_database,
            existing_snapshot_docs=snapshots,
            checkpoint_filter="T_MINUS_10M",
        )
        replay_history = select_replay_checkpoint_targets(
            targets=targets,
            legacy_backtest_database=legacy_backtest_database,
            existing_snapshot_docs=None,
            checkpoint_filter=None,
        )
        due_targets = replay_due["due_targets"]
        documents = {
            "raw_docs": replay_due["raw_docs"],
            "event_link_docs": replay_due["event_link_docs"],
            "market_offer_docs": replay_due["market_offer_docs"],
        }
        market_snapshot_docs = build_market_snapshot_docs(
            due_targets=due_targets,
            market_offer_docs=documents.get("market_offer_docs", []),
            snapshot_time=captured_at,
            source_workflow=source_workflow,
        )
        historical_snapshot_docs = build_market_snapshot_docs(
            due_targets=replay_history["due_targets"],
            market_offer_docs=replay_history["market_offer_docs"],
            snapshot_time=captured_at,
            source_workflow=source_workflow,
        )
        all_snapshot_docs = _dedupe_snapshot_docs(list(snapshots or []) + historical_snapshot_docs)
        match_rows = replay_due["match_rows"]
        errors = sum(1 for row in match_rows if row.get("error"))
        matched_events = len({row["match_key"] for row in match_rows if row.get("v2_event_id")})
    else:
        due_targets = []
        for checkpoint_key in CLOSING_CAPTURE_CHECKPOINTS:
            due_targets.extend(
                select_due_checkpoint_targets(
                    targets=targets,
                    now=captured_at,
                    existing_snapshot_docs=snapshots,
                    checkpoint_filter=checkpoint_key,
                )
            )
        due_targets.sort(
            key=lambda row: (
                row.get("start_time") or captured_at,
                str(row.get("match_key") or ""),
            )
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
        all_snapshot_docs = list(snapshots or []) + market_snapshot_docs
        match_rows = odds_summary["match_rows"]
        errors = odds_summary["errors"]
        matched_events = odds_summary["matched_events"]
    due_match_keys = {str(row["match_key"]) for row in due_targets}
    closing_line_docs = build_closing_line_docs(
        market_snapshot_docs=all_snapshot_docs,
        refreshed_at=captured_at,
        restrict_match_keys=due_match_keys,
        eligible_closing_labels=eligible_closing_labels,
    )
    report_date = captured_at.date().isoformat()
    parity_rows = build_closing_parity_rows(
        source_workflow=source_workflow,
        target_matches=targets,
        due_targets=due_targets,
        match_rows=match_rows,
        market_snapshot_docs=market_snapshot_docs,
        closing_line_docs=closing_line_docs,
        report_date=report_date,
    )
    audit_rows = build_closing_audit_rows(
        source_workflow=source_workflow,
        target_matches=targets,
        due_targets=due_targets,
        match_rows=match_rows,
        market_snapshot_docs=market_snapshot_docs,
        closing_line_docs=closing_line_docs,
        report_date=report_date,
    )
    health_rows = build_closing_health_rows(
        target_matches=targets,
        due_targets=due_targets,
        match_rows=match_rows,
        closing_line_docs=closing_line_docs,
        market_snapshot_docs=market_snapshot_docs,
        report_date=report_date,
    )
    invalid_for_model_rows = sum(1 for row in market_snapshot_docs if row.get("invalid_for_model"))
    checkpoint_counts = {
        checkpoint_key: sum(
            1 for row in due_targets if row.get("checkpoint_key") == checkpoint_key
        )
        for checkpoint_key in CLOSING_CAPTURE_CHECKPOINTS
        if any(row.get("checkpoint_key") == checkpoint_key for row in due_targets)
    }
    closing_quality_counts = {
        quality: sum(
            1 for row in closing_line_docs if row.get("closing_quality") == quality
        )
        for quality in sorted(
            {
                str(row.get("closing_quality") or "missing")
                for row in closing_line_docs
            }
        )
    }
    summary: dict[str, Any] = {
        "job": "capture_closing_snapshots",
        "captured_at": captured_at.isoformat(),
        "target_matches": len(targets),
        "due_matches": len(due_targets),
        "checkpoint_counts": checkpoint_counts,
        "raw_docs": len(documents.get("raw_docs", [])),
        "event_links": len(documents.get("event_link_docs", [])),
        "market_offers": len(documents.get("market_offer_docs", [])),
        "market_snapshots": len(market_snapshot_docs),
        "closing_lines": len(closing_line_docs),
        "official_closing_lines": sum(
            1 for row in closing_line_docs if row.get("closing_is_official") is True
        ),
        "fallback_closing_lines": sum(
            1 for row in closing_line_docs if row.get("closing_quality") == "t30_fallback"
        ),
        "closing_quality_counts": closing_quality_counts,
        "matched_events": matched_events,
        "errors": errors,
        "invalid_for_model_rows": invalid_for_model_rows,
        "checkpoint_gap_count": sum(1 for row in match_rows if row.get("checkpoint_capture_gap")),
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
        "due_targets": due_targets,
        "match_rows": match_rows,
        "closing_line_docs": closing_line_docs,
    }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="capture_closing_snapshots",
        source_workflow=source_workflow,
        target_window={"captured_at": captured_at.isoformat(), "due_match_count": len(due_targets)},
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {
        key: value
        for key, value in summary.items()
        if key not in {"due_targets", "match_rows", "closing_line_docs"}
    }
    try:
        odds_metrics = persist_odds_data_records(
            database,
            raw_docs=documents.get("raw_docs", []),
            event_link_docs=documents.get("event_link_docs", []),
            market_offer_docs=documents.get("market_offer_docs", []),
        )
        closing_metrics = persist_closing_records(
            database,
            market_snapshot_docs=market_snapshot_docs,
            closing_line_docs=closing_line_docs,
            parity_rows=parity_rows,
            audit_rows=audit_rows,
            health_rows=health_rows,
        )
        summary.update(odds_metrics)
        summary.update(closing_metrics)
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics={**odds_metrics, **closing_metrics, **job_metrics},
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
