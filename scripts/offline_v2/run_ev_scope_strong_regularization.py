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

from ullebets_v2.ev_model.categorical_interactions import (
    add_categorical_interaction_features,
)
from ullebets_v2.ev_model.falsification import (
    build_candidate_falsification_report,
)
from ullebets_v2.ev_model.market_walk_forward import (
    select_market_classifier_bets,
)
from ullebets_v2.ev_model.model_comparison import (
    build_paired_strategy_comparison,
)
from ullebets_v2.ev_model.nested_regularization import (
    NestedRegularizationConfig,
    run_nested_regularization_walk_forward,
)


SOURCE_COLUMNS = (
    "line_value",
    "market_fair_probability_over",
    "market_anchor_lambda",
    "baseline_lambda",
    "history_role_expected_10",
    "history_all_expected_10",
    "history_role_trend_3_10",
    "history_all_trend_3_10",
)
STRONG_C_GRID = (
    0.001,
    0.003,
    0.01,
    0.03,
    0.10,
    0.25,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extend V6 regularization below the previous C-grid boundary "
            "for fixed 60- and 90-day windows."
        )
    )
    parser.add_argument(
        "--market-frame",
        type=Path,
        default=Path(
            "data/v2/ev_model/research_cache/"
            "asof_market_frame.parquet"
        ),
    )
    parser.add_argument(
        "--v6-predictions",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_060_period_scope_interactions/"
            "scope_deviations/predictions.parquet"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_065_scope_strong_regularization"
        ),
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=100_000,
    )
    return parser.parse_args()


def _performance(
    name: str,
    predictions: pd.DataFrame,
    selections: pd.DataFrame,
) -> dict[str, object]:
    markets = predictions.drop_duplicates("sample_key")
    markets = markets[markets["is_over_win"].notna()]
    return {
        "variant": name,
        "markets": int(len(markets)),
        "brier": float(
            brier_score_loss(
                markets["is_over_win"],
                markets["predicted_over_probability"],
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
    market_frame = add_categorical_interaction_features(
        pd.read_parquet(args.market_frame),
        category_column="scope",
        source_columns=SOURCE_COLUMNS,
        deviation_values=("home", "away"),
    )
    v6_predictions = pd.read_parquet(args.v6_predictions)
    v6_selections = select_market_classifier_bets(
        v6_predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )
    summaries: list[dict[str, object]] = []
    selections_by_name: dict[str, pd.DataFrame] = {}
    for train_days in (60, 90):
        name = f"scope_strong_regularization_train{train_days}"
        config = NestedRegularizationConfig(
            train_window_days=train_days,
            recency_half_life_days=45.0,
            c_grid=STRONG_C_GRID,
            default_logistic_c=0.01,
            evaluation_start_date="2026-02-19",
            evaluation_end_date="2026-05-24",
        )
        predictions, windows = (
            run_nested_regularization_walk_forward(
                market_frame,
                config,
            )
        )
        predictions["model_name"] = name
        selections = select_market_classifier_bets(
            predictions,
            minimum_ev=0.075,
            maximum_ev=0.25,
        )
        variant_dir = args.output_dir / name
        variant_dir.mkdir(parents=True, exist_ok=True)
        predictions.to_parquet(
            variant_dir / "predictions.parquet",
            index=False,
        )
        selections.to_parquet(
            variant_dir / "exact_policy_selections.parquet",
            index=False,
        )
        windows.to_json(
            variant_dir / "window_summary.json",
            orient="records",
            indent=2,
        )
        summary = _performance(
            name,
            predictions,
            selections,
        )
        summary["train_window_days"] = train_days
        summary["c_grid"] = list(STRONG_C_GRID)
        summary["selected_c_by_window"] = (
            windows[
                ["test_start", "selected_logistic_c"]
            ].to_dict(orient="records")
        )
        summaries.append(summary)
        selections_by_name[name] = selections
        _write_json(
            variant_dir / "paired_vs_v6.json",
            build_paired_strategy_comparison(
                reference_selections=v6_selections,
                challenger_selections=selections,
                reference_predictions=v6_predictions,
                challenger_predictions=predictions,
                bootstrap_iterations=args.bootstrap_iterations,
            ),
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "summary.json", summaries)
    _write_json(
        args.output_dir / "falsification.json",
        build_candidate_falsification_report(
            selections_by_name,
            experiments_inspected=135,
            bootstrap_iterations=args.bootstrap_iterations,
        ),
    )
    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
