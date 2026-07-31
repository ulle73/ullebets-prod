from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from ullebets_v2.ev_model.market_classifier import (
    expand_market_predictions_to_sides,
    fit_market_classifier,
)


@dataclass(frozen=True)
class MarketWalkForwardConfig:
    train_window_days: int = 90
    test_window_days: int = 14
    step_days: int = 14
    min_train_rows: int = 250
    recency_half_life_days: float | None = None
    model_names: tuple[str, ...] = (
        "market_probability",
        "logistic_market",
        "hierarchical_logistic_market",
        "hgb_market",
        "market_residual_hgb",
    )
    minimum_ev_thresholds: tuple[float, ...] = (0.0, 0.02, 0.05, 0.10)
    evaluation_end_date: str | None = None


def select_market_classifier_bets(
    predictions: pd.DataFrame,
    *,
    minimum_ev: float,
    maximum_ev: float | None = None,
) -> pd.DataFrame:
    eligible = predictions[
        predictions["expected_roi_units"].gt(minimum_ev)
    ].copy()
    if maximum_ev is not None:
        eligible = eligible[
            eligible["expected_roi_units"].lt(maximum_ev)
        ].copy()
    if eligible.empty:
        return eligible
    eligible = eligible.sort_values(
        ["model_name", "sample_key", "expected_roi_units"],
        ascending=[True, True, False],
    )
    return eligible.drop_duplicates(
        subset=["model_name", "sample_key"],
        keep="first",
    ).reset_index(drop=True)


def _apply_recency_weight(
    train: pd.DataFrame,
    *,
    train_end: pd.Timestamp,
    half_life_days: float | None,
) -> pd.DataFrame:
    weighted = train.copy()
    if half_life_days is None:
        return weighted
    age_days = (
        train_end - weighted["_match_day"]
    ).dt.total_seconds() / 86_400.0
    weighted["training_weight"] = (
        weighted["training_weight"]
        * np.power(0.5, age_days / half_life_days)
    )
    return weighted


def run_market_classifier_walk_forward(
    market_frame: pd.DataFrame,
    config: MarketWalkForwardConfig,
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
        test_end = min(
            test_start + timedelta(days=config.test_window_days - 1),
            last_day,
        )
        train = frame[
            frame["_match_day"].between(train_start, train_end)
            & frame["is_over_win"].notna()
        ].copy()
        test = frame[frame["_match_day"].between(test_start, test_end)].copy()
        if len(train) < config.min_train_rows or test.empty:
            test_start += timedelta(days=config.step_days)
            continue
        train = _apply_recency_weight(
            train,
            train_end=train_end,
            half_life_days=config.recency_half_life_days,
        )

        for model_name in config.model_names:
            model = fit_market_classifier(model_name, train)
            market_predictions = test.drop(columns=["_match_day"]).copy()
            market_predictions["model_name"] = model_name
            market_predictions["predicted_over_probability"] = (
                model.predict_probability_over(test)
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
                "train_start": train_start.date().isoformat(),
                "train_end": train_end.date().isoformat(),
                "test_start": test_start.date().isoformat(),
                "test_end": test_end.date().isoformat(),
                "train_rows": len(train),
                "test_rows": len(scored),
                "brier": float(
                    brier_score_loss(
                        scored["is_over_win"],
                        scored["predicted_over_probability"],
                    )
                ),
                "log_loss": float(
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
