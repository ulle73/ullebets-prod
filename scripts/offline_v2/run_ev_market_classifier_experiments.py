from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from ullebets_v1.audit.odds_timing import annotate_backtest_timing
from ullebets_v2.ev_model.asof_features import (
    build_asof_compact_model_features,
)
from ullebets_v2.ev_model.dataset import prepare_modeling_frame
from ullebets_v2.ev_model.engineering import (
    add_snapshot_horizon_features,
    build_compact_model_features,
    build_context_model_features,
    build_horizon_model_features,
)
from ullebets_v2.ev_model.line_history import (
    build_asof_line_history_features,
    build_line_history_features,
)
from ullebets_v2.ev_model.market_classifier import (
    build_market_classifier_frame,
)
from ullebets_v2.ev_model.market_walk_forward import (
    MarketWalkForwardConfig,
    run_market_classifier_walk_forward,
    select_market_classifier_bets,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one-row-per-market EV classifier experiments."
    )
    parser.add_argument("--offline-v1-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--feature-set",
        choices=("compact", "context", "horizon", "line_history"),
        default="compact",
    )
    parser.add_argument("--train-window-days", type=int, default=90)
    parser.add_argument("--recency-half-life-days", type=float)
    parser.add_argument(
        "--as-of-snapshot-features",
        action="store_true",
        help=(
            "Rebuild rolling histories using only matches available before "
            "the odds snapshot."
        ),
    )
    parser.add_argument(
        "--history-availability-buffer-hours",
        type=float,
        default=3.0,
    )
    parser.add_argument("--evaluation-end-date", default="2026-04-30")
    return parser.parse_args()


def _aggregate(
    predictions: pd.DataFrame,
    thresholds: tuple[float, ...],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    overall_rows: list[dict[str, object]] = []
    segment_rows: list[dict[str, object]] = []
    for model_name, rows in predictions.groupby("model_name"):
        markets = rows.drop_duplicates(
            subset=["model_name", "sample_key"],
            keep="first",
        )
        markets = markets[markets["is_over_win"].notna()]
        brier = float(
            brier_score_loss(
                markets["is_over_win"],
                markets["predicted_over_probability"],
            )
        )
        loss = float(
            log_loss(
                markets["is_over_win"],
                markets["predicted_over_probability"],
                labels=[0, 1],
            )
        )
        for threshold in thresholds:
            selections = select_market_classifier_bets(
                rows,
                minimum_ev=threshold,
            )
            bets = len(selections)
            pnl = (
                float(selections["realized_roi_units"].sum())
                if bets
                else 0.0
            )
            overall_rows.append(
                {
                    "model_name": model_name,
                    "minimum_ev": threshold,
                    "market_predictions": len(markets),
                    "brier": brier,
                    "log_loss": loss,
                    "bets": bets,
                    "pnl_units": pnl,
                    "roi_pct": pnl / bets * 100.0 if bets else 0.0,
                }
            )
            if not bets:
                continue
            grouped = (
                selections.groupby(["stat_key", "period", "scope"])
                .agg(
                    bets=("realized_roi_units", "size"),
                    pnl_units=("realized_roi_units", "sum"),
                    avg_expected_ev=("expected_roi_units", "mean"),
                )
                .reset_index()
            )
            grouped["roi_pct"] = (
                grouped["pnl_units"] / grouped["bets"] * 100.0
            )
            grouped["model_name"] = model_name
            grouped["minimum_ev"] = threshold
            segment_rows.extend(grouped.to_dict(orient="records"))
    return pd.DataFrame(overall_rows), pd.DataFrame(segment_rows)


def _report(
    overall: pd.DataFrame,
    segments: pd.DataFrame,
    *,
    feature_set: str,
    train_window_days: int,
    recency_half_life_days: float | None,
) -> str:
    lines = [
        "# Market-level EV Classifier Experiment",
        "",
        f"- Feature set: `{feature_set}`",
        f"- Training window: `{train_window_days}` days",
        f"- Recency half-life: `{recency_half_life_days}`",
        "",
        "| Model | EV gate | Brier | Log loss | Bets | PnL | ROI |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in overall.sort_values(
        ["minimum_ev", "roi_pct"],
        ascending=[True, False],
    ).itertuples():
        lines.append(
            f"| {row.model_name} | {row.minimum_ev:.0%} | "
            f"{row.brier:.4f} | {row.log_loss:.4f} | {row.bets} | "
            f"{row.pnl_units:.2f} | {row.roi_pct:.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Positive exploratory segments",
            "",
            "| Model | EV gate | Stat | Period | Scope | Bets | ROI |",
            "| --- | ---: | --- | --- | --- | ---: | ---: |",
        ]
    )
    positive = segments[
        (segments["roi_pct"] > 0) & (segments["bets"] >= 30)
    ].sort_values(["roi_pct", "bets"], ascending=[False, False])
    for row in positive.head(30).itertuples():
        lines.append(
            f"| {row.model_name} | {row.minimum_ev:.0%} | "
            f"{row.stat_key} | {row.period} | {row.scope} | "
            f"{row.bets} | {row.roi_pct:.2f}% |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    features = pd.read_parquet(
        args.offline_v1_dir / "features" / "market_points_primary.parquet"
    )
    lines = pd.read_parquet(
        args.offline_v1_dir / "normalized" / "market_lines.parquet"
    )
    modeling_frame, _ = prepare_modeling_frame(
        annotate_backtest_timing(features, lines)
    )
    asof_audit = None
    if args.as_of_snapshot_features:
        if args.feature_set == "context":
            raise ValueError(
                "--as-of-snapshot-features does not support "
                "--feature-set context"
            )
        team_stats = pd.read_parquet(
            args.offline_v1_dir
            / "normalized"
            / "team_stats_long.parquet"
        )
        model_features, compact_asof_audit = (
            build_asof_compact_model_features(
                modeling_frame,
                team_stats,
                availability_buffer_hours=(
                    args.history_availability_buffer_hours
                ),
            )
        )
        asof_audit = compact_asof_audit
        if args.feature_set == "horizon":
            model_features = add_snapshot_horizon_features(
                model_features
            )
        if args.feature_set == "line_history":
            line_features, line_asof_audit = (
                build_asof_line_history_features(
                    modeling_frame,
                    team_stats,
                    availability_buffer_hours=(
                        args.history_availability_buffer_hours
                    ),
                )
            )
            model_features = pd.concat(
                [model_features, line_features],
                axis=1,
            )
            asof_audit = {
                "compact_features": compact_asof_audit,
                "line_history_features": line_asof_audit,
            }
    elif args.feature_set == "context":
        model_features = build_context_model_features(modeling_frame)
    elif args.feature_set == "horizon":
        model_features = build_horizon_model_features(modeling_frame)
    else:
        model_features = build_compact_model_features(modeling_frame)
    if (
        args.feature_set == "line_history"
        and not args.as_of_snapshot_features
    ):
        team_stats = pd.read_parquet(
            args.offline_v1_dir
            / "normalized"
            / "team_stats_long.parquet"
        )
        model_features = pd.concat(
            [
                model_features,
                build_line_history_features(modeling_frame, team_stats),
            ],
            axis=1,
        )
    market_frame = build_market_classifier_frame(
        modeling_frame,
        model_features,
    )
    model_names = MarketWalkForwardConfig.model_names
    if args.feature_set == "line_history":
        model_names = (*model_names, "empirical_bayes_line")
    config = MarketWalkForwardConfig(
        train_window_days=args.train_window_days,
        recency_half_life_days=args.recency_half_life_days,
        model_names=model_names,
        evaluation_end_date=args.evaluation_end_date,
    )
    predictions, windows = run_market_classifier_walk_forward(
        market_frame,
        config,
    )
    overall, segments = _aggregate(
        predictions,
        config.minimum_ev_thresholds,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(args.output_dir / "predictions.parquet", index=False)
    windows.to_csv(args.output_dir / "window_summary.csv", index=False)
    overall.to_csv(args.output_dir / "overall_summary.csv", index=False)
    segments.to_csv(args.output_dir / "segment_summary.csv", index=False)
    if asof_audit is not None:
        (args.output_dir / "asof_feature_audit.json").write_text(
            json.dumps(asof_audit, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    (args.output_dir / "report.md").write_text(
        _report(
            overall,
            segments,
            feature_set=args.feature_set,
            train_window_days=args.train_window_days,
            recency_half_life_days=args.recency_half_life_days,
        ),
        encoding="utf-8",
    )
    print(
        overall.sort_values(
            ["minimum_ev", "roi_pct"],
            ascending=[True, False],
        ).to_string(index=False)
    )
    print(f"wrote_market_classifier_experiment={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
