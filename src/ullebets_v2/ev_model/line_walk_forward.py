from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from ullebets_v2.ev_model.line_classifier import fit_line_classifier


@dataclass(frozen=True)
class LineWalkForwardConfig:
    train_window_days: int = 90
    test_window_days: int = 14
    step_days: int = 14
    min_train_rows: int = 500
    model_names: tuple[str, ...] = (
        "market_probability",
        "logistic",
        "hgb_classifier",
    )
    minimum_ev_thresholds: tuple[float, ...] = (0.0, 0.02, 0.05, 0.10)
    evaluation_end_date: str | None = None


def select_line_classifier_bets(
    predictions: pd.DataFrame,
    *,
    minimum_ev: float,
) -> pd.DataFrame:
    eligible = predictions[
        predictions["expected_roi_units"].gt(minimum_ev)
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


def run_line_classifier_walk_forward(
    line_frame: pd.DataFrame,
    config: LineWalkForwardConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = line_frame.reset_index(drop=True).copy()
    frame["_match_day"] = pd.to_datetime(frame["match_date"], errors="raise").dt.normalize()
    first_day = frame["_match_day"].min()
    last_day = frame["_match_day"].max()
    if config.evaluation_end_date is not None:
        last_day = min(last_day, pd.Timestamp(config.evaluation_end_date).normalize())

    prediction_parts: list[pd.DataFrame] = []
    summary_rows: list[dict] = []
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
            & frame["is_win"].notna()
        ].copy()
        test = frame[frame["_match_day"].between(test_start, test_end)].copy()
        if len(train) < config.min_train_rows or test.empty:
            test_start += timedelta(days=config.step_days)
            continue

        for model_name in config.model_names:
            model = fit_line_classifier(model_name, train)
            probabilities = np.clip(
                model.predict_probability(test),
                1e-6,
                1.0 - 1e-6,
            )
            predictions = test.drop(columns=["_match_day"]).copy()
            predictions["model_name"] = model_name
            predictions["predicted_win_probability"] = probabilities
            predictions["expected_roi_units"] = (
                probabilities * predictions["offered_odds"] - 1.0
            )
            predictions["train_start"] = train_start.date().isoformat()
            predictions["train_end"] = train_end.date().isoformat()
            predictions["test_start"] = test_start.date().isoformat()
            predictions["test_end"] = test_end.date().isoformat()
            prediction_parts.append(predictions)

            scored = predictions[predictions["is_win"].notna()]
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
                        scored["is_win"],
                        scored["predicted_win_probability"],
                        sample_weight=scored["sample_weight"],
                    )
                ),
                "log_loss": float(
                    log_loss(
                        scored["is_win"],
                        scored["predicted_win_probability"],
                        sample_weight=scored["sample_weight"],
                        labels=[0, 1],
                    )
                ),
            }
            for threshold in config.minimum_ev_thresholds:
                selections = select_line_classifier_bets(
                    predictions,
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
