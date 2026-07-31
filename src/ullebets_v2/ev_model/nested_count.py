from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import math

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, mean_absolute_error, mean_squared_error

from ullebets_v2.ev_model.dispersion import estimate_nb_dispersion
from ullebets_v2.ev_model.models import fit_count_candidate
from ullebets_v2.ev_model.probabilities import (
    expected_roi,
    negative_binomial_line_probabilities,
)


COUNT_CATEGORICAL_COLUMNS = (
    "league_name_normalized",
    "period",
    "scope",
    "stat_key",
)

COUNT_NUMERIC_COLUMNS = (
    "line_value",
    "over_odds",
    "under_odds",
    "market_fair_probability_over",
    "market_anchor_lambda",
    "market_overround",
    "baseline_lambda",
    "snapshot_lead_hours",
    "history_role_attack_3",
    "history_role_defense_3",
    "history_role_expected_3",
    "history_role_attack_5",
    "history_role_defense_5",
    "history_role_expected_5",
    "history_role_attack_10",
    "history_role_defense_10",
    "history_role_expected_10",
    "history_role_attack_20",
    "history_role_defense_20",
    "history_role_expected_20",
    "history_all_attack_3",
    "history_all_defense_3",
    "history_all_expected_3",
    "history_all_attack_5",
    "history_all_defense_5",
    "history_all_expected_5",
    "history_all_attack_10",
    "history_all_defense_10",
    "history_all_expected_10",
    "history_all_attack_20",
    "history_all_defense_20",
    "history_all_expected_20",
    "history_role_trend_3_10",
    "history_all_trend_3_10",
)


@dataclass(frozen=True)
class NestedCountConfig:
    train_window_days: int = 90
    validation_window_days: int = 21
    test_window_days: int = 14
    step_days: int = 14
    min_model_train_rows: int = 250
    min_inner_train_rows: int = 250
    min_validation_rows: int = 100
    min_segment_dispersion_rows: int = 30
    recency_half_life_days: float = 45.0
    model_name: str = "hgb_market_residual"
    evaluation_start_date: str | None = None
    evaluation_end_date: str | None = None


@dataclass(frozen=True)
class _DispersionProfile:
    global_dispersion: float
    by_segment: dict[tuple[str, str, str], float]
    validation_start: str
    validation_end: str


def build_count_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        column
        for column in (*COUNT_CATEGORICAL_COLUMNS, *COUNT_NUMERIC_COLUMNS)
        if column in frame.columns
    ]
    required = {
        "league_name_normalized",
        "period",
        "scope",
        "stat_key",
        "market_anchor_lambda",
    }
    missing = sorted(required.difference(columns))
    if missing:
        raise ValueError(f"count feature frame is missing columns: {missing}")
    return frame.loc[:, columns].copy()


def _validate_snapshot_timing(frame: pd.DataFrame) -> None:
    required = {"odds_snapshot_time", "match_start_time"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"count walk-forward is missing timing columns: {missing}")
    snapshot = pd.to_datetime(
        frame["odds_snapshot_time"],
        errors="coerce",
        utc=True,
    )
    kickoff = pd.to_datetime(
        frame["match_start_time"],
        errors="coerce",
        utc=True,
    )
    if snapshot.isna().any() or kickoff.isna().any():
        raise ValueError("count walk-forward contains missing timing")
    if snapshot.ge(kickoff).any():
        raise ValueError(
            "every odds snapshot must be strictly before kickoff"
        )


def _recency_weights(
    frame: pd.DataFrame,
    *,
    reference_day: pd.Timestamp,
    half_life_days: float,
) -> np.ndarray:
    if half_life_days <= 0.0:
        raise ValueError("recency_half_life_days must be positive")
    age_days = (
        reference_day - frame["_match_day"]
    ).dt.total_seconds() / 86_400.0
    base = (
        pd.to_numeric(
            frame.get(
                "training_weight",
                pd.Series(1.0, index=frame.index),
            ),
            errors="coerce",
        )
        .fillna(1.0)
        .clip(lower=0.0)
    )
    return (
        base * np.power(0.5, age_days / half_life_days)
    ).to_numpy(dtype=float)


def _build_dispersion_profile(
    validation: pd.DataFrame,
    validation_means: np.ndarray,
    *,
    min_segment_rows: int,
) -> _DispersionProfile:
    actual = validation["actual_value"].to_numpy(dtype=float)
    global_dispersion = estimate_nb_dispersion(actual, validation_means)
    working = validation[["stat_key", "period", "scope"]].copy()
    working["_actual"] = actual
    working["_mean"] = validation_means
    by_segment: dict[tuple[str, str, str], float] = {}
    for key, group in working.groupby(
        ["stat_key", "period", "scope"],
        sort=False,
    ):
        if len(group) < min_segment_rows:
            continue
        normalized_key = tuple(str(value) for value in key)
        by_segment[normalized_key] = estimate_nb_dispersion(
            group["_actual"].to_numpy(dtype=float),
            group["_mean"].to_numpy(dtype=float),
        )
    return _DispersionProfile(
        global_dispersion=float(global_dispersion),
        by_segment=by_segment,
        validation_start=str(validation["_match_day"].min().date()),
        validation_end=str(validation["_match_day"].max().date()),
    )


def _apply_dispersion_profile(
    profile: _DispersionProfile,
    target: pd.DataFrame,
) -> np.ndarray:
    return np.asarray(
        [
            profile.by_segment.get(
                (
                    str(row.stat_key),
                    str(row.period),
                    str(row.scope),
                ),
                profile.global_dispersion,
            )
            for row in target.itertuples(index=False)
        ],
        dtype=float,
    )


def _expand_count_predictions_to_sides(
    market_predictions: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for prediction in market_predictions.itertuples(index=False):
        for direction, odds, settlement, realized in (
            (
                "over",
                prediction.over_odds,
                prediction.over_settlement_result,
                prediction.over_realized_roi_units,
            ),
            (
                "under",
                prediction.under_odds,
                prediction.under_settlement_result,
                prediction.under_realized_roi_units,
            ),
        ):
            if odds is None or pd.isna(odds) or float(odds) <= 1.0:
                continue
            probabilities = negative_binomial_line_probabilities(
                mean=float(prediction.predicted_count_mean),
                dispersion=float(prediction.nb_dispersion),
                line=float(prediction.line_value),
                direction=direction,
            )
            row = prediction._asdict()
            row.update(
                {
                    "side_key": f"{prediction.sample_key}|{direction}",
                    "direction": direction,
                    "offered_odds": float(odds),
                    "predicted_win_probability": probabilities.win,
                    "predicted_push_probability": probabilities.push,
                    "expected_roi_units": expected_roi(
                        win_probability=probabilities.win,
                        push_probability=probabilities.push,
                        decimal_odds=float(odds),
                    ),
                    "settlement_result": settlement,
                    "realized_roi_units": realized,
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def run_nested_count_walk_forward(
    market_frame: pd.DataFrame,
    config: NestedCountConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {
        "sample_key",
        "exposure_match_id",
        "match_date",
        "actual_value",
        "line_value",
        "over_odds",
        "under_odds",
        "over_settlement_result",
        "under_settlement_result",
        "over_realized_roi_units",
        "under_realized_roi_units",
    }
    missing = sorted(required.difference(market_frame.columns))
    if missing:
        raise ValueError(f"count walk-forward is missing columns: {missing}")
    _validate_snapshot_timing(market_frame)
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
    prior_dispersion_profile: _DispersionProfile | None = None
    test_start = first_day + timedelta(days=config.train_window_days)
    if config.evaluation_start_date is not None:
        test_start = max(
            test_start,
            pd.Timestamp(config.evaluation_start_date).normalize(),
        )
    while test_start <= last_day:
        train_start = test_start - timedelta(days=config.train_window_days)
        train_end = test_start - timedelta(days=1)
        validation_start = train_end - timedelta(
            days=config.validation_window_days - 1
        )
        inner_train_end = validation_start - timedelta(days=1)
        test_end = min(
            test_start + timedelta(days=config.test_window_days - 1),
            last_day,
        )
        resolved = frame[frame["actual_value"].notna()]
        inner_train = resolved[
            resolved["_match_day"].between(train_start, inner_train_end)
        ].copy()
        validation = resolved[
            resolved["_match_day"].between(validation_start, train_end)
        ].copy()
        full_train = resolved[
            resolved["_match_day"].between(train_start, train_end)
        ].copy()
        test = frame[
            frame["_match_day"].between(test_start, test_end)
        ].copy()
        if (
            len(full_train) < config.min_model_train_rows
            or test.empty
        ):
            test_start += timedelta(days=config.step_days)
            continue

        validation_means: np.ndarray | None = None
        if (
            len(inner_train) >= config.min_inner_train_rows
            and len(validation) >= config.min_validation_rows
        ):
            inner_features = build_count_feature_frame(inner_train)
            validation_features = build_count_feature_frame(validation)
            inner_weights = _recency_weights(
                inner_train,
                reference_day=inner_train_end,
                half_life_days=config.recency_half_life_days,
            )
            inner_model = fit_count_candidate(
                config.model_name,
                inner_features,
                inner_train["actual_value"].to_numpy(dtype=float),
                sample_weight=inner_weights,
            )
            validation_means = np.clip(
                inner_model.predict(validation_features),
                1e-9,
                None,
            )
            prior_dispersion_profile = _build_dispersion_profile(
                validation,
                validation_means,
                min_segment_rows=config.min_segment_dispersion_rows,
            )
            dispersion_source = "inner_temporal_validation"
        elif prior_dispersion_profile is not None:
            dispersion_source = "carried_forward_prior_validation"
        else:
            test_start += timedelta(days=config.step_days)
            continue
        test_dispersions = _apply_dispersion_profile(
            prior_dispersion_profile,
            test,
        )

        full_features = build_count_feature_frame(full_train)
        test_features = build_count_feature_frame(test)
        full_weights = _recency_weights(
            full_train,
            reference_day=train_end,
            half_life_days=config.recency_half_life_days,
        )
        final_model = fit_count_candidate(
            config.model_name,
            full_features,
            full_train["actual_value"].to_numpy(dtype=float),
            sample_weight=full_weights,
        )
        test_means = np.clip(
            final_model.predict(test_features),
            1e-9,
            None,
        )
        market_predictions = test.drop(columns=["_match_day"]).copy()
        market_predictions["model_name"] = (
            f"nested_count_{config.model_name}"
        )
        market_predictions["predicted_count_mean"] = test_means
        market_predictions["nb_dispersion"] = test_dispersions
        market_predictions["dispersion_source"] = dispersion_source
        market_predictions["dispersion_validation_start"] = (
            prior_dispersion_profile.validation_start
        )
        market_predictions["dispersion_validation_end"] = (
            prior_dispersion_profile.validation_end
        )
        market_predictions["train_start"] = train_start.date().isoformat()
        market_predictions["train_end"] = train_end.date().isoformat()
        market_predictions["validation_start"] = (
            validation_start.date().isoformat()
        )
        market_predictions["validation_end"] = train_end.date().isoformat()
        market_predictions["test_start"] = test_start.date().isoformat()
        market_predictions["test_end"] = test_end.date().isoformat()
        over_probabilities = [
            negative_binomial_line_probabilities(
                mean=float(mean),
                dispersion=float(dispersion),
                line=float(line),
                direction="over",
            ).win
            for mean, dispersion, line in zip(
                test_means,
                test_dispersions,
                market_predictions["line_value"],
                strict=True,
            )
        ]
        market_predictions["predicted_over_probability"] = over_probabilities
        side_predictions = _expand_count_predictions_to_sides(
            market_predictions
        )
        prediction_parts.append(side_predictions)

        scored = market_predictions[
            market_predictions["is_over_win"].notna()
        ].copy()
        observed = scored["actual_value"].to_numpy(dtype=float)
        scored_means = scored["predicted_count_mean"].to_numpy(dtype=float)
        window_rows.append(
            {
                "train_start": train_start.date().isoformat(),
                "inner_train_end": inner_train_end.date().isoformat(),
                "validation_start": validation_start.date().isoformat(),
                "validation_end": train_end.date().isoformat(),
                "test_start": test_start.date().isoformat(),
                "test_end": test_end.date().isoformat(),
                "inner_train_rows": int(len(inner_train)),
                "validation_rows": int(len(validation)),
                "full_train_rows": int(len(full_train)),
                "test_rows": int(len(scored)),
                "dispersion_source": dispersion_source,
                "dispersion_validation_start": (
                    prior_dispersion_profile.validation_start
                ),
                "dispersion_validation_end": (
                    prior_dispersion_profile.validation_end
                ),
                "validation_mae": (
                    float(
                        mean_absolute_error(
                            validation["actual_value"],
                            validation_means,
                        )
                    )
                    if validation_means is not None
                    else None
                ),
                "validation_rmse": (
                    float(
                        math.sqrt(
                            mean_squared_error(
                                validation["actual_value"],
                                validation_means,
                            )
                        )
                    )
                    if validation_means is not None
                    else None
                ),
                "validation_global_nb_dispersion": (
                    prior_dispersion_profile.global_dispersion
                ),
                "validation_segment_dispersions": len(
                    prior_dispersion_profile.by_segment
                ),
                "test_mae": float(mean_absolute_error(observed, scored_means)),
                "test_rmse": float(
                    math.sqrt(mean_squared_error(observed, scored_means))
                ),
                "test_brier": float(
                    brier_score_loss(
                        scored["is_over_win"],
                        scored["predicted_over_probability"],
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
