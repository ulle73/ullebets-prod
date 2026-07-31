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

from ullebets_v1.audit.odds_timing import annotate_backtest_timing
from ullebets_v2.ev_model.dataset import prepare_modeling_frame
from ullebets_v2.ev_model.engineering import build_compact_model_features
from ullebets_v2.ev_model.evaluation import score_market_rows
from ullebets_v2.ev_model.walk_forward import (
    WalkForwardExperimentConfig,
    run_count_walk_forward,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run leakage-safe Ullebets V2 EV model experiments."
    )
    parser.add_argument(
        "--offline-v1-dir",
        type=Path,
        default=ROOT / "data" / "derived" / "offline_v1",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "v2" / "ev_model" / "experiment_003",
    )
    parser.add_argument("--evaluation-end-date", default="2026-04-30")
    return parser.parse_args()


def _aggregate(
    predictions: pd.DataFrame,
    thresholds: tuple[float, ...],
    distributions: tuple[str, ...],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    overall_rows: list[dict] = []
    segment_rows: list[dict] = []
    for model_name, model_predictions in predictions.groupby("model_name"):
        actual = model_predictions["actual_value"]
        predicted = model_predictions["predicted_mean"]
        for distribution in distributions:
            for threshold in thresholds:
                selections = score_market_rows(
                    model_predictions,
                    predicted_means=predicted,
                    minimum_ev=threshold,
                    distribution=distribution,
                    dispersions=model_predictions["nb_dispersion"],
                )
                pnl = float(selections["realized_roi_units"].sum()) if not selections.empty else 0.0
                bets = len(selections)
                overall_rows.append(
                    {
                        "model_name": model_name,
                        "distribution": distribution,
                        "minimum_ev": threshold,
                        "prediction_rows": len(model_predictions),
                        "mae": float((actual - predicted).abs().mean()),
                        "rmse": float(((actual - predicted) ** 2).mean() ** 0.5),
                        "bets": bets,
                        "pnl_units": pnl,
                        "roi_pct": pnl / bets * 100.0 if bets else 0.0,
                    }
                )
                if selections.empty:
                    continue
                grouped = (
                    selections.groupby(["stat_key", "period", "scope"], dropna=False)
                    .agg(
                        bets=("realized_roi_units", "size"),
                        pnl_units=("realized_roi_units", "sum"),
                        avg_expected_ev=("expected_roi_units", "mean"),
                    )
                    .reset_index()
                )
                grouped["roi_pct"] = grouped["pnl_units"] / grouped["bets"] * 100.0
                grouped["model_name"] = model_name
                grouped["distribution"] = distribution
                grouped["minimum_ev"] = threshold
                segment_rows.extend(grouped.to_dict(orient="records"))
    return pd.DataFrame(overall_rows), pd.DataFrame(segment_rows)


def _markdown_report(
    *,
    dataset_audit: dict,
    overall: pd.DataFrame,
    segment: pd.DataFrame,
    config: WalkForwardExperimentConfig,
) -> str:
    lines = [
        "# EV Model Experiment 003",
        "",
        "Leakage-safe development walk-forward. May 2026 is not included.",
        "",
        "## Dataset",
        "",
        f"- Input rows: `{dataset_audit['input_rows']}`",
        f"- Eligible canonical prematch rows: `{dataset_audit['output_rows']}`",
        f"- Train window: `{config.train_window_days}` days",
        f"- Test window: `{config.test_window_days}` days",
        f"- Evaluation end: `{config.evaluation_end_date}`",
        "",
        "## Overall results",
        "",
        "| Model | Distribution | Minimum EV | Predictions | MAE | Bets | PnL | ROI |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in overall.sort_values(["minimum_ev", "roi_pct"], ascending=[True, False]).itertuples():
        lines.append(
            f"| {row.model_name} | {row.distribution} | {row.minimum_ev:.0%} | {row.prediction_rows} | "
            f"{row.mae:.3f} | {row.bets} | {row.pnl_units:.2f} | {row.roi_pct:.2f}% |"
        )
    if not segment.empty:
        lines.extend(
            [
                "",
                "## Positive development segments",
                "",
                "| Model | Distribution | EV gate | Stat | Period | Scope | Bets | ROI |",
                "| --- | --- | ---: | --- | --- | --- | ---: | ---: |",
            ]
        )
        positive = segment[
            (segment["roi_pct"] > 0)
            & (segment["bets"] >= 30)
        ].sort_values(["roi_pct", "bets"], ascending=[False, False])
        for row in positive.head(30).itertuples():
            lines.append(
                f"| {row.model_name} | {row.distribution} | {row.minimum_ev:.0%} | {row.stat_key} | "
                f"{row.period} | {row.scope} | {row.bets} | {row.roi_pct:.2f}% |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    features_path = args.offline_v1_dir / "features" / "market_points_primary.parquet"
    lines_path = args.offline_v1_dir / "normalized" / "market_lines.parquet"
    feature_frame = pd.read_parquet(features_path)
    market_lines = pd.read_parquet(lines_path)
    audited = annotate_backtest_timing(feature_frame, market_lines)
    modeling_frame, dataset_audit = prepare_modeling_frame(audited)
    model_features = build_compact_model_features(modeling_frame)

    config = WalkForwardExperimentConfig(
        evaluation_end_date=args.evaluation_end_date,
    )
    predictions, window_summary = run_count_walk_forward(
        modeling_frame,
        model_features,
        config,
    )
    overall, segment = _aggregate(
        predictions,
        config.minimum_ev_thresholds,
        config.probability_distributions,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(args.output_dir / "predictions.parquet", index=False)
    window_summary.to_csv(args.output_dir / "window_summary.csv", index=False)
    overall.to_csv(args.output_dir / "overall_summary.csv", index=False)
    segment.to_csv(args.output_dir / "segment_summary.csv", index=False)
    (args.output_dir / "experiment.json").write_text(
        json.dumps(
            {
                "dataset_audit": dataset_audit.__dict__,
                "config": config.__dict__,
                "model_feature_columns": model_features.columns.tolist(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (args.output_dir / "report.md").write_text(
        _markdown_report(
            dataset_audit=dataset_audit.__dict__,
            overall=overall,
            segment=segment,
            config=config,
        ),
        encoding="utf-8",
    )
    print(overall.sort_values(["minimum_ev", "roi_pct"], ascending=[True, False]).to_string(index=False))
    print(f"wrote_experiment={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
