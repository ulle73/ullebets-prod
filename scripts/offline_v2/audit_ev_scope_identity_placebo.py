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

from ullebets_v2.ev_model.prequential_router import (
    PrequentialScopeRouterConfig,
    run_scope_identity_permutation_test,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run an exact scope-identity placebo for the central "
            "prequential corner router."
        )
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
            / "experiment_041_scope_identity_placebo"
        ),
    )
    parser.add_argument(
        "--prior-comparison-family",
        type=int,
        default=72,
    )
    return parser.parse_args()


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


def _markdown(report: dict[str, object]) -> str:
    permutation = report["scope_identity_permutation"]
    baseline = report["delayed_all_scope_baseline"]
    return "\n".join(
        [
            "# Scope Identity Placebo Audit",
            "",
            "The scope labels home, away, and total were independently "
            "permuted in every outer test window. All exact label "
            "sequences were enumerated while preserving each window's "
            "counts and PnL.",
            "",
            f"- Exact permutations: "
            f"`{permutation['exact_permutations']}`",
            f"- Observed router bets: "
            f"`{permutation['observed_selected_bets']}`",
            f"- Observed router ROI: "
            f"`{permutation['observed_roi_pct']:.2f}%`",
            f"- Null mean ROI: "
            f"`{permutation['null_mean_roi_pct']:.2f}%`",
            f"- Null 95% range: "
            f"`{permutation['null_low_95_pct']:.2f}%` to "
            f"`{permutation['null_high_95_pct']:.2f}%`",
            f"- Exact one-sided p-value: "
            f"`{permutation['one_sided_p_value']:.4f}`",
            f"- 73-test adjusted p-value: "
            f"`{report['adjusted_p_value']:.4f}`",
            f"- Delayed all-scope baseline: "
            f"`{baseline['bets']}` bets at "
            f"`{baseline['roi_pct']:.2f}%` ROI",
            "",
            "## Decision",
            "",
            "The observed router is better than the delayed all-scope "
            "baseline, but scope identity is not significant at 5%. "
            "A large share of the result comes from abstaining during the "
            "first negative window and betting later generally profitable "
            "corner windows. The away/total filter remains a forward "
            "hypothesis, not a historically confirmed causal segment.",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    selections = pd.read_parquet(args.v4_selections)
    corners = selections[
        selections["stat_key"].eq("cornerKicks")
    ].copy()
    config = PrequentialScopeRouterConfig(
        minimum_prior_bets=10,
        minimum_prior_roi=0.0,
        cold_start="abstain",
    )
    permutation = run_scope_identity_permutation_test(
        corners,
        config,
    )
    windows = sorted(corners["test_start"].astype(str).unique())
    delayed_all = corners[
        corners["test_start"].astype(str) > windows[0]
    ]
    total_family = args.prior_comparison_family + 1
    report = {
        "configuration": {
            "minimum_prior_bets": 10,
            "minimum_prior_roi": 0.0,
            "cold_start": "abstain",
            "prior_comparison_family": (
                args.prior_comparison_family
            ),
            "total_comparison_family": total_family,
        },
        "scope_identity_permutation": permutation,
        "adjusted_p_value": min(
            1.0,
            float(permutation["one_sided_p_value"])
            * total_family,
        ),
        "delayed_all_scope_baseline": _performance(
            delayed_all
        ),
        "incremental_router_roi_pct": (
            float(permutation["observed_roi_pct"])
            - _performance(delayed_all)["roi_pct"]
        ),
        "decision": (
            "scope identity not confirmed; preserve as a frozen "
            "forward hypothesis only"
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "scope_identity_placebo.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output_dir / "scope_identity_placebo.md").write_text(
        _markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
