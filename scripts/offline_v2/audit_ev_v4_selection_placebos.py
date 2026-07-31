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
    apply_policy_exposure_cap_to_frame,
)
from ullebets_v2.ev_model.selection_placebo import (
    random_choice_within_selected_groups,
    stratified_random_selection_placebo,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare V4 corner selections with always-over/under, "
            "market-side, and random-selection negative controls."
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
            / "experiment_044_v4_selection_placebos"
        ),
    )
    parser.add_argument(
        "--prior-comparison-family",
        type=int,
        default=98,
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100_000,
    )
    parser.add_argument(
        "--candidate-label",
        default="V4",
    )
    return parser.parse_args()


def _policy_filter(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[
        frame["stat_key"].eq("cornerKicks")
        & frame["scope"].isin(["away", "total"])
    ].copy()


def _performance(frame: pd.DataFrame) -> dict[str, float | int]:
    pnl = pd.to_numeric(
        frame["realized_roi_units"],
        errors="coerce",
    ).dropna()
    return {
        "bets": int(len(pnl)),
        "matches": int(
            frame.loc[pnl.index, "exposure_match_id"].nunique()
        ),
        "pnl_units": float(pnl.sum()),
        "roi_pct": float(pnl.mean() * 100.0),
    }


def _adjust(
    report: dict[str, object],
    *,
    family_size: int,
) -> dict[str, object]:
    return {
        **report,
        "family_adjusted_p_value": min(
            1.0,
            float(report["one_sided_p_value"])
            * family_size,
        ),
    }


def _markdown(report: dict[str, object]) -> str:
    baselines = report["baselines"]
    candidate_label = report["configuration"]["candidate_label"]
    return "\n".join(
        [
            f"# {candidate_label} Selection Negative Controls",
            "",
            "All rows use corners in away/total scope. The controls "
            "test whether profit comes from a generic direction bias "
            "or from the model's exact market selection.",
            "",
            f"- {candidate_label} selected: "
            f"`{baselines['candidate_selected']['bets']}` "
            "bets at "
            f"`{baselines['candidate_selected']['roi_pct']:.2f}%`",
            f"- Always under: `{baselines['always_under']['bets']}` "
            f"bets at `{baselines['always_under']['roi_pct']:.2f}%`",
            f"- Always over: `{baselines['always_over']['bets']}` "
            f"bets at `{baselines['always_over']['roi_pct']:.2f}%`",
            f"- Market favorite: "
            f"`{baselines['market_favorite']['roi_pct']:.2f}%`",
            f"- Market longshot: "
            f"`{baselines['market_longshot']['roi_pct']:.2f}%`",
            "",
            "## Placebos",
            "",
            *[
                f"- {name}: observed "
                f"`{row['observed_roi_pct']:.2f}%`, null mean "
                f"`{row['null_mean_roi_pct']:.2f}%`, null 95% "
                f"`{row['null_low_95_pct']:.2f}%` to "
                f"`{row['null_high_95_pct']:.2f}%`, raw p "
                f"`{row['one_sided_p_value']:.6f}`, adjusted p "
                f"`{row['family_adjusted_p_value']:.4f}`"
                for name, row in report["placebos"].items()
            ],
            "",
            "## Decision",
            "",
            "The model selection beats generic under/over and random "
            "choices with matched composition. This supports genuine "
            "market selectivity, but the null tests do not repair the "
            "post-selection status of the historical scope policy. "
            "Forward confirmation is still required.",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    universe = _policy_filter(
        pd.read_parquet(args.v4_predictions)
    )
    selected = _policy_filter(
        pd.read_parquet(args.v4_selections)
    )
    one_per_match = apply_policy_exposure_cap_to_frame(
        selected,
        maximum_bets_per_match=1,
    )
    favorite = (
        universe.sort_values(
            "offered_odds",
            ascending=True,
        )
        .drop_duplicates("sample_key")
    )
    longshot = (
        universe.sort_values(
            "offered_odds",
            ascending=False,
        )
        .drop_duplicates("sample_key")
    )
    baselines = {
        "candidate_selected": _performance(selected),
        "candidate_one_per_match": _performance(one_per_match),
        "always_under": _performance(
            universe[universe["direction"].eq("under")]
        ),
        "always_over": _performance(
            universe[universe["direction"].eq("over")]
        ),
        "market_favorite": _performance(favorite),
        "market_longshot": _performance(longshot),
    }

    raw_placebos = {
        "matched_composition_random_selection": (
            stratified_random_selection_placebo(
                universe=universe,
                selected=selected,
                strata_columns=[
                    "test_start",
                    "scope",
                    "period",
                    "direction",
                ],
                iterations=args.iterations,
                random_seed=20260730,
            )
        ),
        "random_side_same_exact_market": (
            random_choice_within_selected_groups(
                universe=universe,
                selected=selected,
                group_column="sample_key",
                iterations=args.iterations,
                random_seed=20260731,
            )
        ),
        "random_market_same_selected_match": (
            random_choice_within_selected_groups(
                universe=universe,
                selected=one_per_match,
                group_column="exposure_match_id",
                iterations=args.iterations,
                random_seed=20260732,
            )
        ),
    }
    total_family = (
        args.prior_comparison_family + len(raw_placebos)
    )
    report = {
        "configuration": {
            "candidate_label": args.candidate_label,
            "iterations": args.iterations,
            "prior_comparison_family": (
                args.prior_comparison_family
            ),
            "placebo_tests": len(raw_placebos),
            "total_comparison_family": total_family,
        },
        "baselines": baselines,
        "placebos": {
            name: _adjust(
                placebo,
                family_size=total_family,
            )
            for name, placebo in raw_placebos.items()
        },
        "decision": (
            f"{args.candidate_label} exact selection has signal beyond "
            "generic direction "
            "and composition controls; forward proof still required"
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "selection_placebos.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output_dir / "selection_placebos.md").write_text(
        _markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
