from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from ullebets_v1.audit.odds_timing import annotate_backtest_timing
from ullebets_v1.backtest.pipeline import (
    build_walk_forward_feature_columns,
    select_walk_forward_candidate_rows,
)
from ullebets_v1.backtest.walk_forward import (
    WalkForwardConfig,
    _dedupe_selection_rows,
    _selection_candidate_rows,
    _to_date,
)
from ullebets_v1.config import PipelineConfig
from ullebets_v1.features.targets import CONTEXT_STAT_KEYS
from ullebets_v1.logging_utils import configure_logging
from ullebets_v1.models.baseline import baseline_lambda
from ullebets_v1.models.calibration import train_poisson_model


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
    merged["bets_delta"] = merged["after_bets"] - merged["before_bets"]
    merged["roi_delta_pct"] = merged["after_roi_pct"] - merged["before_roi_pct"]
    merged["abs_bets_delta"] = merged["bets_delta"].abs()
    merged["abs_roi_delta_pct"] = merged["roi_delta_pct"].abs()
    merged = merged[
        (merged["abs_bets_delta"] > 0)
        | (merged["abs_roi_delta_pct"] > 1e-12)
    ].sort_values(
        ["abs_bets_delta", "abs_roi_delta_pct"],
        ascending=[False, False],
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
                "before_roi_pct": float(row.before_roi_pct),
                "after_roi_pct": float(row.after_roi_pct),
                "bets_delta": int(row.bets_delta),
                "roi_delta_pct": float(row.roi_delta_pct),
            }
        )
    return rows


def _selection_duplicate_summary(frame: pd.DataFrame) -> dict:
    exact_key = [
        "window_start",
        "window_end",
        "strategy",
        "exposure_match_id",
        "stat_key",
        "period",
        "scope",
        "line_value",
        "selected_side",
    ]
    grouped = frame.groupby(exact_key, dropna=False).size()
    duplicate_groups = grouped[grouped > 1]
    return {
        "rows": int(len(frame)),
        "duplicate_groups": int(len(duplicate_groups)),
        "duplicate_rows": int(duplicate_groups.sum()) if not duplicate_groups.empty else 0,
        "max_group_size": int(grouped.max()) if len(grouped) else 0,
    }


def _run_walk_forward_with_duplicate_audit(
    feature_frame: pd.DataFrame,
    *,
    feature_columns: list[str],
    categorical_columns: list[str],
    config: WalkForwardConfig,
) -> tuple[pd.DataFrame, dict]:
    frame = feature_frame.copy()
    frame = frame[frame["actual_value"].notna()].copy()
    frame["match_day"] = frame["match_date"].map(_to_date)
    all_days = sorted(frame["match_day"].dropna().unique())
    if not all_days:
        return pd.DataFrame(), {
            "raw": {"rows": 0, "duplicate_groups": 0, "duplicate_rows": 0, "max_group_size": 0},
            "after_exact_dedupe": {"rows": 0, "duplicate_groups": 0, "duplicate_rows": 0, "max_group_size": 0},
            "final": {"rows": 0, "duplicate_groups": 0, "duplicate_rows": 0, "max_group_size": 0},
        }

    start_day = min(all_days) + timedelta(days=config.train_window_days)
    end_day = max(all_days)
    selection_rows: list[pd.DataFrame] = []
    raw_rows: list[pd.DataFrame] = []
    exact_rows: list[pd.DataFrame] = []
    window_start = start_day

    while window_start <= end_day:
        train_start = window_start - timedelta(days=config.train_window_days)
        train_end = window_start - timedelta(days=1)
        test_end = window_start + timedelta(days=config.test_window_days - 1)

        train = frame[(frame["match_day"] >= train_start) & (frame["match_day"] <= train_end)].copy()
        test = frame[(frame["match_day"] >= window_start) & (frame["match_day"] <= test_end)].copy()

        if len(train) < config.min_train_rows or test.empty:
            window_start += timedelta(days=config.step_days)
            continue

        model = train_poisson_model(
            train,
            feature_columns=feature_columns,
            categorical_columns=categorical_columns,
        )
        test = test.copy()
        test["model_lambda"] = model.predict_lambda(test)
        test["baseline_lambda_eval"] = baseline_lambda(test)

        for strategy, lambda_column in (
            ("poisson_model", "model_lambda"),
            ("baseline_lambda", "baseline_lambda_eval"),
        ):
            raw = _selection_candidate_rows(test, lambda_column, config.min_expected_edge)
            if raw.empty:
                continue
            raw["window_start"] = window_start.isoformat()
            raw["window_end"] = test_end.isoformat()
            raw["strategy"] = strategy
            raw_rows.append(raw)

            exact = raw.sort_values(
                [
                    "window_start",
                    "window_end",
                    "strategy",
                    "exposure_match_id",
                    "stat_key",
                    "period",
                    "scope",
                    "line_value",
                    "selected_side",
                    "expected_roi_units",
                ],
                ascending=[True, True, True, True, True, True, True, True, True, False],
            ).drop_duplicates(
                subset=[
                    "window_start",
                    "window_end",
                    "strategy",
                    "exposure_match_id",
                    "stat_key",
                    "period",
                    "scope",
                    "line_value",
                    "selected_side",
                ],
                keep="first",
            )
            exact_rows.append(exact)

            final = _dedupe_selection_rows(raw)
            final["window_start"] = window_start.isoformat()
            final["window_end"] = test_end.isoformat()
            final["strategy"] = strategy
            selection_rows.append(final)

        window_start += timedelta(days=config.step_days)

    raw_frame = pd.concat(raw_rows, ignore_index=True) if raw_rows else pd.DataFrame()
    exact_frame = pd.concat(exact_rows, ignore_index=True) if exact_rows else pd.DataFrame()
    final_frame = pd.concat(selection_rows, ignore_index=True) if selection_rows else pd.DataFrame()
    return final_frame, {
        "raw": _selection_duplicate_summary(raw_frame),
        "after_exact_dedupe": _selection_duplicate_summary(exact_frame),
        "final": _selection_duplicate_summary(final_frame),
    }


def _outcome_summary_rows(market_lines: pd.DataFrame) -> list[dict]:
    modeled = market_lines[market_lines["stat_key"].isin({"cornerKicks", "shotsOnGoal", "totalShots"})].copy()
    grouped = modeled.groupby(["stat_key", "period", "scope"], dropna=False)
    rows: list[dict] = []
    for keys, group in grouped:
        rows.append(
            {
                "stat_key": str(keys[0]),
                "period": str(keys[1]),
                "scope": str(keys[2]),
                "rows": int(len(group)),
                "verified_rows": int(group["has_authoritative_teamstats_outcome"].fillna(False).sum()),
                "missing_line_actual": int(group["legacy_actual_value"].isna().sum()),
                "missing_teamstats_actual": int((group["outcome_verification_status"] == "missing_teamstats_actual").sum()),
                "legacy_actual_mismatch": int((group["outcome_verification_status"] == "verified_legacy_actual_mismatch").sum()),
                "legacy_settlement_missing": int((group["outcome_verification_status"] == "verified_missing_legacy_settlement").sum()),
                "legacy_settlement_mismatch": int((group["outcome_verification_status"] == "verified_legacy_settlement_mismatch").sum()),
                "teamstats_actual_zero": int(group["teamstats_actual_value"].eq(0).sum()),
                "teamstats_actual_negative": int(group["teamstats_actual_value"].lt(0).sum()),
                "teamstats_actual_non_integer": int(
                    (
                        group["teamstats_actual_value"].notna()
                        & (group["teamstats_actual_value"] % 1 != 0)
                    ).sum()
                ),
            }
        )
    return sorted(rows, key=lambda row: (row["stat_key"], row["period"], row["scope"]))


def _feature_leakage_counts(team_stats_long: pd.DataFrame, sort_columns: list[str]) -> dict:
    base = team_stats_long[team_stats_long["stat_item_key"].isin(set(CONTEXT_STAT_KEYS))].copy()
    base = base.sort_values(sort_columns)
    all_group = ["team_name", "period", "stat_item_key"]
    role_group = ["team_name", "team_role", "period", "stat_item_key"]
    all_prev = base.groupby(all_group, dropna=False)["kickoff_ts"].shift(1)
    role_prev = base.groupby(role_group, dropna=False)["kickoff_ts"].shift(1)
    all_same_or_future = int(((all_prev.notna()) & (all_prev >= base["kickoff_ts"])).sum())
    role_same_or_future = int(((role_prev.notna()) & (role_prev >= base["kickoff_ts"])).sum())
    return {
        "rows": int(len(base)),
        "all_group_prev_kickoff_ge_current": all_same_or_future,
        "role_group_prev_kickoff_ge_current": role_same_or_future,
    }


def _build_markdown(summary: dict) -> str:
    lines = ["# Backtest Integrity Audit", ""]
    lines.append("## Outcome Verification")
    for row in summary["outcome_verification"]:
        lines.append(
            f"- `{row['stat_key']}` `{row['period']}` `{row['scope']}`: "
            f"rows `{row['rows']}`, verified `{row['verified_rows']}`, "
            f"missing teamstats `{row['missing_teamstats_actual']}`, "
            f"legacy actual mismatch `{row['legacy_actual_mismatch']}`, "
            f"legacy settlement mismatch `{row['legacy_settlement_mismatch']}`, "
            f"zero actual `{row['teamstats_actual_zero']}`"
        )
    lines.append("")

    lines.append("## Settlement Rules")
    lines.append("- Decimal odds grading in code: `win = odds - 1`, `loss = -1`, `push = 0`.")
    lines.append(f"- Whole-number lines in modeled market rows: `{summary['settlement_rules']['whole_number_lines']}`")
    lines.append(f"- Half-point lines in modeled market rows: `{summary['settlement_rules']['half_point_lines']}`")
    lines.append(f"- Expected push rows from verified teamstats: `{summary['settlement_rules']['expected_push_rows']}`")
    lines.append("")

    lines.append("## Duplicate Exposure")
    for label, payload in summary["duplicate_exposure"].items():
        lines.append(
            f"- `{label}`: rows `{payload['rows']}`, duplicate groups `{payload['duplicate_groups']}`, "
            f"duplicate rows `{payload['duplicate_rows']}`, max group size `{payload['max_group_size']}`"
        )
    lines.append("")

    lines.append("## Feature Leakage")
    legacy = summary["feature_leakage"]["legacy_sort_order"]
    fixed = summary["feature_leakage"]["fixed_sort_order"]
    lines.append(
        f"- Legacy all-group ordering had `{legacy['all_group_prev_kickoff_ge_current']}` same/future-history risks; "
        f"fixed ordering has `{fixed['all_group_prev_kickoff_ge_current']}`."
    )
    lines.append(
        f"- Role-group ordering risk: legacy `{legacy['role_group_prev_kickoff_ge_current']}`, "
        f"fixed `{fixed['role_group_prev_kickoff_ge_current']}`."
    )
    lines.append("")

    lines.append("## ROI Before vs After")
    before = summary["roi_before"]
    after = summary["roi_after"]
    for strategy in sorted(set(before) | set(after)):
        before_payload = before.get(strategy, {"bets": 0, "roi_pct": 0.0})
        after_payload = after.get(strategy, {"bets": 0, "roi_pct": 0.0})
        lines.append(
            f"- `{strategy}`: bets `{before_payload['bets']}` -> `{after_payload['bets']}`, "
            f"ROI `{before_payload['roi_pct']:.2f}%` -> `{after_payload['roi_pct']:.2f}%`"
        )
    lines.append("")

    affected = summary["most_changed_segments"]
    if affected:
        lines.append("## Most Changed Segments")
        for row in affected:
            lines.append(
                f"- `{row['strategy']}` `{row['stat_key']}` `{row['period']}` `{row['scope']}`: "
                f"bets `{row['before_bets']}` -> `{row['after_bets']}`, "
                f"ROI `{row['before_roi_pct']:.2f}%` -> `{row['after_roi_pct']:.2f}%`"
            )
        lines.append("")

    corner = summary["poisson_cornerkicks_after"]
    lines.append(
        f"## Poisson CornerKicks\n- `poisson_model cornerKicks` after filters: bets `{corner['bets']}`, ROI `{corner['roi_pct']:.2f}%`"
    )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    configure_logging()
    config = PipelineConfig.from_env()
    config.ensure_directories()

    market_lines = pd.read_parquet(config.normalized_dir / "market_lines.parquet")
    team_stats_long = pd.read_parquet(config.normalized_dir / "team_stats_long.parquet")
    features = pd.read_parquet(config.features_dir / "market_points_primary.parquet")
    before_selections = pd.read_parquet(config.models_dir / "walk_forward_selections_pre_integrity_audit.parquet")

    audited = annotate_backtest_timing(features, market_lines)
    candidates = select_walk_forward_candidate_rows(audited, enforce_strict_prematch=True)
    feature_columns, categorical_columns = build_walk_forward_feature_columns(candidates)
    after_selections, duplicate_summary = _run_walk_forward_with_duplicate_audit(
        candidates,
        feature_columns=feature_columns,
        categorical_columns=categorical_columns,
        config=WalkForwardConfig(),
    )

    modeled = market_lines[market_lines["stat_key"].isin({"cornerKicks", "shotsOnGoal", "totalShots"})].copy()
    verified = modeled[modeled["has_authoritative_teamstats_outcome"] == True].copy()
    settlement_rules = {
        "whole_number_lines": int((modeled["line_value"] % 1 == 0).sum()),
        "half_point_lines": int((modeled["line_value"] % 1 == 0.5).sum()),
        "expected_push_rows": int((verified["verified_settlement_result"] == "push").sum()),
    }

    poisson_corner = after_selections[
        (after_selections["strategy"] == "poisson_model")
        & (after_selections["stat_key"] == "cornerKicks")
    ]
    corner_roi = (
        float((poisson_corner["realized_roi_units"].sum() / len(poisson_corner)) * 100.0)
        if len(poisson_corner)
        else 0.0
    )

    summary = {
        "outcome_verification": _outcome_summary_rows(market_lines),
        "settlement_rules": settlement_rules,
        "duplicate_exposure": duplicate_summary,
        "feature_leakage": {
            "legacy_sort_order": _feature_leakage_counts(
                team_stats_long,
                ["team_name", "team_role", "period", "stat_item_key", "kickoff_ts", "match_id"],
            ),
            "fixed_sort_order": _feature_leakage_counts(
                team_stats_long,
                ["team_name", "period", "stat_item_key", "kickoff_ts", "match_id", "team_role"],
            ),
        },
        "roi_before": _strategy_summary(before_selections),
        "roi_after": _strategy_summary(after_selections),
        "most_changed_segments": _segment_comparison(before_selections, after_selections),
        "poisson_cornerkicks_after": {
            "bets": int(len(poisson_corner)),
            "roi_pct": corner_roi,
        },
    }

    json_path = config.reports_dir / "backtest_integrity_audit.json"
    md_path = config.reports_dir / "backtest_integrity_audit.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(summary), encoding="utf-8")
    print(f"wrote_backtest_integrity_audit_json={json_path}")
    print(f"wrote_backtest_integrity_audit_markdown={md_path}")


if __name__ == "__main__":
    main()
