from __future__ import annotations

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.calibration import BetaProbabilityCalibrator


def sequentially_calibrate_market_predictions(
    side_predictions: pd.DataFrame,
    *,
    minimum_history_markets: int = 250,
    minimum_group_markets: int = 100,
) -> pd.DataFrame:
    sides = side_predictions.copy()
    markets = sides.drop_duplicates(
        subset=["model_name", "sample_key"],
        keep="first",
    ).copy()
    markets["_test_day"] = pd.to_datetime(
        markets["test_start"],
        errors="raise",
    )
    markets["calibrated_over_probability"] = np.nan
    markets["calibration_eligible"] = False
    markets["calibration_level"] = None

    for _, model_rows in markets.groupby("model_name"):
        for test_day in sorted(model_rows["_test_day"].unique()):
            current_index = model_rows.index[
                model_rows["_test_day"].eq(test_day)
            ]
            history = model_rows[
                model_rows["_test_day"].lt(test_day)
                & model_rows["is_over_win"].notna()
            ]
            if len(history) < minimum_history_markets:
                continue
            global_calibrator = BetaProbabilityCalibrator(
                min_samples=minimum_history_markets
            ).fit(
                history["predicted_over_probability"].to_numpy(dtype=float),
                history["is_over_win"].to_numpy(dtype=float),
            )
            if global_calibrator.model is None:
                continue

            group_calibrators: dict[str, BetaProbabilityCalibrator] = {}
            for stat_key, group in history.groupby("stat_key"):
                calibrator = BetaProbabilityCalibrator(
                    min_samples=minimum_group_markets
                ).fit(
                    group["predicted_over_probability"].to_numpy(dtype=float),
                    group["is_over_win"].to_numpy(dtype=float),
                )
                if calibrator.model is not None:
                    group_calibrators[str(stat_key)] = calibrator

            for index in current_index:
                row = markets.loc[index]
                stat_key = str(row["stat_key"])
                calibrator = group_calibrators.get(
                    stat_key,
                    global_calibrator,
                )
                probability = float(
                    calibrator.predict(
                        np.asarray(
                            [float(row["predicted_over_probability"])]
                        )
                    )[0]
                )
                markets.loc[index, "calibrated_over_probability"] = probability
                markets.loc[index, "calibration_eligible"] = True
                markets.loc[index, "calibration_level"] = (
                    "stat"
                    if stat_key in group_calibrators
                    else "global"
                )

    calibration = markets[
        [
            "model_name",
            "sample_key",
            "calibrated_over_probability",
            "calibration_eligible",
            "calibration_level",
        ]
    ]
    calibrated = sides.merge(
        calibration,
        on=["model_name", "sample_key"],
        how="left",
        validate="many_to_one",
    )
    calibrated["calibrated_win_probability"] = np.where(
        calibrated["direction"].eq("over"),
        calibrated["calibrated_over_probability"],
        1.0 - calibrated["calibrated_over_probability"],
    )
    calibrated["calibrated_expected_roi_units"] = (
        calibrated["calibrated_win_probability"]
        * calibrated["offered_odds"]
        - 1.0
    )
    return calibrated


def select_calibrated_market_bets(
    calibrated_predictions: pd.DataFrame,
    *,
    minimum_ev: float,
) -> pd.DataFrame:
    eligible = calibrated_predictions[
        calibrated_predictions["calibration_eligible"].eq(True)
        & calibrated_predictions["calibrated_expected_roi_units"].gt(
            minimum_ev
        )
    ].copy()
    if eligible.empty:
        return eligible
    eligible = eligible.sort_values(
        [
            "model_name",
            "sample_key",
            "calibrated_expected_roi_units",
        ],
        ascending=[True, True, False],
    )
    return eligible.drop_duplicates(
        subset=["model_name", "sample_key"],
        keep="first",
    ).reset_index(drop=True)
