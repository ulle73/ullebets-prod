from __future__ import annotations

from typing import Any

from ullebets_v2.clv_tracking.service import run_clv_tracking_refresh
from ullebets_v2.forward_results.service import run_forward_result_refresh


def _compact_summary(summary: dict[str, Any], document_key: str) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if key != document_key}


def refresh_closing_dependents(
    *,
    database: Any,
    closing_summary: dict[str, Any],
    dry_run: bool,
) -> dict[str, Any]:
    closing_line_docs = list(closing_summary.get("closing_line_docs") or [])
    if not closing_line_docs:
        return {
            "status": "skipped",
            "reason": "no_closing_lines_materialized",
        }

    clv_summary = run_clv_tracking_refresh(
        closing_line_docs=closing_line_docs,
        database=database,
        dry_run=dry_run,
    )
    forward_summary = run_forward_result_refresh(
        clv_tracking_docs=clv_summary["clv_docs"],
        closing_line_docs=closing_line_docs,
        database=database,
        dry_run=dry_run,
    )
    return {
        "status": "refreshed",
        "clv": _compact_summary(clv_summary, "clv_docs"),
        "forward_results": _compact_summary(forward_summary, "result_docs"),
    }
