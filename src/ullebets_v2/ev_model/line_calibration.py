from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.calibration import BetaProbabilityCalibrator
from ullebets_v2.ev_model.probabilities import (
    expected_roi,
    negative_binomial_line_probabilities,
    poisson_line_probabilities,
)


def _settlement(actual: float, line: float, direction: str, odds: float) -> tuple[str, float]:
    if math.isclose(actual, line, rel_tol=0.0, abs_tol=1e-9):
        return "push", 0.0
    won = actual > line if direction == "over" else actual < line
    return ("win", odds - 1.0) if won else ("loss", -1.0)


def build_line_probability_rows(
    predictions: pd.DataFrame,
    *,
    distribution: str,
) -> pd.DataFrame:
    if distribution not in {"poisson", "negative_binomial"}:
        raise ValueError("distribution must be poisson or negative_binomial")
    rows: list[dict] = []
    for prediction in predictions.itertuples(index=False):
        for direction, odds_value in (
            ("over", prediction.over_odds),
            ("under", prediction.under_odds),
        ):
            if odds_value is None or pd.isna(odds_value):
                continue
            if distribution == "negative_binomial":
                probabilities = negative_binomial_line_probabilities(
                    mean=float(prediction.predicted_mean),
                    dispersion=float(prediction.nb_dispersion),
                    line=float(prediction.line_value),
                    direction=direction,
                )
            else:
                probabilities = poisson_line_probabilities(
                    mean=float(prediction.predicted_mean),
                    line=float(prediction.line_value),
                    direction=direction,
                )
            result, realized = _settlement(
                float(prediction.actual_value),
                float(prediction.line_value),
                direction,
                float(odds_value),
            )
            rows.append(
                {
                    "sample_key": prediction.sample_key,
                    "exposure_match_id": prediction.exposure_match_id,
                    "match_date": prediction.match_date,
                    "test_start": prediction.test_start,
                    "model_name": prediction.model_name,
                    "distribution": distribution,
                    "stat_key": prediction.stat_key,
                    "period": prediction.period,
                    "scope": prediction.scope,
                    "line_value": float(prediction.line_value),
                    "direction": direction,
                    "selected_odds": float(odds_value),
                    "predicted_mean": float(prediction.predicted_mean),
                    "dispersion": (
                        float(prediction.nb_dispersion)
                        if distribution == "negative_binomial"
                        else None
                    ),
                    "raw_win_probability": probabilities.win,
                    "push_probability": probabilities.push,
                    "settlement_result": result,
                    "realized_roi_units": realized,
                }
            )
    return pd.DataFrame(rows)


def sequentially_calibrate_probability_rows(
    probability_rows: pd.DataFrame,
    *,
    minimum_history_rows: int = 500,
    minimum_group_rows: int = 100,
) -> pd.DataFrame:
    calibrated = probability_rows.copy()
    calibrated["calibrated_win_probability"] = np.nan
    calibrated["calibrated_expected_roi_units"] = np.nan
    calibrated["calibration_eligible"] = False
    calibrated["calibration_level"] = None
    calibrated["_test_day"] = pd.to_datetime(calibrated["test_start"], errors="raise")

    for _, model_rows in calibrated.groupby(["model_name", "distribution"]):
        for test_day in sorted(model_rows["_test_day"].unique()):
            current_index = model_rows.index[model_rows["_test_day"].eq(test_day)]
            history = model_rows[model_rows["_test_day"].lt(test_day)]
            history = history[history["settlement_result"].ne("push")]
            if len(history) < minimum_history_rows:
                continue

            history_raw = history["raw_win_probability"].to_numpy(dtype=float)
            history_outcomes = history["settlement_result"].eq("win").to_numpy(dtype=float)
            global_calibrator = BetaProbabilityCalibrator(
                min_samples=minimum_history_rows
            ).fit(history_raw, history_outcomes)
            if global_calibrator.model is None:
                continue

            group_calibrators: dict[tuple[str, str], BetaProbabilityCalibrator] = {}
            for key, group in history.groupby(["stat_key", "direction"]):
                calibrator = BetaProbabilityCalibrator(
                    min_samples=minimum_group_rows
                ).fit(
                    group["raw_win_probability"].to_numpy(dtype=float),
                    group["settlement_result"].eq("win").to_numpy(dtype=float),
                )
                if calibrator.model is not None:
                    group_calibrators[(str(key[0]), str(key[1]))] = calibrator

            for index in current_index:
                row = calibrated.loc[index]
                key = (str(row["stat_key"]), str(row["direction"]))
                row_calibrator = group_calibrators.get(key, global_calibrator)
                level = "stat_direction" if key in group_calibrators else "global"
                non_push_mass = max(1e-9, 1.0 - float(row["push_probability"]))
                conditional_raw = np.asarray(
                    [
                        np.clip(
                            float(row["raw_win_probability"]) / non_push_mass,
                            1e-6,
                            1.0 - 1e-6,
                        )
                    ]
                )
                conditional_calibrated = float(
                    row_calibrator.predict(conditional_raw)[0]
                )
                win_probability = conditional_calibrated * non_push_mass
                calibrated.loc[index, "calibrated_win_probability"] = win_probability
                calibrated.loc[index, "calibrated_expected_roi_units"] = expected_roi(
                    win_probability=win_probability,
                    push_probability=float(row["push_probability"]),
                    decimal_odds=float(row["selected_odds"]),
                )
                calibrated.loc[index, "calibration_eligible"] = True
                calibrated.loc[index, "calibration_level"] = level

    return calibrated.drop(columns=["_test_day"])


def select_calibrated_bets(
    calibrated_rows: pd.DataFrame,
    *,
    minimum_ev: float,
) -> pd.DataFrame:
    eligible = calibrated_rows[
        calibrated_rows["calibration_eligible"].eq(True)
        & calibrated_rows["calibrated_expected_roi_units"].gt(minimum_ev)
    ].copy()
    if eligible.empty:
        return eligible
    eligible = eligible.sort_values(
        [
            "model_name",
            "distribution",
            "sample_key",
            "calibrated_expected_roi_units",
        ],
        ascending=[True, True, True, False],
    )
    return eligible.drop_duplicates(
        subset=["model_name", "distribution", "sample_key"],
        keep="first",
    ).reset_index(drop=True)
