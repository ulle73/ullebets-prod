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
    build_candidate_falsification_report,
)
from ullebets_v2.ev_model.selection_placebo import (
    random_choice_within_selected_groups,
    stratified_random_selection_placebo,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Falsify the scope-interaction candidate using clustered "
            "inference, exposure caps, and selection placebos."
        )
    )
    parser.add_argument(
        "--candidate-dir",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_060_period_scope_interactions/"
            "scope_deviations"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_061_scope_interaction_audit"
        ),
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=100_000,
    )
    return parser.parse_args()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _selection_placebos(
    universe: pd.DataFrame,
    selected: pd.DataFrame,
    *,
    iterations: int,
) -> dict[str, object]:
    settled_universe = universe[
        universe["realized_roi_units"].notna()
    ].copy()
    selected_markets = settled_universe[
        settled_universe["sample_key"].isin(
            selected["sample_key"]
        )
    ]
    return {
        "direction_within_selected_market": (
            random_choice_within_selected_groups(
                universe=selected_markets,
                selected=selected,
                group_column="sample_key",
                iterations=iterations,
                random_seed=20260730,
            )
        ),
        "selection_within_market_strata": (
            stratified_random_selection_placebo(
                universe=settled_universe,
                selected=selected,
                strata_columns=[
                    "test_start",
                    "stat_key",
                    "period",
                    "scope",
                    "direction",
                ],
                iterations=iterations,
                random_seed=20260731,
            )
        ),
        "selection_within_league_market_strata": (
            stratified_random_selection_placebo(
                universe=settled_universe,
                selected=selected,
                strata_columns=[
                    "test_start",
                    "league_name_normalized",
                    "stat_key",
                    "period",
                    "scope",
                    "direction",
                ],
                iterations=iterations,
                random_seed=20260732,
            )
        ),
    }


def main() -> int:
    args = parse_args()
    predictions = pd.read_parquet(
        args.candidate_dir / "predictions.parquet"
    )
    selections = pd.read_parquet(
        args.candidate_dir
        / "exact_policy_selections.parquet"
    )
    capped = apply_policy_exposure_cap_to_frame(
        selections,
        maximum_bets_per_match=1,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    capped.to_parquet(
        args.output_dir / "one_per_match_selections.parquet",
        index=False,
    )
    report = {
        "comparison_family_size": 124,
        "falsification": build_candidate_falsification_report(
            {
                "scope_interactions_all_exposures": selections,
                "scope_interactions_one_per_match": capped,
            },
            experiments_inspected=124,
            bootstrap_iterations=args.bootstrap_iterations,
        ),
        "selection_placebos": {
            "all_exposures": _selection_placebos(
                predictions,
                selections,
                iterations=args.bootstrap_iterations,
            ),
            "one_per_match": _selection_placebos(
                predictions,
                capped,
                iterations=args.bootstrap_iterations,
            ),
        },
        "decision_rule": (
            "retain only as score-only forward challenger unless the "
            "multiple-comparison-adjusted historical gate passes"
        ),
    }
    _write_json(
        args.output_dir / "scope_interaction_audit.json",
        report,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
