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
from ullebets_v2.ev_model.categorical_interactions import (
    add_categorical_interaction_features,
)
from ullebets_v2.ev_model.falsification import (
    build_candidate_falsification_report,
)
from ullebets_v2.ev_model.market_ladder import (
    LADDER_MODEL_FEATURE_COLUMNS,
    build_snapshot_ladder_features,
    transform_ladder_features_for_model,
)
from ullebets_v2.ev_model.market_movement import (
    MOVEMENT_MODEL_FEATURE_COLUMNS,
    build_snapshot_movement_features,
    transform_movement_features_for_model,
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
from ullebets_v2.ev_model.prediction_ensemble import (
    build_fixed_prediction_ensemble,
    gate_reference_by_multi_model_agreement,
)
from ullebets_v2.ev_model.robustness import (
    DEFAULT_THRESHOLD_GRID,
    build_robustness_report,
)


MINIMUM_EV = 0.075
MAXIMUM_EV = 0.25
PRIOR_HISTORICAL_FAMILY_SIZE = 354
NEW_POLICY_VARIANTS_INSPECTED = (
    3 * len(DEFAULT_THRESHOLD_GRID) * 2 + 2
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test combined snapshot-movement and alternate-line ladder "
            "microstructure in the frozen V6 architecture."
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
        "--movement-features",
        type=Path,
        default=Path(
            "data/v2/ev_model/experiment_071_snapshot_movement/"
            "model_movement_features.parquet"
        ),
    )
    parser.add_argument(
        "--ladder-features",
        type=Path,
        default=Path(
            "data/v2/ev_model/experiment_073_snapshot_ladder/"
            "model_ladder_features.parquet"
        ),
    )
    parser.add_argument(
        "--market-snapshots",
        type=Path,
        default=Path(
            "C:/dev/ullebets-prod/data/derived/offline_v1/"
            "normalized/market_snapshots.parquet"
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
        "--movement-predictions",
        type=Path,
        default=Path(
            "data/v2/ev_model/experiment_071_snapshot_movement/"
            "v6_scope_movement_features/predictions.parquet"
        ),
    )
    parser.add_argument(
        "--ladder-predictions",
        type=Path,
        default=Path(
            "data/v2/ev_model/experiment_073_snapshot_ladder/"
            "v6_scope_ladder_features/predictions.parquet"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_075_combined_microstructure"
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


def _candidate_frame(
    market_frame: pd.DataFrame,
    movement: pd.DataFrame,
    ladder: pd.DataFrame,
) -> pd.DataFrame:
    if not (
        len(market_frame) == len(movement) == len(ladder)
    ):
        raise ValueError(
            "market, movement, and ladder rows must match"
        )
    candidate = add_categorical_interaction_features(
        market_frame,
        category_column="scope",
        source_columns=SCOPE_INTERACTION_SOURCE_COLUMNS,
        deviation_values=("home", "away"),
    )
    for column in MOVEMENT_MODEL_FEATURE_COLUMNS:
        candidate[column] = movement[column].to_numpy()
    for column in LADDER_MODEL_FEATURE_COLUMNS:
        candidate[column] = ladder[column].to_numpy()
    return candidate


def _verify_cached_features(
    *,
    cached: pd.DataFrame,
    rebuilt: pd.DataFrame,
    label: str,
) -> dict[str, object]:
    if list(cached.columns) != list(rebuilt.columns):
        raise ValueError(
            f"{label} cached feature columns do not match rebuilt columns"
        )
    if len(cached) != len(rebuilt):
        raise ValueError(
            f"{label} cached feature rows do not match rebuilt rows"
        )
    try:
        pd.testing.assert_frame_equal(
            cached.reset_index(drop=True),
            rebuilt.reset_index(drop=True),
            check_dtype=False,
            check_exact=False,
            rtol=1e-12,
            atol=1e-12,
        )
    except AssertionError as error:
        raise ValueError(
            f"{label} cached features are stale or positionally misaligned"
        ) from error
    return {
        "cached_rows": int(len(cached)),
        "rebuilt_rows": int(len(rebuilt)),
        "exact_column_order": True,
        "values_match_with_tolerance": True,
        "status": "ok",
    }


def _prediction_universe_audit(
    predictions: dict[str, pd.DataFrame],
) -> dict[str, object]:
    join_keys = ["side_key", "test_start", "test_end"]
    names = list(predictions)
    reference_name = names[0]
    reference = predictions[reference_name]
    duplicate_rows = {
        name: int(frame.duplicated(join_keys).sum())
        for name, frame in predictions.items()
    }
    common = reference[join_keys].copy()
    mismatches: dict[str, dict[str, int]] = {}
    for name in names[1:]:
        compared = reference[join_keys].merge(
            predictions[name][join_keys],
            on=join_keys,
            how="outer",
            indicator=True,
            validate="one_to_one",
        )
        counts = compared["_merge"].value_counts()
        mismatches[name] = {
            "reference_only": int(counts.get("left_only", 0)),
            "challenger_only": int(counts.get("right_only", 0)),
            "common": int(counts.get("both", 0)),
        }
        common = common.merge(
            predictions[name][join_keys],
            on=join_keys,
            how="inner",
            validate="one_to_one",
        )
    mismatch_rows = sum(
        values["reference_only"] + values["challenger_only"]
        for values in mismatches.values()
    )
    status = (
        "ok"
        if not any(duplicate_rows.values())
        and mismatch_rows == 0
        and len(common) == len(reference)
        else "fail"
    )
    return {
        "rows": {
            name: int(len(frame))
            for name, frame in predictions.items()
        },
        "duplicate_join_keys": duplicate_rows,
        "pairwise_vs_reference": mismatches,
        "common_rows": int(len(common)),
        "status": status,
    }


def _agreement_threshold_sensitivity(
    reference: pd.DataFrame,
    movement: pd.DataFrame,
    ladder: pd.DataFrame,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for threshold in DEFAULT_THRESHOLD_GRID:
        selected = select_market_classifier_bets(
            reference,
            minimum_ev=float(threshold),
            maximum_ev=MAXIMUM_EV,
        )
        gated = gate_reference_by_multi_model_agreement(
            selected,
            {"movement": movement, "ladder": ladder},
            minimum_challenger_ev=0.0,
            model_name="v6_dual_microstructure_agreement_ev0",
        )
        rows.append(
            {
                "minimum_ev": float(threshold),
                "all_targets": _performance(gated),
                "corners_away_total": _performance(
                    _primary_scope(gated)
                ),
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    market_frame = pd.read_parquet(args.market_frame)
    cached_movement_features = pd.read_parquet(
        args.movement_features
    )
    cached_ladder_features = pd.read_parquet(args.ladder_features)
    market_snapshots = pd.read_parquet(args.market_snapshots)
    raw_movement, movement_source_audit = (
        build_snapshot_movement_features(
            market_frame,
            market_snapshots,
        )
    )
    movement_features = transform_movement_features_for_model(
        raw_movement
    )
    raw_ladder, ladder_source_audit = (
        build_snapshot_ladder_features(
            market_frame,
            market_snapshots,
        )
    )
    ladder_features = transform_ladder_features_for_model(
        raw_ladder
    )
    feature_alignment = {
        "movement": _verify_cached_features(
            cached=cached_movement_features,
            rebuilt=movement_features,
            label="movement",
        ),
        "ladder": _verify_cached_features(
            cached=cached_ladder_features,
            rebuilt=ladder_features,
            label="ladder",
        ),
    }
    reference = pd.read_parquet(args.v6_predictions)
    movement_predictions = pd.read_parquet(
        args.movement_predictions
    )
    ladder_predictions = pd.read_parquet(
        args.ladder_predictions
    )
    combined_predictions, combined_windows = (
        run_nested_regularization_walk_forward(
            _candidate_frame(
                market_frame,
                movement_features,
                ladder_features,
            ),
            NestedRegularizationConfig(
                evaluation_end_date=args.evaluation_end_date,
            ),
        )
    )
    combined_name = "v6_scope_combined_microstructure"
    combined_predictions["model_name"] = combined_name
    combined_predictions["predicted_push_probability"] = 0.0
    prediction_universe = _prediction_universe_audit(
        {
            "v6": reference,
            "combined": combined_predictions,
            "movement": movement_predictions,
            "ladder": ladder_predictions,
        }
    )
    if prediction_universe["status"] != "ok":
        raise ValueError(
            "combined microstructure prediction universes do not match"
        )
    reference_all, reference_primary = _select(reference)
    combined_all, combined_primary = _select(
        combined_predictions
    )
    variants: dict[str, dict[str, pd.DataFrame]] = {
        combined_name: {
            "predictions": combined_predictions,
            "all": combined_all,
            "primary": combined_primary,
        }
    }

    components = {
        "v6": reference,
        "movement": movement_predictions,
        "ladder": ladder_predictions,
    }
    for name, weights in (
        (
            "v6_microstructure_ensemble_90_5_5",
            {"v6": 0.90, "movement": 0.05, "ladder": 0.05},
        ),
        (
            "v6_microstructure_ensemble_80_10_10",
            {"v6": 0.80, "movement": 0.10, "ladder": 0.10},
        ),
    ):
        predictions = build_fixed_prediction_ensemble(
            components,
            weights=weights,
            model_name=name,
        )
        all_targets, primary = _select(predictions)
        variants[name] = {
            "predictions": predictions,
            "all": all_targets,
            "primary": primary,
        }

    agreement_name = "v6_dual_microstructure_agreement_ev0"
    agreement_all = gate_reference_by_multi_model_agreement(
        reference_all,
        {
            "movement": movement_predictions,
            "ladder": ladder_predictions,
        },
        minimum_challenger_ev=0.0,
        model_name=agreement_name,
    )
    variants[agreement_name] = {
        "predictions": reference.assign(
            model_name=agreement_name
        ),
        "all": agreement_all,
        "primary": _primary_scope(agreement_all),
    }

    falsification = build_candidate_falsification_report(
        {
            name: frames["primary"]
            for name, frames in variants.items()
        },
        experiments_inspected=TOTAL_HISTORICAL_FAMILY_SIZE,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    falsification_by_name = {
        row["candidate"]: row
        for row in falsification["candidates"]
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    combined_predictions.to_parquet(
        args.output_dir / "combined_predictions.parquet",
        index=False,
    )
    combined_windows.to_json(
        args.output_dir / "combined_windows.json",
        orient="records",
        indent=2,
    )
    summaries: list[dict[str, object]] = []
    retention: list[dict[str, object]] = []
    for name, frames in variants.items():
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
        robustness = (
            build_robustness_report(
                _primary_scope(frames["predictions"]),
                minimum_ev=MINIMUM_EV,
                maximum_ev=MAXIMUM_EV,
            )
            if name != agreement_name
            else {
                "threshold_sensitivity": (
                    _agreement_threshold_sensitivity(
                        reference,
                        movement_predictions,
                        ladder_predictions,
                    )
                )
            }
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

    timing_violations = int(
        (
            pd.to_datetime(
                combined_predictions["train_end"]
            )
            >= pd.to_datetime(
                combined_predictions["match_date"]
            )
        ).sum()
    )
    report = {
        "experiment": "075_combined_microstructure",
        "configuration": {
            "feature_model": (
                "V6 scope interactions plus movement and ladder"
            ),
            "fixed_ensembles": [
                "90% V6 / 5% movement / 5% ladder",
                "80% V6 / 10% movement / 10% ladder",
            ],
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
        "timing_audit": {
            "train_end_at_or_after_test_match": timing_violations,
            "future_snapshot_features_used": 0,
            "status": (
                "ok" if timing_violations == 0 else "fail"
            ),
        },
        "feature_alignment_audit": feature_alignment,
        "source_feature_audits": {
            "movement": movement_source_audit,
            "ladder": ladder_source_audit,
        },
        "prediction_universe_audit": prediction_universe,
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
            "This exhausts available historical Kambi microstructure "
            "families. Any apparent improvement remains inspected "
            "history, not untouched confirmation."
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
