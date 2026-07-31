from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (SRC, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pandas as pd

from run_ev_snapshot_movement_experiment import (
    _market_brier,
    _one_per_match,
    _performance,
    _primary_scope,
    _segments,
    _select,
    _write_json,
)
from run_ev_combined_microstructure_experiment import (
    _prediction_universe_audit,
)
from ullebets_v2.ev_model.categorical_interactions import (
    add_categorical_interaction_features,
)
from ullebets_v2.ev_model.falsification import (
    build_candidate_falsification_report,
)
from ullebets_v2.ev_model.market_classifier import (
    MARKET_CATEGORICAL_COLUMNS,
    MARKET_EXCLUDED_COLUMNS,
)
from ullebets_v2.ev_model.market_walk_forward import (
    MarketWalkForwardConfig,
    run_market_classifier_walk_forward,
)
from ullebets_v2.ev_model.model_comparison import (
    build_paired_strategy_comparison,
)
from ullebets_v2.ev_model.robustness import (
    DEFAULT_THRESHOLD_GRID,
    build_robustness_report,
)


MINIMUM_EV = 0.075
MAXIMUM_EV = 0.25
PRIOR_HISTORICAL_FAMILY_SIZE = 426
MODEL_NAMES = ("hgb_market", "market_residual_hgb")
NEW_POLICY_VARIANTS_INSPECTED = (
    len(MODEL_NAMES) * len(DEFAULT_THRESHOLD_GRID) * 2
)
TOTAL_HISTORICAL_FAMILY_SIZE = (
    PRIOR_HISTORICAL_FAMILY_SIZE
    + NEW_POLICY_VARIANTS_INSPECTED
)

SCOPE_INTERACTION_SOURCE_COLUMNS = (
    "line_value",
    "market_fair_probability_over",
    "market_anchor_lambda",
    "baseline_lambda",
    "history_role_expected_10",
    "history_all_expected_10",
    "history_role_trend_3_10",
    "history_all_trend_3_10",
)

FORBIDDEN_MODEL_COLUMNS = {
    "actual_value",
    "is_over_win",
    "over_realized_roi_units",
    "over_settlement_result",
    "under_realized_roi_units",
    "under_settlement_result",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test the existing nonlinear HGB families on the exact "
            "snapshot-as-of V6 feature contract."
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
            "experiment_077_exact_asof_hgb"
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


def _candidate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return add_categorical_interaction_features(
        frame,
        category_column="scope",
        source_columns=SCOPE_INTERACTION_SOURCE_COLUMNS,
        deviation_values=("home", "away"),
    )


def _feature_contract_audit(
    frame: pd.DataFrame,
) -> dict[str, object]:
    categorical = [
        column
        for column in MARKET_CATEGORICAL_COLUMNS
        if column in frame.columns
    ]
    numeric = [
        column
        for column in frame.columns
        if column not in MARKET_EXCLUDED_COLUMNS
        and column not in categorical
        and pd.api.types.is_numeric_dtype(frame[column])
        and frame[column].notna().any()
    ]
    used = set(categorical) | set(numeric)
    forbidden_used = sorted(used & FORBIDDEN_MODEL_COLUMNS)
    snapshot_time = pd.to_datetime(
        frame["odds_snapshot_time"],
        errors="coerce",
        utc=True,
    )
    start_time = pd.to_datetime(
        frame["match_start_time"],
        errors="coerce",
        utc=True,
    )
    missing_snapshot = int(snapshot_time.isna().sum())
    missing_start = int(start_time.isna().sum())
    post_start = int(
        (
            snapshot_time.notna()
            & start_time.notna()
            & snapshot_time.ge(start_time)
        ).sum()
    )
    status = (
        "ok"
        if not forbidden_used
        and missing_snapshot == 0
        and missing_start == 0
        and post_start == 0
        else "fail"
    )
    return {
        "rows": int(len(frame)),
        "numeric_features": numeric,
        "categorical_features": categorical,
        "forbidden_features_used": forbidden_used,
        "missing_snapshot_time": missing_snapshot,
        "missing_match_start_time": missing_start,
        "snapshot_at_or_after_start": post_start,
        "status": status,
    }


def main() -> int:
    args = parse_args()
    market_frame = pd.read_parquet(args.market_frame)
    reference = pd.read_parquet(args.v6_predictions)
    candidate_frame = _candidate_frame(market_frame)
    feature_audit = _feature_contract_audit(candidate_frame)
    if feature_audit["status"] != "ok":
        raise ValueError("HGB feature contract audit failed")

    predictions, windows = run_market_classifier_walk_forward(
        candidate_frame,
        MarketWalkForwardConfig(
            train_window_days=90,
            test_window_days=14,
            step_days=14,
            min_train_rows=250,
            recency_half_life_days=45.0,
            model_names=MODEL_NAMES,
            minimum_ev_thresholds=(),
            evaluation_end_date=args.evaluation_end_date,
        ),
    )
    model_predictions = {
        name: predictions[
            predictions["model_name"].eq(name)
        ].reset_index(drop=True)
        for name in MODEL_NAMES
    }
    universe_audit = _prediction_universe_audit(
        {"v6": reference, **model_predictions}
    )
    if universe_audit["status"] != "ok":
        raise ValueError("HGB prediction universes do not match V6")

    reference_all, reference_primary = _select(reference)
    selected: dict[str, dict[str, pd.DataFrame]] = {}
    for name, frame in model_predictions.items():
        all_targets, primary = _select(frame)
        selected[name] = {
            "predictions": frame,
            "all": all_targets,
            "primary": primary,
        }

    falsification = build_candidate_falsification_report(
        {
            name: frames["primary"]
            for name, frames in selected.items()
        },
        experiments_inspected=TOTAL_HISTORICAL_FAMILY_SIZE,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    falsification_by_name = {
        row["candidate"]: row
        for row in falsification["candidates"]
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    windows.to_json(
        args.output_dir / "walk_forward_windows.json",
        orient="records",
        indent=2,
    )

    summaries: list[dict[str, object]] = []
    retention: list[dict[str, object]] = []
    for name, frames in selected.items():
        variant_dir = args.output_dir / name
        variant_dir.mkdir(parents=True, exist_ok=True)
        frames["predictions"].to_parquet(
            variant_dir / "predictions.parquet",
            index=False,
        )
        frames["primary"].to_parquet(
            variant_dir / "exact_policy_selections.parquet",
            index=False,
        )
        paired = build_paired_strategy_comparison(
            reference_selections=reference_primary,
            challenger_selections=frames["primary"],
            reference_predictions=reference,
            challenger_predictions=frames["predictions"],
            bootstrap_iterations=args.bootstrap_iterations,
        )
        robustness = build_robustness_report(
            _primary_scope(frames["predictions"]),
            minimum_ev=MINIMUM_EV,
            maximum_ev=MAXIMUM_EV,
        )
        _write_json(variant_dir / "paired_vs_v6.json", paired)
        _write_json(variant_dir / "robustness.json", robustness)
        summary = {
            "variant": name,
            "calibration": _market_brier(
                frames["predictions"]
            ),
            "all_targets": _performance(frames["all"]),
            "corners_away_total": _performance(
                frames["primary"]
            ),
            "one_per_match": _one_per_match(
                frames["primary"]
            ),
            "segments": _segments(frames["primary"]),
        }
        summaries.append(summary)

        falsification_row = falsification_by_name[name]
        paired_bootstrap = paired["paired_bootstrap"]
        brier_improvement = paired["prediction_quality"][
            "brier_improvement"
        ]
        stressed_roi = falsification_row["price_stress"][
            "minus_0.10_decimal"
        ]["roi_pct"]
        primary = summary["corners_away_total"]
        one_per_match = summary["one_per_match"]
        passes = bool(
            falsification_row["mechanical_gate_status"]
            == "passes"
            and primary["positive_windows"]
            == primary["windows_with_bets"]
            and one_per_match["roi_pct"] is not None
            and float(one_per_match["roi_pct"]) > 0.0
            and stressed_roi is not None
            and float(stressed_roi) > 0.0
            and paired_bootstrap["low_95_pct"] is not None
            and float(paired_bootstrap["low_95_pct"]) > 0.0
            and brier_improvement is not None
            and float(brier_improvement) >= 0.0
        )
        retention.append(
            {
                "variant": name,
                "retention_gate": (
                    "passes" if passes else "fails"
                ),
                "registry_action": (
                    "new_generation_required"
                    if passes
                    else "none"
                ),
                "reasons": [
                    reason
                    for condition, reason in (
                        (
                            falsification_row[
                                "mechanical_gate_status"
                            ]
                            != "passes",
                            "historical falsification gate failed",
                        ),
                        (
                            primary["positive_windows"]
                            != primary["windows_with_bets"],
                            "not every betting window was positive",
                        ),
                        (
                            one_per_match["roi_pct"] is None
                            or float(one_per_match["roi_pct"]) <= 0.0,
                            "one-per-match sensitivity was not positive",
                        ),
                        (
                            stressed_roi is None
                            or float(stressed_roi) <= 0.0,
                            "0.10 decimal price stress was not positive",
                        ),
                        (
                            paired_bootstrap["low_95_pct"] is None
                            or float(
                                paired_bootstrap["low_95_pct"]
                            )
                            <= 0.0,
                            "paired ROI improvement over V6 was not proven",
                        ),
                        (
                            brier_improvement is None
                            or float(brier_improvement) < 0.0,
                            "full-universe Brier score worsened",
                        ),
                    )
                    if condition
                ],
            }
        )

    timing_violations = {
        name: int(
            (
                pd.to_datetime(frame["train_end"])
                >= pd.to_datetime(frame["match_date"])
            ).sum()
        )
        for name, frame in model_predictions.items()
    }
    report = {
        "experiment": "077_exact_asof_hgb",
        "configuration": {
            "models": list(MODEL_NAMES),
            "feature_contract": (
                "V6 exact snapshot-as-of compact features plus "
                "scope deviations"
            ),
            "train_window_days": 90,
            "recency_half_life_days": 45.0,
            "minimum_ev": MINIMUM_EV,
            "maximum_ev": MAXIMUM_EV,
            "prior_historical_family_size": (
                PRIOR_HISTORICAL_FAMILY_SIZE
            ),
            "new_policy_variants_inspected": (
                NEW_POLICY_VARIANTS_INSPECTED
            ),
            "total_historical_family_size": (
                TOTAL_HISTORICAL_FAMILY_SIZE
            ),
        },
        "feature_contract_audit": feature_audit,
        "prediction_universe_audit": universe_audit,
        "timing_audit": {
            "train_end_at_or_after_test_match": (
                timing_violations
            ),
            "future_snapshot_features_used": 0,
            "status": (
                "ok"
                if not any(timing_violations.values())
                else "fail"
            ),
        },
        "reference": {
            "calibration": _market_brier(reference),
            "all_targets": _performance(reference_all),
            "corners_away_total": _performance(
                reference_primary
            ),
            "one_per_match": _one_per_match(
                reference_primary
            ),
        },
        "variants": summaries,
        "retention_decisions": retention,
        "registry_v5_mutated": False,
        "evidence_limit": (
            "The HGB family is now tested on the corrected feature "
            "contract, but every historical outcome remains inspected."
        ),
    }
    _write_json(args.output_dir / "falsification.json", falsification)
    _write_json(args.output_dir / "summary.json", summaries)
    _write_json(args.output_dir / "experiment_report.json", report)
    print(
        json.dumps(
            {
                "reference": report["reference"],
                "variants": [
                    {
                        "variant": row["variant"],
                        "calibration": row["calibration"],
                        "corners_away_total": (
                            row["corners_away_total"]
                        ),
                    }
                    for row in summaries
                ],
                "retention": retention,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
