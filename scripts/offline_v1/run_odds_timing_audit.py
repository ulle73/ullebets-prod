from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from ullebets_v1.audit.odds_timing import (
    AT_OR_AFTER_START_STATUS,
    PRE_MATCH_STATUS,
    annotate_backtest_timing,
    build_backtest_timing_summary,
    required_odds_rows,
)
from ullebets_v1.backtest.pipeline import (
    build_walk_forward_feature_columns,
    select_walk_forward_candidate_rows,
)
from ullebets_v1.backtest.walk_forward import WalkForwardConfig, run_walk_forward
from ullebets_v1.config import PipelineConfig
from ullebets_v1.logging_utils import configure_logging


def _strategy_summary(selections: pd.DataFrame) -> dict[str, dict]:
    if selections.empty:
        return {}
    grouped = (
        selections.groupby("strategy", dropna=False)["realized_roi_units"]
        .agg(["count", "sum"])
        .reset_index()
    )
    payload: dict[str, dict] = {}
    for row in grouped.itertuples(index=False):
        payload[str(row.strategy)] = {
            "bets": int(row.count),
            "pnl_units": float(row.sum),
            "roi_pct": float((row.sum / row.count) * 100.0) if row.count else 0.0,
        }
    return payload


def _segment_comparison(before: pd.DataFrame, after: pd.DataFrame) -> list[dict]:
    grouped_before = (
        before.groupby(["strategy", "stat_key", "period", "scope"], dropna=False)["realized_roi_units"]
        .agg(["count", "sum"])
        .reset_index()
        .rename(columns={"count": "before_bets", "sum": "before_pnl_units"})
    )
    grouped_after = (
        after.groupby(["strategy", "stat_key", "period", "scope"], dropna=False)["realized_roi_units"]
        .agg(["count", "sum"])
        .reset_index()
        .rename(columns={"count": "after_bets", "sum": "after_pnl_units"})
    )
    merged = grouped_before.merge(
        grouped_after,
        how="outer",
        on=["strategy", "stat_key", "period", "scope"],
    ).fillna(0)
    merged["before_bets"] = merged["before_bets"].astype(int)
    merged["after_bets"] = merged["after_bets"].astype(int)
    merged["before_roi_pct"] = merged.apply(
        lambda row: float((row["before_pnl_units"] / row["before_bets"]) * 100.0)
        if row["before_bets"]
        else 0.0,
        axis=1,
    )
    merged["after_roi_pct"] = merged.apply(
        lambda row: float((row["after_pnl_units"] / row["after_bets"]) * 100.0)
        if row["after_bets"]
        else 0.0,
        axis=1,
    )
    merged["bets_removed"] = merged["before_bets"] - merged["after_bets"]
    merged["pnl_delta_units"] = merged["after_pnl_units"] - merged["before_pnl_units"]
    merged["roi_delta_pct"] = merged["after_roi_pct"] - merged["before_roi_pct"]
    merged = merged[
        (merged["bets_removed"] != 0)
        | (merged["pnl_delta_units"].abs() > 1e-12)
        | (merged["roi_delta_pct"].abs() > 1e-12)
    ].copy()
    merged["abs_bets_removed"] = merged["bets_removed"].abs()
    merged["abs_pnl_delta_units"] = merged["pnl_delta_units"].abs()
    merged["abs_roi_delta_pct"] = merged["roi_delta_pct"].abs()
    merged = merged.sort_values(
        ["abs_bets_removed", "abs_pnl_delta_units", "abs_roi_delta_pct"],
        ascending=[False, False, False],
    )
    rows: list[dict] = []
    for row in merged.head(20).itertuples(index=False):
        rows.append(
            {
                "strategy": str(row.strategy),
                "stat_key": str(row.stat_key),
                "period": str(row.period),
                "scope": str(row.scope),
                "before_bets": int(row.before_bets),
                "after_bets": int(row.after_bets),
                "bets_removed": int(row.bets_removed),
                "before_roi_pct": float(row.before_roi_pct),
                "after_roi_pct": float(row.after_roi_pct),
                "roi_delta_pct": float(row.roi_delta_pct),
                "before_pnl_units": float(row.before_pnl_units),
                "after_pnl_units": float(row.after_pnl_units),
                "pnl_delta_units": float(row.pnl_delta_units),
            }
        )
    return rows


def _build_markdown(summary: dict) -> str:
    timing = summary["timing_audit"]
    collections = summary["time_field_provenance"]
    lines = ["# Odds Timing Leakage Audit", ""]
    lines.append(f"- Total tested odds rows: `{timing['total_tested_odds_rows']}`")
    lines.append(f"- Rows before matchstart: `{timing['rows_before_matchstart']}`")
    lines.append(f"- Rows at/after matchstart: `{timing['rows_at_or_after_matchstart']}`")
    lines.append(f"- Rows exactly at matchstart: `{timing['rows_exactly_at_matchstart']}`")
    lines.append(f"- Rows without snapshot_time: `{timing['rows_without_snapshot_time']}`")
    lines.append(f"- Rows without match_start_time: `{timing['rows_without_matchstart']}`")
    lines.append(f"- Candidate segments before strict filter: `{summary['candidate_segments_before_filter']}`")
    lines.append(f"- Candidate segments after strict filter: `{summary['candidate_segments_after_filter']}`")
    lines.append(f"- Excluded segments: `{summary['excluded_segments']}`")
    lines.append("")

    lines.append("## Time Fields Used")
    for label, value in collections.items():
        lines.append(f"- {label}: `{value}`")
    lines.append("")

    lines.append("## Snapshot Time Source Counts")
    for source, count in timing["snapshot_time_source_counts"].items():
        lines.append(f"- `{source}`: `{count}`")
    lines.append("")

    lines.append("## Match Start Time Source Counts")
    for source, count in timing["match_start_time_source_counts"].items():
        lines.append(f"- `{source}`: `{count}`")
    lines.append("")

    lines.append("## ROI Before vs After Filter")
    before = summary["roi_before_filter"]
    after = summary["roi_after_filter"]
    for strategy in sorted(set(before) | set(after)):
        before_payload = before.get(strategy, {"bets": 0, "pnl_units": 0.0, "roi_pct": 0.0})
        after_payload = after.get(strategy, {"bets": 0, "pnl_units": 0.0, "roi_pct": 0.0})
        lines.append(
            f"- `{strategy}` before: bets `{before_payload['bets']}`, ROI `{before_payload['roi_pct']:.2f}%`; "
            f"after: bets `{after_payload['bets']}`, ROI `{after_payload['roi_pct']:.2f}%`"
        )
    lines.append("")

    affected = summary["most_affected_segments"]
    if affected:
        lines.append("## Most Affected Segments")
        for row in affected:
            lines.append(
                f"- `{row['strategy']}` `{row['stat_key']}` `{row['period']}` `{row['scope']}`: "
                f"bets `{row['before_bets']}` -> `{row['after_bets']}`, "
                f"ROI `{row['before_roi_pct']:.2f}%` -> `{row['after_roi_pct']:.2f}%`"
            )
        lines.append("")

    leakage_rows = summary["leakage_risk_rows"]
    if leakage_rows:
        lines.append("## Leakage-Risk Rows")
        for row in leakage_rows[:20]:
            lines.append(
                f"- match `{row['match_id']}` `{row['stat_key']}` `{row['period']}` `{row['scope']}` `{row['direction']}` line `{row['line_value']}`: "
                f"`{row['snapshot_time_source']}` at `{row['snapshot_time']}` vs start `{row['match_start_time']}`"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    configure_logging()
    config = PipelineConfig.from_env()
    config.ensure_directories()

    features = pd.read_parquet(config.features_dir / "market_points_primary.parquet")
    market_lines = pd.read_parquet(config.normalized_dir / "market_lines.parquet")

    audited = annotate_backtest_timing(features, market_lines)
    before_features = select_walk_forward_candidate_rows(
        audited,
        enforce_strict_prematch=False,
    )
    before_features = before_features[before_features["actual_value"].notna()].copy()
    after_features = select_walk_forward_candidate_rows(
        audited,
        enforce_strict_prematch=True,
    )
    after_features = after_features[after_features["actual_value"].notna()].copy()
    feature_columns, categorical_columns = build_walk_forward_feature_columns(before_features)

    before_summary_df, before_selections = run_walk_forward(
        before_features,
        feature_columns=feature_columns,
        categorical_columns=categorical_columns,
        config=WalkForwardConfig(),
    )
    after_summary_df, after_selections = run_walk_forward(
        after_features,
        feature_columns=feature_columns,
        categorical_columns=categorical_columns,
        config=WalkForwardConfig(),
    )

    timing_candidates = before_features.copy()
    timing_summary = build_backtest_timing_summary(timing_candidates)
    odds_rows = required_odds_rows(timing_candidates)
    leakage_rows = odds_rows[odds_rows["timing_status"] == AT_OR_AFTER_START_STATUS].copy()
    leakage_rows = leakage_rows[
        [
            "match_id",
            "stat_key",
            "period",
            "scope",
            "direction",
            "line_value",
            "snapshot_time_source",
            "snapshot_time",
            "match_start_time",
        ]
    ]
    leakage_rows["snapshot_time"] = leakage_rows["snapshot_time"].astype("string")
    leakage_rows["match_start_time"] = leakage_rows["match_start_time"].astype("string")

    summary = {
        "timing_audit": timing_summary,
        "time_field_provenance": {
            "snapshot_time_fields": "unibet-backtest snapshots.snapshot_fetched_at -> unibet-backtest lines.updated_at -> unibet-backtest lines.generated_at",
            "match_start_time_field": "teamstats.kickoff_ts",
        },
        "candidate_segments_before_filter": int(len(before_features)),
        "candidate_segments_after_filter": int(len(after_features)),
        "excluded_segments": int(len(before_features) - len(after_features)),
        "roi_before_filter": _strategy_summary(before_selections),
        "roi_after_filter": _strategy_summary(after_selections),
        "before_window_count": int(len(before_summary_df)),
        "after_window_count": int(len(after_summary_df)),
        "most_affected_segments": _segment_comparison(before_selections, after_selections),
        "leakage_risk_rows": leakage_rows.to_dict(orient="records"),
    }

    report_md = _build_markdown(summary)
    json_path = config.reports_dir / "odds_timing_audit.json"
    md_path = config.reports_dir / "odds_timing_audit.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md_path.write_text(report_md, encoding="utf-8")
    print(f"wrote_odds_timing_audit_json={json_path}")
    print(f"wrote_odds_timing_audit_markdown={md_path}")


if __name__ == "__main__":
    main()
