from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import (
    build_audit_report_row,
    build_health_report_row,
    build_parity_report_row,
)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _checkpoint_counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def _target_pairs(rows: list[dict[str, Any]], field: str) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for row in rows:
        match_key = str(row.get("match_key") or "")
        checkpoint_key = str(row.get(field) or "")
        if not match_key or not checkpoint_key:
            continue
        pairs.add((match_key, checkpoint_key))
    return pairs


def build_checkpoint_parity_rows(
    *,
    source_workflow: str,
    target_matches: list[dict[str, Any]],
    due_targets: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    market_snapshot_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    gap_rows = [row for row in match_rows if row.get("checkpoint_capture_gap")]
    source_error_count = sum(1 for row in match_rows if row.get("error"))
    if not target_matches:
        return [
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": ["rolling fixtures", "existing checkpoint snapshots", "Unibet/Kambi raw odds"],
                    "old_outputs": ["checkpointed odds in unibet-backtest"],
                    "v2_job": "capture_odds_checkpoints.py",
                    "v2_outputs": ["market_snapshots", "parity_reports", "audit_reports"],
                    "smoke_test": "dry-run current 7-day checkpoint window",
                    "parity_proof": "verify no due targets are handled as an explicit no-op rather than a failed capture",
                },
                counts_old={"eligible_match_count": 0, "checkpoint_counts": {}},
                counts_v2={"captured_match_count": 0, "snapshot_count": 0, "checkpoint_counts": {}},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]
    if not due_targets and not gap_rows:
        return [
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": ["rolling fixtures", "existing checkpoint snapshots", "Unibet/Kambi raw odds"],
                    "old_outputs": ["checkpointed odds in unibet-backtest"],
                    "v2_job": "capture_odds_checkpoints.py",
                    "v2_outputs": ["market_snapshots", "parity_reports", "audit_reports"],
                    "smoke_test": "dry-run current 7-day checkpoint window",
                    "parity_proof": "verify no due checkpoint captures are treated as a clean no-op rather than a failed run",
                },
                counts_old={"eligible_match_count": 0, "checkpoint_counts": {}},
                counts_v2={"captured_match_count": 0, "snapshot_count": 0, "checkpoint_counts": {}},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    due_pairs = _target_pairs(due_targets, "checkpoint_key")
    captured_pairs = _target_pairs(market_snapshot_docs, "snapshot_label")
    invalid_count = sum(1 for row in market_snapshot_docs if row.get("invalid_for_model"))
    missing = sorted(due_pairs - captured_pairs)
    gap_count = len(gap_rows)
    parity_status = "matched" if not missing and invalid_count == 0 and source_error_count == 0 else "mismatch"

    return [
        build_parity_report_row(
            workflow_entry={
                "old_workflow": source_workflow,
                "old_inputs": ["rolling fixtures", "existing checkpoint snapshots", "Unibet/Kambi raw odds"],
                "old_outputs": ["checkpointed odds in unibet-backtest"],
                "v2_job": "capture_odds_checkpoints.py",
                "v2_outputs": ["market_snapshots", "parity_reports", "audit_reports"],
                "smoke_test": "dry-run current 7-day checkpoint window",
                "parity_proof": "compare due-match count under V2 checkpoint policy against captured unique match keys and require zero post-start snapshots",
            },
            counts_old={
                "available_checkpoint_target_count": len(due_pairs),
                "available_checkpoint_counts": _checkpoint_counts(due_targets, "checkpoint_key"),
            },
            counts_v2={
                "captured_checkpoint_target_count": len(captured_pairs),
                "snapshot_count": len(market_snapshot_docs),
                "checkpoint_counts": _checkpoint_counts(market_snapshot_docs, "snapshot_label"),
                "invalid_for_model_count": invalid_count,
                "source_error_count": source_error_count,
                "checkpoint_gap_count": gap_count,
                "gap_checkpoint_counts": _checkpoint_counts(gap_rows, "requested_checkpoint_key") if gap_rows else {},
            },
            parity_status=parity_status,
            blocking_issues=[
                f"missing_snapshot_capture:{match_key}:{checkpoint_key}"
                for match_key, checkpoint_key in missing
            ]
            + (["post_start_snapshot_detected"] if invalid_count else [])
            + (["checkpoint_source_errors_present"] if source_error_count else []),
            audit_risks=(
                [f"historical_policy_gap:{row.get('match_key')}:{row.get('requested_checkpoint_key')}" for row in gap_rows]
                if gap_rows
                else []
            )
            + ([] if parity_status == "matched" else ["checkpoint_capture_risk"]),
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_checkpoint_audit_rows(
    *,
    source_workflow: str,
    target_matches: list[dict[str, Any]],
    due_targets: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    market_snapshot_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    gap_rows = [row for row in match_rows if row.get("checkpoint_capture_gap")]
    source_errors = [row for row in match_rows if row.get("error")]
    if not target_matches:
        return [
            build_audit_report_row(
                audit_type="odds_checkpoints",
                scope_key=source_workflow,
                status="ok",
                metrics={
                    "eligible_match_count": 0,
                    "captured_match_count": 0,
                    "market_snapshot_count": 0,
                    "rows_before_matchstart": 0,
                    "rows_at_or_after_matchstart": 0,
                    "rows_without_snapshot_time": 0,
                    "rows_without_matchstart": 0,
                    "invalid_for_model_count": 0,
                },
                findings=["no_due_targets_in_requested_window"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]
    if not due_targets and not gap_rows:
        return [
            build_audit_report_row(
                audit_type="odds_checkpoints",
                scope_key=source_workflow,
                status="ok",
                metrics={
                    "eligible_match_count": 0,
                    "captured_match_count": 0,
                    "market_snapshot_count": 0,
                    "rows_before_matchstart": 0,
                    "rows_at_or_after_matchstart": 0,
                    "rows_without_snapshot_time": 0,
                    "rows_without_matchstart": 0,
                    "invalid_for_model_count": 0,
                },
                findings=["no_due_targets_in_requested_window"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    valid_rows = [row for row in market_snapshot_docs if not row.get("invalid_for_model")]
    invalid_rows = [row for row in market_snapshot_docs if row.get("invalid_for_model")]
    missing_snapshot_time = [row for row in market_snapshot_docs if row.get("snapshot_time") is None]
    missing_matchstart = [row for row in market_snapshot_docs if row.get("match_start_time") is None]
    empty_offer_matches = [
        row["match_key"]
        for row in match_rows
        if row.get("v2_event_id") and not row.get("v2_offer_count") and not row.get("checkpoint_capture_gap")
    ]
    findings: list[str] = []
    if invalid_rows:
        findings.append("post_start_snapshot_rows_present")
    if missing_snapshot_time:
        findings.append("missing_snapshot_time_rows_present")
    if missing_matchstart:
        findings.append("missing_match_start_rows_present")
    if source_errors:
        findings.extend(f"source_error:{row['match_key']}" for row in source_errors)
    if empty_offer_matches:
        findings.extend(f"empty_offer_set:{match_key}" for match_key in empty_offer_matches)
    if gap_rows:
        findings.extend(
            f"historical_policy_gap:{row.get('match_key')}:{row.get('requested_checkpoint_key')}"
            for row in gap_rows
        )
    status = "ok" if not invalid_rows and not missing_snapshot_time and not missing_matchstart and not source_errors and not empty_offer_matches else "warn"

    return [
        build_audit_report_row(
            audit_type="odds_checkpoints",
            scope_key=source_workflow,
            status=status,
            metrics={
                "available_checkpoint_target_count": len(_target_pairs(due_targets, "checkpoint_key")),
                "captured_checkpoint_target_count": len(_target_pairs(market_snapshot_docs, "snapshot_label")),
                "market_snapshot_count": len(market_snapshot_docs),
                "rows_before_matchstart": len(valid_rows),
                "rows_at_or_after_matchstart": len(invalid_rows),
                "rows_without_snapshot_time": len(missing_snapshot_time),
                "rows_without_matchstart": len(missing_matchstart),
                "invalid_for_model_count": len(invalid_rows),
                "source_error_count": len(source_errors),
                "checkpoint_gap_count": len(gap_rows),
                "gap_checkpoint_counts": _checkpoint_counts(gap_rows, "requested_checkpoint_key") if gap_rows else {},
                "checkpoint_counts": _checkpoint_counts(market_snapshot_docs, "snapshot_label"),
                "snapshot_time_source_counts": _checkpoint_counts(market_snapshot_docs, "snapshot_time_source"),
                "match_start_time_source_counts": _checkpoint_counts(market_snapshot_docs, "match_start_time_source"),
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_checkpoint_health_rows(
    *,
    target_matches: list[dict[str, Any]],
    due_targets: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    market_snapshot_docs: list[dict[str, Any]],
    error_count: int,
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    gap_count = sum(1 for row in match_rows if row.get("checkpoint_capture_gap"))
    source_error_count = sum(1 for row in match_rows if row.get("error"))
    if not target_matches:
        return [
            build_health_report_row(
                job_name="capture_odds_checkpoints",
                status="ok",
                summary="No checkpoint captures were due in the requested window.",
                metrics={
                    "eligible_match_count": 0,
                    "captured_match_count": 0,
                    "market_snapshot_count": 0,
                    "error_count": 0,
                },
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]
    if not due_targets and gap_count == 0:
        return [
            build_health_report_row(
                job_name="capture_odds_checkpoints",
                status="ok",
                summary="No checkpoint captures were due in the requested window.",
                metrics={
                    "eligible_match_count": 0,
                    "captured_match_count": 0,
                    "market_snapshot_count": 0,
                    "error_count": 0,
                },
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    invalid_count = sum(1 for row in market_snapshot_docs if row.get("invalid_for_model"))
    due_pair_count = len(_target_pairs(due_targets, "checkpoint_key"))
    captured_pair_count = len(_target_pairs(market_snapshot_docs, "snapshot_label"))
    status = "ok" if captured_pair_count == due_pair_count and invalid_count == 0 and error_count == 0 and source_error_count == 0 else "warn"
    return [
        build_health_report_row(
            job_name="capture_odds_checkpoints",
            status=status,
            summary=(
                "Checkpoint capture stored prematch snapshots for every due match."
                if status == "ok"
                else "Checkpoint capture finished with missing snapshots, source errors, or post-start rows."
            ),
            metrics={
                "available_checkpoint_target_count": due_pair_count,
                "captured_checkpoint_target_count": captured_pair_count,
                "market_snapshot_count": len(market_snapshot_docs),
                "invalid_for_model_count": invalid_count,
                "historical_policy_gap_count": gap_count,
                "source_error_count": source_error_count,
                "checkpoint_gap_count": gap_count,
                "error_count": error_count,
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
