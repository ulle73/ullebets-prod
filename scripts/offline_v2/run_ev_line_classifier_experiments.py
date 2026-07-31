from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from ullebets_v1.audit.odds_timing import annotate_backtest_timing
from ullebets_v2.ev_model.dataset import prepare_modeling_frame
from ullebets_v2.ev_model.engineering import build_compact_model_features
from ullebets_v2.ev_model.line_classifier import build_line_classifier_frame
from ullebets_v2.ev_model.line_walk_forward import (
    LineWalkForwardConfig,
    run_line_classifier_walk_forward,
    select_line_classifier_bets,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run direct line-level EV classifier experiments."
    )
    parser.add_argument("--offline-v1-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--evaluation-end-date", default="2026-04-30")
    return parser.parse_args()


def _aggregate(
    predictions: pd.DataFrame,
    thresholds: tuple[float, ...],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    overall_rows: list[dict] = []
    segment_rows: list[dict] = []
    for model_name, rows in predictions.groupby("model_name"):
        scored = rows[rows["is_win"].notna()]
        for threshold in thresholds:
            selections = select_line_classifier_bets(rows, minimum_ev=threshold)
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
                    "line_predictions": len(scored),
                    "brier": float(
                        brier_score_loss(
                            scored["is_win"],
                            scored["predicted_win_probability"],
                            sample_weight=scored["sample_weight"],
                        )
                    ),
                    "log_loss": float(
                        log_loss(
                            scored["is_win"],
                            scored["predicted_win_probability"],
                            sample_weight=scored["sample_weight"],
                            labels=[0, 1],
                        )
                    ),
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
            grouped["roi_pct"] = grouped["pnl_units"] / grouped["bets"] * 100.0
            grouped["model_name"] = model_name
            grouped["minimum_ev"] = threshold
            segment_rows.extend(grouped.to_dict(orient="records"))
    return pd.DataFrame(overall_rows), pd.DataFrame(segment_rows)


def _report(overall: pd.DataFrame, segments: pd.DataFrame) -> str:
    lines = [
        "# EV Model Experiment 007: Direct Line Classifiers",
        "",
        "| Model | EV gate | Brier | Log loss | Bets | PnL | ROI |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in overall.sort_values(
        ["minimum_ev", "roi_pct"],
        ascending=[True, False],
    ).itertuples():
        lines.append(
            f"| {row.model_name} | {row.minimum_ev:.0%} | {row.brier:.4f} | "
            f"{row.log_loss:.4f} | {row.bets} | {row.pnl_units:.2f} | {row.roi_pct:.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Positive segments",
            "",
            "| Model | EV gate | Stat | Period | Scope | Bets | ROI |",
            "| --- | ---: | --- | --- | --- | ---: | ---: |",
        ]
    )
    positive = segments[
        (segments["roi_pct"] > 0)
        & (segments["bets"] >= 30)
    ].sort_values(["roi_pct", "bets"], ascending=[False, False])
    for row in positive.head(30).itertuples():
        lines.append(
            f"| {row.model_name} | {row.minimum_ev:.0%} | {row.stat_key} | "
            f"{row.period} | {row.scope} | {row.bets} | {row.roi_pct:.2f}% |"
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
    compact_features = build_compact_model_features(modeling_frame)
    line_frame = build_line_classifier_frame(modeling_frame, compact_features)
    config = LineWalkForwardConfig(
        evaluation_end_date=args.evaluation_end_date,
    )
    predictions, windows = run_line_classifier_walk_forward(line_frame, config)
    overall, segments = _aggregate(predictions, config.minimum_ev_thresholds)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(args.output_dir / "predictions.parquet", index=False)
    windows.to_csv(args.output_dir / "window_summary.csv", index=False)
    overall.to_csv(args.output_dir / "overall_summary.csv", index=False)
    segments.to_csv(args.output_dir / "segment_summary.csv", index=False)
    (args.output_dir / "report.md").write_text(
        _report(overall, segments),
        encoding="utf-8",
    )
    print(overall.sort_values(["minimum_ev", "roi_pct"], ascending=[True, False]).to_string(index=False))
    print(f"wrote_line_classifier_experiment={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
