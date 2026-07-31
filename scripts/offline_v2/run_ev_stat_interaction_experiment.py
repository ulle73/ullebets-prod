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
from ullebets_v2.ev_model.stat_interactions import (
    add_stat_interaction_features,
)


FEATURE_PROFILES = {
    "market_deviations": (
        "line_value",
        "market_fair_probability_over",
        "market_anchor_lambda",
        "market_overround",
        "baseline_lambda",
        "snapshot_lead_hours",
    ),
    "expected_history_deviations": (
        "history_role_expected_3",
        "history_role_expected_5",
        "history_role_expected_10",
        "history_role_expected_20",
        "history_all_expected_3",
        "history_all_expected_5",
        "history_all_expected_10",
        "history_all_expected_20",
        "history_role_trend_3_10",
        "history_all_trend_3_10",
    ),
    "compact_core_deviations": (
        "line_value",
        "market_fair_probability_over",
        "market_anchor_lambda",
        "baseline_lambda",
        "history_role_expected_5",
        "history_role_expected_10",
        "history_all_expected_5",
        "history_all_expected_10",
        "history_role_trend_3_10",
        "history_all_trend_3_10",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test strongly regularized stat-specific slope deviations "
            "inside the shared nested temporal logistic model."
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
        "--v4-predictions",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_037_nested_regularization_full/"
            "predictions.parquet"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_058_regularized_stat_interactions"
        ),
    )
    parser.add_argument(
        "--evaluation-end-date",
        default="2026-05-24",
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
    market_frame = pd.read_parquet(args.market_frame)
    v4_predictions = pd.read_parquet(args.v4_predictions)
    v4_selections = select_market_classifier_bets(
        v4_predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )
    config = NestedRegularizationConfig(
        evaluation_end_date=args.evaluation_end_date,
    )
    summaries: list[dict[str, object]] = []
    selections_by_name: dict[str, pd.DataFrame] = {}

    for name, source_columns in FEATURE_PROFILES.items():
        candidate_frame = add_stat_interaction_features(
            market_frame,
            source_columns=source_columns,
        )
        predictions, windows = (
            run_nested_regularization_walk_forward(
                candidate_frame,
                config,
            )
        )
        model_name = f"nested_logistic_{name}"
        predictions["model_name"] = model_name
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
            model_name,
            predictions,
            selections,
        )
        summary["interaction_source_columns"] = list(
            source_columns
        )
        summaries.append(summary)
        selections_by_name[model_name] = selections
        _write_json(
            variant_dir / "paired_vs_v4.json",
            build_paired_strategy_comparison(
                reference_selections=v4_selections,
                challenger_selections=selections,
                reference_predictions=v4_predictions,
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
            experiments_inspected=120,
            bootstrap_iterations=args.bootstrap_iterations,
        ),
    )
    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
