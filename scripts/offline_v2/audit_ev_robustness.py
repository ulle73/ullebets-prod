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

from ullebets_v2.ev_model.robustness import build_robustness_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build reproducible stress tests for one EV candidate."
    )
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-name", default="logistic_market")
    parser.add_argument("--minimum-ev", type=float, default=0.075)
    parser.add_argument("--maximum-ev", type=float, default=0.25)
    return parser.parse_args()


def _markdown(report: dict[str, object]) -> str:
    performance = report["performance"]
    calibration = report["calibration"]
    risk = report["risk"]
    concentration = report["match_concentration"]
    lines = [
        "# EV Candidate Robustness Audit",
        "",
        "## Frozen Policy",
        "",
        f"- Minimum EV: `{report['policy']['minimum_ev']:.1%}`",
        f"- Maximum EV: `{report['policy']['maximum_ev']:.1%}`",
        f"- Rejected above maximum: "
        f"`{report['policy']['rejected_above_maximum_ev']}`",
        "",
        "## Performance And Calibration",
        "",
        f"- Bets: `{performance['bets']}`",
        f"- PnL: `{performance['pnl_units']:.2f}` units",
        f"- ROI: `{performance['roi_pct']:.2f}%`",
        f"- Actual win rate: `{calibration['actual_win_rate']:.2%}`",
        f"- Mean model probability: "
        f"`{calibration['mean_model_probability']:.2%}`",
        f"- Mean market probability: "
        f"`{calibration['mean_market_probability']:.2%}`",
        f"- Model/market Brier: `{calibration['model_brier']:.4f}` / "
        f"`{calibration['market_brier']:.4f}`",
        f"- Model/market log loss: `{calibration['model_log_loss']:.4f}` / "
        f"`{calibration['market_log_loss']:.4f}`",
        "",
        "## Risk",
        "",
        f"- Maximum drawdown: `{risk['maximum_drawdown_units']:.2f}` units",
        f"- Maximum losing streak: `{risk['maximum_loss_streak']}`",
        f"- Match clusters: `{concentration['match_clusters']}`",
        f"- Top-ten match contribution: "
        f"`{concentration['top_10_match_pnl_units']:.2f}` units",
        "",
        "## Decision",
        "",
        "The candidate remains shadow-only. Its probability metrics beat the "
        "market on this history, but profit is match-clustered, CLV evidence "
        "is insufficient, and historical model selection invalidates a "
        "confirmatory claim.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    predictions = pd.read_parquet(args.predictions)
    model_predictions = predictions[
        predictions["model_name"].eq(args.model_name)
    ].copy()
    report = build_robustness_report(
        model_predictions,
        minimum_ev=args.minimum_ev,
        maximum_ev=args.maximum_ev,
    )
    report["configuration"] = {
        "model_name": args.model_name,
        "predictions": str(args.predictions),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "robustness_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output_dir / "robustness_audit.md").write_text(
        _markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
