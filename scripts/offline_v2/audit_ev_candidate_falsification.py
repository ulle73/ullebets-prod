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

from ullebets_v2.ev_model.falsification import (
    build_candidate_falsification_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Try to falsify frozen EV candidates with clustered "
            "inference, regime jackknifes, calibration, and price stress."
        )
    )
    parser.add_argument(
        "--v3-selections",
        type=Path,
        default=(
            Path("data/v2/ev_model/candidate_032_asof_capped")
            / "frozen_candidate_selections.parquet"
        ),
    )
    parser.add_argument(
        "--v4-selections",
        type=Path,
        default=(
            Path(
                "data/v2/ev_model/"
                "experiment_037_nested_regularization_full"
            )
            / "exact_policy_selections.parquet"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            Path("data/v2/ev_model")
            / "experiment_038_candidate_falsification"
        ),
    )
    parser.add_argument(
        "--experiments-inspected",
        type=int,
        default=37,
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=50_000,
    )
    return parser.parse_args()


def _format_optional(
    value: object,
    *,
    suffix: str = "",
) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}{suffix}"


def _markdown(report: dict[str, object]) -> str:
    lines = [
        "# EV Candidate Falsification Audit",
        "",
        "This report tries to reject the frozen candidates. It does not "
        "search for a profitable subgroup.",
        "",
        "## Method",
        "",
        f"- Experiments already inspected: "
        f"`{report['methodology']['experiments_inspected']}`",
        "- Cluster unit: `match`",
        "- League and outer test window: leave-one-group-out",
        "- Price stress: 0.02, 0.05, and 0.10 decimal odds removed "
        "from every winning price",
        "- Confirmation requires a positive clustered lower bound, "
        "adjusted one-sided p < 0.05, and every jackknife ROI > 0",
        "",
    ]
    for candidate in report["candidates"]:
        performance = candidate["performance"]
        inference = candidate["cluster_inference"]
        concentration = candidate["concentration"]
        calibration = candidate["calibration"]
        lines.extend(
            [
                f"## {candidate['candidate']}",
                "",
                f"- Status: `{candidate['historical_edge_status']}`",
                f"- Mechanical gate: "
                f"`{candidate['mechanical_gate_status']}`",
                f"- Bets/matches: `{performance['bets']}` / "
                f"`{performance['matches']}`",
                f"- PnL: `{performance['pnl_units']:.2f}` units",
                f"- ROI: `{performance['roi_pct']:.2f}%`",
                f"- Clustered 95% interval: "
                f"`{_format_optional(inference['low_95_pct'], suffix='%')}` "
                f"to "
                f"`{_format_optional(inference['high_95_pct'], suffix='%')}`",
                f"- One-sided null p: "
                f"`{_format_optional(inference['one_sided_null_p_value'])}`",
                f"- Experiment-count adjusted p: "
                f"`{_format_optional(inference['multiple_comparison_adjusted_p_value'])}`",
                f"- Every leave-one-league-out ROI positive: "
                f"`{candidate['leave_one_league_out']['all_positive']}`",
                f"- Minimum leave-one-league-out ROI: "
                f"`{_format_optional(candidate['leave_one_league_out']['minimum_roi_pct'], suffix='%')}`",
                f"- Every leave-one-window-out ROI positive: "
                f"`{candidate['leave_one_test_window_out']['all_positive']}`",
                f"- Minimum leave-one-window-out ROI: "
                f"`{_format_optional(candidate['leave_one_test_window_out']['minimum_roi_pct'], suffix='%')}`",
                f"- Top net-PnL league: "
                f"`{concentration['top_net_pnl_league']}`",
                f"- ROI without top net-PnL league: "
                f"`{_format_optional(concentration['roi_without_top_net_pnl_league_pct'], suffix='%')}`",
                f"- Model/market Brier on selections: "
                f"`{_format_optional(calibration['model_brier'])}` / "
                f"`{_format_optional(calibration['market_brier'])}`",
                "",
                "Failure reasons:",
                "",
            ]
        )
        lines.extend(
            f"- {reason}"
            for reason in candidate["failure_reasons"]
        )
        lines.append("")
    lines.extend(
        [
            "## Decision",
            "",
            "A candidate that is `not_confirmed` may remain in score-only "
            "shadow testing, but the inspected history is not sufficient "
            "for a real-money +EV claim.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    candidates = {
        "V3 compact logistic": pd.read_parquet(
            args.v3_selections
        ),
        "V4 nested regularization": pd.read_parquet(
            args.v4_selections
        ),
    }
    report = build_candidate_falsification_report(
        candidates,
        experiments_inspected=args.experiments_inspected,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "falsification_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output_dir / "falsification_audit.md").write_text(
        _markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
