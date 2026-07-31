from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
from sklearn.metrics import brier_score_loss

from ullebets_v2.ev_model.market_calibration import (
    select_calibrated_market_bets,
    sequentially_calibrate_market_predictions,
)


THRESHOLDS = (0.0, 0.02, 0.05, 0.10)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sequentially calibrate one-row-per-market classifier predictions."
        )
    )
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    predictions = pd.read_parquet(args.predictions)
    calibrated = sequentially_calibrate_market_predictions(predictions)

    summary_rows: list[dict[str, object]] = []
    segment_rows: list[dict[str, object]] = []
    for model_name, model_sides in calibrated.groupby("model_name"):
        markets = model_sides.drop_duplicates(
            subset=["model_name", "sample_key"],
            keep="first",
        )
        eligible_markets = markets[
            markets["calibration_eligible"].eq(True)
            & markets["is_over_win"].notna()
        ]
        outcomes = eligible_markets["is_over_win"].to_numpy(dtype=float)
        raw_brier = float(
            brier_score_loss(
                outcomes,
                eligible_markets[
                    "predicted_over_probability"
                ].to_numpy(dtype=float),
            )
        )
        calibrated_brier = float(
            brier_score_loss(
                outcomes,
                eligible_markets[
                    "calibrated_over_probability"
                ].to_numpy(dtype=float),
            )
        )
        for threshold in THRESHOLDS:
            selections = select_calibrated_market_bets(
                model_sides,
                minimum_ev=threshold,
            )
            bets = len(selections)
            pnl = (
                float(selections["realized_roi_units"].sum())
                if bets
                else 0.0
            )
            summary_rows.append(
                {
                    "model_name": model_name,
                    "minimum_ev": threshold,
                    "raw_brier": raw_brier,
                    "calibrated_brier": calibrated_brier,
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

    summary = pd.DataFrame(summary_rows)
    segments = pd.DataFrame(segment_rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    calibrated.to_parquet(
        args.output_dir / "calibrated_probabilities.parquet",
        index=False,
    )
    summary.to_csv(args.output_dir / "overall_summary.csv", index=False)
    segments.to_csv(args.output_dir / "segment_summary.csv", index=False)
    print(
        summary.sort_values(
            ["minimum_ev", "roi_pct"],
            ascending=[True, False],
        ).to_string(index=False)
    )
    print(f"wrote_market_calibration={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
