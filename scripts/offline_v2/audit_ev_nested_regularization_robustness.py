from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np
import pandas as pd

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


VARIANTS = (
    ("validation_14_full_grid", 14, (0.01, 0.03, 0.10, 0.25, 0.75, 2.0)),
    ("validation_21_full_grid", 21, (0.01, 0.03, 0.10, 0.25, 0.75, 2.0)),
    ("validation_28_full_grid", 28, (0.01, 0.03, 0.10, 0.25, 0.75, 2.0)),
    ("validation_42_full_grid", 42, (0.01, 0.03, 0.10, 0.25, 0.75, 2.0)),
    ("validation_21_no_c2", 21, (0.01, 0.03, 0.10, 0.25, 0.75)),
    ("validation_21_strong_only", 21, (0.01, 0.03, 0.10, 0.25)),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit temporal and regularization-grid sensitivity for the "
            "nested logistic challenger."
        )
    )
    parser.add_argument("--offline-v1-dir", type=Path, required=True)
    parser.add_argument("--v3-predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--evaluation-end-date", default="2026-05-24")
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


def _cluster_bootstrap(
    frame: pd.DataFrame,
    *,
    iterations: int = 50_000,
) -> dict[str, float | int | None]:
    if frame.empty:
        return {
            "clusters": 0,
            "low_95_pct": None,
            "high_95_pct": None,
            "probability_positive": None,
        }
    clusters = (
        frame.groupby("exposure_match_id")["realized_roi_units"]
        .agg(["sum", "size"])
        .to_numpy(dtype=float)
    )
    rng = np.random.default_rng(20260730)
    sampled = clusters[
        rng.integers(
            0,
            len(clusters),
            size=(iterations, len(clusters)),
        )
    ]
    roi = (
        sampled[:, :, 0].sum(axis=1)
        / sampled[:, :, 1].sum(axis=1)
        * 100.0
    )
    return {
        "clusters": int(len(clusters)),
        "low_95_pct": float(np.quantile(roi, 0.025)),
        "high_95_pct": float(np.quantile(roi, 0.975)),
        "probability_positive": float(np.mean(roi > 0.0)),
    }


def _side_keys(frame: pd.DataFrame) -> set[str]:
    return set(frame["side_key"].astype(str))


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
    modeling_frame, _ = prepare_modeling_frame(
        annotate_backtest_timing(features, lines)
    )
    model_features, asof_audit = (
        build_asof_compact_model_features(
            modeling_frame,
            team_stats,
            availability_buffer_hours=3.0,
        )
    )
    market_frame = build_market_classifier_frame(
        modeling_frame,
        model_features,
    )

    v3_predictions = pd.read_parquet(args.v3_predictions)
    v3_predictions = v3_predictions[
        v3_predictions["model_name"].eq("logistic_market")
    ]
    v3_selections = select_market_classifier_bets(
        v3_predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )
    v3_keys = _side_keys(v3_selections)

    result_rows: list[dict[str, object]] = []
    prediction_parts: list[pd.DataFrame] = []
    for variant, validation_days, c_grid in VARIANTS:
        config = NestedRegularizationConfig(
            validation_window_days=validation_days,
            c_grid=c_grid,
            evaluation_end_date=args.evaluation_end_date,
        )
        predictions, windows = (
            run_nested_regularization_walk_forward(
                market_frame,
                config,
            )
        )
        selections = select_market_classifier_bets(
            predictions,
            minimum_ev=0.075,
            maximum_ev=0.25,
        )
        selection_windows = [
            _performance(rows)
            for _, rows in selections.groupby("test_start")
        ]
        challenger_keys = _side_keys(selections)
        predictions["robustness_variant"] = variant
        prediction_parts.append(predictions)
        result_rows.append(
            {
                "variant": variant,
                "validation_window_days": validation_days,
                "c_grid": list(c_grid),
                **_performance(selections),
                "windows": len(selection_windows),
                "positive_windows": sum(
                    row["roi_pct"] > 0.0
                    for row in selection_windows
                ),
                "fallback_windows": int(
                    windows["selection_source"]
                    .eq("default_insufficient_validation")
                    .sum()
                ),
                "selected_c_counts": {
                    str(key): int(value)
                    for key, value in windows[
                        "selected_logistic_c"
                    ].value_counts().items()
                },
                "overlap_with_v3_bets": len(
                    challenger_keys.intersection(v3_keys)
                ),
                "unique_challenger_bets": len(
                    challenger_keys.difference(v3_keys)
                ),
                "cluster_bootstrap": _cluster_bootstrap(
                    selections
                ),
            }
        )

    report = {
        "configuration": {
            "minimum_ev": 0.075,
            "maximum_ev": 0.25,
            "train_window_days": 90,
            "recency_half_life_days": 45.0,
            "default_logistic_c": 0.25,
            "evaluation_end_date": args.evaluation_end_date,
        },
        "asof_audit": asof_audit,
        "v3_reference": {
            **_performance(v3_selections),
            "cluster_bootstrap": _cluster_bootstrap(
                v3_selections
            ),
        },
        "variants": result_rows,
        "decision_rule": (
            "A challenger is not promoted from inspected history unless "
            "results remain positive across the predefined validation and "
            "regularization grids and the clustered lower bound is positive."
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(prediction_parts, ignore_index=True).to_parquet(
        args.output_dir / "variant_predictions.parquet",
        index=False,
    )
    pd.DataFrame(result_rows).to_json(
        args.output_dir / "variant_summary.json",
        orient="records",
        indent=2,
    )
    (args.output_dir / "robustness_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
