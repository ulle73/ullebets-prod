from __future__ import annotations

import argparse
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
from ullebets_v2.ev_model.market_classifier import (
    build_market_classifier_frame,
)
from ullebets_v2.ev_model.market_walk_forward import (
    select_market_classifier_bets,
)
from ullebets_v2.ev_model.nested_market_walk_forward import (
    NestedMarketWalkForwardConfig,
    run_nested_market_walk_forward,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run nested temporal calibration EV experiments."
    )
    parser.add_argument("--offline-v1-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
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
    model_features = build_compact_model_features(modeling_frame)
    market_frame = build_market_classifier_frame(
        modeling_frame,
        model_features,
    )
    config = NestedMarketWalkForwardConfig(
        evaluation_end_date=args.evaluation_end_date,
    )
    predictions, windows = run_nested_market_walk_forward(
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
    print(
        overall.sort_values(
            ["minimum_ev", "roi_pct"],
            ascending=[True, False],
        ).to_string(index=False)
    )
    print(f"wrote_nested_market_experiment={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
