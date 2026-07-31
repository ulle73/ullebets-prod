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
    build_line_probability_rows,
    select_calibrated_bets,
    sequentially_calibrate_probability_rows,
)


DISTRIBUTIONS = ("poisson", "negative_binomial")
THRESHOLDS = (0.0, 0.02, 0.05, 0.10)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sequentially calibrate OOS EV model predictions."
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=ROOT / "data" / "v2" / "ev_model" / "experiment_003" / "predictions.parquet",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "v2" / "ev_model" / "experiment_004",
    )
    return parser.parse_args()


def _summaries(calibrated: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    overall_rows: list[dict] = []
    segment_rows: list[dict] = []
    for (model_name, distribution), rows in calibrated.groupby(
        ["model_name", "distribution"]
    ):
        eligible = rows[
            rows["calibration_eligible"].eq(True)
            & rows["settlement_result"].ne("push")
        ]
        outcomes = eligible["settlement_result"].eq("win").astype(float)
        raw_brier = float(
            ((eligible["raw_win_probability"] - outcomes) ** 2).mean()
        )
        calibrated_brier = float(
            ((eligible["calibrated_win_probability"] - outcomes) ** 2).mean()
        )
        for threshold in THRESHOLDS:
            selections = select_calibrated_bets(rows, minimum_ev=threshold)
            bets = len(selections)
            pnl = (
                float(selections["realized_roi_units"].sum())
                if bets
                else 0.0
            )
            overall_rows.append(
                {
                    "model_name": model_name,
                    "distribution": distribution,
                    "minimum_ev": threshold,
                    "calibrated_line_rows": len(eligible),
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
                    avg_calibrated_ev=("calibrated_expected_roi_units", "mean"),
                )
                .reset_index()
            )
            grouped["roi_pct"] = grouped["pnl_units"] / grouped["bets"] * 100.0
            grouped["model_name"] = model_name
            grouped["distribution"] = distribution
            grouped["minimum_ev"] = threshold
            segment_rows.extend(grouped.to_dict(orient="records"))
    return pd.DataFrame(overall_rows), pd.DataFrame(segment_rows)


def _report(overall: pd.DataFrame, segments: pd.DataFrame) -> str:
    lines = [
        "# EV Model Experiment 004",
        "",
        "Sequential beta calibration using prior OOS windows only.",
        "",
        "## Overall results",
        "",
        "| Model | Distribution | EV gate | Raw Brier | Calibrated Brier | Bets | PnL | ROI |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in overall.sort_values(
        ["minimum_ev", "roi_pct"],
        ascending=[True, False],
    ).itertuples():
        lines.append(
            f"| {row.model_name} | {row.distribution} | {row.minimum_ev:.0%} | "
            f"{row.raw_brier:.4f} | {row.calibrated_brier:.4f} | {row.bets} | "
            f"{row.pnl_units:.2f} | {row.roi_pct:.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Positive calibrated development segments",
            "",
            "| Model | Distribution | EV gate | Stat | Period | Scope | Bets | ROI |",
            "| --- | --- | ---: | --- | --- | --- | ---: | ---: |",
        ]
    )
    positive = segments[
        (segments["roi_pct"] > 0)
        & (segments["bets"] >= 20)
    ].sort_values(["roi_pct", "bets"], ascending=[False, False])
    for row in positive.head(30).itertuples():
        lines.append(
            f"| {row.model_name} | {row.distribution} | {row.minimum_ev:.0%} | "
            f"{row.stat_key} | {row.period} | {row.scope} | {row.bets} | "
            f"{row.roi_pct:.2f}% |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    predictions = pd.read_parquet(args.predictions)
    line_rows = pd.concat(
        [
            build_line_probability_rows(predictions, distribution=distribution)
            for distribution in DISTRIBUTIONS
        ],
        ignore_index=True,
    )
    calibrated = sequentially_calibrate_probability_rows(line_rows)
    overall, segments = _summaries(calibrated)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    line_rows.to_parquet(args.output_dir / "line_probabilities.parquet", index=False)
    calibrated.to_parquet(args.output_dir / "calibrated_probabilities.parquet", index=False)
    overall.to_csv(args.output_dir / "overall_summary.csv", index=False)
    segments.to_csv(args.output_dir / "segment_summary.csv", index=False)
    (args.output_dir / "report.md").write_text(
        _report(overall, segments),
        encoding="utf-8",
    )
    print(overall.sort_values(["minimum_ev", "roi_pct"], ascending=[True, False]).to_string(index=False))
    print(f"wrote_calibration_experiment={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
