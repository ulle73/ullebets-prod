from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import math

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance, mean_squared_error

from ullebets_v2.ev_model.dispersion import estimate_nb_dispersion
from ullebets_v2.ev_model.evaluation import score_market_rows
from ullebets_v2.ev_model.models import fit_count_candidate


@dataclass(frozen=True)
class WalkForwardExperimentConfig:
    train_window_days: int = 90
    test_window_days: int = 14
    step_days: int = 14
    min_train_rows: int = 500
    model_names: tuple[str, ...] = (
        "market_anchor",
        "historical_baseline",
        "poisson_glm",
        "hgb_poisson",
        "hgb_market_residual",
    )
    minimum_ev_thresholds: tuple[float, ...] = (0.0, 0.02, 0.05, 0.10)
    probability_distributions: tuple[str, ...] = ("poisson", "negative_binomial")
    evaluation_end_date: str | None = None


def _prediction_rows(
    test: pd.DataFrame,
    *,
    model_name: str,
    means: np.ndarray,
    dispersions: np.ndarray,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    test_start: pd.Timestamp,
    test_end: pd.Timestamp,
) -> pd.DataFrame:
    rows = test[
        [
            "sample_key",
            "exposure_match_id",
            "match_date",
            "stat_key",
            "period",
            "scope",
            "line_value",
            "actual_value",
            "over_odds",
            "under_odds",
        ]
    ].copy()
    rows["model_name"] = model_name
    rows["predicted_mean"] = means
    rows["nb_dispersion"] = dispersions
    rows["train_start"] = train_start.date().isoformat()
    rows["train_end"] = train_end.date().isoformat()
    rows["test_start"] = test_start.date().isoformat()
    rows["test_end"] = test_end.date().isoformat()
    return rows


def _test_dispersions(
    train: pd.DataFrame,
    test: pd.DataFrame,
    train_means: np.ndarray,
) -> np.ndarray:
    working = train[["stat_key", "period", "scope", "actual_value"]].copy()
    working["_predicted_mean"] = train_means
    global_dispersion = estimate_nb_dispersion(
        working["actual_value"].to_numpy(dtype=float),
        working["_predicted_mean"].to_numpy(dtype=float),
    )
    dispersion_by_segment: dict[tuple[str, str, str], float] = {}
    for key, group in working.groupby(["stat_key", "period", "scope"]):
        if len(group) < 30:
            continue
        dispersion_by_segment[key] = estimate_nb_dispersion(
            group["actual_value"].to_numpy(dtype=float),
            group["_predicted_mean"].to_numpy(dtype=float),
        )
    return np.asarray(
        [
            dispersion_by_segment.get(
                (str(row.stat_key), str(row.period), str(row.scope)),
                global_dispersion,
            )
            for row in test.itertuples(index=False)
        ],
        dtype=float,
    )


def run_count_walk_forward(
    modeling_frame: pd.DataFrame,
    model_features: pd.DataFrame,
    config: WalkForwardExperimentConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(modeling_frame) != len(model_features):
        raise ValueError("modeling_frame and model_features must have equal length")

    frame = modeling_frame.reset_index(drop=True).copy()
    features = model_features.reset_index(drop=True).copy()
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
        train_mask = frame["_match_day"].between(train_start, train_end)
        test_mask = frame["_match_day"].between(test_start, test_end)
        train = frame.loc[train_mask]
        test = frame.loc[test_mask]
        if len(train) < config.min_train_rows or test.empty:
            test_start += timedelta(days=config.step_days)
            continue

        train_features = features.loc[train.index]
        test_features = features.loc[test.index]
        targets = train["actual_value"].to_numpy(dtype=float)
        for model_name in config.model_names:
            model = fit_count_candidate(model_name, train_features, targets)
            train_means = np.clip(model.predict(train_features), 1e-9, None)
            means = np.clip(model.predict(test_features), 1e-9, None)
            dispersions = _test_dispersions(train, test, train_means)
            predictions = _prediction_rows(
                test,
                model_name=model_name,
                means=means,
                dispersions=dispersions,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
            prediction_parts.append(predictions)

            actual = test["actual_value"].to_numpy(dtype=float)
            base_metrics = {
                "model_name": model_name,
                "train_start": train_start.date().isoformat(),
                "train_end": train_end.date().isoformat(),
                "test_start": test_start.date().isoformat(),
                "test_end": test_end.date().isoformat(),
                "train_rows": len(train),
                "test_rows": len(test),
                "mae": float(mean_absolute_error(actual, means)),
                "rmse": float(math.sqrt(mean_squared_error(actual, means))),
                "poisson_deviance": float(mean_poisson_deviance(actual, means)),
            }
            for distribution in config.probability_distributions:
                for threshold in config.minimum_ev_thresholds:
                    selections = score_market_rows(
                        test.drop(columns=["_match_day"]),
                        predicted_means=means,
                        minimum_ev=threshold,
                        distribution=distribution,
                        dispersions=dispersions,
                    )
                    pnl = (
                        float(selections["realized_roi_units"].sum())
                        if not selections.empty
                        else 0.0
                    )
                    bets = len(selections)
                    summary_rows.append(
                        {
                            **base_metrics,
                            "distribution": distribution,
                            "minimum_ev": threshold,
                            "bets": bets,
                            "pnl_units": pnl,
                            "roi_pct": (pnl / bets * 100.0) if bets else 0.0,
                        }
                    )
        test_start += timedelta(days=config.step_days)

    predictions = (
        pd.concat(prediction_parts, ignore_index=True)
        if prediction_parts
        else pd.DataFrame()
    )
    return predictions, pd.DataFrame(summary_rows)
