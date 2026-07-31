from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from ullebets_v2.ev_model.line_calibration import (
    select_calibrated_bets,
    sequentially_calibrate_probability_rows,
)


THRESHOLDS = (0.0, 0.02, 0.05, 0.10)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sequentially calibrate direct line-classifier predictions."
    )
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    predictions = pd.read_parquet(args.predictions)
    rows = predictions.copy()
    rows["distribution"] = "direct_classifier"
    rows["selected_odds"] = rows["offered_odds"]
    rows["raw_win_probability"] = rows["predicted_win_probability"]
    rows["push_probability"] = 0.0
    calibrated = sequentially_calibrate_probability_rows(rows)

    summary_rows: list[dict] = []
    segment_rows: list[dict] = []
    for model_name, model_rows in calibrated.groupby("model_name"):
        eligible = model_rows[model_rows["calibration_eligible"].eq(True)]
        outcomes = eligible["settlement_result"].eq("win").astype(float)
        raw_brier = float(
            ((eligible["raw_win_probability"] - outcomes) ** 2).mean()
        )
        calibrated_brier = float(
            ((eligible["calibrated_win_probability"] - outcomes) ** 2).mean()
        )
        for threshold in THRESHOLDS:
            selections = select_calibrated_bets(
                model_rows,
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
            grouped["roi_pct"] = grouped["pnl_units"] / grouped["bets"] * 100.0
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
    print(f"wrote_line_calibration={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
