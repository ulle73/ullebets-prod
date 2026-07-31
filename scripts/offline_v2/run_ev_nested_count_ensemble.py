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

import pandas as pd
import numpy as np
from sklearn.metrics import brier_score_loss

from ullebets_v2.ev_model.count_ensemble import (
    blend_reference_with_count,
    gate_reference_by_count_agreement,
    merge_reference_count_predictions,
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
from ullebets_v2.ev_model.nested_count import (
    COUNT_CATEGORICAL_COLUMNS,
    COUNT_NUMERIC_COLUMNS,
    NestedCountConfig,
    run_nested_count_walk_forward,
)
from ullebets_v2.ev_model.robustness import (
    DEFAULT_THRESHOLD_GRID,
    build_robustness_report,
)


MINIMUM_EV = 0.075
MAXIMUM_EV = 0.25
PRIOR_HISTORICAL_FAMILY_SIZE = 166
BLEND_COUNT_WEIGHTS = (0.10, 0.25)
COUNT_AGREEMENT_MINIMUM_EV = 0.0

# Three probability policies are inspected at seven EV thresholds for both
# all-target and corner/scope surfaces. The agreement policy adds two more.
NEW_POLICY_VARIANTS_INSPECTED = (
    3 * len(DEFAULT_THRESHOLD_GRID) * 2 + 2
)
TOTAL_HISTORICAL_FAMILY_SIZE = (
    PRIOR_HISTORICAL_FAMILY_SIZE
    + NEW_POLICY_VARIANTS_INSPECTED
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a leakage-safe nested count residual model and fixed "
            "count/V6 ensemble policies."
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
            "experiment_070_nested_count_ensemble"
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


def _write_json(path: Path, payload: object) -> None:
    def json_safe(value: object) -> object:
        if isinstance(value, dict):
            return {
                str(key): json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [json_safe(item) for item in value]
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value

    path.write_text(
        json.dumps(
            json_safe(payload),
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
    ].copy()
    return {
        "markets": int(len(markets)),
        "brier": float(
            brier_score_loss(
                markets["is_over_win"],
                markets["predicted_over_probability"],
            )
        ),
    }


def _segment_rows(frame: pd.DataFrame) -> dict[str, object]:
    def grouped(columns: list[str]) -> list[dict[str, object]]:
        result = (
            frame.groupby(columns, dropna=False)
            .agg(
                bets=("realized_roi_units", "size"),
                matches=("exposure_match_id", "nunique"),
                pnl_units=("realized_roi_units", "sum"),
                roi_pct=("realized_roi_units", "mean"),
            )
            .reset_index()
        )
        result["roi_pct"] *= 100.0
        return result.to_dict(orient="records")

    return {
        "stat": grouped(["stat_key"]),
        "period": grouped(["period"]),
        "scope": grouped(["scope"]),
        "window": grouped(["test_start"]),
        "stat_period_scope": grouped(
            ["stat_key", "period", "scope"]
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
        .copy()
    )
    return _performance(selected)


def _timing_audit(
    market_frame: pd.DataFrame,
    count_predictions: pd.DataFrame,
    reference_predictions: pd.DataFrame,
    count_windows: pd.DataFrame,
) -> dict[str, object]:
    snapshot = pd.to_datetime(
        market_frame["odds_snapshot_time"],
        errors="coerce",
        utc=True,
    )
    kickoff = pd.to_datetime(
        market_frame["match_start_time"],
        errors="coerce",
        utc=True,
    )
    prediction_train_end = pd.to_datetime(
        count_predictions["train_end"],
        errors="coerce",
    )
    prediction_match_day = pd.to_datetime(
        count_predictions["match_date"],
        errors="coerce",
    )
    dispersion_validation_end = pd.to_datetime(
        count_predictions["dispersion_validation_end"],
        errors="coerce",
    )
    prediction_test_start = pd.to_datetime(
        count_predictions["test_start"],
        errors="coerce",
    )
    join_keys = ["side_key", "test_start", "test_end"]
    universe = reference_predictions[join_keys].merge(
        count_predictions[join_keys],
        on=join_keys,
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    feature_columns = list(
        (*COUNT_CATEGORICAL_COLUMNS, *COUNT_NUMERIC_COLUMNS)
    )
    forbidden_features = {
        "actual_value",
        "exposure_match_id",
        "is_over_win",
        "match_date",
        "match_start_time",
        "odds_snapshot_time",
        "over_realized_roi_units",
        "over_settlement_result",
        "sample_key",
        "training_weight",
        "under_realized_roi_units",
        "under_settlement_result",
    }
    forbidden_used = sorted(
        forbidden_features.intersection(feature_columns)
    )
    return {
        "market_rows": int(len(market_frame)),
        "missing_snapshot_time": int(snapshot.isna().sum()),
        "missing_match_start_time": int(kickoff.isna().sum()),
        "snapshot_at_or_after_kickoff": int(snapshot.ge(kickoff).sum()),
        "prediction_rows": int(len(count_predictions)),
        "train_end_at_or_after_prediction_match": int(
            prediction_train_end.ge(prediction_match_day).sum()
        ),
        "dispersion_validation_at_or_after_test": int(
            dispersion_validation_end.ge(prediction_test_start).sum()
        ),
        "count_duplicate_side_window_keys": int(
            count_predictions.duplicated(join_keys).sum()
        ),
        "reference_duplicate_side_window_keys": int(
            reference_predictions.duplicated(join_keys).sum()
        ),
        "prediction_universe": (
            {
                str(key): int(value)
                for key, value in (
                    universe["_merge"].value_counts().items()
                )
            }
        ),
        "dispersion_sources": (
            {
                str(key): int(value)
                for key, value in (
                    count_predictions["dispersion_source"]
                    .value_counts()
                    .items()
                )
            }
        ),
        "windows": int(len(count_windows)),
        "feature_columns": feature_columns,
        "forbidden_outcome_or_timing_features": forbidden_used,
        "status": (
            "ok"
            if (
                snapshot.notna().all()
                and kickoff.notna().all()
                and snapshot.lt(kickoff).all()
                and prediction_train_end.lt(
                    prediction_match_day
                ).all()
                and dispersion_validation_end.lt(
                    prediction_test_start
                ).all()
                and universe["_merge"].eq("both").all()
                and not forbidden_used
            )
            else "fail"
        ),
    }


def _agreement_threshold_sensitivity(
    reference_predictions: pd.DataFrame,
    count_predictions: pd.DataFrame,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for threshold in DEFAULT_THRESHOLD_GRID:
        reference = select_market_classifier_bets(
            reference_predictions,
            minimum_ev=float(threshold),
            maximum_ev=MAXIMUM_EV,
        )
        gated = gate_reference_by_count_agreement(
            reference,
            count_predictions,
            minimum_count_ev=COUNT_AGREEMENT_MINIMUM_EV,
            model_name="v6_reference_count_agreement_ev0",
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
    reference = pd.read_parquet(args.v6_predictions)
    count_config = NestedCountConfig(
        evaluation_end_date=args.evaluation_end_date,
    )
    count_predictions, count_windows = (
        run_nested_count_walk_forward(
            market_frame,
            count_config,
        )
    )
    merged = merge_reference_count_predictions(
        reference,
        count_predictions,
    )
    if (
        pd.to_numeric(
            count_predictions["predicted_push_probability"],
            errors="coerce",
        )
        .abs()
        .max()
        > 1e-12
    ):
        raise ValueError(
            "experiment 070 expects half-point lines without pushes"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    count_predictions.to_parquet(
        args.output_dir / "count_predictions.parquet",
        index=False,
    )
    count_windows.to_json(
        args.output_dir / "count_windows.json",
        orient="records",
        indent=2,
    )

    reference_all, reference_primary = _select(reference)
    variants: dict[str, dict[str, pd.DataFrame]] = {}
    count_name = "nested_count_hgb_residual_nb"
    count_predictions["model_name"] = count_name
    count_all, count_primary = _select(count_predictions)
    variants[count_name] = {
        "predictions": count_predictions,
        "all": count_all,
        "primary": count_primary,
    }

    for count_weight in BLEND_COUNT_WEIGHTS:
        name = (
            "v6_count_blend_"
            f"{int((1.0 - count_weight) * 100)}_"
            f"{int(count_weight * 100)}"
        )
        predictions = blend_reference_with_count(
            merged,
            count_weight=count_weight,
            model_name=name,
        )
        all_targets, primary = _select(predictions)
        variants[name] = {
            "predictions": predictions,
            "all": all_targets,
            "primary": primary,
        }

    agreement_name = "v6_reference_count_agreement_ev0"
    agreement_all = gate_reference_by_count_agreement(
        reference_all,
        count_predictions,
        minimum_count_ev=COUNT_AGREEMENT_MINIMUM_EV,
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
    summaries: list[dict[str, object]] = []
    paired_reports: dict[str, dict[str, object]] = {}
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
        paired_reports[name] = paired
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
                        count_predictions,
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
                "segments": _segment_rows(frames["primary"]),
            }
        )

    leakage_audit = _timing_audit(
        market_frame,
        count_predictions,
        reference,
        count_windows,
    )
    _write_json(args.output_dir / "falsification.json", falsification)
    _write_json(args.output_dir / "leakage_audit.json", leakage_audit)
    _write_json(args.output_dir / "summary.json", summaries)

    retention_rows: list[dict[str, object]] = []
    for summary in summaries:
        name = str(summary["variant"])
        falsification_row = falsification_by_name[name]
        paired = paired_reports[name]
        primary = summary["corners_away_total"]
        one_per_match = summary["one_per_match"]
        price_stress = falsification_row["price_stress"]
        prediction_quality = paired["prediction_quality"]
        paired_bootstrap = paired["paired_bootstrap"]
        brier_improvement = prediction_quality[
            "brier_improvement"
        ]
        passes = bool(
            leakage_audit["status"] == "ok"
            and falsification_row["mechanical_gate_status"]
            == "passes"
            and primary["positive_windows"]
            == primary["windows_with_bets"]
            and one_per_match["roi_pct"] is not None
            and float(one_per_match["roi_pct"]) > 0.0
            and float(
                price_stress["minus_0.10_decimal"]["roi_pct"]
            )
            > 0.0
            and paired_bootstrap["low_95_pct"] is not None
            and float(paired_bootstrap["low_95_pct"]) > 0.0
            and brier_improvement is not None
            and float(brier_improvement) >= 0.0
        )
        retention_rows.append(
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
                            leakage_audit["status"] != "ok",
                            "leakage audit failed",
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
                            float(
                                price_stress[
                                    "minus_0.10_decimal"
                                ]["roi_pct"]
                            )
                            <= 0.0,
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
        "experiment": "070_nested_count_ensemble",
        "configuration": {
            "count_model": count_config.model_name,
            "train_window_days": count_config.train_window_days,
            "validation_window_days": (
                count_config.validation_window_days
            ),
            "test_window_days": count_config.test_window_days,
            "step_days": count_config.step_days,
            "recency_half_life_days": (
                count_config.recency_half_life_days
            ),
            "dispersion": (
                "negative_binomial estimated only from prior temporal "
                "validation; last valid profile is carried across an "
                "empty validation window"
            ),
            "minimum_ev": MINIMUM_EV,
            "maximum_ev": MAXIMUM_EV,
            "blend_count_weights": list(BLEND_COUNT_WEIGHTS),
            "agreement_minimum_count_ev": (
                COUNT_AGREEMENT_MINIMUM_EV
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
            "reference_policy": (
                "v6_scope_interaction_corners_away_total_"
                "primary_challenger"
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
        "count_window_metrics": count_windows.to_dict(
            orient="records"
        ),
        "variants": summaries,
        "retention_decisions": retention_rows,
        "registry_v5_mutated": False,
        "evidence_limit": (
            "All outcomes were already available and inspected. Even a "
            "passing historical gate would remain a score-only "
            "challenger requiring untouched in-domain forward evidence."
        ),
    }
    _write_json(args.output_dir / "experiment_report.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
