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
from scipy.special import expit, logit
from sklearn.metrics import brier_score_loss

from ullebets_v1.audit.odds_timing import (
    annotate_backtest_timing,
)
from ullebets_v2.ev_model.asof_features import (
    build_asof_compact_model_features,
)
from ullebets_v2.ev_model.dataset import (
    prepare_modeling_frame,
)
from ullebets_v2.ev_model.falsification import (
    apply_policy_exposure_cap_to_frame,
    build_candidate_falsification_report,
)
from ullebets_v2.ev_model.market_classifier import (
    build_market_classifier_frame,
    expand_market_predictions_to_sides,
    fit_market_classifier,
)
from ullebets_v2.ev_model.market_calibration import (
    sequentially_calibrate_market_predictions,
)
from ullebets_v2.ev_model.market_walk_forward import (
    select_market_classifier_bets,
)
from ullebets_v2.ev_model.model_comparison import (
    build_paired_strategy_comparison,
)
from ullebets_v2.ev_model.nested_regularization import (
    NestedRegularizationConfig,
    _with_recency_weight,
    run_nested_regularization_walk_forward,
)


PRIMARY_STATS = (
    "cornerKicks",
    "shotsOnGoal",
    "totalShots",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reproduce EV experiments 046-054 on one fixed outer "
            "walk-forward universe."
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
        "--market-frame-cache",
        type=Path,
        default=(
            Path("data/v2/ev_model/research_cache")
            / "asof_market_frame.parquet"
        ),
    )
    parser.add_argument(
        "--v3-predictions",
        type=Path,
        default=(
            Path(
                "data/v2/ev_model/"
                "experiment_031_asof_snapshot_recency45_full"
            )
            / "predictions.parquet"
        ),
    )
    parser.add_argument(
        "--v4-predictions",
        type=Path,
        default=(
            Path(
                "data/v2/ev_model/"
                "experiment_037_nested_regularization_full"
            )
            / "predictions.parquet"
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/v2/ev_model"),
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


def _market_frame(args: argparse.Namespace) -> pd.DataFrame:
    if args.market_frame_cache.exists():
        return pd.read_parquet(args.market_frame_cache)
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
    model_features, _ = build_asof_compact_model_features(
        modeling_frame,
        team_stats,
        availability_buffer_hours=3.0,
    )
    frame = build_market_classifier_frame(
        modeling_frame,
        model_features,
    )
    args.market_frame_cache.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    frame.to_parquet(
        args.market_frame_cache,
        index=False,
    )
    return frame


def _performance(
    name: str,
    predictions: pd.DataFrame,
    selections: pd.DataFrame,
) -> dict[str, object]:
    markets = predictions.drop_duplicates("sample_key")
    markets = markets[markets["is_over_win"].notna()]
    return {
        "variant": name,
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
        "brier": float(
            brier_score_loss(
                markets["is_over_win"],
                markets["predicted_over_probability"],
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


def _write_nested(
    *,
    name: str,
    frame: pd.DataFrame,
    config: NestedRegularizationConfig,
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    predictions, windows = (
        run_nested_regularization_walk_forward(
            frame,
            config,
        )
    )
    predictions["model_name"] = name
    selections = select_market_classifier_bets(
        predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )
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
    return (
        predictions,
        selections,
        _performance(name, predictions, selections),
    )


def _ensemble_frame(
    v3: pd.DataFrame,
    v4: pd.DataFrame,
) -> pd.DataFrame:
    keys = ["sample_key", "direction", "test_start", "test_end"]
    return v4.merge(
        v3[
            keys + ["predicted_win_probability"]
        ],
        on=keys,
        suffixes=("_v4", "_v3"),
        validate="one_to_one",
    )


def _write_probability_variant(
    *,
    merged: pd.DataFrame,
    name: str,
    probability: pd.Series | np.ndarray,
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    predictions = merged.copy()
    predictions["model_name"] = name
    predictions["predicted_win_probability"] = probability
    predictions["predicted_over_probability"] = np.where(
        predictions["direction"].eq("over"),
        predictions["predicted_win_probability"],
        1.0 - predictions["predicted_win_probability"],
    )
    predictions["expected_roi_units"] = (
        predictions["predicted_win_probability"]
        * predictions["offered_odds"]
        - 1.0
    )
    selections = select_market_classifier_bets(
        predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(
        output_dir / "predictions.parquet",
        index=False,
    )
    selections.to_parquet(
        output_dir / "exact_policy_selections.parquet",
        index=False,
    )
    return (
        predictions,
        selections,
        _performance(name, predictions, selections),
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    market = _market_frame(args)
    base_config = NestedRegularizationConfig(
        evaluation_end_date=args.evaluation_end_date,
    )
    all_summaries: dict[str, list[dict[str, object]]] = {}

    experiment_046 = (
        args.output_root
        / "experiment_046_stat_specific_nested"
    )
    summaries_046: list[dict[str, object]] = []
    for stat_key in PRIMARY_STATS:
        _, _, summary = _write_nested(
            name=f"stat_specific_{stat_key}",
            frame=market[
                market["stat_key"].eq(stat_key)
            ],
            config=base_config,
            output_dir=experiment_046 / stat_key,
        )
        summaries_046.append(summary)
    _write_json(
        experiment_046 / "summary.json",
        summaries_046,
    )
    all_summaries["experiment_046"] = summaries_046

    experiment_047 = (
        args.output_root
        / "experiment_047_league_agnostic_nested"
    )
    league_agnostic = market.copy()
    league_agnostic["evaluation_league"] = (
        league_agnostic["league_name_normalized"]
    )
    league_agnostic["league_name_normalized"] = (
        "ALL_LEAGUES"
    )
    predictions_047, selections_047, summary_047 = (
        _write_nested(
            name="league_agnostic",
            frame=league_agnostic,
            config=base_config,
            output_dir=experiment_047,
        )
    )
    predictions_047["league_name_normalized"] = (
        predictions_047["evaluation_league"]
    )
    selections_047["league_name_normalized"] = (
        selections_047["evaluation_league"]
    )
    predictions_047.to_parquet(
        experiment_047 / "predictions.parquet",
        index=False,
    )
    selections_047.to_parquet(
        experiment_047 / "exact_policy_selections.parquet",
        index=False,
    )
    _write_json(
        experiment_047 / "summary.json",
        summary_047,
    )
    all_summaries["experiment_047"] = [summary_047]

    engineered = market.copy()
    engineered["market_logit_over"] = logit(
        engineered["market_fair_probability_over"].clip(
            1e-6,
            1.0 - 1e-6,
        )
    )
    engineered["baseline_market_lambda_gap"] = (
        engineered["baseline_lambda"]
        - engineered["market_anchor_lambda"]
    )
    engineered["baseline_line_gap"] = (
        engineered["baseline_lambda"]
        - engineered["line_value"]
    )
    feature_variants = {
        "market_logit": ["market_logit_over"],
        "lambda_gaps": [
            "baseline_market_lambda_gap",
            "baseline_line_gap",
        ],
        "market_logit_lambda_gaps": [
            "market_logit_over",
            "baseline_market_lambda_gap",
            "baseline_line_gap",
        ],
    }
    experiment_048 = (
        args.output_root
        / "experiment_048_market_anchor_features"
    )
    summaries_048: list[dict[str, object]] = []
    for name, extra_columns in feature_variants.items():
        _, _, summary = _write_nested(
            name=name,
            frame=engineered[
                list(market.columns) + extra_columns
            ],
            config=base_config,
            output_dir=experiment_048 / name,
        )
        summaries_048.append(summary)
    _write_json(
        experiment_048 / "summary.json",
        summaries_048,
    )
    all_summaries["experiment_048"] = summaries_048

    experiment_049 = (
        args.output_root
        / "experiment_049_stat_balanced_nested"
    )
    summaries_049: list[dict[str, object]] = []
    for power in (0.5, 1.0):
        name = f"stat_balance_{power:g}"
        _, _, summary = _write_nested(
            name=name,
            frame=market,
            config=NestedRegularizationConfig(
                evaluation_end_date=(
                    args.evaluation_end_date
                ),
                stat_balance_power=power,
            ),
            output_dir=experiment_049 / name,
        )
        summary["stat_balance_power"] = power
        summaries_049.append(summary)
    _write_json(
        experiment_049 / "summary.json",
        summaries_049,
    )
    all_summaries["experiment_049"] = summaries_049

    v3 = pd.read_parquet(args.v3_predictions)
    v3 = v3[v3["model_name"].eq("logistic_market")]
    v4 = pd.read_parquet(args.v4_predictions)
    merged = _ensemble_frame(v3, v4)
    experiment_050 = (
        args.output_root
        / "experiment_050_v3_v4_ensembles"
    )
    summaries_050: list[dict[str, object]] = []
    ensemble_outputs: dict[
        float,
        tuple[pd.DataFrame, pd.DataFrame],
    ] = {}
    for weight_v4 in (0.25, 0.50, 0.75):
        name = f"ensemble_v4_{weight_v4:g}"
        predictions, selections, summary = (
            _write_probability_variant(
                merged=merged,
                name=name,
                probability=(
                    weight_v4
                    * merged[
                        "predicted_win_probability_v4"
                    ]
                    + (1.0 - weight_v4)
                    * merged[
                        "predicted_win_probability_v3"
                    ]
                ),
                output_dir=experiment_050 / name,
            )
        )
        summary["weight_v4"] = weight_v4
        summaries_050.append(summary)
        ensemble_outputs[weight_v4] = (
            predictions,
            selections,
        )
    _write_json(
        experiment_050 / "summary.json",
        summaries_050,
    )
    all_summaries["experiment_050"] = summaries_050

    best_predictions, best_selections = (
        ensemble_outputs[0.25]
    )
    capped = apply_policy_exposure_cap_to_frame(
        best_selections,
        maximum_bets_per_match=1,
    )
    falsification = build_candidate_falsification_report(
        {
            "V3/V4 ensemble 25% V4": best_selections,
            (
                "V3/V4 ensemble 25% V4 one-per-match"
            ): capped,
        },
        experiments_inspected=116,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    _write_json(
        experiment_050 / "falsification.json",
        falsification,
    )
    v3_selections = select_market_classifier_bets(
        v3,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )
    paired = build_paired_strategy_comparison(
        reference_selections=v3_selections,
        challenger_selections=best_selections,
        reference_predictions=v3,
        challenger_predictions=best_predictions,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    _write_json(
        experiment_050 / "paired_vs_v3.json",
        paired,
    )

    experiment_051 = (
        args.output_root
        / "experiment_051_v3_v4_consensus"
    )
    consensus_variants = {
        "conservative_min": np.minimum(
            merged["predicted_win_probability_v3"],
            merged["predicted_win_probability_v4"],
        ),
        "logit_mean": expit(
            (
                logit(
                    merged[
                        "predicted_win_probability_v3"
                    ].clip(1e-6, 1.0 - 1e-6)
                )
                + logit(
                    merged[
                        "predicted_win_probability_v4"
                    ].clip(1e-6, 1.0 - 1e-6)
                )
            )
            / 2.0
        ),
    }
    summaries_051: list[dict[str, object]] = []
    for name, probability in consensus_variants.items():
        _, _, summary = _write_probability_variant(
            merged=merged,
            name=name,
            probability=probability,
            output_dir=experiment_051 / name,
        )
        summaries_051.append(summary)
    _write_json(
        experiment_051 / "summary.json",
        summaries_051,
    )
    all_summaries["experiment_051"] = summaries_051

    experiment_052 = (
        args.output_root
        / "experiment_052_v5_sequential_calibration"
    )
    experiment_052.mkdir(parents=True, exist_ok=True)
    calibrated = sequentially_calibrate_market_predictions(
        best_predictions,
        minimum_history_markets=250,
        minimum_group_markets=100,
    )
    calibrated_selections = calibrated[
        calibrated["calibration_eligible"].eq(True)
        & calibrated[
            "calibrated_expected_roi_units"
        ].gt(0.075)
        & calibrated[
            "calibrated_expected_roi_units"
        ].lt(0.25)
    ].copy()
    calibrated_selections = (
        calibrated_selections.sort_values(
            "calibrated_expected_roi_units",
            ascending=False,
        )
        .drop_duplicates(["model_name", "sample_key"])
        .reset_index(drop=True)
    )
    calibrated_markets = calibrated.drop_duplicates(
        ["model_name", "sample_key"]
    )
    calibrated_markets = calibrated_markets[
        calibrated_markets[
            "calibration_eligible"
        ].eq(True)
        & calibrated_markets["is_over_win"].notna()
    ]
    summary_052 = {
        "variant": "v5_sequential_beta_calibration",
        "eligible_markets": int(len(calibrated_markets)),
        "raw_brier": float(
            brier_score_loss(
                calibrated_markets["is_over_win"],
                calibrated_markets[
                    "predicted_over_probability"
                ],
            )
        ),
        "calibrated_brier": float(
            brier_score_loss(
                calibrated_markets["is_over_win"],
                calibrated_markets[
                    "calibrated_over_probability"
                ],
            )
        ),
        "bets": int(len(calibrated_selections)),
        "matches": int(
            calibrated_selections[
                "exposure_match_id"
            ].nunique()
        ),
        "pnl_units": float(
            calibrated_selections[
                "realized_roi_units"
            ].sum()
        ),
        "roi_pct": (
            float(
                calibrated_selections[
                    "realized_roi_units"
                ].mean()
                * 100.0
            )
            if len(calibrated_selections)
            else None
        ),
        "positive_windows": int(
            sum(
                rows["realized_roi_units"].mean() > 0.0
                for _, rows in calibrated_selections.groupby(
                    "test_start"
                )
            )
        ),
        "windows_with_bets": int(
            calibrated_selections[
                "test_start"
            ].nunique()
        ),
    }
    calibrated.to_parquet(
        experiment_052 / "calibrated_predictions.parquet",
        index=False,
    )
    calibrated_selections.to_parquet(
        experiment_052 / "selections.parquet",
        index=False,
    )
    _write_json(
        experiment_052 / "summary.json",
        summary_052,
    )
    all_summaries["experiment_052"] = [summary_052]

    experiment_053 = (
        args.output_root
        / "experiment_053_prequential_ensemble_weight"
    )
    experiment_053.mkdir(parents=True, exist_ok=True)
    candidate_weights = (0.0, 0.25, 0.50, 0.75, 1.0)
    prequential_parts: list[pd.DataFrame] = []
    weight_decisions: list[dict[str, object]] = []
    test_windows = sorted(merged["test_start"].unique())
    for test_window in test_windows:
        history = merged[
            merged["test_start"].lt(test_window)
        ]
        if history.empty:
            selected_weight = 0.50
            source = "cold_default"
            prior_markets = 0
        else:
            history_markets = history[
                history["direction"].eq("over")
                & history["is_over_win"].notna()
            ].drop_duplicates("sample_key")
            metrics: list[tuple[float, float, float]] = []
            for weight in candidate_weights:
                probability = (
                    weight
                    * history_markets[
                        "predicted_win_probability_v4"
                    ]
                    + (1.0 - weight)
                    * history_markets[
                        "predicted_win_probability_v3"
                    ]
                )
                metrics.append(
                    (
                        float(
                            brier_score_loss(
                                history_markets["is_over_win"],
                                probability,
                            )
                        ),
                        abs(weight - 0.50),
                        weight,
                    )
                )
            selected_weight = min(metrics)[2]
            source = "prior_outer_brier"
            prior_markets = int(len(history_markets))
        current = merged[
            merged["test_start"].eq(test_window)
        ].copy()
        current["model_name"] = (
            "prequential_ensemble_weight"
        )
        current["predicted_win_probability"] = (
            selected_weight
            * current["predicted_win_probability_v4"]
            + (1.0 - selected_weight)
            * current["predicted_win_probability_v3"]
        )
        current["predicted_over_probability"] = np.where(
            current["direction"].eq("over"),
            current["predicted_win_probability"],
            1.0 - current["predicted_win_probability"],
        )
        current["expected_roi_units"] = (
            current["predicted_win_probability"]
            * current["offered_odds"]
            - 1.0
        )
        current["selected_v4_weight"] = selected_weight
        prequential_parts.append(current)
        weight_decisions.append(
            {
                "test_start": str(test_window),
                "selected_v4_weight": selected_weight,
                "selection_source": source,
                "prior_markets": prior_markets,
            }
        )
    prequential_predictions = pd.concat(
        prequential_parts,
        ignore_index=True,
    )
    prequential_selections = (
        select_market_classifier_bets(
            prequential_predictions,
            minimum_ev=0.075,
            maximum_ev=0.25,
        )
    )
    cold_abstain_selections = prequential_selections[
        prequential_selections["test_start"].ne(
            test_windows[0]
        )
    ].copy()
    summary_053 = {
        "variant": "prequential_ensemble_weight",
        "candidate_weights": list(candidate_weights),
        "decisions": weight_decisions,
        "cold_default": _performance(
            "prequential_ensemble_weight",
            prequential_predictions,
            prequential_selections,
        ),
        "cold_abstain": {
            "bets": int(len(cold_abstain_selections)),
            "matches": int(
                cold_abstain_selections[
                    "exposure_match_id"
                ].nunique()
            ),
            "pnl_units": float(
                cold_abstain_selections[
                    "realized_roi_units"
                ].sum()
            ),
            "roi_pct": float(
                cold_abstain_selections[
                    "realized_roi_units"
                ].mean()
                * 100.0
            ),
            "positive_windows": int(
                sum(
                    rows[
                        "realized_roi_units"
                    ].mean()
                    > 0.0
                    for _, rows in (
                        cold_abstain_selections.groupby(
                            "test_start"
                        )
                    )
                )
            ),
        },
    }
    prequential_predictions.to_parquet(
        experiment_053 / "predictions.parquet",
        index=False,
    )
    prequential_selections.to_parquet(
        experiment_053 / "selections_cold_default.parquet",
        index=False,
    )
    cold_abstain_selections.to_parquet(
        experiment_053 / "selections_cold_abstain.parquet",
        index=False,
    )
    _write_json(
        experiment_053 / "summary.json",
        summary_053,
    )
    all_summaries["experiment_053"] = [summary_053]

    experiment_054 = (
        args.output_root
        / "experiment_054_leave_one_league_training_transfer"
    )
    experiment_054.mkdir(parents=True, exist_ok=True)
    transfer_frame = market.copy()
    transfer_frame["_match_day"] = pd.to_datetime(
        transfer_frame["match_date"],
        errors="raise",
    ).dt.normalize()
    transfer_parts: list[pd.DataFrame] = []
    transfer_fit_audit: list[dict[str, object]] = []
    outer_windows = (
        v4[["test_start", "test_end"]]
        .drop_duplicates()
        .sort_values("test_start")
    )
    for window in outer_windows.itertuples(index=False):
        test_start = pd.Timestamp(window.test_start)
        test_end = pd.Timestamp(window.test_end)
        train_end = test_start - pd.Timedelta(days=1)
        train_start = test_start - pd.Timedelta(days=90)
        train = transfer_frame[
            transfer_frame["_match_day"].between(
                train_start,
                train_end,
            )
            & transfer_frame["is_over_win"].notna()
        ]
        test = transfer_frame[
            transfer_frame["_match_day"].between(
                test_start,
                test_end,
            )
        ]
        for held_out_league in sorted(
            test["league_name_normalized"].unique()
        ):
            model_train = train[
                train["league_name_normalized"].ne(
                    held_out_league
                )
            ].copy()
            model_test = test[
                test["league_name_normalized"].eq(
                    held_out_league
                )
            ].copy()
            if len(model_train) < 250 or model_test.empty:
                continue
            model_train = _with_recency_weight(
                model_train,
                reference_day=train_end,
                half_life_days=45.0,
            )
            model = fit_market_classifier(
                "logistic_market",
                model_train,
                logistic_c=0.01,
            )
            market_predictions = model_test.drop(
                columns=["_match_day"]
            ).copy()
            market_predictions["model_name"] = (
                "leave_one_league_training_transfer"
            )
            market_predictions[
                "predicted_over_probability"
            ] = model.predict_probability_over(model_test)
            market_predictions["train_start"] = (
                train_start.date().isoformat()
            )
            market_predictions["train_end"] = (
                train_end.date().isoformat()
            )
            market_predictions["test_start"] = (
                str(window.test_start)
            )
            market_predictions["test_end"] = (
                str(window.test_end)
            )
            market_predictions["held_out_league"] = (
                held_out_league
            )
            transfer_parts.append(
                expand_market_predictions_to_sides(
                    market_predictions
                )
            )
            transfer_fit_audit.append(
                {
                    "test_start": str(window.test_start),
                    "held_out_league": held_out_league,
                    "train_rows": int(len(model_train)),
                    "test_markets": int(len(model_test)),
                }
            )
    transfer_predictions = pd.concat(
        transfer_parts,
        ignore_index=True,
    )
    transfer_selections = select_market_classifier_bets(
        transfer_predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )
    summary_054 = _performance(
        "leave_one_league_training_transfer",
        transfer_predictions,
        transfer_selections,
    )
    summary_054["fit_audit"] = transfer_fit_audit
    summary_054["by_held_out_league"] = (
        transfer_selections.groupby("held_out_league")[
            "realized_roi_units"
        ]
        .agg(["size", "sum", "mean"])
        .reset_index()
        .to_dict(orient="records")
    )
    transfer_predictions.to_parquet(
        experiment_054 / "predictions.parquet",
        index=False,
    )
    transfer_selections.to_parquet(
        experiment_054 / "selections.parquet",
        index=False,
    )
    _write_json(
        experiment_054 / "summary.json",
        summary_054,
    )
    all_summaries["experiment_054"] = [summary_054]

    _write_json(
        args.output_root
        / "experiments_046_054_summary.json",
        all_summaries,
    )
    print(json.dumps(all_summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
