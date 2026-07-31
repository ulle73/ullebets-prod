from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ullebets_v2.ev_model.categorical_interactions import (
    add_categorical_interaction_features,
)


META_COLUMNS = (
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
    "odds_snapshot_time",
    "match_start_time",
)

MARKET_CATEGORICAL_COLUMNS = (
    "league_name_normalized",
    "period",
    "scope",
    "snapshot_horizon_bucket",
    "stat_key",
)

MARKET_EXCLUDED_COLUMNS = {
    "actual_value",
    "exposure_match_id",
    "is_over_win",
    "match_date",
    "over_realized_roi_units",
    "over_settlement_result",
    "sample_key",
    "training_weight",
    "under_realized_roi_units",
    "under_settlement_result",
}


def _settlement(
    actual: float,
    line: float,
    direction: str,
    odds: float | None,
) -> tuple[str | None, float | None]:
    if odds is None or pd.isna(odds):
        return None, None
    if math.isclose(actual, line, rel_tol=0.0, abs_tol=1e-9):
        return "push", 0.0
    won = actual > line if direction == "over" else actual < line
    return ("win", float(odds) - 1.0) if won else ("loss", -1.0)


def build_market_classifier_frame(
    modeling_frame: pd.DataFrame,
    model_features: pd.DataFrame,
) -> pd.DataFrame:
    prediction_frame = build_market_prediction_frame(
        modeling_frame,
        model_features,
    )
    markets = modeling_frame.reset_index(drop=True)
    rows: list[dict[str, object]] = []
    for index, market in markets.iterrows():
        actual = float(market["actual_value"])
        line = float(market["line_value"])
        over_result, over_roi = _settlement(
            actual,
            line,
            "over",
            market.get("over_odds"),
        )
        under_result, under_roi = _settlement(
            actual,
            line,
            "under",
            market.get("under_odds"),
        )
        row = prediction_frame.loc[index].to_dict()
        row.update(
            {
                "is_over_win": (
                    math.nan
                    if math.isclose(actual, line, rel_tol=0.0, abs_tol=1e-9)
                    else float(actual > line)
                ),
                "over_settlement_result": over_result,
                "under_settlement_result": under_result,
                "over_realized_roi_units": over_roi,
                "under_realized_roi_units": under_roi,
                "training_weight": 1.0,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def build_market_prediction_frame(
    modeling_frame: pd.DataFrame,
    model_features: pd.DataFrame,
) -> pd.DataFrame:
    if len(modeling_frame) != len(model_features):
        raise ValueError("modeling_frame and model_features must have equal length")
    markets = modeling_frame.reset_index(drop=True)
    features = model_features.reset_index(drop=True)
    rows: list[dict[str, object]] = []
    for index, market in markets.iterrows():
        row = features.loc[index].to_dict()
        row.update(
            {
                column: market.get(column)
                for column in META_COLUMNS
                if column in markets.columns
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


class MarketClassifier(Protocol):
    name: str

    def predict_probability_over(self, frame: pd.DataFrame) -> np.ndarray: ...


@dataclass
class StaticMarketClassifier:
    name: str
    column: str

    def predict_probability_over(self, frame: pd.DataFrame) -> np.ndarray:
        return np.clip(
            pd.to_numeric(frame[self.column], errors="coerce")
            .fillna(0.5)
            .to_numpy(dtype=float),
            1e-6,
            1.0 - 1e-6,
        )


@dataclass
class PipelineMarketClassifier:
    name: str
    pipeline: Pipeline

    def predict_probability_over(self, frame: pd.DataFrame) -> np.ndarray:
        return np.clip(
            self.pipeline.predict_proba(frame)[:, 1],
            1e-6,
            1.0 - 1e-6,
        )


@dataclass
class WeightedEnsembleMarketClassifier:
    name: str
    models: tuple[MarketClassifier, ...]
    weights: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.models or len(self.models) != len(self.weights):
            raise ValueError(
                "ensemble requires equal non-empty models and weights"
            )
        if any(weight < 0.0 for weight in self.weights):
            raise ValueError("ensemble weights must be non-negative")
        if not math.isclose(
            sum(self.weights),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("ensemble weights must sum to one")

    def predict_probability_over(
        self,
        frame: pd.DataFrame,
    ) -> np.ndarray:
        probabilities = np.zeros(len(frame), dtype=float)
        for model, weight in zip(
            self.models,
            self.weights,
            strict=True,
        ):
            probabilities += (
                weight
                * model.predict_probability_over(frame)
            )
        return np.clip(probabilities, 1e-6, 1.0 - 1e-6)


@dataclass
class CategoricalInteractionMarketClassifier:
    name: str
    model: MarketClassifier
    category_column: str
    source_columns: tuple[str, ...]
    deviation_values: tuple[str, ...]

    def predict_probability_over(
        self,
        frame: pd.DataFrame,
    ) -> np.ndarray:
        engineered = add_categorical_interaction_features(
            frame,
            category_column=self.category_column,
            source_columns=self.source_columns,
            deviation_values=self.deviation_values,
        )
        return self.model.predict_probability_over(engineered)


@dataclass
class ResidualMarketClassifier:
    name: str
    pipeline: Pipeline
    market_column: str = "market_fair_probability_over"

    def predict_probability_over(self, frame: pd.DataFrame) -> np.ndarray:
        market = pd.to_numeric(
            frame[self.market_column],
            errors="coerce",
        ).fillna(0.5)
        residual = self.pipeline.predict(frame)
        return np.clip(market.to_numpy(dtype=float) + residual, 1e-6, 1.0 - 1e-6)


@dataclass
class HierarchicalMarketClassifier:
    name: str
    global_model: MarketClassifier
    stat_models: dict[str, MarketClassifier]
    segment_models: dict[tuple[str, str, str], MarketClassifier]

    def predict_probability_over(self, frame: pd.DataFrame) -> np.ndarray:
        probabilities = self.global_model.predict_probability_over(frame)
        stat_values = frame["stat_key"].astype(str)
        for stat_key, model in self.stat_models.items():
            mask = stat_values.eq(stat_key).to_numpy()
            if mask.any():
                probabilities[mask] = model.predict_probability_over(
                    frame.loc[mask]
                )
        for key, model in self.segment_models.items():
            mask = (
                stat_values.eq(key[0])
                & frame["period"].astype(str).eq(key[1])
                & frame["scope"].astype(str).eq(key[2])
            ).to_numpy()
            if mask.any():
                probabilities[mask] = model.predict_probability_over(
                    frame.loc[mask]
                )
        return probabilities


def _preprocessor(
    frame: pd.DataFrame,
    *,
    scale_numeric: bool,
) -> ColumnTransformer:
    categorical = [
        column
        for column in MARKET_CATEGORICAL_COLUMNS
        if column in frame.columns
    ]
    numeric = [
        column
        for column in frame.columns
        if column not in MARKET_EXCLUDED_COLUMNS
        and column not in categorical
        and pd.api.types.is_numeric_dtype(frame[column])
        and frame[column].notna().any()
    ]
    numeric_steps: list[tuple[str, object]] = [
        ("imputer", SimpleImputer(strategy="median")),
    ]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))
    return ColumnTransformer(
        [
            ("numeric", Pipeline(numeric_steps), numeric),
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "onehot",
                            OneHotEncoder(
                                handle_unknown="ignore",
                                sparse_output=False,
                            ),
                        ),
                    ]
                ),
                categorical,
            ),
        ],
        sparse_threshold=0.0,
    )


def fit_market_classifier(
    name: str,
    training_frame: pd.DataFrame,
    *,
    logistic_c: float = 0.25,
) -> MarketClassifier:
    if name == "market_probability":
        return StaticMarketClassifier(
            name=name,
            column="market_fair_probability_over",
        )
    if name == "empirical_bayes_line":
        return StaticMarketClassifier(
            name=name,
            column="line_history_all_posterior_over_20",
        )

    trainable = training_frame[training_frame["is_over_win"].notna()].copy()
    y = trainable["is_over_win"].to_numpy(dtype=int)
    sample_weight = trainable["training_weight"].to_numpy(dtype=float)
    if name == "hierarchical_logistic_market":
        global_model = fit_market_classifier(
            "logistic_market",
            trainable,
            logistic_c=logistic_c,
        )
        stat_models: dict[str, MarketClassifier] = {}
        for stat_key, group in trainable.groupby("stat_key"):
            if len(group) >= 180 and group["is_over_win"].nunique() >= 2:
                stat_models[str(stat_key)] = fit_market_classifier(
                    "logistic_market",
                    group,
                    logistic_c=logistic_c,
                )
        segment_models: dict[
            tuple[str, str, str],
            MarketClassifier,
        ] = {}
        for key, group in trainable.groupby(["stat_key", "period", "scope"]):
            if len(group) >= 120 and group["is_over_win"].nunique() >= 2:
                normalized_key = tuple(str(part) for part in key)
                segment_models[normalized_key] = fit_market_classifier(
                    "logistic_market",
                    group,
                    logistic_c=logistic_c,
                )
        return HierarchicalMarketClassifier(
            name=name,
            global_model=global_model,
            stat_models=stat_models,
            segment_models=segment_models,
        )
    if name == "logistic_market":
        pipeline = Pipeline(
            [
                ("features", _preprocessor(trainable, scale_numeric=True)),
                (
                    "model",
                    LogisticRegression(
                        C=logistic_c,
                        max_iter=1000,
                        random_state=42,
                    ),
                ),
            ]
        )
        pipeline.fit(trainable, y, model__sample_weight=sample_weight)
        return PipelineMarketClassifier(name=name, pipeline=pipeline)
    if name == "hgb_market":
        pipeline = Pipeline(
            [
                ("features", _preprocessor(trainable, scale_numeric=False)),
                (
                    "model",
                    HistGradientBoostingClassifier(
                        learning_rate=0.04,
                        max_iter=160,
                        max_leaf_nodes=11,
                        min_samples_leaf=35,
                        l2_regularization=2.0,
                        random_state=42,
                    ),
                ),
            ]
        )
        pipeline.fit(trainable, y, model__sample_weight=sample_weight)
        return PipelineMarketClassifier(name=name, pipeline=pipeline)
    if name == "market_residual_hgb":
        market = pd.to_numeric(
            trainable["market_fair_probability_over"],
            errors="coerce",
        ).fillna(0.5)
        residual_target = y - market.to_numpy(dtype=float)
        pipeline = Pipeline(
            [
                ("features", _preprocessor(trainable, scale_numeric=False)),
                (
                    "model",
                    HistGradientBoostingRegressor(
                        loss="squared_error",
                        learning_rate=0.035,
                        max_iter=140,
                        max_leaf_nodes=9,
                        min_samples_leaf=40,
                        l2_regularization=3.0,
                        random_state=42,
                    ),
                ),
            ]
        )
        pipeline.fit(
            trainable,
            residual_target,
            model__sample_weight=sample_weight,
        )
        return ResidualMarketClassifier(name=name, pipeline=pipeline)
    raise ValueError(f"unknown market classifier: {name}")


def expand_market_predictions_to_sides(
    market_predictions: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for prediction in market_predictions.itertuples(index=False):
        probability_over = float(prediction.predicted_over_probability)
        for direction, odds, probability, settlement, realized in (
            (
                "over",
                prediction.over_odds,
                probability_over,
                getattr(prediction, "over_settlement_result", None),
                getattr(prediction, "over_realized_roi_units", None),
            ),
            (
                "under",
                prediction.under_odds,
                1.0 - probability_over,
                getattr(prediction, "under_settlement_result", None),
                getattr(prediction, "under_realized_roi_units", None),
            ),
        ):
            if odds is None or pd.isna(odds) or float(odds) <= 1.0:
                continue
            row = prediction._asdict()
            row.update(
                {
                    "side_key": f"{prediction.sample_key}|{direction}",
                    "direction": direction,
                    "offered_odds": float(odds),
                    "predicted_win_probability": probability,
                    "expected_roi_units": probability * float(odds) - 1.0,
                    "settlement_result": settlement,
                    "realized_roi_units": realized,
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)
