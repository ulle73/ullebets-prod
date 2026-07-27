from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.model_snapshots.service import _select_legacy_snapshot_lines
from ullebets_v2.odds.service import _find_legacy_backtest_doc, run_unibet_odds_ingest
from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _normalize_direction(line: dict[str, Any]) -> str | None:
    direction = str(line.get("direction") or "").strip().lower()
    if direction in {"over", "under"}:
        return direction
    condition = str(line.get("condition") or "").strip().lower()
    if condition in {"över", "over"}:
        return "over"
    if condition == "under":
        return "under"
    return None


def _line_signature(line: dict[str, Any]) -> tuple[str, str, str, float, str] | None:
    direction = _normalize_direction(line)
    if direction is None:
        return None
    stat_key = str(line.get("statKey") or line.get("stat_key") or "").strip()
    scope = str(line.get("scope") or "").strip()
    period = str(line.get("period") or "").strip()
    if not stat_key or not scope or not period:
        return None
    try:
        line_value = float(line.get("line") if line.get("line") is not None else line.get("line_value"))
    except (TypeError, ValueError):
        return None
    return (stat_key, scope, period, line_value, direction)


def _signature_label(signature: tuple[str, str, str, float, str]) -> str:
    stat_key, scope, period, line_value, direction = signature
    return f"{stat_key}|{scope}|{period}|{direction}|{line_value}"


def _build_reference_offer_rows(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, float], dict[str, Any]] = {}
    for line in lines:
        signature = _line_signature(line)
        if signature is None:
            continue
        stat_key, scope, period, line_value, direction = signature
        odds_value = line.get("odds")
        if not isinstance(odds_value, (int, float)) or odds_value <= 1:
            continue
        entry = grouped.setdefault(
            (stat_key, scope, period, line_value),
            {
                "statKey": stat_key,
                "scope": scope,
                "period": period,
                "line": line_value,
                "odds": {},
            },
        )
        entry["odds"][direction] = float(odds_value)
    return sorted(
        grouped.values(),
        key=lambda row: (
            str(row.get("statKey") or ""),
            str(row.get("scope") or ""),
            str(row.get("period") or ""),
            float(row.get("line") or 0),
        ),
    )


def compare_line_sets(
    *,
    reference_lines: list[dict[str, Any]],
    generated_lines: list[dict[str, Any]],
) -> dict[str, Any]:
    reference_by_signature = {
        signature: line
        for line in reference_lines
        if (signature := _line_signature(line)) is not None
    }
    generated_by_signature = {
        signature: line
        for line in generated_lines
        if (signature := _line_signature(line)) is not None
    }
    reference_signatures = set(reference_by_signature)
    generated_signatures = set(generated_by_signature)
    matched_signatures = sorted(reference_signatures & generated_signatures)
    missing_signatures = sorted(reference_signatures - generated_signatures)
    extra_signatures = sorted(generated_signatures - reference_signatures)

    odds_mismatches: list[str] = []
    for signature in matched_signatures:
        reference_odds = reference_by_signature[signature].get("odds")
        generated_odds = generated_by_signature[signature].get("odds")
        if isinstance(reference_odds, (int, float)) and isinstance(generated_odds, (int, float)):
            if float(reference_odds) != float(generated_odds):
                odds_mismatches.append(_signature_label(signature))

    return {
        "reference_line_count": len(reference_by_signature),
        "generated_line_count": len(generated_by_signature),
        "matched_line_count": len(matched_signatures),
        "missing_line_count": len(missing_signatures),
        "extra_line_count": len(extra_signatures),
        "odds_mismatch_count": len(odds_mismatches),
        "matched_signatures": [_signature_label(signature) for signature in matched_signatures],
        "missing_signatures": [_signature_label(signature) for signature in missing_signatures],
        "extra_signatures": [_signature_label(signature) for signature in extra_signatures],
        "odds_mismatches": odds_mismatches,
    }


def _build_runtime_parity_report_row(
    *,
    source_workflow: str,
    snapshot_mode: str,
    target_source: str,
    counts_old: dict[str, Any],
    counts_v2: dict[str, Any],
    parity_status: str,
    blocking_issues: list[str],
    audit_risks: list[str],
    report_date: str,
) -> dict[str, Any]:
    return build_parity_report_row(
        workflow_entry={
            "old_workflow": f"{source_workflow}#runtime-parity#{target_source}",
            "old_inputs": [f"{target_source} targets", "legacy snapshot lines", "legacy historical odds tuples"],
            "old_outputs": [f"legacy {snapshot_mode} snapshot lines"],
            "v2_job": "audit_model_snapshot_runtime_parity.py",
            "v2_outputs": ["parity_reports", "audit_reports", "health_reports"],
            "smoke_test": f"dry-run replay audit for one historical {snapshot_mode} window",
            "parity_proof": "compare legacy snapshot line keys/counts against lines generated by the V2-owned JS runtime from the same historical tuple set",
        },
        counts_old=counts_old,
        counts_v2=counts_v2,
        parity_status=parity_status,
        blocking_issues=blocking_issues,
        audit_risks=audit_risks,
        report_date=report_date,
    )


def _build_runtime_match_info(
    *,
    target: dict[str, Any],
    match_row: dict[str, Any],
    event_link_docs_by_match: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    match_key = str(target.get("match_key") or "")
    event_link = event_link_docs_by_match.get(match_key, {})
    return {
        "matchId": target.get("source_match_id") or target.get("match_key"),
        "matchKey": target.get("match_key"),
        "homeTeam": event_link.get("canonical_home_team_name") or target.get("home_team_name"),
        "awayTeam": event_link.get("canonical_away_team_name") or target.get("away_team_name"),
        "homeTeamKey": target.get("home_team_key"),
        "awayTeamKey": target.get("away_team_key"),
        "leagueKey": target.get("league_key"),
        "sourceDate": target.get("source_date"),
        "startTime": target.get("start_time"),
        "eventId": match_row.get("historical_event_id"),
    }


def _persist_runtime_parity_reports(
    database: Any,
    *,
    parity_rows: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    health_rows: list[dict[str, Any]],
) -> dict[str, int]:
    parity_upserts = 0
    for row in parity_rows:
        result = database["parity_reports"].update_one(
            {"old_workflow": row["old_workflow"], "report_date": row["report_date"]},
            {"$set": row},
            upsert=True,
        )
        parity_upserts += 1 if result.upserted_id is not None else 0

    audit_upserts = 0
    for row in audit_rows:
        result = database["audit_reports"].update_one(
            {
                "audit_type": row["audit_type"],
                "scope_key": row["scope_key"],
                "report_date": row["report_date"],
            },
            {"$set": row},
            upsert=True,
        )
        audit_upserts += 1 if result.upserted_id is not None else 0

    health_upserts = 0
    for row in health_rows:
        result = database["health_reports"].update_one(
            {"job_name": row["job_name"], "report_date": row["report_date"]},
            {"$set": row},
            upsert=True,
        )
        health_upserts += 1 if result.upserted_id is not None else 0

    return {
        "parity_upserts": parity_upserts,
        "audit_upserts": audit_upserts,
        "health_upserts": health_upserts,
    }


def run_model_snapshot_runtime_parity_audit(
    *,
    targets: list[dict[str, Any]],
    support_docs: dict[str, Any],
    source_workflow: str,
    snapshot_mode: str,
    legacy_backtest_database: Any,
    model_oracle: Any,
    target_source: str = "replay-fixtures",
    database: Any | None = None,
    dry_run: bool = False,
    fetched_at: datetime | None = None,
    return_documents: bool = False,
) -> dict[str, Any]:
    captured_at = fetched_at or utc_now()
    odds_summary = run_unibet_odds_ingest(
        targets=targets,
        support_docs=support_docs,
        source_workflow=source_workflow,
        dry_run=True,
        legacy_backtest_database=legacy_backtest_database,
        fetched_at=captured_at,
        return_documents=True,
    )
    documents = odds_summary.get("documents", {})
    event_link_docs_by_match = {
        str(row.get("match_key") or ""): row
        for row in documents.get("event_link_docs", [])
        if row.get("match_key") is not None
    }
    targets_by_match = {str(row.get("match_key") or ""): row for row in targets}

    match_rows: list[dict[str, Any]] = []
    total_reference_lines = 0
    total_generated_lines = 0
    total_matched_lines = 0
    total_missing_lines = 0
    total_extra_lines = 0
    total_odds_mismatches = 0

    for imported_row in odds_summary.get("match_rows", []):
        row = {
            "match_key": imported_row.get("match_key"),
            "historical_source_found": bool(imported_row.get("historical_source_found")),
            "historical_event_id": imported_row.get("historical_event_id"),
            "generated_lines": [],
            "model_errors": [],
            "comparison": None,
        }
        match_key = str(imported_row.get("match_key") or "")
        target = targets_by_match.get(match_key)
        if target is None:
            row["model_errors"] = [{"message": "missing_target_match"}]
            match_rows.append(row)
            continue
        if not imported_row.get("historical_source_found"):
            row["model_errors"] = [{"message": "missing_legacy_snapshot_reference"}]
            match_rows.append(row)
            continue

        legacy_doc = _find_legacy_backtest_doc(
            legacy_backtest_database=legacy_backtest_database,
            match=target,
        )
        legacy_snapshot = (
            _select_legacy_snapshot_lines(legacy_doc=legacy_doc, snapshot_mode=snapshot_mode)
            if legacy_doc is not None
            else None
        )
        if legacy_snapshot is None:
            row["model_errors"] = [{"message": "missing_legacy_snapshot_lines_for_mode", "snapshot_mode": snapshot_mode}]
            match_rows.append(row)
            continue

        reference_lines = list(legacy_snapshot.get("lines") or [])
        offer_rows = _build_reference_offer_rows(reference_lines)
        if not offer_rows:
            row["comparison"] = {
                "reference_line_count": 0,
                "generated_line_count": 0,
                "matched_line_count": 0,
                "missing_line_count": 0,
                "extra_line_count": 0,
                "odds_mismatch_count": 0,
                "matched_signatures": [],
                "missing_signatures": [],
                "extra_signatures": [],
                "odds_mismatches": [],
            }
            match_rows.append(row)
            continue

        built = model_oracle.build_match_lines(
            match_info=_build_runtime_match_info(
                target=target,
                match_row=imported_row,
                event_link_docs_by_match=event_link_docs_by_match,
            ),
            offers=offer_rows,
        )
        row["generated_lines"] = built.get("lines", []) if isinstance(built, dict) else []
        row["model_errors"] = built.get("errors", []) if isinstance(built, dict) else [{"message": "invalid_model_oracle_response"}]
        row["comparison"] = compare_line_sets(
            reference_lines=reference_lines,
            generated_lines=row["generated_lines"],
        )
        total_reference_lines += row["comparison"]["reference_line_count"]
        total_generated_lines += row["comparison"]["generated_line_count"]
        total_matched_lines += row["comparison"]["matched_line_count"]
        total_missing_lines += row["comparison"]["missing_line_count"]
        total_extra_lines += row["comparison"]["extra_line_count"]
        total_odds_mismatches += row["comparison"]["odds_mismatch_count"]
        match_rows.append(row)

    report_date = captured_at.date().isoformat()
    match_error_count = sum(1 for row in match_rows if row.get("model_errors"))
    comparable_match_count = sum(1 for row in match_rows if row.get("comparison") is not None)
    blocking_issues: list[str] = []
    if total_missing_lines:
        blocking_issues.append(f"missing_generated_lines:{total_missing_lines}")
    if total_extra_lines:
        blocking_issues.append(f"extra_generated_lines:{total_extra_lines}")
    if total_odds_mismatches:
        blocking_issues.append(f"odds_mismatches:{total_odds_mismatches}")
    if match_error_count:
        blocking_issues.append(f"model_or_reference_errors:{match_error_count}")
    parity_status = (
        "no_targets"
        if not targets
        else "matched"
        if comparable_match_count > 0 and not blocking_issues
        else "mismatch"
    )
    parity_rows = [
        _build_runtime_parity_report_row(
            source_workflow=source_workflow,
            snapshot_mode=snapshot_mode,
            target_source=target_source,
            counts_old={
                "target_match_count": len(targets),
                "comparable_match_count": comparable_match_count,
                "reference_line_count": total_reference_lines,
            },
            counts_v2={
                "generated_line_count": total_generated_lines,
                "matched_line_count": total_matched_lines,
                "missing_line_count": total_missing_lines,
                "extra_line_count": total_extra_lines,
                "odds_mismatch_count": total_odds_mismatches,
                "match_error_count": match_error_count,
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=[] if parity_status in {"matched", "no_targets"} else ["runtime_parity_not_proven"],
            report_date=report_date,
        )
    ]

    audit_findings: list[str] = []
    if not targets:
        audit_findings.append(f"no_{target_source.replace('-', '_')}_targets_for_requested_window")
    if comparable_match_count == 0 and targets:
        audit_findings.append("no_comparable_legacy_snapshot_matches")
    if total_missing_lines:
        audit_findings.append("v2_runtime_missing_legacy_lines")
    if total_extra_lines:
        audit_findings.append("v2_runtime_extra_lines_vs_legacy")
    if total_odds_mismatches:
        audit_findings.append("v2_runtime_odds_mismatch_vs_legacy")
    if match_error_count:
        audit_findings.append("v2_runtime_or_reference_errors_present")
    audit_rows = [
        build_audit_report_row(
            audit_type="model_snapshot_runtime_parity",
            scope_key=f"{source_workflow}:{snapshot_mode}:{target_source}",
            status="ok" if not audit_findings else "warn",
            metrics={
                "target_match_count": len(targets),
                "comparable_match_count": comparable_match_count,
                "reference_line_count": total_reference_lines,
                "generated_line_count": total_generated_lines,
                "matched_line_count": total_matched_lines,
                "missing_line_count": total_missing_lines,
                "extra_line_count": total_extra_lines,
                "odds_mismatch_count": total_odds_mismatches,
                "match_error_count": match_error_count,
            },
            findings=audit_findings,
            report_date=report_date,
        )
    ]
    health_rows = [
        build_health_report_row(
            job_name=f"audit_model_snapshot_runtime_parity:{target_source}",
            status="ok" if parity_status in {"matched", "no_targets"} else "warn",
            summary=(
                f"No {target_source} targets were available for the requested historical window."
                if parity_status == "no_targets"
                else "V2-owned snapshot runtime matched the legacy historical line set for the audited window."
                if parity_status == "matched"
                else "V2-owned snapshot runtime deviated from the legacy historical line set or lacked comparable inputs."
            ),
            metrics={
                "target_match_count": len(targets),
                "comparable_match_count": comparable_match_count,
                "reference_line_count": total_reference_lines,
                "generated_line_count": total_generated_lines,
                "matched_line_count": total_matched_lines,
                "missing_line_count": total_missing_lines,
                "extra_line_count": total_extra_lines,
                "match_error_count": match_error_count,
            },
            report_date=report_date,
        )
    ]

    summary: dict[str, Any] = {
        "job": "audit_model_snapshot_runtime_parity",
        "captured_at": captured_at.isoformat(),
        "source_workflow": source_workflow,
        "snapshot_mode": snapshot_mode,
        "target_source": target_source,
        "target_matches": len(targets),
        "comparable_matches": comparable_match_count,
        "reference_lines": total_reference_lines,
        "generated_lines": total_generated_lines,
        "matched_lines": total_matched_lines,
        "missing_lines": total_missing_lines,
        "extra_lines": total_extra_lines,
        "odds_mismatches": total_odds_mismatches,
        "match_error_count": match_error_count,
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
            "odds_documents": documents,
            "parity_rows": parity_rows,
            "audit_rows": audit_rows,
            "health_rows": health_rows,
        }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="audit_model_snapshot_runtime_parity",
        source_workflow=source_workflow,
        target_window={
            "target_match_count": len(targets),
            "snapshot_mode": snapshot_mode,
            "captured_at": captured_at.isoformat(),
        },
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {key: value for key, value in summary.items() if key not in {"match_rows", "documents"}}
    try:
        persistence_metrics = _persist_runtime_parity_reports(
            database,
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
