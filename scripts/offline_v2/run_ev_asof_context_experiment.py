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

from ullebets_v1.audit.odds_timing import (
    annotate_backtest_timing,
)
from ullebets_v2.ev_model.asof_features import (
    build_asof_compact_model_features,
    build_asof_context_model_features,
)
from ullebets_v2.ev_model.dataset import (
    prepare_modeling_frame,
)
from ullebets_v2.ev_model.market_classifier import (
    build_market_classifier_frame,
)
from ullebets_v2.ev_model.market_walk_forward import (
    select_market_classifier_bets,
)
from ullebets_v2.ev_model.nested_regularization import (
    NestedRegularizationConfig,
    run_nested_regularization_walk_forward,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run leakage-safe snapshot-as-of cross-stat context "
            "experiment 055."
        )
    )
    parser.add_argument(
        "--offline-v1-dir",
        type=Path,
        default=Path(
            "C:/dev/ullebets-prod/data/derived/offline_v1"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            Path("data/v2/ev_model")
            / "experiment_055_asof_cross_stat_context"
        ),
    )
    parser.add_argument(
        "--evaluation-end-date",
        default="2026-05-24",
    )
    return parser.parse_args()


def _group_performance(
    frame: pd.DataFrame,
    columns: list[str],
) -> list[dict[str, object]]:
    grouped = (
        frame.groupby(columns, dropna=False)[
            "realized_roi_units"
        ]
        .agg(["size", "sum", "mean"])
        .reset_index()
    )
    grouped["roi_pct"] = grouped["mean"] * 100.0
    return grouped.drop(columns=["mean"]).to_dict(
        orient="records"
    )


def _run_profile(
    *,
    modeling_frame: pd.DataFrame,
    model_features: pd.DataFrame,
    model_name: str,
    output_dir: Path,
    evaluation_end_date: str,
) -> dict[str, object]:
    market_frame = build_market_classifier_frame(
        modeling_frame,
        model_features,
    )
    predictions, windows = (
        run_nested_regularization_walk_forward(
            market_frame,
            NestedRegularizationConfig(
                evaluation_end_date=evaluation_end_date
            ),
        )
    )
    predictions["model_name"] = model_name
    selections = select_market_classifier_bets(
        predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )
    markets = predictions.drop_duplicates("sample_key")
    markets = markets[markets["is_over_win"].notna()]
    summary = {
        "model_name": model_name,
        "feature_columns": int(len(model_features.columns)),
        "probability": {
            "markets": int(len(markets)),
            "brier": float(
                brier_score_loss(
                    markets["is_over_win"],
                    markets[
                        "predicted_over_probability"
                    ],
                )
            ),
        },
        "performance": {
            "bets": int(len(selections)),
            "matches": int(
                selections[
                    "exposure_match_id"
                ].nunique()
            ),
            "pnl_units": float(
                selections[
                    "realized_roi_units"
                ].sum()
            ),
            "roi_pct": (
                float(
                    selections[
                        "realized_roi_units"
                    ].mean()
                    * 100.0
                )
                if len(selections)
                else None
            ),
            "positive_windows": int(
                sum(
                    rows[
                        "realized_roi_units"
                    ].mean()
                    > 0.0
                    for _, rows in selections.groupby(
                        "test_start"
                    )
                )
            ),
            "by_stat": _group_performance(
                selections,
                ["stat_key"],
            ),
            "by_window": _group_performance(
                selections,
                ["test_start"],
            ),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(
        output_dir / "predictions.parquet",
        index=False,
    )
    selections.to_parquet(
        output_dir / "exact_policy_selections.parquet",
        index=False,
    )
    windows.to_json(
        output_dir / "window_summary.json",
        orient="records",
        indent=2,
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    args = parse_args()
    features = pd.read_parquet(
        args.offline_v1_dir
        / "features"
        / "market_points_primary.parquet"
    )
    lines = pd.read_parquet(
        args.offline_v1_dir
        / "normalized"
        / "market_lines.parquet"
    )
    team_stats = pd.read_parquet(
        args.offline_v1_dir
        / "normalized"
        / "team_stats_long.parquet"
    )
    modeling_frame, dataset_audit = (
        prepare_modeling_frame(
            annotate_backtest_timing(features, lines)
        )
    )
    compact_features, compact_audit = (
        build_asof_compact_model_features(
            modeling_frame,
            team_stats,
            availability_buffer_hours=3.0,
        )
    )
    context_features, context_audit = (
        build_asof_context_model_features(
            modeling_frame,
            team_stats,
            availability_buffer_hours=3.0,
            windows=(5, 10),
        )
    )
    model_features = pd.concat(
        [compact_features, context_features],
        axis=1,
    )
    market_frame = build_market_classifier_frame(
        modeling_frame,
        model_features,
    )
    predictions, windows = (
        run_nested_regularization_walk_forward(
            market_frame,
            NestedRegularizationConfig(
                evaluation_end_date=(
                    args.evaluation_end_date
                )
            ),
        )
    )
    predictions["model_name"] = "asof_cross_stat_context"
    selections = select_market_classifier_bets(
        predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )
    markets = predictions.drop_duplicates("sample_key")
    markets = markets[markets["is_over_win"].notna()]
    summary = {
        "configuration": {
            "context_windows": [5, 10],
            "minimum_ev": 0.075,
            "maximum_ev": 0.25,
            "evaluation_end_date": (
                args.evaluation_end_date
            ),
        },
        "dataset_audit": dataset_audit.__dict__,
        "compact_asof_audit": compact_audit,
        "context_asof_audit": context_audit,
        "feature_columns": int(len(model_features.columns)),
        "context_feature_columns": int(
            len(context_features.columns)
        ),
        "probability": {
            "markets": int(len(markets)),
            "brier": float(
                brier_score_loss(
                    markets["is_over_win"],
                    markets[
                        "predicted_over_probability"
                    ],
                )
            ),
        },
        "performance": {
            "bets": int(len(selections)),
            "matches": int(
                selections[
                    "exposure_match_id"
                ].nunique()
            ),
            "pnl_units": float(
                selections[
                    "realized_roi_units"
                ].sum()
            ),
            "roi_pct": (
                float(
                    selections[
                        "realized_roi_units"
                    ].mean()
                    * 100.0
                )
                if len(selections)
                else None
            ),
            "positive_windows": int(
                sum(
                    rows[
                        "realized_roi_units"
                    ].mean()
                    > 0.0
                    for _, rows in selections.groupby(
                        "test_start"
                    )
                )
            ),
            "by_stat": _group_performance(
                selections,
                ["stat_key"],
            ),
            "by_window": _group_performance(
                selections,
                ["test_start"],
            ),
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(
        args.output_dir / "predictions.parquet",
        index=False,
    )
    selections.to_parquet(
        args.output_dir / "exact_policy_selections.parquet",
        index=False,
    )
    windows.to_json(
        args.output_dir / "window_summary.json",
        orient="records",
        indent=2,
    )
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    reduced_output = (
        args.output_dir.parent
        / "experiment_056_reduced_asof_context"
    )
    profiles = {
        "xg_big_chances_10": (
            "expectedGoals",
            "bigChanceCreated",
        ),
        "xg_big_chances_possession_10": (
            "expectedGoals",
            "bigChanceCreated",
            "ballPossession",
        ),
        "target_support_stats_10": (
            "cornerKicks",
            "shotsOnGoal",
            "totalShotsOnGoal",
        ),
    }
    reduced_summaries: list[dict[str, object]] = []
    for profile_name, stat_keys in profiles.items():
        context_columns = [
            column
            for column in context_features.columns
            if column.endswith("_10")
            and any(
                column.startswith(f"context_{stat_key}_")
                for stat_key in stat_keys
            )
        ]
        profile_features = pd.concat(
            [
                compact_features,
                context_features[context_columns],
            ],
            axis=1,
        )
        profile_summary = _run_profile(
            modeling_frame=modeling_frame,
            model_features=profile_features,
            model_name=profile_name,
            output_dir=reduced_output / profile_name,
            evaluation_end_date=args.evaluation_end_date,
        )
        profile_summary["context_stat_keys"] = list(
            stat_keys
        )
        profile_summary["context_windows"] = [10]
        profile_summary["context_feature_columns"] = len(
            context_columns
        )
        reduced_summaries.append(profile_summary)
    reduced_output.mkdir(parents=True, exist_ok=True)
    (
        reduced_output / "summary.json"
    ).write_text(
        json.dumps(
            reduced_summaries,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
