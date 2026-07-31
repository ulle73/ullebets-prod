from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

from ullebets_v2.ev_model.market_classifier import (
    expand_market_predictions_to_sides,
    fit_market_classifier,
)
from ullebets_v2.ev_model.shadow_candidate import (
    ShadowCandidateBundle,
)


@dataclass(frozen=True)
class NestedRegularizationConfig:
    train_window_days: int = 90
    validation_window_days: int = 21
    test_window_days: int = 14
    step_days: int = 14
    min_model_train_rows: int = 250
    min_validation_rows: int = 100
    c_grid: tuple[float, ...] = (
        0.01,
        0.03,
        0.10,
        0.25,
        0.75,
        2.0,
    )
    default_logistic_c: float = 0.25
    recency_half_life_days: float = 45.0
    stat_balance_power: float = 0.0
    evaluation_start_date: str | None = None
    evaluation_end_date: str | None = None


@dataclass(frozen=True)
class NestedRegularizationTrainingResult:
    bundle: ShadowCandidateBundle
    selected_logistic_c: float
    selected_validation_brier: float | None
    selection_source: str
    validation_start: str
    validation_end: str
    candidate_metrics: tuple[dict[str, float], ...]


def _with_recency_weight(
    frame: pd.DataFrame,
    *,
    reference_day: pd.Timestamp,
    half_life_days: float,
    stat_balance_power: float = 0.0,
) -> pd.DataFrame:
    if not 0.0 <= stat_balance_power <= 1.0:
        raise ValueError(
            "stat_balance_power must be between zero and one"
        )
    weighted = frame.copy()
    age_days = (
        reference_day - weighted["_match_day"]
    ).dt.total_seconds() / 86_400.0
    weighted["training_weight"] = (
        pd.to_numeric(
            weighted["training_weight"],
            errors="coerce",
        ).fillna(1.0)
        * np.power(0.5, age_days / half_life_days)
    )
    if stat_balance_power > 0.0:
        if "stat_key" not in weighted.columns:
            raise ValueError(
                "stat-balanced training requires stat_key"
            )
        group_size = weighted.groupby(
            "stat_key"
        )["stat_key"].transform("size")
        target_size = len(weighted) / weighted["stat_key"].nunique()
        balance = np.power(
            target_size / group_size,
            stat_balance_power,
        )
        balance /= float(balance.mean())
        weighted["training_weight"] *= balance
    return weighted


def _select_logistic_c(
    inner_train: pd.DataFrame,
    validation: pd.DataFrame,
    *,
    inner_train_end: pd.Timestamp,
    config: NestedRegularizationConfig,
) -> tuple[
    float,
    float | None,
    str,
    list[dict[str, float]],
]:
    can_select_regularization = (
        len(inner_train) >= config.min_model_train_rows
        and len(validation) >= config.min_validation_rows
        and inner_train["is_over_win"].nunique() >= 2
        and validation["is_over_win"].nunique() >= 2
    )
    if not can_select_regularization:
        return (
            float(config.default_logistic_c),
            None,
            "default_insufficient_validation",
            [],
        )

    weighted_inner = _with_recency_weight(
        inner_train,
        reference_day=inner_train_end,
        half_life_days=config.recency_half_life_days,
        stat_balance_power=config.stat_balance_power,
    )
    candidate_metrics: list[dict[str, float]] = []
    for logistic_c in config.c_grid:
        model = fit_market_classifier(
            "logistic_market",
            weighted_inner,
            logistic_c=logistic_c,
        )
        probability = model.predict_probability_over(validation)
        candidate_metrics.append(
            {
                "logistic_c": float(logistic_c),
                "validation_brier": float(
                    brier_score_loss(
                        validation["is_over_win"],
                        probability,
                    )
                ),
            }
        )
    selected = min(
        candidate_metrics,
        key=lambda row: (
            row["validation_brier"],
            row["logistic_c"],
        ),
    )
    return (
        float(selected["logistic_c"]),
        float(selected["validation_brier"]),
        "inner_temporal_validation",
        candidate_metrics,
    )


def train_nested_regularization_candidate(
    market_frame: pd.DataFrame,
    *,
    cutoff_date: date | str,
    config: NestedRegularizationConfig,
) -> NestedRegularizationTrainingResult:
    cutoff = pd.Timestamp(cutoff_date).normalize()
    train_start = cutoff - timedelta(
        days=config.train_window_days
    )
    train_end = cutoff - timedelta(days=1)
    validation_start = train_end - timedelta(
        days=config.validation_window_days - 1
    )
    inner_train_end = validation_start - timedelta(days=1)
    frame = market_frame.copy()
    frame["_match_day"] = pd.to_datetime(
        frame["match_date"],
        errors="raise",
    ).dt.normalize()
    trainable = frame[frame["is_over_win"].notna()]
    full_train = trainable[
        trainable["_match_day"].between(train_start, train_end)
    ].copy()
    inner_train = full_train[
        full_train["_match_day"].le(inner_train_end)
    ].copy()
    validation = full_train[
        full_train["_match_day"].between(
            validation_start,
            train_end,
        )
    ].copy()
    if (
        len(full_train) < config.min_model_train_rows
        or full_train["is_over_win"].nunique() < 2
    ):
        raise ValueError(
            "insufficient full training rows for nested candidate"
        )
    (
        selected_c,
        selected_brier,
        selection_source,
        candidate_metrics,
    ) = _select_logistic_c(
        inner_train,
        validation,
        inner_train_end=inner_train_end,
        config=config,
    )
    weighted_full = _with_recency_weight(
        full_train,
        reference_day=train_end,
        half_life_days=config.recency_half_life_days,
        stat_balance_power=config.stat_balance_power,
    )
    model = fit_market_classifier(
        "logistic_market",
        weighted_full,
        logistic_c=selected_c,
    )
    bundle = ShadowCandidateBundle(
        model=model,
        training_start=train_start.date().isoformat(),
        training_end=train_end.date().isoformat(),
        training_rows=len(full_train),
        train_window_days=config.train_window_days,
        recency_half_life_days=config.recency_half_life_days,
    )
    return NestedRegularizationTrainingResult(
        bundle=bundle,
        selected_logistic_c=selected_c,
        selected_validation_brier=selected_brier,
        selection_source=selection_source,
        validation_start=validation_start.date().isoformat(),
        validation_end=train_end.date().isoformat(),
        candidate_metrics=tuple(candidate_metrics),
    )


def run_nested_regularization_walk_forward(
    market_frame: pd.DataFrame,
    config: NestedRegularizationConfig,
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
    window_rows: list[dict[str, object]] = []
    test_start = first_day + timedelta(
        days=config.train_window_days
    )
    if config.evaluation_start_date is not None:
        test_start = max(
            test_start,
            pd.Timestamp(
                config.evaluation_start_date
            ).normalize(),
        )
    while test_start <= last_day:
        train_start = test_start - timedelta(
            days=config.train_window_days
        )
        train_end = test_start - timedelta(days=1)
        validation_start = train_end - timedelta(
            days=config.validation_window_days - 1
        )
        inner_train_end = validation_start - timedelta(days=1)
        test_end = min(
            test_start
            + timedelta(days=config.test_window_days - 1),
            last_day,
        )
        trainable = frame[frame["is_over_win"].notna()]
        inner_train = trainable[
            trainable["_match_day"].between(
                train_start,
                inner_train_end,
            )
        ].copy()
        validation = trainable[
            trainable["_match_day"].between(
                validation_start,
                train_end,
            )
        ].copy()
        full_train = trainable[
            trainable["_match_day"].between(
                train_start,
                train_end,
            )
        ].copy()
        test = frame[
            frame["_match_day"].between(test_start, test_end)
        ].copy()
        if (
            len(full_train) < config.min_model_train_rows
            or full_train["is_over_win"].nunique() < 2
            or test.empty
        ):
            test_start += timedelta(days=config.step_days)
            continue

        (
            selected_c,
            selected_validation_brier,
            selection_source,
            candidate_metrics,
        ) = _select_logistic_c(
            inner_train,
            validation,
            inner_train_end=inner_train_end,
            config=config,
        )
        weighted_full = _with_recency_weight(
            full_train,
            reference_day=train_end,
            half_life_days=config.recency_half_life_days,
            stat_balance_power=config.stat_balance_power,
        )
        final_model = fit_market_classifier(
            "logistic_market",
            weighted_full,
            logistic_c=selected_c,
        )
        market_predictions = test.drop(
            columns=["_match_day"]
        ).copy()
        market_predictions["model_name"] = (
            "nested_logistic_regularization"
        )
        market_predictions["predicted_over_probability"] = (
            final_model.predict_probability_over(test)
        )
        market_predictions["selected_logistic_c"] = selected_c
        market_predictions["regularization_selection_source"] = (
            selection_source
        )
        market_predictions["train_start"] = (
            train_start.date().isoformat()
        )
        market_predictions["train_end"] = (
            train_end.date().isoformat()
        )
        market_predictions["test_start"] = (
            test_start.date().isoformat()
        )
        market_predictions["test_end"] = (
            test_end.date().isoformat()
        )
        prediction_parts.append(
            expand_market_predictions_to_sides(
                market_predictions
            )
        )

        scored_test = market_predictions[
            market_predictions["is_over_win"].notna()
        ]
        window_rows.append(
            {
                "train_start": train_start.date().isoformat(),
                "inner_train_end": (
                    inner_train_end.date().isoformat()
                ),
                "validation_start": (
                    validation_start.date().isoformat()
                ),
                "validation_end": train_end.date().isoformat(),
                "test_start": test_start.date().isoformat(),
                "test_end": test_end.date().isoformat(),
                "inner_train_rows": int(len(inner_train)),
                "validation_rows": int(len(validation)),
                "full_train_rows": int(len(full_train)),
                "test_rows": int(len(scored_test)),
                "selected_logistic_c": selected_c,
                "selected_validation_brier": (
                    selected_validation_brier
                ),
                "selection_source": selection_source,
                "stat_balance_power": config.stat_balance_power,
                "candidate_metrics": candidate_metrics,
                "test_brier": float(
                    brier_score_loss(
                        scored_test["is_over_win"],
                        scored_test[
                            "predicted_over_probability"
                        ],
                    )
                ),
            }
        )
        test_start += timedelta(days=config.step_days)

    predictions = (
        pd.concat(prediction_parts, ignore_index=True)
        if prediction_parts
        else pd.DataFrame()
    )
    return predictions, pd.DataFrame(window_rows)
