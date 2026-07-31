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
from ullebets_v2.ev_model.market_walk_forward import (
    select_market_classifier_bets,
)


MINIMUM_EV = (0.05, 0.065, 0.075, 0.09, 0.10, 0.125)
MAXIMUM_EV = (0.20, 0.25, 0.30, None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit V4 corner away/total EV threshold sensitivity "
            "without changing the frozen policy registry."
        )
    )
    parser.add_argument(
        "--v4-predictions",
        type=Path,
        default=(
            Path(
                "data/v2/ev_model/"
                "experiment_037_nested_regularization_full"
            )
            / "predictions.parquet"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            Path("data/v2/ev_model")
            / "experiment_043_v4_policy_thresholds"
        ),
    )
    parser.add_argument(
        "--prior-comparison-family",
        type=int,
        default=74,
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=50_000,
    )
    return parser.parse_args()


def _variant_name(
    minimum_ev: float,
    maximum_ev: float | None,
) -> str:
    maximum = (
        "none"
        if maximum_ev is None
        else str(int(round(maximum_ev * 1000)))
    )
    return (
        f"min_{int(round(minimum_ev * 1000))}_"
        f"max_{maximum}"
    )


def _markdown(report: dict[str, object]) -> str:
    lines = [
        "# V4 Corner Policy Threshold Audit",
        "",
        "All variants use the same V4 probabilities and corner "
        "away/total policy. Only the predeclared EV boundaries change.",
        "",
        f"- Variants: `{report['methodology']['threshold_variants']}`",
        f"- Total comparison family: "
        f"`{report['methodology']['experiments_inspected']}`",
        "",
        "| Minimum EV | Maximum EV | Bets | ROI | "
        "Clustered 95% CI | Adjusted p |",
        "| ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in report["threshold_rows"]:
        lines.append(
            f"| {row['minimum_ev']:.1%} | "
            f"{row['maximum_ev_label']} | "
            f"{row['bets']} | {row['roi_pct']:.2f}% | "
            f"{row['low_95_pct']:.2f}% to "
            f"{row['high_95_pct']:.2f}% | "
            f"{row['adjusted_p_value']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The profitable region is broad from 5% through 7.5% "
            "minimum EV, but 9%+ is unstable and 12.5% is negative. "
            "The frozen 7.5%-25% gate remains unchanged. No inspected "
            "threshold variant is promoted.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    predictions = pd.read_parquet(args.v4_predictions)
    predictions = predictions[
        predictions["stat_key"].eq("cornerKicks")
        & predictions["scope"].isin(["away", "total"])
    ].copy()
    candidates: dict[str, pd.DataFrame] = {}
    config_by_variant: dict[str, tuple[float, float | None]] = {}
    for minimum_ev in MINIMUM_EV:
        for maximum_ev in MAXIMUM_EV:
            variant = _variant_name(
                minimum_ev,
                maximum_ev,
            )
            candidates[variant] = (
                select_market_classifier_bets(
                    predictions,
                    minimum_ev=minimum_ev,
                    maximum_ev=maximum_ev,
                )
            )
            config_by_variant[variant] = (
                minimum_ev,
                maximum_ev,
            )

    total_family = (
        args.prior_comparison_family + len(candidates)
    )
    report = build_candidate_falsification_report(
        candidates,
        experiments_inspected=total_family,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    report["methodology"].update(
        {
            "threshold_variants": len(candidates),
            "prior_comparison_family": (
                args.prior_comparison_family
            ),
        }
    )
    threshold_rows: list[dict[str, object]] = []
    for candidate in report["candidates"]:
        minimum_ev, maximum_ev = config_by_variant[
            candidate["candidate"]
        ]
        performance = candidate["performance"]
        inference = candidate["cluster_inference"]
        threshold_rows.append(
            {
                "variant": candidate["candidate"],
                "minimum_ev": minimum_ev,
                "maximum_ev": maximum_ev,
                "maximum_ev_label": (
                    "none"
                    if maximum_ev is None
                    else f"{maximum_ev:.1%}"
                ),
                "bets": performance["bets"],
                "roi_pct": performance["roi_pct"],
                "low_95_pct": inference["low_95_pct"],
                "high_95_pct": inference["high_95_pct"],
                "adjusted_p_value": inference[
                    "multiple_comparison_adjusted_p_value"
                ],
            }
        )
    report["threshold_rows"] = threshold_rows
    report["decision"] = (
        "retain frozen 7.5%-25% gate; high model-EV tail is "
        "unstable and no threshold is confirmatory"
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "threshold_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output_dir / "threshold_audit.md").write_text(
        _markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
