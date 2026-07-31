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
from sklearn.metrics import brier_score_loss, log_loss

from ullebets_v1.audit.odds_timing import annotate_backtest_timing
from ullebets_v2.ev_model.asof_features import (
    build_asof_compact_model_features,
)
from ullebets_v2.ev_model.dataset import prepare_modeling_frame
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
            "Run nested temporal logistic-regularization selection."
        )
    )
    parser.add_argument("--offline-v1-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--evaluation-end-date", default="2026-05-24")
    parser.add_argument(
        "--history-availability-buffer-hours",
        type=float,
        default=3.0,
    )
    return parser.parse_args()


def _performance(frame: pd.DataFrame) -> dict[str, float | int]:
    pnl = pd.to_numeric(
        frame.get("realized_roi_units"),
        errors="coerce",
    ).fillna(0.0)
    return {
        "bets": int(len(frame)),
        "matches": int(frame["exposure_match_id"].nunique()),
        "pnl_units": float(pnl.sum()),
        "roi_pct": float(pnl.mean() * 100.0) if len(frame) else 0.0,
    }


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
    modeling_frame, dataset_audit = prepare_modeling_frame(
        annotate_backtest_timing(features, lines)
    )
    model_features, asof_audit = (
        build_asof_compact_model_features(
            modeling_frame,
            team_stats,
            availability_buffer_hours=(
                args.history_availability_buffer_hours
            ),
        )
    )
    market_frame = build_market_classifier_frame(
        modeling_frame,
        model_features,
    )
    config = NestedRegularizationConfig(
        evaluation_end_date=args.evaluation_end_date,
    )
    predictions, windows = (
        run_nested_regularization_walk_forward(
            market_frame,
            config,
        )
    )
    markets = predictions.drop_duplicates(
        ["model_name", "sample_key"]
    )
    markets = markets[markets["is_over_win"].notna()]
    exact_policy = select_market_classifier_bets(
        predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )
    policy_windows = [
        {
            "test_start": str(test_start),
            **_performance(rows),
        }
        for test_start, rows in exact_policy.groupby("test_start")
    ]
    summary = {
        "configuration": {
            **config.__dict__,
            "history_availability_buffer_hours": (
                args.history_availability_buffer_hours
            ),
        },
        "dataset_audit": dataset_audit.__dict__,
        "asof_audit": asof_audit,
        "probability": {
            "markets": int(len(markets)),
            "brier": float(
                brier_score_loss(
                    markets["is_over_win"],
                    markets["predicted_over_probability"],
                )
            ),
            "log_loss": float(
                log_loss(
                    markets["is_over_win"],
                    markets["predicted_over_probability"],
                    labels=[0, 1],
                )
            ),
        },
        "exact_v3_policy": {
            **_performance(exact_policy),
            "positive_windows": sum(
                row["roi_pct"] > 0.0
                for row in policy_windows
            ),
            "windows": policy_windows,
        },
        "selected_c_by_window": windows[
            [
                "test_start",
                "selected_logistic_c",
                "selected_validation_brier",
                "test_brier",
            ]
        ].to_dict("records"),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(
        args.output_dir / "predictions.parquet",
        index=False,
    )
    windows.to_json(
        args.output_dir / "window_summary.json",
        orient="records",
        indent=2,
    )
    exact_policy.to_parquet(
        args.output_dir / "exact_policy_selections.parquet",
        index=False,
    )
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
