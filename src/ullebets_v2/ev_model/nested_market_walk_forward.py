from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from ullebets_v2.ev_model.calibration import BetaProbabilityCalibrator
from ullebets_v2.ev_model.market_classifier import (
    expand_market_predictions_to_sides,
    fit_market_classifier,
)
from ullebets_v2.ev_model.market_walk_forward import (
    select_market_classifier_bets,
)


@dataclass(frozen=True)
class NestedMarketWalkForwardConfig:
    train_window_days: int = 90
    calibration_window_days: int = 21
    test_window_days: int = 14
    step_days: int = 14
    min_model_train_rows: int = 250
    min_calibration_rows: int = 100
    min_group_calibration_rows: int = 60
    model_names: tuple[str, ...] = (
        "logistic_market",
        "hgb_market",
        "market_residual_hgb",
    )
    minimum_ev_thresholds: tuple[float, ...] = (0.0, 0.02, 0.05, 0.10)
    evaluation_end_date: str | None = None


def _fit_calibrators(
    calibration: pd.DataFrame,
    raw_probabilities: np.ndarray,
    config: NestedMarketWalkForwardConfig,
) -> tuple[
    BetaProbabilityCalibrator | None,
    dict[str, BetaProbabilityCalibrator],
]:
    outcomes = calibration["is_over_win"].to_numpy(dtype=float)
    global_calibrator = BetaProbabilityCalibrator(
        min_samples=config.min_calibration_rows
    ).fit(raw_probabilities, outcomes)
    if global_calibrator.model is None:
        return None, {}

    group_calibrators: dict[str, BetaProbabilityCalibrator] = {}
    calibration_with_probabilities = calibration.copy()
    calibration_with_probabilities["_raw_probability"] = raw_probabilities
    for stat_key, group in calibration_with_probabilities.groupby("stat_key"):
        calibrator = BetaProbabilityCalibrator(
            min_samples=config.min_group_calibration_rows
        ).fit(
            group["_raw_probability"].to_numpy(dtype=float),
            group["is_over_win"].to_numpy(dtype=float),
        )
        if calibrator.model is not None:
            group_calibrators[str(stat_key)] = calibrator
    return global_calibrator, group_calibrators


def _calibrate_test_probabilities(
    test: pd.DataFrame,
    raw_probabilities: np.ndarray,
    global_calibrator: BetaProbabilityCalibrator,
    group_calibrators: dict[str, BetaProbabilityCalibrator],
) -> np.ndarray:
    calibrated = np.empty(len(test), dtype=float)
    for position, (_, row) in enumerate(test.iterrows()):
        calibrator = group_calibrators.get(
            str(row["stat_key"]),
            global_calibrator,
        )
        calibrated[position] = calibrator.predict(
            np.asarray([raw_probabilities[position]])
        )[0]
    return np.clip(calibrated, 1e-6, 1.0 - 1e-6)


def run_nested_market_walk_forward(
    market_frame: pd.DataFrame,
    config: NestedMarketWalkForwardConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = market_frame.reset_index(drop=True).copy()
    frame["_match_day"] = pd.to_datetime(
        frame["match_date"],
        errors="raise",
    ).dt.normalize()
    first_day = frame["_match_day"].min()
    last_day = frame["_match_day"].max()
    if config.evaluation_end_date is not None:
        last_day = min(
            last_day,
            pd.Timestamp(config.evaluation_end_date).normalize(),
        )

    prediction_parts: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []
    test_start = first_day + timedelta(days=config.train_window_days)
    while test_start <= last_day:
        train_start = test_start - timedelta(days=config.train_window_days)
        train_end = test_start - timedelta(days=1)
        calibration_start = (
            train_end - timedelta(days=config.calibration_window_days - 1)
        )
        model_train_end = calibration_start - timedelta(days=1)
        test_end = min(
            test_start + timedelta(days=config.test_window_days - 1),
            last_day,
        )
        model_train = frame[
            frame["_match_day"].between(train_start, model_train_end)
            & frame["is_over_win"].notna()
        ].copy()
        calibration = frame[
            frame["_match_day"].between(calibration_start, train_end)
            & frame["is_over_win"].notna()
        ].copy()
        test = frame[frame["_match_day"].between(test_start, test_end)].copy()
        if (
            len(model_train) < config.min_model_train_rows
            or len(calibration) < config.min_calibration_rows
            or test.empty
        ):
            test_start += timedelta(days=config.step_days)
            continue

        for model_name in config.model_names:
            model = fit_market_classifier(model_name, model_train)
            calibration_raw = model.predict_probability_over(calibration)
            global_calibrator, group_calibrators = _fit_calibrators(
                calibration,
                calibration_raw,
                config,
            )
            if global_calibrator is None:
                continue
            raw_probabilities = model.predict_probability_over(test)
            calibrated_probabilities = _calibrate_test_probabilities(
                test,
                raw_probabilities,
                global_calibrator,
                group_calibrators,
            )
            market_predictions = test.drop(columns=["_match_day"]).copy()
            market_predictions["model_name"] = model_name
            market_predictions["raw_over_probability"] = raw_probabilities
            market_predictions["predicted_over_probability"] = (
                calibrated_probabilities
            )
            market_predictions["model_train_start"] = (
                train_start.date().isoformat()
            )
            market_predictions["model_train_end"] = (
                model_train_end.date().isoformat()
            )
            market_predictions["calibration_start"] = (
                calibration_start.date().isoformat()
            )
            market_predictions["calibration_end"] = (
                train_end.date().isoformat()
            )
            market_predictions["train_start"] = train_start.date().isoformat()
            market_predictions["train_end"] = train_end.date().isoformat()
            market_predictions["test_start"] = test_start.date().isoformat()
            market_predictions["test_end"] = test_end.date().isoformat()
            side_predictions = expand_market_predictions_to_sides(
                market_predictions
            )
            prediction_parts.append(side_predictions)

            scored = market_predictions[
                market_predictions["is_over_win"].notna()
            ]
            base_metrics = {
                "model_name": model_name,
                "model_train_start": train_start.date().isoformat(),
                "model_train_end": model_train_end.date().isoformat(),
                "calibration_start": calibration_start.date().isoformat(),
                "calibration_end": train_end.date().isoformat(),
                "test_start": test_start.date().isoformat(),
                "test_end": test_end.date().isoformat(),
                "model_train_rows": len(model_train),
                "calibration_rows": len(calibration),
                "test_rows": len(scored),
                "raw_brier": float(
                    brier_score_loss(
                        scored["is_over_win"],
                        scored["raw_over_probability"],
                    )
                ),
                "calibrated_brier": float(
                    brier_score_loss(
                        scored["is_over_win"],
                        scored["predicted_over_probability"],
                    )
                ),
                "calibrated_log_loss": float(
                    log_loss(
                        scored["is_over_win"],
                        scored["predicted_over_probability"],
                        labels=[0, 1],
                    )
                ),
            }
            for threshold in config.minimum_ev_thresholds:
                selections = select_market_classifier_bets(
                    side_predictions,
                    minimum_ev=threshold,
                )
                bets = len(selections)
                pnl = (
                    float(selections["realized_roi_units"].sum())
                    if bets
                    else 0.0
                )
                summary_rows.append(
                    {
                        **base_metrics,
                        "minimum_ev": threshold,
                        "bets": bets,
                        "pnl_units": pnl,
                        "roi_pct": pnl / bets * 100.0 if bets else 0.0,
                    }
                )
        test_start += timedelta(days=config.step_days)

    predictions = (
        pd.concat(prediction_parts, ignore_index=True)
        if prediction_parts
        else pd.DataFrame()
    )
    return predictions, pd.DataFrame(summary_rows)
