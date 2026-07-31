from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

from ullebets_v2.ev_model.categorical_interactions import (
    add_categorical_interaction_features,
)
from ullebets_v2.ev_model.count_ensemble import (
    blend_reference_with_count,
    gate_reference_by_count_agreement,
    merge_reference_count_predictions,
)
from ullebets_v2.ev_model.falsification import (
    build_candidate_falsification_report,
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
from ullebets_v2.ev_model.robustness import (
    DEFAULT_THRESHOLD_GRID,
    build_robustness_report,
)


MINIMUM_EV = 0.075
MAXIMUM_EV = 0.25
PRIOR_HISTORICAL_FAMILY_SIZE = 210
MOVEMENT_BLEND_WEIGHTS = (0.10, 0.25)
MOVEMENT_AGREEMENT_MINIMUM_EV = 0.0
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
            "Test strictly as-of opening-to-current market movement "
            "features in the frozen V6 architecture."
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
        "--output-dir",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_071_snapshot_movement"
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


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(
            _json_safe(payload),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


def _primary_scope(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[
        frame["stat_key"].eq("cornerKicks")
        & frame["scope"].isin(["away", "total"])
    ].copy()


def _select(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_targets = select_market_classifier_bets(
        predictions,
        minimum_ev=MINIMUM_EV,
        maximum_ev=MAXIMUM_EV,
    )
    return all_targets, _primary_scope(all_targets)


def _performance(frame: pd.DataFrame) -> dict[str, object]:
    return {
        "bets": int(len(frame)),
        "matches": int(frame["exposure_match_id"].nunique()),
        "pnl_units": float(frame["realized_roi_units"].sum()),
        "roi_pct": (
            float(frame["realized_roi_units"].mean() * 100.0)
            if len(frame)
            else None
        ),
        "positive_windows": int(
            sum(
                rows["realized_roi_units"].mean() > 0.0
                for _, rows in frame.groupby("test_start")
            )
        ),
        "windows_with_bets": int(frame["test_start"].nunique()),
    }


def _market_brier(predictions: pd.DataFrame) -> dict[str, object]:
    markets = predictions[
        predictions["direction"].eq("over")
        & predictions["is_over_win"].notna()
    ]
    return {
        "markets": int(len(markets)),
        "brier": float(
            brier_score_loss(
                markets["is_over_win"],
                markets["predicted_over_probability"],
            )
        ),
    }


def _one_per_match(frame: pd.DataFrame) -> dict[str, object]:
    selected = (
        frame.sort_values(
            "expected_roi_units",
            ascending=False,
            kind="stable",
        )
        .drop_duplicates("exposure_match_id", keep="first")
    )
    return _performance(selected)


def _segments(frame: pd.DataFrame) -> dict[str, object]:
    def grouped(columns: list[str]) -> list[dict[str, object]]:
        rows = (
            frame.groupby(columns, dropna=False)
            .agg(
                bets=("realized_roi_units", "size"),
                matches=("exposure_match_id", "nunique"),
                pnl_units=("realized_roi_units", "sum"),
                roi_pct=("realized_roi_units", "mean"),
            )
            .reset_index()
        )
        rows["roi_pct"] *= 100.0
        return rows.to_dict(orient="records")

    return {
        "stat": grouped(["stat_key"]),
        "period": grouped(["period"]),
        "scope": grouped(["scope"]),
        "window": grouped(["test_start"]),
        "stat_period_scope": grouped(
            ["stat_key", "period", "scope"]
        ),
    }


def _movement_candidate_frame(
    market_frame: pd.DataFrame,
    movement_features: pd.DataFrame,
) -> pd.DataFrame:
    if len(market_frame) != len(movement_features):
        raise ValueError(
            "market and movement feature rows must have equal length"
        )
    candidate = add_categorical_interaction_features(
        market_frame,
        category_column="scope",
        source_columns=SCOPE_INTERACTION_SOURCE_COLUMNS,
        deviation_values=("home", "away"),
    )
    for column in MOVEMENT_MODEL_FEATURE_COLUMNS:
        candidate[column] = movement_features[column].to_numpy()
    return candidate


def _agreement_threshold_sensitivity(
    reference: pd.DataFrame,
    movement: pd.DataFrame,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for threshold in DEFAULT_THRESHOLD_GRID:
        reference_selected = select_market_classifier_bets(
            reference,
            minimum_ev=float(threshold),
            maximum_ev=MAXIMUM_EV,
        )
        gated = gate_reference_by_count_agreement(
            reference_selected,
            movement,
            minimum_count_ev=MOVEMENT_AGREEMENT_MINIMUM_EV,
            model_name="v6_reference_movement_agreement_ev0",
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


def _leakage_audit(
    market_frame: pd.DataFrame,
    movement_predictions: pd.DataFrame,
    reference: pd.DataFrame,
    source_audit: dict[str, object],
) -> dict[str, object]:
    train_end = pd.to_datetime(
        movement_predictions["train_end"],
        errors="coerce",
    )
    match_day = pd.to_datetime(
        movement_predictions["match_date"],
        errors="coerce",
    )
    join_keys = ["side_key", "test_start", "test_end"]
    universe = reference[join_keys].merge(
        movement_predictions[join_keys],
        on=join_keys,
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    forbidden = {
        "actual_value",
        "is_over_win",
        "match_start_time",
        "odds_snapshot_time",
        "over_realized_roi_units",
        "over_settlement_result",
        "under_realized_roi_units",
        "under_settlement_result",
    }
    forbidden_used = sorted(
        forbidden.intersection(MOVEMENT_MODEL_FEATURE_COLUMNS)
    )
    usable_rate = (
        float(source_audit["rows_with_usable_movement"])
        / len(market_frame)
    )
    status = (
        "ok"
        if (
            int(source_audit["future_market_observations_used"])
            == 0
            and train_end.lt(match_day).all()
            and universe["_merge"].eq("both").all()
            and not forbidden_used
            and usable_rate >= 0.80
        )
        else "fail"
    )
    return {
        "status": status,
        "source_movement_audit": source_audit,
        "usable_movement_rate": usable_rate,
        "model_feature_columns": list(
            MOVEMENT_MODEL_FEATURE_COLUMNS
        ),
        "forbidden_features_used": forbidden_used,
        "train_end_at_or_after_test_match": int(
            train_end.ge(match_day).sum()
        ),
        "prediction_universe": {
            str(key): int(value)
            for key, value in (
                universe["_merge"].value_counts().items()
            )
        },
        "duplicate_movement_prediction_keys": int(
            movement_predictions.duplicated(join_keys).sum()
        ),
    }


def main() -> int:
    args = parse_args()
    market_frame = pd.read_parquet(args.market_frame)
    snapshots = pd.read_parquet(args.market_snapshots)
    reference = pd.read_parquet(args.v6_predictions)
    raw_movement, movement_audit = (
        build_snapshot_movement_features(
            market_frame,
            snapshots,
        )
    )
    movement_features = (
        transform_movement_features_for_model(raw_movement)
    )
    candidate_frame = _movement_candidate_frame(
        market_frame,
        movement_features,
    )
    movement_predictions, movement_windows = (
        run_nested_regularization_walk_forward(
            candidate_frame,
            NestedRegularizationConfig(
                evaluation_end_date=args.evaluation_end_date,
            ),
        )
    )
    movement_name = "v6_scope_movement_features"
    movement_predictions["model_name"] = movement_name
    movement_predictions["predicted_push_probability"] = 0.0
    merged = merge_reference_count_predictions(
        reference,
        movement_predictions,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_movement.to_parquet(
        args.output_dir / "raw_movement_features.parquet",
        index=False,
    )
    movement_features.to_parquet(
        args.output_dir / "model_movement_features.parquet",
        index=False,
    )
    movement_windows.to_json(
        args.output_dir / "movement_windows.json",
        orient="records",
        indent=2,
    )

    reference_all, reference_primary = _select(reference)
    movement_all, movement_primary = _select(
        movement_predictions
    )
    variants: dict[str, dict[str, pd.DataFrame]] = {
        movement_name: {
            "predictions": movement_predictions,
            "all": movement_all,
            "primary": movement_primary,
        }
    }
    for movement_weight in MOVEMENT_BLEND_WEIGHTS:
        name = (
            "v6_movement_blend_"
            f"{int((1.0 - movement_weight) * 100)}_"
            f"{int(movement_weight * 100)}"
        )
        predictions = blend_reference_with_count(
            merged,
            count_weight=movement_weight,
            model_name=name,
        )
        all_targets, primary = _select(predictions)
        variants[name] = {
            "predictions": predictions,
            "all": all_targets,
            "primary": primary,
        }

    agreement_name = "v6_reference_movement_agreement_ev0"
    agreement_all = gate_reference_by_count_agreement(
        reference_all,
        movement_predictions,
        minimum_count_ev=MOVEMENT_AGREEMENT_MINIMUM_EV,
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
    leakage = _leakage_audit(
        market_frame,
        movement_predictions,
        reference,
        movement_audit,
    )
    summaries: list[dict[str, object]] = []
    paired_by_name: dict[str, dict[str, object]] = {}
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
        paired_by_name[name] = paired
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
                    )
                )
            }
        )
        _write_json(variant_dir / "paired_vs_v6.json", paired)
        _write_json(variant_dir / "robustness.json", robustness)
        summaries.append(
            {
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
        )

    retention: list[dict[str, object]] = []
    for summary in summaries:
        name = str(summary["variant"])
        falsification_row = falsification_by_name[name]
        paired = paired_by_name[name]
        primary = summary["corners_away_total"]
        one_per_match = summary["one_per_match"]
        paired_bootstrap = paired["paired_bootstrap"]
        brier_improvement = paired["prediction_quality"][
            "brier_improvement"
        ]
        stressed_roi = falsification_row["price_stress"][
            "minus_0.10_decimal"
        ]["roi_pct"]
        passes = bool(
            leakage["status"] == "ok"
            and falsification_row["mechanical_gate_status"]
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
                "retention_gate": "passes" if passes else "fails",
                "registry_action": (
                    "new_generation_required"
                    if passes
                    else "none"
                ),
                "reasons": [
                    reason
                    for condition, reason in (
                        (
                            leakage["status"] != "ok",
                            "movement leakage/coverage audit failed",
                        ),
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

    report = {
        "experiment": "071_snapshot_movement",
        "configuration": {
            "architecture": (
                "V6 nested scope interactions plus strictly as-of "
                "signed-log market movement features"
            ),
            "minimum_ev": MINIMUM_EV,
            "maximum_ev": MAXIMUM_EV,
            "movement_blend_weights": list(
                MOVEMENT_BLEND_WEIGHTS
            ),
            "movement_agreement_minimum_ev": (
                MOVEMENT_AGREEMENT_MINIMUM_EV
            ),
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
        "leakage_audit": leakage,
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
        "movement_window_metrics": movement_windows.to_dict(
            orient="records"
        ),
        "variants": summaries,
        "retention_decisions": retention,
        "registry_v5_mutated": False,
        "evidence_limit": (
            "The snapshot history and outcomes were already available. "
            "Any retained result would remain score-only until untouched "
            "in-domain forward settlement."
        ),
    }
    _write_json(args.output_dir / "movement_audit.json", movement_audit)
    _write_json(args.output_dir / "leakage_audit.json", leakage)
    _write_json(args.output_dir / "falsification.json", falsification)
    _write_json(args.output_dir / "summary.json", summaries)
    _write_json(args.output_dir / "experiment_report.json", report)
    print(
        json.dumps(
            {
                "experiment": report["experiment"],
                "leakage_status": leakage["status"],
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
