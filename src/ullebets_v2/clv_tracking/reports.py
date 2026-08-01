from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, build_parity_report_row
from ullebets_v2.storage.collections import CLV_TRACKING, FORWARD_BETS


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _workflow_entry() -> dict[str, Any]:
    return {
        "old_workflow": "closing-line-tracking",
        "old_inputs": ["result-loop tracked odds", "market observations"],
        "old_outputs": ["closing-line-tracking"],
        "v2_job": "refresh_clv_tracking.py",
        "v2_outputs": [FORWARD_BETS, CLV_TRACKING, "audit_reports"],
        "smoke_test": "dry-run with synthetic tracked bets and canonical closing lines",
        "parity_proof": "compare saved odds, direction-specific opening/latest/closing odds, beat-close flags, and CLV percentages against the legacy closing-line-tracking semantics",
    }


def _count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "missing") for row in rows))


def _float_matches(left: Any, right: Any, *, precision: int = 4) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    try:
        return round(float(left), precision) == round(float(right), precision)
    except (TypeError, ValueError):
        return False


def _legacy_clv_mismatch_counts(
    clv_docs: list[dict[str, Any]],
    legacy_reference_docs: list[dict[str, Any]],
) -> dict[str, int]:
    reference_by_key = {
        str(row.get("tracking_key") or ""): row
        for row in legacy_reference_docs
        if row.get("tracking_key") is not None
    }
    comparable = 0
    missing_reference = 0
    saved_odds_mismatch = 0
    opening_odds_mismatch = 0
    latest_odds_mismatch = 0
    closing_odds_mismatch = 0
    clv_pct_mismatch = 0
    implied_edge_delta_mismatch = 0
    beat_close_mismatch = 0
    prematch_count_mismatch = 0
    matched_keys: set[str] = set()

    for row in clv_docs:
        tracking_key = str(row.get("tracking_key") or "")
        reference = reference_by_key.get(tracking_key)
        if reference is None:
            missing_reference += 1
            continue
        matched_keys.add(tracking_key)
        comparable += 1
        if not _float_matches(row.get("saved_odds"), reference.get("saved_odds")):
            saved_odds_mismatch += 1
        if not _float_matches(row.get("opening_odds"), reference.get("opening_odds")):
            opening_odds_mismatch += 1
        if not _float_matches(row.get("latest_observed_odds"), reference.get("latest_observed_odds")):
            latest_odds_mismatch += 1
        if not _float_matches(row.get("closing_odds"), reference.get("closing_odds")):
            closing_odds_mismatch += 1
        if not _float_matches(row.get("clv_pct"), reference.get("clv_pct"), precision=1):
            clv_pct_mismatch += 1
        if not _float_matches(row.get("implied_edge_delta"), reference.get("implied_edge_delta"), precision=2):
            implied_edge_delta_mismatch += 1
        if row.get("beat_closing_line") != reference.get("beat_closing_line"):
            beat_close_mismatch += 1
        if int(row.get("prematch_observation_count") or 0) != int(reference.get("prematch_observation_count") or 0):
            prematch_count_mismatch += 1

    reference_only = sum(1 for key in reference_by_key if key not in matched_keys)
    return {
        "legacy_reference_count": len(reference_by_key),
        "legacy_comparable_count": comparable,
        "legacy_missing_reference_count": missing_reference,
        "legacy_reference_only_count": reference_only,
        "legacy_saved_odds_mismatch_count": saved_odds_mismatch,
        "legacy_opening_odds_mismatch_count": opening_odds_mismatch,
        "legacy_latest_odds_mismatch_count": latest_odds_mismatch,
        "legacy_closing_odds_mismatch_count": closing_odds_mismatch,
        "legacy_clv_pct_mismatch_count": clv_pct_mismatch,
        "legacy_implied_edge_delta_mismatch_count": implied_edge_delta_mismatch,
        "legacy_beat_close_mismatch_count": beat_close_mismatch,
        "legacy_prematch_count_mismatch_count": prematch_count_mismatch,
    }


def build_clv_tracking_parity_rows(
    *,
    tracked_bet_docs: list[dict[str, Any]],
    clv_docs: list[dict[str, Any]],
    legacy_reference_docs: list[dict[str, Any]] | None = None,
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not tracked_bet_docs:
        return [
            build_parity_report_row(
                workflow_entry=_workflow_entry(),
                counts_old={"tracked_bet_count": 0, "tracked_count": 0},
                counts_v2={"tracked_bet_count": 0, "tracked_count": 0},
                parity_status="no_targets",
                blocking_issues=[],
                audit_risks=[],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(clv_docs, "clv_status")
    invalid_timing_count = status_counts.get("invalid_snapshot_timing", 0)
    legacy_mismatches = (
        _legacy_clv_mismatch_counts(clv_docs, legacy_reference_docs)
        if legacy_reference_docs
        else {
            "legacy_reference_count": 0,
            "legacy_comparable_count": 0,
            "legacy_missing_reference_count": 0,
            "legacy_reference_only_count": 0,
            "legacy_saved_odds_mismatch_count": 0,
            "legacy_opening_odds_mismatch_count": 0,
            "legacy_latest_odds_mismatch_count": 0,
            "legacy_closing_odds_mismatch_count": 0,
            "legacy_clv_pct_mismatch_count": 0,
            "legacy_implied_edge_delta_mismatch_count": 0,
            "legacy_beat_close_mismatch_count": 0,
            "legacy_prematch_count_mismatch_count": 0,
        }
    )
    blocking_issues = ["invalid_snapshot_timing_present"] if invalid_timing_count else []
    if legacy_mismatches["legacy_missing_reference_count"]:
        blocking_issues.append("legacy_missing_reference_rows_present")
    if legacy_mismatches["legacy_reference_only_count"]:
        blocking_issues.append("legacy_reference_only_rows_present")
    if legacy_mismatches["legacy_saved_odds_mismatch_count"]:
        blocking_issues.append("legacy_saved_odds_mismatches_present")
    if legacy_mismatches["legacy_opening_odds_mismatch_count"]:
        blocking_issues.append("legacy_opening_odds_mismatches_present")
    if legacy_mismatches["legacy_latest_odds_mismatch_count"]:
        blocking_issues.append("legacy_latest_odds_mismatches_present")
    if legacy_mismatches["legacy_closing_odds_mismatch_count"]:
        blocking_issues.append("legacy_closing_odds_mismatches_present")
    if legacy_mismatches["legacy_clv_pct_mismatch_count"]:
        blocking_issues.append("legacy_clv_pct_mismatches_present")
    if legacy_mismatches["legacy_implied_edge_delta_mismatch_count"]:
        blocking_issues.append("legacy_implied_edge_delta_mismatches_present")
    if legacy_mismatches["legacy_beat_close_mismatch_count"]:
        blocking_issues.append("legacy_beat_close_mismatches_present")
    if legacy_mismatches["legacy_prematch_count_mismatch_count"]:
        blocking_issues.append("legacy_prematch_count_mismatches_present")
    parity_status = "matched" if not blocking_issues else "mismatch"
    audit_risks: list[str] = []
    if status_counts.get("missing_closing_line", 0):
        audit_risks.append("closing_coverage_gap")
    if invalid_timing_count:
        audit_risks.append("timing_leakage_risk")
    if status_counts.get("tracked_fallback_t30", 0):
        audit_risks.append("t30_fallback_clv_present")
    if legacy_reference_docs and parity_status != "matched":
        audit_risks.append("legacy_clv_parity_risk")
    return [
        build_parity_report_row(
            workflow_entry=_workflow_entry(),
            counts_old={"tracked_bet_count": len(tracked_bet_docs)},
            counts_v2={
                "tracked_bet_count": len(tracked_bet_docs),
                "tracked_count": len(clv_docs),
                "status_counts": status_counts,
                **legacy_mismatches,
            },
            parity_status=parity_status,
            blocking_issues=blocking_issues,
            audit_risks=audit_risks,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_clv_tracking_audit_rows(
    *,
    clv_docs: list[dict[str, Any]],
    legacy_reference_docs: list[dict[str, Any]] | None = None,
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not clv_docs:
        return [
            build_audit_report_row(
                audit_type="clv_tracking",
                scope_key="closing-line-tracking",
                status="ok",
                metrics={"tracked_count": 0},
                findings=["no_tracked_bets_to_track"],
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(clv_docs, "clv_status")
    legacy_mismatches = (
        _legacy_clv_mismatch_counts(clv_docs, legacy_reference_docs)
        if legacy_reference_docs
        else {
            "legacy_reference_count": 0,
            "legacy_comparable_count": 0,
            "legacy_missing_reference_count": 0,
            "legacy_reference_only_count": 0,
            "legacy_saved_odds_mismatch_count": 0,
            "legacy_opening_odds_mismatch_count": 0,
            "legacy_latest_odds_mismatch_count": 0,
            "legacy_closing_odds_mismatch_count": 0,
            "legacy_clv_pct_mismatch_count": 0,
            "legacy_implied_edge_delta_mismatch_count": 0,
            "legacy_beat_close_mismatch_count": 0,
            "legacy_prematch_count_mismatch_count": 0,
        }
    )
    findings: list[str] = []
    if status_counts.get("missing_closing_line", 0):
        findings.append("missing_closing_lines_present")
    if status_counts.get("missing_selected_odds", 0):
        findings.append("missing_selected_or_closing_odds_present")
    if status_counts.get("invalid_snapshot_timing", 0):
        findings.append("invalid_snapshot_timing_present")
    if status_counts.get("tracked_fallback_t30", 0):
        findings.append("t30_fallback_clv_reported_separately")
    if legacy_mismatches["legacy_missing_reference_count"]:
        findings.append("legacy_missing_reference_rows_present")
    if legacy_mismatches["legacy_reference_only_count"]:
        findings.append("legacy_reference_only_rows_present")
    if legacy_mismatches["legacy_saved_odds_mismatch_count"]:
        findings.append("legacy_saved_odds_mismatches_present")
    if legacy_mismatches["legacy_opening_odds_mismatch_count"]:
        findings.append("legacy_opening_odds_mismatches_present")
    if legacy_mismatches["legacy_latest_odds_mismatch_count"]:
        findings.append("legacy_latest_odds_mismatches_present")
    if legacy_mismatches["legacy_closing_odds_mismatch_count"]:
        findings.append("legacy_closing_odds_mismatches_present")
    if legacy_mismatches["legacy_clv_pct_mismatch_count"]:
        findings.append("legacy_clv_pct_mismatches_present")
    if legacy_mismatches["legacy_implied_edge_delta_mismatch_count"]:
        findings.append("legacy_implied_edge_delta_mismatches_present")
    if legacy_mismatches["legacy_beat_close_mismatch_count"]:
        findings.append("legacy_beat_close_mismatches_present")
    if legacy_mismatches["legacy_prematch_count_mismatch_count"]:
        findings.append("legacy_prematch_count_mismatches_present")
    status = "warn" if (
        status_counts.get("invalid_snapshot_timing", 0)
        or legacy_mismatches["legacy_missing_reference_count"]
        or legacy_mismatches["legacy_reference_only_count"]
        or legacy_mismatches["legacy_saved_odds_mismatch_count"]
        or legacy_mismatches["legacy_opening_odds_mismatch_count"]
        or legacy_mismatches["legacy_latest_odds_mismatch_count"]
        or legacy_mismatches["legacy_closing_odds_mismatch_count"]
        or legacy_mismatches["legacy_clv_pct_mismatch_count"]
        or legacy_mismatches["legacy_implied_edge_delta_mismatch_count"]
        or legacy_mismatches["legacy_beat_close_mismatch_count"]
        or legacy_mismatches["legacy_prematch_count_mismatch_count"]
    ) else "ok"
    tracked_rows = [
        row
        for row in clv_docs
        if row.get("clv_status") == "tracked"
        and (
            row.get("official_clv") is True
            or row.get("closing_snapshot_label") == "T_MINUS_10M"
            or row.get("closing_quality") == "t10"
        )
    ]
    fallback_rows = [
        row for row in clv_docs if row.get("clv_status") == "tracked_fallback_t30"
    ]
    return [
        build_audit_report_row(
            audit_type="clv_tracking",
            scope_key="closing-line-tracking",
            status=status,
            metrics={
                "tracked_count": len(clv_docs),
                "tracked_with_clv_count": len(tracked_rows),
                "official_clv_count": sum(
                    1 for row in tracked_rows if row.get("official_clv") is True
                ),
                "fallback_t30_clv_count": len(fallback_rows),
                "beat_close_count": sum(1 for row in tracked_rows if row.get("beat_closing_line") is True),
                "status_counts": status_counts,
                **legacy_mismatches,
            },
            findings=findings,
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]


def build_clv_tracking_health_rows(
    *,
    clv_docs: list[dict[str, Any]],
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    if not clv_docs:
        return [
            build_health_report_row(
                job_name="refresh_clv_tracking",
                status="ok",
                summary="No tracked bet rows required CLV refresh.",
                metrics={"tracked_count": 0},
                report_date=report_date or utc_now().date().isoformat(),
            )
        ]

    status_counts = _count_by(clv_docs, "clv_status")
    status = "ok" if status_counts.get("invalid_snapshot_timing", 0) == 0 else "warn"
    return [
        build_health_report_row(
            job_name="refresh_clv_tracking",
            status=status,
            summary=(
                "CLV tracking refreshed from canonical closing lines."
                if status == "ok"
                else "CLV tracking found invalid snapshot timing rows."
            ),
            metrics={
                "tracked_count": len(clv_docs),
                "tracked_with_clv_count": sum(
                    1
                    for row in clv_docs
                    if row.get("clv_status") == "tracked"
                    and (
                        row.get("official_clv") is True
                        or row.get("closing_snapshot_label") == "T_MINUS_10M"
                        or row.get("closing_quality") == "t10"
                    )
                ),
                "fallback_t30_clv_count": status_counts.get("tracked_fallback_t30", 0),
                "missing_closing_line_count": status_counts.get("missing_closing_line", 0),
                "invalid_snapshot_timing_count": status_counts.get("invalid_snapshot_timing", 0),
            },
            report_date=report_date or utc_now().date().isoformat(),
        )
    ]
