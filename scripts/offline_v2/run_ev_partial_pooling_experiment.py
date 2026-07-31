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
from sklearn.metrics import brier_score_loss

from ullebets_v2.ev_model.falsification import (
    build_candidate_falsification_report,
)
from ullebets_v2.ev_model.market_classifier import (
    expand_market_predictions_to_sides,
)
from ullebets_v2.ev_model.market_walk_forward import (
    select_market_classifier_bets,
)
from ullebets_v2.ev_model.model_comparison import (
    build_paired_strategy_comparison,
)
from ullebets_v2.ev_model.partial_pooling import (
    build_prequential_partial_pooling_predictions,
)


PRIMARY_STATS = (
    "cornerKicks",
    "shotsOnGoal",
    "totalShots",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Blend global and stat-specific OOS predictions using only "
            "completed earlier outer windows."
        )
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("data/v2/ev_model"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_057_prequential_partial_pooling"
        ),
    )
    parser.add_argument(
        "--min-prior-markets",
        type=int,
        default=250,
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=100_000,
    )
    return parser.parse_args()


def _performance(
    market_predictions: pd.DataFrame,
    selections: pd.DataFrame,
) -> dict[str, object]:
    settled_markets = market_predictions[
        market_predictions["is_over_win"].notna()
    ]
    return {
        "markets": int(len(settled_markets)),
        "brier": float(
            brier_score_loss(
                settled_markets["is_over_win"],
                settled_markets[
                    "predicted_over_probability"
                ],
            )
        ),
        "bets": int(len(selections)),
        "matches": int(
            selections["exposure_match_id"].nunique()
        ),
        "pnl_units": float(
            selections["realized_roi_units"].sum()
        ),
        "roi_pct": (
            float(
                selections["realized_roi_units"].mean()
                * 100.0
            )
            if len(selections)
            else None
        ),
        "positive_windows": int(
            sum(
                rows["realized_roi_units"].mean() > 0.0
                for _, rows in selections.groupby(
                    "test_start"
                )
            )
        ),
        "windows_with_bets": int(
            selections["test_start"].nunique()
        ),
        "by_stat": (
            selections.groupby("stat_key")[
                "realized_roi_units"
            ]
            .agg(["size", "sum", "mean"])
            .reset_index()
            .to_dict(orient="records")
        ),
        "by_window": (
            selections.groupby("test_start")[
                "realized_roi_units"
            ]
            .agg(["size", "sum", "mean"])
            .reset_index()
            .to_dict(orient="records")
        ),
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    global_predictions = pd.read_parquet(
        args.input_root
        / "experiment_037_nested_regularization_full"
        / "predictions.parquet"
    )
    local_predictions = pd.concat(
        [
            pd.read_parquet(
                args.input_root
                / "experiment_046_stat_specific_nested"
                / stat_key
                / "predictions.parquet"
            )
            for stat_key in PRIMARY_STATS
        ],
        ignore_index=True,
    )
    market_predictions, weight_audit = (
        build_prequential_partial_pooling_predictions(
            global_predictions,
            local_predictions,
            min_prior_markets=args.min_prior_markets,
        )
    )
    model_name = "prequential_stat_partial_pooling"
    market_predictions["model_name"] = model_name
    side_predictions = expand_market_predictions_to_sides(
        market_predictions
    )
    selections = select_market_classifier_bets(
        side_predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )
    reference_selections = select_market_classifier_bets(
        global_predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    market_predictions.to_parquet(
        args.output_dir / "market_predictions.parquet",
        index=False,
    )
    side_predictions.to_parquet(
        args.output_dir / "predictions.parquet",
        index=False,
    )
    selections.to_parquet(
        args.output_dir / "exact_policy_selections.parquet",
        index=False,
    )
    weight_audit.to_json(
        args.output_dir / "weight_audit.json",
        orient="records",
        indent=2,
    )

    summary = _performance(
        market_predictions,
        selections,
    )
    summary["candidate_local_weights"] = [
        0.0,
        0.10,
        0.25,
        0.50,
        0.75,
        1.0,
    ]
    summary["min_prior_markets"] = args.min_prior_markets
    _write_json(args.output_dir / "summary.json", summary)
    _write_json(
        args.output_dir / "falsification.json",
        build_candidate_falsification_report(
            {model_name: selections},
            experiments_inspected=117,
            bootstrap_iterations=args.bootstrap_iterations,
        ),
    )
    _write_json(
        args.output_dir / "paired_vs_v4.json",
        build_paired_strategy_comparison(
            reference_selections=reference_selections,
            challenger_selections=selections,
            reference_predictions=global_predictions,
            challenger_predictions=side_predictions,
            bootstrap_iterations=args.bootstrap_iterations,
        ),
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
