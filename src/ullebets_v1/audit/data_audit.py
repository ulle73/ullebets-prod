from __future__ import annotations

from collections import Counter

import pandas as pd

from ullebets_v1.features.targets import get_market_side_policy, is_segment_model_ready, segment_shape_from_flags


def summarize_filter_reasons(rows: list[dict]) -> dict:
    filtered = Counter()
    kept = 0
    for row in rows:
        reason = row.get("filter_reason")
        if reason:
            filtered[reason] += 1
        else:
            kept += 1
    return {"kept": kept, "filtered": dict(filtered)}


def build_audit_summary(
    market_lines: pd.DataFrame,
    coverage: pd.DataFrame,
    team_stats_long: pd.DataFrame,
) -> dict:
    coverage_rows = coverage.to_dict(orient="records")
    filter_summary = summarize_filter_reasons(coverage_rows)

    primary_mask = market_lines["is_primary_target"].fillna(False)
    primary_kept_mask = primary_mask & market_lines["filter_reason"].isna()
    primary_kept = market_lines[primary_kept_mask].copy()

    primary_target_market_completeness: dict[str, dict] = {}
    if not primary_kept.empty:
        grouped = (
            primary_kept.groupby(["stat_key", "match_id", "period", "scope"], dropna=False)["direction"]
            .agg(
                total_rows="size",
                has_over=lambda series: bool((series == "over").any()),
                has_under=lambda series: bool((series == "under").any()),
            )
            .reset_index()
        )
        grouped["segment_shape"] = grouped.apply(
            lambda row: segment_shape_from_flags(
                has_over=bool(row["has_over"]),
                has_under=bool(row["has_under"]),
            ),
            axis=1,
        )

        for stat_key, stat_rows in grouped.groupby("stat_key", dropna=False):
            shape_counts = stat_rows["segment_shape"].value_counts().to_dict()
            model_ready_mask = stat_rows.apply(
                lambda row: is_segment_model_ready(
                    str(stat_key),
                    has_over=bool(row["has_over"]),
                    has_under=bool(row["has_under"]),
                ),
                axis=1,
            )
            primary_target_market_completeness[str(stat_key)] = {
                "market_side_policy": get_market_side_policy(str(stat_key)),
                "kept_rows": int(
                    primary_kept[primary_kept["stat_key"] == stat_key].shape[0]
                ),
                "kept_segments": int(len(stat_rows)),
                "two_sided_segments": int(shape_counts.get("two_sided", 0)),
                "over_only_segments": int(shape_counts.get("over_only", 0)),
                "under_only_segments": int(shape_counts.get("under_only", 0)),
                "model_ready_segments": int(model_ready_mask.sum()),
                "rows_in_two_sided_segments": int(
                    stat_rows.loc[stat_rows["segment_shape"] == "two_sided", "total_rows"].sum()
                ),
                "rows_in_model_ready_segments": int(
                    stat_rows.loc[model_ready_mask, "total_rows"].sum()
                ),
                "direction_counts": (
                    primary_kept[primary_kept["stat_key"] == stat_key]["direction"]
                    .fillna("MISSING")
                    .value_counts()
                    .to_dict()
                ),
            }

    model_ready_rows = int(
        sum(payload["rows_in_model_ready_segments"] for payload in primary_target_market_completeness.values())
    )
    model_ready_segments = int(
        sum(payload["model_ready_segments"] for payload in primary_target_market_completeness.values())
    )
    model_ready_stat_keys = sorted(
        [
            stat_key
            for stat_key, payload in primary_target_market_completeness.items()
            if payload["model_ready_segments"] > 0
        ]
    )
    latest_snapshot_covered_rows = int(
        market_lines.get("has_latest_prematch_snapshot", pd.Series(dtype="bool"))
        .fillna(False)
        .sum()
    )
    effective_snapshot_rows = int(
        market_lines.get("effective_odds_source", pd.Series(dtype="object"))
        .eq("latest_snapshot")
        .sum()
    )
    snapshot_minutes = market_lines.get("latest_snapshot_minutes_before_kickoff")
    latest_snapshot_minutes_summary = None
    if snapshot_minutes is not None and not snapshot_minutes.dropna().empty:
        latest_snapshot_minutes_summary = {
            "count": int(snapshot_minutes.dropna().shape[0]),
            "mean": float(snapshot_minutes.dropna().mean()),
            "median": float(snapshot_minutes.dropna().median()),
            "min": float(snapshot_minutes.dropna().min()),
            "max": float(snapshot_minutes.dropna().max()),
        }

    return {
        "market_line_rows_total": int(len(market_lines)),
        "market_line_rows_kept": int(filter_summary["kept"]),
        "market_line_rows_filtered": int(sum(filter_summary["filtered"].values())),
        "filter_reasons": filter_summary["filtered"],
        "primary_target_rows_total": int(primary_mask.sum()),
        "primary_target_rows_kept": int(primary_kept_mask.sum()),
        "clv_covered_rows": int(market_lines["has_clv"].fillna(False).sum()),
        "teamstats_covered_rows": int(market_lines["has_teamstats_match"].fillna(False).sum()),
        "match_mapping_method_counts": market_lines["match_mapping_method"].fillna("missing").value_counts().to_dict(),
        "team_stats_long_rows_total": int(len(team_stats_long)),
        "stat_key_counts": market_lines["stat_key"].fillna("MISSING").value_counts().to_dict(),
        "period_counts": market_lines["period"].fillna("MISSING").value_counts().to_dict(),
        "scope_counts": market_lines["scope"].fillna("MISSING").value_counts().to_dict(),
        "primary_target_model_ready_rows": model_ready_rows,
        "primary_target_model_ready_segments": model_ready_segments,
        "primary_target_model_ready_stat_keys": model_ready_stat_keys,
        "primary_target_preserved_for_later_rows": int(primary_kept_mask.sum()) - model_ready_rows,
        "latest_prematch_snapshot_covered_rows": latest_snapshot_covered_rows,
        "effective_snapshot_rows": effective_snapshot_rows,
        "latest_snapshot_minutes_before_kickoff_summary": latest_snapshot_minutes_summary,
        "primary_target_market_completeness": primary_target_market_completeness,
        "teamstats_stat_item_counts": team_stats_long["stat_item_key"].fillna("MISSING").value_counts().head(50).to_dict(),
    }


def build_audit_markdown(summary: dict) -> str:
    filter_lines = "\n".join(
        f"- `{reason}`: {count}" for reason, count in sorted(summary["filter_reasons"].items())
    ) or "- none"
    top_stats = "\n".join(
        f"- `{stat_key}`: {count}" for stat_key, count in list(summary["stat_key_counts"].items())[:10]
    )
    mapping_lines = "\n".join(
        f"- `{method}`: {count}" for method, count in summary["match_mapping_method_counts"].items()
    )
    completeness_lines = "\n".join(
        (
            f"- `{stat_key}`: policy `{payload['market_side_policy']}`, kept rows `{payload['kept_rows']}`, kept segments `{payload['kept_segments']}`, "
            f"model-ready segments `{payload['model_ready_segments']}`, "
            f"two-sided `{payload['two_sided_segments']}`, over-only `{payload['over_only_segments']}`, "
            f"under-only `{payload['under_only_segments']}`"
        )
        for stat_key, payload in summary.get("primary_target_market_completeness", {}).items()
    ) or "- none"
    return (
        "# Offline V1 Audit Summary\n\n"
        f"- Total market lines: `{summary['market_line_rows_total']}`\n"
        f"- Kept market lines: `{summary['market_line_rows_kept']}`\n"
        f"- Filtered market lines: `{summary['market_line_rows_filtered']}`\n"
        f"- Primary target rows total: `{summary['primary_target_rows_total']}`\n"
        f"- Primary target rows kept: `{summary['primary_target_rows_kept']}`\n"
        f"- Primary target model-ready rows: `{summary['primary_target_model_ready_rows']}`\n"
        f"- Primary target preserved-for-later rows: `{summary['primary_target_preserved_for_later_rows']}`\n"
        f"- Rows with latest prematch snapshot: `{summary['latest_prematch_snapshot_covered_rows']}`\n"
        f"- Rows using snapshot as effective odds source: `{summary['effective_snapshot_rows']}`\n"
        f"- CLV-covered rows: `{summary['clv_covered_rows']}`\n"
        f"- Teamstats-covered rows: `{summary['teamstats_covered_rows']}`\n"
        f"- Team-stats-long rows: `{summary['team_stats_long_rows_total']}`\n\n"
        "## Filter Reasons\n"
        f"{filter_lines}\n\n"
        "## Match Mapping Methods\n"
        f"{mapping_lines}\n\n"
        "## Primary Target Completeness\n"
        f"{completeness_lines}\n\n"
        "## Top Stat Keys\n"
        f"{top_stats}\n"
    )
