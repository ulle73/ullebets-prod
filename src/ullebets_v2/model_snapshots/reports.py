from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def build_model_snapshot_parity_rows(
    *,
    source_workflow: str,
    target_matches: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    model_snapshot_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not target_matches:
        return [
            build_parity_report_row(
                workflow_entry={
                    "old_workflow": source_workflow,
                    "old_inputs": ["fixtures", "Unibet/Kambi", "legacy JS EV engine"],
                    "old_outputs": ["unibet-backtest snapshot lines"],
                    "v2_job": "build_model_snapshots.py",
                    "v2_outputs": ["raw_odds_kambi", "unibet_event_links", "market_offers", "model_snapshots"],
                    "smoke_test": "dry-run current selection window",
                    "parity_proof": "treat no eligible targets as a clean no-op while keeping the line-generation oracle unchanged",
                },
                counts_old={"target_match_count": 0, "line_count": 0},
                counts_v2={"target_match_count": 0, "line_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    line_errors = sum(len(row.get("model_errors", [])) for row in match_rows)
    offerless_matches = [
        row["match_key"]
        for row in match_rows
        if row.get("v2_event_id") and int(row.get("v2_offer_count", 0)) == 0
    ]
    missing_matches = [
        row["match_key"]
        for row in match_rows
        if row.get("v2_event_id")
        and int(row.get("v2_offer_count", 0)) > 0
        and row.get("generated_line_count", 0) == 0
    ]
    parity_status = "matched" if line_errors == 0 and not missing_matches else "mismatch"
    return [
        build_parity_report_row(
            workflow_entry={
                "old_workflow": source_workflow,
                "old_inputs": ["fixtures", "Unibet/Kambi", "legacy JS EV engine"],
                "old_outputs": ["unibet-backtest snapshot lines"],
                "v2_job": "build_model_snapshots.py",
                "v2_outputs": ["raw_odds_kambi", "unibet_event_links", "market_offers", "model_snapshots"],
                "smoke_test": "dry-run replay or live window against unchanged JS EV engine",
                "parity_proof": "V2 delegates directed line generation to the original JS EV engine, then compares generated line coverage and mode/label counts before persistence",
            },
            counts_old={
                "target_match_count": len(target_matches),
                "line_count": sum(int(row.get("generated_line_count", 0)) for row in match_rows),
                "line_count_by_match": {row["match_key"]: int(row.get("generated_line_count", 0)) for row in match_rows},
            },
            counts_v2={
                "target_match_count": len({row["match_key"] for row in model_snapshot_docs}),
                "line_count": len(model_snapshot_docs),
                "offerless_match_count": len(offerless_matches),
                "snapshot_mode_counts": _count_by(model_snapshot_docs, "snapshot_mode"),
                "direction_counts": _count_by(model_snapshot_docs, "direction"),
            },
            parity_status=parity_status,
            blocking_issues=[f"missing_model_lines:{match_key}" for match_key in missing_matches]
            + (["model_oracle_errors_present"] if line_errors else []),
            audit_risks=[] if parity_status == "matched" else ["model_snapshot_generation_risk"],
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_model_snapshot_audit_rows(
    *,
    source_workflow: str,
    target_matches: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    model_snapshot_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not target_matches:
        return [
            build_audit_report_row(
                audit_type="model_snapshots",
                scope_key=source_workflow,
                status="ok",
                metrics={
                    "target_match_count": 0,
                    "matched_event_count": 0,
                    "generated_line_count": 0,
                    "invalid_for_model_count": 0,
                    "oracle_error_count": 0,
                },
                findings=["no_due_targets_in_requested_window"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    invalid_count = sum(1 for row in model_snapshot_docs if row.get("invalid_for_model"))
    oracle_error_count = sum(len(row.get("model_errors", [])) for row in match_rows)
    unmatched_count = sum(1 for row in match_rows if not row.get("v2_event_id"))
    offerless_match_count = sum(
        1
        for row in match_rows
        if row.get("v2_event_id") and int(row.get("v2_offer_count", 0)) == 0
    )
    status = "ok" if invalid_count == 0 and oracle_error_count == 0 and unmatched_count == 0 else "warn"
    findings: list[str] = []
    if invalid_count:
        findings.append("post_start_model_rows_present")
    if oracle_error_count:
        findings.append("model_oracle_errors_present")
    if unmatched_count:
        findings.append("unmatched_unibet_events_present")
    if offerless_match_count:
        findings.append("no_model_eligible_offers_for_some_matches")
    return [
        build_audit_report_row(
            audit_type="model_snapshots",
            scope_key=source_workflow,
            status=status,
            metrics={
                "target_match_count": len(target_matches),
                "matched_event_count": sum(1 for row in match_rows if row.get("v2_event_id")),
                "generated_line_count": len(model_snapshot_docs),
                "invalid_for_model_count": invalid_count,
                "oracle_error_count": oracle_error_count,
                "unmatched_event_count": unmatched_count,
                "offerless_match_count": offerless_match_count,
                "direction_counts": _count_by(model_snapshot_docs, "direction"),
                "formula_counts": _count_by(model_snapshot_docs, "primary_formula_key"),
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_model_snapshot_health_rows(
    *,
    target_matches: list[dict[str, Any]],
    model_snapshot_docs: list[dict[str, Any]],
    oracle_error_count: int,
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not target_matches:
        return [
            build_health_report_row(
                job_name="build_model_snapshots",
                status="ok",
                summary="No eligible model snapshot targets were present in the requested window.",
                metrics={
                    "target_match_count": 0,
                    "generated_line_count": 0,
                    "oracle_error_count": 0,
                },
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    invalid_count = sum(1 for row in model_snapshot_docs if row.get("invalid_for_model"))
    matches_with_offers = sum(1 for row in target_matches if True)
    offerful_match_count = sum(
        1
        for row in target_matches
        if row.get("match_key") in {match_row["match_key"] for match_row in model_snapshot_docs}
    )
    status = "ok" if invalid_count == 0 and oracle_error_count == 0 else "warn"
    return [
        build_health_report_row(
            job_name="build_model_snapshots",
            status=status,
            summary=(
                "Model snapshot generation produced directed prematch bet rows."
                if model_snapshot_docs
                else "Model snapshot generation found no model-eligible prematch offers in the captured window."
            )
            if status == "ok"
            else (
                "Model snapshot generation completed with missing rows, oracle errors, or post-start timing."
            ),
            metrics={
                "target_match_count": len(target_matches),
                "generated_line_count": len(model_snapshot_docs),
                "invalid_for_model_count": invalid_count,
                "oracle_error_count": oracle_error_count,
                "offerful_match_count": offerful_match_count,
                "matches_considered": matches_with_offers,
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
