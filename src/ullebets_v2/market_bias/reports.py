from __future__ import annotations

from typing import Any

from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row

MARKET_BIAS_AUDIT_METRICS = (
    "timing_rejection_count",
    "missing_actual_count",
    "unmatched_identity_count",
    "invalid_row_count",
    "duplicate_observation_key_count",
    "source_hash_conflict_count",
    "qualifying_line_failure_count",
    "counts_by_stat",
    "counts_by_scope",
    "counts_by_period",
    "counts_by_league",
    "counts_by_snapshot_label",
)


def _complete_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "timing_rejection_count": 0,
        "missing_actual_count": 0,
        "unmatched_identity_count": 0,
        "invalid_row_count": 0,
        "duplicate_observation_key_count": 0,
        "source_hash_conflict_count": 0,
        "qualifying_line_failure_count": 0,
        "counts_by_stat": {},
        "counts_by_scope": {},
        "counts_by_period": {},
        "counts_by_league": {},
        "counts_by_snapshot_label": {},
    }
    return {**defaults, **metrics}


def build_market_bias_audit_rows(*, source_workflow: str, metrics: dict[str, Any], report_date: str) -> list[dict[str, Any]]:
    complete = _complete_metrics(metrics)
    hard_failures = sum(int(complete[field]) for field in ("duplicate_observation_key_count", "source_hash_conflict_count"))
    findings = [field for field in MARKET_BIAS_AUDIT_METRICS if isinstance(complete[field], int) and complete[field] > 0]
    return [
        build_audit_report_row(
            audit_type="market_bias_refresh",
            scope_key=source_workflow,
            status="failed" if hard_failures else "ok",
            metrics=complete,
            findings=findings,
            report_date=report_date,
        )
    ]


def build_market_bias_health_rows(*, metrics: dict[str, Any], report_date: str) -> list[dict[str, Any]]:
    complete = _complete_metrics(metrics)
    warning_count = sum(int(complete[field]) for field in MARKET_BIAS_AUDIT_METRICS[:7])
    return [
        build_health_report_row(
            job_name="refresh_market_bias",
            status="ok" if warning_count == 0 else "warn",
            summary="Market-bias refresh completed." if warning_count == 0 else "Market-bias refresh completed with rejected or incomplete candidate rows.",
            metrics=complete,
            report_date=report_date,
        )
    ]
