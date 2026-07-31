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
from ullebets_v2.ev_model.prequential_router import (
    PrequentialScopeRouterConfig,
    run_prequential_scope_router,
)


MINIMUM_PRIOR_BETS = (5, 10, 20, 30)
MINIMUM_PRIOR_ROI = (0.0, 0.05, 0.10)
COLD_STARTS = ("include", "abstain")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test scope routing where every window can use only "
            "outcomes from earlier outer walk-forward windows."
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
            / "experiment_040_prequential_scope_router"
        ),
    )
    parser.add_argument(
        "--prior-comparison-family",
        type=int,
        default=47,
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=50_000,
    )
    return parser.parse_args()


def _variant_name(
    *,
    cold_start: str,
    minimum_prior_bets: int,
    minimum_prior_roi: float,
    maximum_bets_per_match: int | None = None,
) -> str:
    roi_points = int(round(minimum_prior_roi * 100))
    suffix = (
        "_one_per_match"
        if maximum_bets_per_match == 1
        else ""
    )
    return (
        f"{cold_start}_n{minimum_prior_bets}_"
        f"roi{roi_points}{suffix}"
    )


def _markdown(report: dict[str, object]) -> str:
    lines = [
        "# Prequential Scope Router Audit",
        "",
        "Each target window uses only settled candidate outcomes from "
        "earlier outer walk-forward windows. The router never reads the "
        "current or future window when choosing scopes.",
        "",
        f"- Router variants: "
        f"`{report['methodology']['router_variants']}`",
        f"- Total comparison family: "
        f"`{report['methodology']['experiments_inspected']}`",
        f"- Future rows used: "
        f"`{report['temporal_integrity']['future_rows_used']}`",
        f"- Window-order violations: "
        f"`{report['temporal_integrity']['window_order_violations']}`",
        "",
        "| Variant | Bets | ROI | Clustered 95% CI | "
        "Adjusted p | Gate |",
        "| --- | ---: | ---: | --- | ---: | --- |",
    ]
    candidates = sorted(
        report["candidates"],
        key=lambda row: float(
            row["performance"]["roi_pct"] or -10_000.0
        ),
        reverse=True,
    )
    for candidate in candidates:
        performance = candidate["performance"]
        inference = candidate["cluster_inference"]
        lines.append(
            f"| `{candidate['candidate']}` | "
            f"{performance['bets']} | "
            f"{performance['roi_pct']:.2f}% | "
            f"{inference['low_95_pct']:.2f}% to "
            f"{inference['high_95_pct']:.2f}% | "
            f"{inference['multiple_comparison_adjusted_p_value']:.4f} | "
            f"{candidate['mechanical_gate_status']} |"
        )
    passing = [
        row["candidate"]
        for row in report["candidates"]
        if row["mechanical_gate_status"] == "passes"
    ]
    lines.extend(
        [
            "",
            "## Mechanical Gate Passes",
            "",
            *(
                [f"- `{name}`" for name in passing]
                if passing
                else ["- None"]
            ),
            "",
            "## Decision",
            "",
            "Positive prequential results strengthen temporal "
            "plausibility but remain hypothesis-generating because the "
            "router family was designed after the historical scope pattern "
            "was inspected. The frozen forward registry remains the only "
            "confirmatory path.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    selections = pd.read_parquet(args.v4_selections)
    corner_rows = selections[
        selections["stat_key"].eq("cornerKicks")
    ].copy()
    candidate_frames: dict[str, pd.DataFrame] = {}
    selection_parts: list[pd.DataFrame] = []
    decision_parts: list[pd.DataFrame] = []

    for cold_start in COLD_STARTS:
        for minimum_prior_bets in MINIMUM_PRIOR_BETS:
            for minimum_prior_roi in MINIMUM_PRIOR_ROI:
                config = PrequentialScopeRouterConfig(
                    minimum_prior_bets=minimum_prior_bets,
                    minimum_prior_roi=minimum_prior_roi,
                    cold_start=cold_start,
                )
                routed, decisions = (
                    run_prequential_scope_router(
                        corner_rows,
                        config,
                    )
                )
                variant = _variant_name(
                    cold_start=cold_start,
                    minimum_prior_bets=(
                        minimum_prior_bets
                    ),
                    minimum_prior_roi=minimum_prior_roi,
                )
                candidate_frames[variant] = routed
                routed["router_variant"] = variant
                decisions["router_variant"] = variant
                selection_parts.append(routed)
                decision_parts.append(decisions)

    capped_config = PrequentialScopeRouterConfig(
        minimum_prior_bets=10,
        minimum_prior_roi=0.0,
        cold_start="abstain",
        maximum_bets_per_match=1,
    )
    capped, capped_decisions = run_prequential_scope_router(
        corner_rows,
        capped_config,
    )
    capped_variant = _variant_name(
        cold_start="abstain",
        minimum_prior_bets=10,
        minimum_prior_roi=0.0,
        maximum_bets_per_match=1,
    )
    candidate_frames[capped_variant] = capped
    capped["router_variant"] = capped_variant
    capped_decisions["router_variant"] = capped_variant
    selection_parts.append(capped)
    decision_parts.append(capped_decisions)

    all_decisions = pd.concat(
        decision_parts,
        ignore_index=True,
    )
    router_variants = len(candidate_frames)
    total_family = (
        args.prior_comparison_family + router_variants
    )
    report = build_candidate_falsification_report(
        candidate_frames,
        experiments_inspected=total_family,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    report["methodology"].update(
        {
            "router_variants": router_variants,
            "prior_comparison_family": (
                args.prior_comparison_family
            ),
            "scope_decision_source": (
                "all frozen candidate selections from earlier "
                "outer windows only"
            ),
        }
    )
    comparable = all_decisions[
        all_decisions["prior_max_window"].notna()
    ]
    report["temporal_integrity"] = {
        "decision_rows": int(len(all_decisions)),
        "future_rows_used": int(
            all_decisions["future_rows_used"].sum()
        ),
        "window_order_violations": int(
            (
                comparable["prior_max_window"].astype(str)
                >= comparable["target_window"].astype(str)
            ).sum()
        ),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(
        selection_parts,
        ignore_index=True,
    ).to_parquet(
        args.output_dir / "router_selections.parquet",
        index=False,
    )
    all_decisions.to_parquet(
        args.output_dir / "router_decisions.parquet",
        index=False,
    )
    (args.output_dir / "prequential_router_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output_dir / "prequential_router_audit.md").write_text(
        _markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
