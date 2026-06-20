from __future__ import annotations

import json

import pandas as pd


def build_signal_findings(*, strongest: list[dict], filtered: list[dict]) -> dict:
    return {
        "strongest_segments": strongest,
        "filtered_reasons": filtered,
    }


def build_signal_report(audit_summary: dict, walk_forward_summary: pd.DataFrame, selections: pd.DataFrame) -> str:
    lines = ["# Offline V1 Signal Report", ""]
    lines.append(f"- Market lines kept after quality filters: `{audit_summary['market_line_rows_kept']}`")
    lines.append(f"- Primary target rows kept: `{audit_summary['primary_target_rows_kept']}`")
    lines.append(f"- Teamstats-covered rows: `{audit_summary['teamstats_covered_rows']}`")
    lines.append(f"- CLV-covered rows: `{audit_summary['clv_covered_rows']}`")
    lines.append(
        "- Walk-forward universe: canonical model-eligible lines only, with two-sided cornerKicks and over-only totalShots/shotsOnGoal."
    )
    lines.append("")
    completeness = audit_summary.get("primary_target_market_completeness", {})
    if completeness:
        lines.append("## Primary Target Completeness")
        for stat_key, payload in completeness.items():
            lines.append(
                f"- `{stat_key}`: policy `{payload['market_side_policy']}`, segments `{payload['kept_segments']}`, "
                f"model-ready `{payload['model_ready_segments']}`, "
                f"two-sided `{payload['two_sided_segments']}`, "
                f"over-only `{payload['over_only_segments']}`, "
                f"under-only `{payload['under_only_segments']}`"
            )
        lines.append("")
    if not walk_forward_summary.empty:
        lines.append("## Walk-Forward Windows")
        for row in walk_forward_summary.itertuples(index=False):
            lines.append(
                f"- `{row.window_start}` to `{row.window_end}`: "
                f"model bets `{row.model_bets}` ROI `{row.model_roi_pct:.2f}%`, "
                f"baseline bets `{row.baseline_bets}` ROI `{row.baseline_roi_pct:.2f}%`"
            )
        lines.append("")
    if not selections.empty:
        grouped = (
            selections.groupby(["strategy", "stat_key", "period", "scope"], dropna=False)["realized_roi_units"]
            .agg(["count", "sum"])
            .reset_index()
            .sort_values(["strategy", "sum"], ascending=[True, False])
        )
        lines.append("## Top Segments")
        for row in grouped.head(20).itertuples(index=False):
            roi_pct = (row.sum / row.count) * 100.0 if row.count else 0.0
            lines.append(
                f"- `{row.strategy}` `{row.stat_key}` `{row.period}` `{row.scope}`: "
                f"{row.count} bets, ROI `{roi_pct:.2f}%`"
            )
    return "\n".join(lines) + "\n"
