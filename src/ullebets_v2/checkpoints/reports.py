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


def build_checkpoint_parity_rows(
    *,
    source_workflow: str,
    due_targets: list[dict[str, Any]],
    market_snapshot_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not due_targets:
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

    eligible_match_keys = {str(row["match_key"]) for row in due_targets}
    captured_match_keys = {str(row["match_key"]) for row in market_snapshot_docs}
    invalid_count = sum(1 for row in market_snapshot_docs if row.get("invalid_for_model"))
    missing = sorted(eligible_match_keys - captured_match_keys)
    parity_status = "matched" if not missing and invalid_count == 0 else "mismatch"

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
                "eligible_match_count": len(eligible_match_keys),
                "checkpoint_counts": _checkpoint_counts(due_targets, "checkpoint_key"),
            },
            counts_v2={
                "captured_match_count": len(captured_match_keys),
                "snapshot_count": len(market_snapshot_docs),
                "checkpoint_counts": _checkpoint_counts(market_snapshot_docs, "snapshot_label"),
                "invalid_for_model_count": invalid_count,
            },
            parity_status=parity_status,
            blocking_issues=[f"missing_snapshot_capture:{match_key}" for match_key in missing]
            + (["post_start_snapshot_detected"] if invalid_count else []),
            audit_risks=[] if parity_status == "matched" else ["checkpoint_capture_risk"],
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_checkpoint_audit_rows(
    *,
    source_workflow: str,
    due_targets: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    market_snapshot_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not due_targets:
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
    empty_offer_matches = [row["match_key"] for row in match_rows if row.get("v2_event_id") and not row.get("v2_offer_count")]
    findings: list[str] = []
    if invalid_rows:
        findings.append("post_start_snapshot_rows_present")
    if missing_snapshot_time:
        findings.append("missing_snapshot_time_rows_present")
    if missing_matchstart:
        findings.append("missing_match_start_rows_present")
    if empty_offer_matches:
        findings.extend(f"empty_offer_set:{match_key}" for match_key in empty_offer_matches)
    status = "ok" if not findings else "warn"

    return [
        build_audit_report_row(
            audit_type="odds_checkpoints",
            scope_key=source_workflow,
            status=status,
            metrics={
                "eligible_match_count": len(due_targets),
                "captured_match_count": len({row["match_key"] for row in market_snapshot_docs}),
                "market_snapshot_count": len(market_snapshot_docs),
                "rows_before_matchstart": len(valid_rows),
                "rows_at_or_after_matchstart": len(invalid_rows),
                "rows_without_snapshot_time": len(missing_snapshot_time),
                "rows_without_matchstart": len(missing_matchstart),
                "invalid_for_model_count": len(invalid_rows),
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
    due_targets: list[dict[str, Any]],
    market_snapshot_docs: list[dict[str, Any]],
    error_count: int,
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not due_targets:
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
    captured_count = len({row["match_key"] for row in market_snapshot_docs})
    status = "ok" if captured_count == len(due_targets) and invalid_count == 0 and error_count == 0 else "warn"
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
                "eligible_match_count": len(due_targets),
                "captured_match_count": captured_count,
                "market_snapshot_count": len(market_snapshot_docs),
                "invalid_for_model_count": invalid_count,
                "error_count": error_count,
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
