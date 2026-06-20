from __future__ import annotations

import json

import pandas as pd


def _bucket_odds(value: object) -> str:
    if value is None or pd.isna(value):
        return "missing"
    odds = float(value)
    if odds < 1.6:
        return "1.00-1.59"
    if odds < 1.9:
        return "1.60-1.89"
    if odds < 2.2:
        return "1.90-2.19"
    if odds < 2.6:
        return "2.20-2.59"
    return "2.60+"


def _bucket_lead_minutes(value: object) -> str:
    if value is None or pd.isna(value):
        return "missing"
    minutes = float(value)
    if minutes < 60:
        return "<1h"
    if minutes < 180:
        return "1-3h"
    if minutes < 720:
        return "3-12h"
    if minutes < 1440:
        return "12-24h"
    return "24h+"


def _roi_summary(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {"bets": 0, "pnl_units": 0.0, "roi_pct": 0.0}
    pnl_units = float(frame["realized_roi_units"].dropna().sum())
    return {
        "bets": int(len(frame)),
        "pnl_units": pnl_units,
        "roi_pct": float((pnl_units / len(frame)) * 100.0) if len(frame) else 0.0,
    }


def build_model_diagnostics(feature_frame: pd.DataFrame, selections: pd.DataFrame) -> dict:
    diagnostics: dict = {
        "feature_universe": {},
        "selection_summary": {},
        "selection_breakdowns": {},
        "reality_checks": [],
    }

    if not feature_frame.empty:
        diagnostics["feature_universe"] = {
            "rows": int(len(feature_frame)),
            "effective_odds_source_counts": feature_frame.get(
                "effective_odds_source", pd.Series(dtype="object")
            ).fillna("missing").value_counts().to_dict(),
            "latest_snapshot_type_counts": feature_frame.get(
                "latest_snapshot_type", pd.Series(dtype="object")
            ).fillna("missing").value_counts().to_dict(),
            "latest_snapshot_minutes_summary": feature_frame.get(
                "latest_snapshot_minutes_before_kickoff", pd.Series(dtype="float64")
            ).dropna().describe().to_dict()
            if "latest_snapshot_minutes_before_kickoff" in feature_frame.columns
            and not feature_frame["latest_snapshot_minutes_before_kickoff"].dropna().empty
            else None,
        }

    if selections.empty:
        return diagnostics

    selection_frame = selections.copy()
    selection_frame["odds_bucket"] = selection_frame["selected_odds"].map(_bucket_odds)
    selection_frame["lead_time_bucket"] = selection_frame.get(
        "latest_snapshot_minutes_before_kickoff", pd.Series(dtype="float64")
    ).map(_bucket_lead_minutes)

    bets_per_match = selection_frame.groupby(["strategy", "match_id"]).size().rename("bets_per_match").reset_index()
    one_pick_per_match = (
        selection_frame.sort_values(
            ["strategy", "match_id", "expected_roi_units"],
            ascending=[True, True, False],
        )
        .drop_duplicates(subset=["strategy", "match_id"], keep="first")
        .copy()
    )

    diagnostics["selection_summary"] = {
        "overall_by_strategy": {
            strategy: _roi_summary(group)
            for strategy, group in selection_frame.groupby("strategy", dropna=False)
        },
        "one_pick_per_match_by_strategy": {
            strategy: _roi_summary(group)
            for strategy, group in one_pick_per_match.groupby("strategy", dropna=False)
        },
        "bets_per_match_by_strategy": (
            bets_per_match.groupby("strategy", dropna=False)["bets_per_match"]
            .describe()
            .round(4)
            .to_dict()
        ),
        "clv_covered_by_strategy": {
            strategy: int(group["selected_clv_pct"].notna().sum())
            for strategy, group in selection_frame.groupby("strategy", dropna=False)
        },
    }

    def _grouped_breakdown(frame: pd.DataFrame, columns: list[str]) -> list[dict]:
        grouped = (
            frame.groupby(columns, dropna=False)["realized_roi_units"]
            .agg(["count", "sum"])
            .reset_index()
            .sort_values(["sum", "count"], ascending=[False, False])
        )
        rows: list[dict] = []
        for row in grouped.head(20).itertuples(index=False):
            payload = {columns[index]: getattr(row, columns[index]) for index in range(len(columns))}
            payload["bets"] = int(row.count)
            payload["pnl_units"] = float(row.sum)
            payload["roi_pct"] = float((row.sum / row.count) * 100.0) if row.count else 0.0
            rows.append(payload)
        return rows

    diagnostics["selection_breakdowns"] = {
        "by_league": _grouped_breakdown(selection_frame, ["strategy", "league_name"]),
        "by_segment": _grouped_breakdown(selection_frame, ["strategy", "stat_key", "period", "scope"]),
        "by_odds_bucket": _grouped_breakdown(selection_frame, ["strategy", "odds_bucket"]),
        "by_lead_time_bucket": _grouped_breakdown(selection_frame, ["strategy", "lead_time_bucket"]),
    }

    mean_bets_per_match = (
        bets_per_match.groupby("strategy", dropna=False)["bets_per_match"].mean().to_dict()
    )
    for strategy, value in mean_bets_per_match.items():
        if value > 2:
            diagnostics["reality_checks"].append(
                f"{strategy} averages {value:.2f} bets per match, so flat ROI is exposed to correlated same-match risk."
            )

    overall = diagnostics["selection_summary"]["overall_by_strategy"].get("poisson_model", {})
    clv_count = diagnostics["selection_summary"]["clv_covered_by_strategy"].get("poisson_model", 0)
    if overall.get("roi_pct", 0.0) > 20 and clv_count < 50:
        diagnostics["reality_checks"].append(
            "Poisson-model ROI is very high while CLV coverage is still thin, so edge remains unproven."
        )

    return diagnostics


def build_model_diagnostics_markdown(diagnostics: dict) -> str:
    lines = ["# Offline V1 Model Diagnostics", ""]

    feature_universe = diagnostics.get("feature_universe") or {}
    if feature_universe:
        lines.append("## Feature Universe")
        lines.append(f"- Rows: `{feature_universe.get('rows', 0)}`")
        if feature_universe.get("effective_odds_source_counts"):
            lines.append(
                f"- Effective odds sources: `{json.dumps(feature_universe['effective_odds_source_counts'], ensure_ascii=False)}`"
            )
        if feature_universe.get("latest_snapshot_type_counts"):
            lines.append(
                f"- Latest snapshot types: `{json.dumps(feature_universe['latest_snapshot_type_counts'], ensure_ascii=False)}`"
            )
        snapshot_summary = feature_universe.get("latest_snapshot_minutes_summary")
        if snapshot_summary:
            lines.append(
                f"- Snapshot lead-time minutes: median `{snapshot_summary.get('50%'):.1f}`, "
                f"mean `{snapshot_summary.get('mean'):.1f}`, "
                f"min `{snapshot_summary.get('min'):.1f}`, max `{snapshot_summary.get('max'):.1f}`"
            )
        lines.append("")

    selection_summary = diagnostics.get("selection_summary") or {}
    overall = selection_summary.get("overall_by_strategy") or {}
    constrained = selection_summary.get("one_pick_per_match_by_strategy") or {}
    if overall:
        lines.append("## Selection Summary")
        for strategy, payload in overall.items():
            lines.append(
                f"- `{strategy}` official: bets `{payload['bets']}`, pnl `{payload['pnl_units']:.2f}`, ROI `{payload['roi_pct']:.2f}%`"
            )
        for strategy, payload in constrained.items():
            lines.append(
                f"- `{strategy}` one-pick-per-match: bets `{payload['bets']}`, pnl `{payload['pnl_units']:.2f}`, ROI `{payload['roi_pct']:.2f}%`"
            )
        clv = selection_summary.get("clv_covered_by_strategy") or {}
        if clv:
            lines.append(f"- CLV-covered selections: `{json.dumps(clv, ensure_ascii=False)}`")
        lines.append("")

    breakdowns = diagnostics.get("selection_breakdowns") or {}
    if breakdowns.get("by_league"):
        lines.append("## Top Leagues")
        for row in breakdowns["by_league"][:10]:
            lines.append(
                f"- `{row['strategy']}` `{row['league_name']}`: bets `{row['bets']}`, ROI `{row['roi_pct']:.2f}%`"
            )
        lines.append("")
    if breakdowns.get("by_odds_bucket"):
        lines.append("## Odds Buckets")
        for row in breakdowns["by_odds_bucket"][:10]:
            lines.append(
                f"- `{row['strategy']}` `{row['odds_bucket']}`: bets `{row['bets']}`, ROI `{row['roi_pct']:.2f}%`"
            )
        lines.append("")
    if breakdowns.get("by_lead_time_bucket"):
        lines.append("## Lead-Time Buckets")
        for row in breakdowns["by_lead_time_bucket"][:10]:
            lines.append(
                f"- `{row['strategy']}` `{row['lead_time_bucket']}`: bets `{row['bets']}`, ROI `{row['roi_pct']:.2f}%`"
            )
        lines.append("")

    checks = diagnostics.get("reality_checks") or []
    if checks:
        lines.append("## Reality Checks")
        for check in checks:
            lines.append(f"- {check}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
