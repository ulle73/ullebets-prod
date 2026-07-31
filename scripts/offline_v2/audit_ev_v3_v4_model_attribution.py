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
from ullebets_v2.ev_model.model_comparison import (
    build_paired_strategy_comparison,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Attribute the corner away/total result between the V3 "
            "and V4 probability models under the same policy."
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
        "--v3-predictions",
        type=Path,
        default=(
            Path(
                "data/v2/ev_model/"
                "experiment_031_asof_snapshot_recency45_full"
            )
            / "predictions.parquet"
        ),
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
            / "experiment_042_v3_v4_model_attribution"
        ),
    )
    parser.add_argument(
        "--prior-comparison-family",
        type=int,
        default=73,
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=100_000,
    )
    return parser.parse_args()


def _policy_filter(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[
        frame["stat_key"].eq("cornerKicks")
        & frame["scope"].isin(["away", "total"])
    ].copy()


def _markdown(report: dict[str, object]) -> str:
    comparison = report["paired_comparison"]
    paired = comparison["paired_bootstrap"]
    quality = comparison["prediction_quality"]
    return "\n".join(
        [
            "# V3/V4 Model Attribution",
            "",
            "Both models use the identical corners + away/total + "
            "7.5%-25% EV policy. This isolates model selectivity from "
            "the scope filter.",
            "",
            f"- V3: `{comparison['reference']['bets']}` bets, "
            f"`{comparison['reference']['roi_pct']:.2f}%` ROI",
            f"- V4: `{comparison['challenger']['bets']}` bets, "
            f"`{comparison['challenger']['roi_pct']:.2f}%` ROI",
            f"- Observed V4 minus V3 ROI: "
            f"`{paired['observed_roi_difference_pct']:.2f}` points",
            f"- Paired 95% interval: `{paired['low_95_pct']:.2f}` "
            f"to `{paired['high_95_pct']:.2f}` points",
            f"- Probability V4 superior: "
            f"`{paired['probability_challenger_superior']:.2%}`",
            f"- Paired one-sided p-value: "
            f"`{paired['one_sided_p_value']:.4f}`",
            f"- 74-test adjusted p-value: "
            f"`{report['family_adjusted_p_value']:.4f}`",
            "",
            f"- Common selections: "
            f"`{comparison['selection_overlap']['common']}`",
            f"- V3-only selections: "
            f"`{comparison['selection_overlap']['reference_only']}`, "
            f"`{comparison['reference_unique']['roi_pct']:.2f}%` ROI",
            f"- V4-only selections: "
            f"`{comparison['selection_overlap']['challenger_only']}`, "
            f"`{comparison['challenger_unique']['roi_pct']:.2f}%` ROI",
            f"- V3/V4 Brier: "
            f"`{quality['reference_brier']:.6f}` / "
            f"`{quality['challenger_brier']:.6f}`",
            "",
            "## Decision",
            "",
            "V4 is more selective and probably better than V3 under "
            "the same policy, but the paired interval still crosses "
            "zero and the multiple-comparison correction removes "
            "significance. V4 remains score-only.",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    v3_selections = _policy_filter(
        pd.read_parquet(args.v3_selections)
    )
    v4_selections = _policy_filter(
        pd.read_parquet(args.v4_selections)
    )
    v3_predictions = pd.read_parquet(
        args.v3_predictions
    )
    v3_predictions = v3_predictions[
        v3_predictions["model_name"].eq("logistic_market")
    ]
    v3_predictions = _policy_filter(v3_predictions)
    v4_predictions = _policy_filter(
        pd.read_parquet(args.v4_predictions)
    )
    comparison = build_paired_strategy_comparison(
        reference_selections=v3_selections,
        challenger_selections=v4_selections,
        reference_predictions=v3_predictions,
        challenger_predictions=v4_predictions,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    total_family = args.prior_comparison_family + 1
    raw_p = float(
        comparison["paired_bootstrap"][
            "one_sided_p_value"
        ]
    )
    falsification = build_candidate_falsification_report(
        {
            "v3_same_policy": v3_selections,
            "v4_same_policy": v4_selections,
        },
        experiments_inspected=total_family,
        bootstrap_iterations=50_000,
    )
    report = {
        "configuration": {
            "stat_key": "cornerKicks",
            "scopes": ["away", "total"],
            "minimum_ev": 0.075,
            "maximum_ev": 0.25,
            "prior_comparison_family": (
                args.prior_comparison_family
            ),
            "total_comparison_family": total_family,
        },
        "paired_comparison": comparison,
        "family_adjusted_p_value": min(
            1.0,
            raw_p * total_family,
        ),
        "candidate_falsification": falsification,
        "decision": (
            "V4 probable improvement, not confirmed; score-only "
            "forward comparison required"
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "model_attribution.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output_dir / "model_attribution.md").write_text(
        _markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
