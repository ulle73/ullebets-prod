from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.model_snapshots.persistence import persist_model_snapshot_records
from ullebets_v2.model_snapshots.reports import (
    build_model_snapshot_audit_rows,
    build_model_snapshot_health_rows,
    build_model_snapshot_parity_rows,
)
from ullebets_v2.odds.persistence import persist_odds_data_records
from ullebets_v2.odds.service import _build_legacy_tuples, _find_legacy_backtest_doc, _parse_match_time, run_unibet_odds_ingest


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _timing_fields(
    match: dict[str, Any],
    snapshot_time: datetime,
    *,
    snapshot_time_source: str = "job_captured_at",
    match_start_time_source: str = "fixture_target.start_time",
) -> dict[str, Any]:
    match_start = match.get("start_time")
    if not isinstance(match_start, datetime):
        match_start = _parse_match_time(match_start)
    minutes_to_kickoff = None
    invalid_for_model = False
    if isinstance(match_start, datetime):
        minutes_to_kickoff = round((match_start - snapshot_time).total_seconds() / 60)
        invalid_for_model = snapshot_time >= match_start
    return {
        "snapshot_time": snapshot_time,
        "snapshot_time_source": snapshot_time_source,
        "match_start_time": match_start,
        "match_start_time_source": match_start_time_source,
        "minutes_to_kickoff": minutes_to_kickoff,
        "invalid_for_model": invalid_for_model,
    }


def _offer_lookup(offer_docs: list[dict[str, Any]]) -> dict[tuple[str, str, str, float], dict[str, Any]]:
    lookup: dict[tuple[str, str, str, float], dict[str, Any]] = {}
    for row in offer_docs:
        key = (
            str(row.get("stat_key") or ""),
            str(row.get("scope") or ""),
            str(row.get("period") or ""),
            float(row.get("line") or 0),
        )
        lookup[key] = row
    return lookup


def _normalize_legacy_direction(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"över", "over"}:
        return "over"
    if text == "under":
        return "under"
    return None


def _infer_legacy_settlement_result(*, actual_value: Any, line_value: Any, win: Any) -> str | None:
    if isinstance(win, bool):
        return "win" if win else "loss"
    try:
        actual_numeric = float(actual_value)
        line_numeric = float(line_value)
    except (TypeError, ValueError):
        return None
    if actual_numeric == line_numeric:
        return "push"
    return None


def _legacy_reference_signature(line: dict[str, Any]) -> tuple[str, str, str, float, str] | None:
    direction = _normalize_legacy_direction(line.get("condition")) or str(line.get("direction") or "").lower()
    stat_key = str(line.get("statKey") or "")
    scope = str(line.get("scope") or "")
    period = str(line.get("period") or "")
    if not stat_key or not scope or not period or direction not in {"over", "under"}:
        return None
    try:
        line_value = float(line.get("line"))
    except (TypeError, ValueError):
        return None
    return (stat_key, scope, period, line_value, direction)


def _infer_legacy_snapshot_type(snapshot: dict[str, Any]) -> str | None:
    snapshot_type = str(snapshot.get("type") or "").strip().lower()
    if snapshot_type in {"forward", "backtest", "closing"}:
        return snapshot_type
    checkpoint_key = str(snapshot.get("checkpointKey") or "").strip().lower()
    if checkpoint_key in {"t15m", "t10m", "t2h"}:
        return "closing"
    if checkpoint_key in {"d7", "d5", "d3", "d2", "d1"}:
        return "forward"
    horizon_days = snapshot.get("horizonDays")
    if isinstance(horizon_days, (int, float)) and horizon_days > 0:
        return "forward"
    return None


def _select_legacy_snapshot_lines(
    *,
    legacy_doc: dict[str, Any],
    snapshot_mode: str,
) -> dict[str, Any] | None:
    snapshots = [row for row in list(legacy_doc.get("snapshots") or []) if isinstance(row, dict)]
    if snapshots:
        typed_candidates = [
            row
            for row in snapshots
            if _infer_legacy_snapshot_type(row) == snapshot_mode
        ]
        if not typed_candidates:
            return None
        selected = sorted(
            typed_candidates,
            key=lambda row: _parse_match_time(row.get("fetchedAt")) or datetime.min.replace(tzinfo=UTC),
        )[-1]
        return {
            "lines": list(selected.get("lines") or []),
            "snapshot_time": _parse_match_time(selected.get("fetchedAt")),
            "snapshot_time_source": "legacy_snapshot.fetchedAt",
            "selection_source": f"legacy_snapshot.{snapshot_mode}",
            "model_source": "legacy_unibet_backtest_snapshot",
            "legacy_reference_lines": list(legacy_doc.get("lines") or []),
        }

    if snapshot_mode != "backtest":
        return None

    return {
        "lines": list(legacy_doc.get("lines") or []),
        "snapshot_time": _parse_match_time(legacy_doc.get("generatedAt")) or _parse_match_time(legacy_doc.get("updatedAt")),
        "snapshot_time_source": "legacy_doc.generatedAt",
        "selection_source": "legacy_doc.lines",
        "model_source": "legacy_unibet_backtest_root_lines",
        "legacy_reference_lines": list(legacy_doc.get("lines") or []),
    }


def _build_legacy_generated_lines(
    *,
    match_key: str,
    target_match: dict[str, Any],
    legacy_lines: list[dict[str, Any]],
    legacy_reference_lines: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    generated_lines: list[dict[str, Any]] = []
    source_match_id = target_match.get("source_match_id") or match_key
    reference_by_bet_key: dict[str, dict[str, Any]] = {}
    reference_by_signature: dict[tuple[str, str, str, float, str], dict[str, Any]] = {}
    for reference in legacy_reference_lines or legacy_lines:
        reference_signature = _legacy_reference_signature(reference)
        if reference_signature is None:
            continue
        bet_key = str(reference.get("betKey") or "")
        if bet_key:
            reference_by_bet_key[bet_key] = reference
        reference_by_signature[reference_signature] = reference
    for line in legacy_lines:
        direction = _normalize_legacy_direction(line.get("condition"))
        odds_value = line.get("odds")
        if direction is None:
            continue
        if not isinstance(odds_value, (int, float)) or odds_value <= 1:
            continue
        stat_key = line.get("statKey")
        scope = line.get("scope")
        period = line.get("period")
        line_value = line.get("line")
        if not stat_key or not scope or not period or line_value is None:
            continue
        bet_key = line.get("betKey") or "|".join(
            [
                str(source_match_id),
                str(stat_key),
                str(scope),
                str(period),
                direction,
                str(line_value),
            ]
        )
        reference = reference_by_bet_key.get(str(bet_key))
        if reference is None:
            reference = reference_by_signature.get((str(stat_key), str(scope), str(period), float(line_value), direction))
        if reference is None:
            reference = line
        generated_lines.append(
            {
                "betKey": bet_key,
                "statKey": stat_key,
                "line": line_value,
                "condition": "över" if direction == "over" else "under",
                "direction": direction,
                "period": period,
                "scope": scope,
                "odds": float(odds_value),
                "value": line.get("value"),
                "evDetails": line.get("evDetails") if isinstance(line.get("evDetails"), dict) else {},
                "primaryFormulaKey": line.get("primaryFormulaKey"),
                "primaryValueKey": line.get("primaryValueKey"),
                "sampleSize": line.get("sampleSize") or line.get("matches"),
                "homeTeam": line.get("homeTeam") or target_match.get("home_team_name"),
                "awayTeam": line.get("awayTeam") or target_match.get("away_team_name"),
                "actual": None,
                "win": None,
                "legacyActualValue": reference.get("actual"),
                "legacySettlementResult": _infer_legacy_settlement_result(
                    actual_value=reference.get("actual"),
                    line_value=line_value,
                    win=reference.get("win"),
                ),
                "legacyWin": reference.get("win"),
            }
        )
    return generated_lines


def build_model_snapshot_docs(
    *,
    target_matches: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    event_link_docs: list[dict[str, Any]],
    market_offer_docs: list[dict[str, Any]],
    snapshot_mode: str,
    snapshot_label: str,
    snapshot_time: datetime,
    model_source: str,
) -> list[dict[str, Any]]:
    match_by_key = {str(row["match_key"]): row for row in target_matches}
    event_link_by_match = {str(row["match_key"]): row for row in event_link_docs}
    offers_by_match: dict[str, list[dict[str, Any]]] = {}
    for offer in market_offer_docs:
        offers_by_match.setdefault(str(offer["match_key"]), []).append(offer)

    docs: list[dict[str, Any]] = []
    for row in match_rows:
        match_key = str(row["match_key"])
        target_match = match_by_key.get(match_key)
        if target_match is None:
            continue
        offer_lookup = _offer_lookup(offers_by_match.get(match_key, []))
        event_link = event_link_by_match.get(match_key, {})
        effective_snapshot_time = row.get("snapshot_time_override")
        if not isinstance(effective_snapshot_time, datetime):
            effective_snapshot_time = snapshot_time
        timing = _timing_fields(
            target_match,
            effective_snapshot_time,
            snapshot_time_source=str(row.get("snapshot_time_source_override") or "job_captured_at"),
            match_start_time_source=str(row.get("match_start_time_source_override") or "fixture_target.start_time"),
        )
        for line in row.get("generated_lines", []):
            offer = offer_lookup.get(
                (
                    str(line.get("statKey") or ""),
                    str(line.get("scope") or ""),
                    str(line.get("period") or ""),
                    float(line.get("line") or 0),
                )
            )
            offer_key = offer.get("offer_key") if offer else None
            direction = str(line.get("direction") or "over")
            selection_key = "|".join(
                [
                    match_key,
                    str(line.get("betKey") or ""),
                    snapshot_mode,
                    snapshot_label,
                ]
            )
            docs.append(
                {
                    "selection_key": selection_key,
                    "match_key": match_key,
                    "source_match_id": target_match.get("source_match_id"),
                    "offer_key": offer_key,
                    "bet_key": line.get("betKey"),
                    "event_id": row.get("v2_event_id"),
                    "event_url": event_link.get("event_url"),
                    "league_key": target_match.get("league_key"),
                    "league_name": target_match.get("league_name"),
                    "home_team_name": line.get("homeTeam") or target_match.get("home_team_name"),
                    "away_team_name": line.get("awayTeam") or target_match.get("away_team_name"),
                    "stat_key": line.get("statKey"),
                    "period": line.get("period"),
                    "scope": line.get("scope"),
                    "direction": direction,
                    "line_value": line.get("line"),
                    "selected_odds": line.get("odds"),
                    "condition_label": line.get("condition"),
                    "primary_ev": line.get("value"),
                    "ev_details": line.get("evDetails") or {},
                    "primary_formula_key": line.get("primaryFormulaKey"),
                    "primary_value_key": line.get("primaryValueKey"),
                    "sample_size": line.get("sampleSize"),
                    "actual_value": None,
                    "settlement_result": None,
                    "win": None,
                    "legacy_actual_value": line.get("legacyActualValue"),
                    "legacy_settlement_result": line.get("legacySettlementResult"),
                    "legacy_win": line.get("legacyWin"),
                    "snapshot_mode": snapshot_mode,
                    "snapshot_label": snapshot_label,
                    "model_source": row.get("model_source_override") or model_source,
                    **timing,
                }
            )
    return docs


def run_model_snapshot_build(
    *,
    targets: list[dict[str, Any]],
    support_docs: dict[str, Any],
    source_workflow: str,
    snapshot_mode: str,
    snapshot_label: str = "CURRENT",
    database: Any | None = None,
    dry_run: bool = False,
    transport: Any | None = None,
    odds_oracle: Any | None = None,
    model_oracle: Any | None = None,
    legacy_backtest_database: Any | None = None,
    use_legacy_snapshot_lines: bool = True,
    fetched_at: datetime | None = None,
    return_documents: bool = False,
) -> dict[str, Any]:
    captured_at = fetched_at or utc_now()
    odds_summary = run_unibet_odds_ingest(
        targets=targets,
        support_docs=support_docs,
        source_workflow=source_workflow,
        dry_run=True,
        transport=transport,
        oracle=odds_oracle,
        legacy_backtest_database=legacy_backtest_database,
        fetched_at=captured_at,
        return_documents=True,
    )
    documents = odds_summary.get("documents", {})
    match_rows: list[dict[str, Any]] = []
    target_by_match_key = {str(row["match_key"]): row for row in targets}
    event_links_by_match = {}
    for event_link in documents.get("event_link_docs", []):
        event_links_by_match[str(event_link["match_key"])] = event_link
    offers_by_match: dict[str, list[dict[str, Any]]] = {}
    for offer in documents.get("market_offer_docs", []):
        offers_by_match.setdefault(str(offer["match_key"]), []).append(offer)

    for odds_row in odds_summary["match_rows"]:
        row = dict(odds_row)
        row["generated_lines"] = []
        row["model_errors"] = []
        match_key = str(row["match_key"])
        target = target_by_match_key.get(match_key)
        if target is None or not row.get("v2_event_id"):
            row["generated_line_count"] = 0
            match_rows.append(row)
            continue
        legacy_snapshot = None
        if legacy_backtest_database is not None and row.get("historical_source_found"):
            legacy_doc = _find_legacy_backtest_doc(
                legacy_backtest_database=legacy_backtest_database,
                match=target,
            )
            legacy_snapshot = (
                _select_legacy_snapshot_lines(
                    legacy_doc=legacy_doc,
                    snapshot_mode=snapshot_mode,
                )
                if legacy_doc is not None
                else None
            )
            if legacy_snapshot is None and use_legacy_snapshot_lines:
                row["model_errors"] = [
                    {
                        "message": "missing_legacy_snapshot_lines_for_mode",
                        "snapshot_mode": snapshot_mode,
                    }
                ]
            elif legacy_snapshot is not None and use_legacy_snapshot_lines:
                row["generated_lines"] = _build_legacy_generated_lines(
                    match_key=match_key,
                    target_match=target,
                    legacy_lines=legacy_snapshot["lines"],
                    legacy_reference_lines=legacy_snapshot.get("legacy_reference_lines"),
                )
                snapshot_time_override = legacy_snapshot.get("snapshot_time")
                if isinstance(snapshot_time_override, datetime):
                    row["snapshot_time_override"] = snapshot_time_override
                    row["snapshot_time_source_override"] = legacy_snapshot.get("snapshot_time_source")
                row["model_source_override"] = legacy_snapshot.get("model_source")
                row["legacy_selection_source"] = legacy_snapshot.get("selection_source")
                row["generated_line_count"] = len(row["generated_lines"])
                match_rows.append(row)
                continue

        if legacy_snapshot is not None and not use_legacy_snapshot_lines:
            oracle_input = _build_legacy_tuples(list(legacy_snapshot.get("lines") or []))
            snapshot_time_override = legacy_snapshot.get("snapshot_time")
            if isinstance(snapshot_time_override, datetime):
                row["snapshot_time_override"] = snapshot_time_override
                row["snapshot_time_source_override"] = legacy_snapshot.get("snapshot_time_source")
            row["legacy_selection_source"] = legacy_snapshot.get("selection_source")
        else:
            offer_docs = offers_by_match.get(match_key, [])
            oracle_input = [
                {
                    "statKey": offer.get("stat_key"),
                    "scope": offer.get("scope"),
                    "period": offer.get("period"),
                    "line": offer.get("line"),
                    "odds": {
                        "over": offer.get("over_odds"),
                        "under": offer.get("under_odds"),
                    },
                }
                for offer in offer_docs
            ]
        if oracle_input and model_oracle is not None:
            built = model_oracle.build_match_lines(
                match_info={
                    "matchId": target.get("source_match_id") or target.get("match_key"),
                    "matchKey": target.get("match_key"),
                    "homeTeam": event_links_by_match.get(match_key, {}).get("canonical_home_team_name")
                    or target.get("home_team_name"),
                    "awayTeam": event_links_by_match.get(match_key, {}).get("canonical_away_team_name")
                    or target.get("away_team_name"),
                    "homeTeamKey": target.get("home_team_key"),
                    "awayTeamKey": target.get("away_team_key"),
                    "leagueKey": target.get("league_key"),
                    "sourceDate": target.get("source_date"),
                    "startTime": target.get("start_time"),
                },
                offers=oracle_input,
            )
            row["generated_lines"] = built.get("lines", []) if isinstance(built, dict) else []
            row["model_errors"] = built.get("errors", []) if isinstance(built, dict) else [{"message": "invalid_model_oracle_response"}]
        elif oracle_input:
            row["model_errors"] = [{"message": "model_oracle_required"}]
        row["generated_line_count"] = len(row["generated_lines"])
        match_rows.append(row)

    model_snapshot_docs = build_model_snapshot_docs(
        target_matches=targets,
        match_rows=match_rows,
        event_link_docs=documents.get("event_link_docs", []),
        market_offer_docs=documents.get("market_offer_docs", []),
        snapshot_mode=snapshot_mode,
        snapshot_label=snapshot_label,
        snapshot_time=captured_at,
        model_source=getattr(model_oracle, "model_source", "model_oracle_missing"),
    )
    report_date = captured_at.date().isoformat()
    parity_rows = build_model_snapshot_parity_rows(
        source_workflow=source_workflow,
        target_matches=targets,
        match_rows=match_rows,
        model_snapshot_docs=model_snapshot_docs,
        report_date=report_date,
    )
    audit_rows = build_model_snapshot_audit_rows(
        source_workflow=source_workflow,
        target_matches=targets,
        match_rows=match_rows,
        model_snapshot_docs=model_snapshot_docs,
        report_date=report_date,
    )
    oracle_error_count = sum(len(row.get("model_errors", [])) for row in match_rows)
    health_rows = build_model_snapshot_health_rows(
        target_matches=targets,
        match_rows=match_rows,
        model_snapshot_docs=model_snapshot_docs,
        oracle_error_count=oracle_error_count,
        report_date=report_date,
    )

    summary: dict[str, Any] = {
        "job": "build_model_snapshots",
        "captured_at": captured_at.isoformat(),
        "target_matches": len(targets),
        "raw_docs": len(documents.get("raw_docs", [])),
        "event_links": len(documents.get("event_link_docs", [])),
        "market_offers": len(documents.get("market_offer_docs", [])),
        "model_snapshots": len(model_snapshot_docs),
        "matched_events": odds_summary["matched_events"],
        "errors": odds_summary["errors"] + oracle_error_count,
        "oracle_error_count": oracle_error_count,
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
        "match_rows": match_rows,
    }
    if return_documents:
        summary["documents"] = {
            **documents,
            "model_snapshot_docs": model_snapshot_docs,
            "parity_rows": parity_rows,
            "audit_rows": audit_rows,
            "health_rows": health_rows,
        }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="build_model_snapshots",
        source_workflow=source_workflow,
        target_window={
            "target_match_count": len(targets),
            "snapshot_mode": snapshot_mode,
            "snapshot_label": snapshot_label,
            "captured_at": captured_at.isoformat(),
        },
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {key: value for key, value in summary.items() if key != "match_rows"}
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
            parity_rows=parity_rows,
            audit_rows=audit_rows,
            health_rows=health_rows,
        )
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics={**odds_metrics, **model_metrics, **job_metrics},
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
