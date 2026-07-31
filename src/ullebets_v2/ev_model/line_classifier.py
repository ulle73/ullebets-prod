from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


META_COLUMNS = (
    "sample_key",
    "exposure_match_id",
    "match_date",
    "stat_key",
    "period",
    "scope",
    "line_value",
    "actual_value",
)

CLASSIFIER_CATEGORICAL_COLUMNS = (
    "league_name_normalized",
    "period",
    "scope",
    "stat_key",
    "direction",
)

CLASSIFIER_EXCLUDED_COLUMNS = {
    "actual_value",
    "exposure_match_id",
    "is_win",
    "match_date",
    "realized_roi_units",
    "sample_key",
    "sample_weight",
    "settlement_result",
    "side_key",
}


def _settlement(actual: float, line: float, direction: str, odds: float) -> tuple[str, float | None, float]:
    if math.isclose(actual, line, rel_tol=0.0, abs_tol=1e-9):
        return "push", None, 0.0
    won = actual > line if direction == "over" else actual < line
    return (
        ("win", 1.0, odds - 1.0)
        if won
        else ("loss", 0.0, -1.0)
    )


def build_line_classifier_frame(
    modeling_frame: pd.DataFrame,
    model_features: pd.DataFrame,
) -> pd.DataFrame:
    if len(modeling_frame) != len(model_features):
        raise ValueError("modeling_frame and model_features must have equal length")
    markets = modeling_frame.reset_index(drop=True)
    features = model_features.reset_index(drop=True)
    rows: list[dict] = []
    for index, market in markets.iterrows():
        available_sides = [
            (direction, float(odds))
            for direction, odds in (
                ("over", market.get("over_odds")),
                ("under", market.get("under_odds")),
            )
            if odds is not None and not pd.isna(odds)
        ]
        if not available_sides:
            continue
        sample_weight = 1.0 / len(available_sides)
        fair_over = float(
            features.loc[index].get(
                "market_fair_probability_over",
                1.0 / float(market["over_odds"]),
            )
        )
        for direction, odds in available_sides:
            result, is_win, realized = _settlement(
                float(market["actual_value"]),
                float(market["line_value"]),
                direction,
                odds,
            )
            row = features.loc[index].to_dict()
            row.update(
                {
                    column: market.get(column)
                    for column in META_COLUMNS
                }
            )
            row.update(
                {
                    "side_key": f"{market['sample_key']}|{direction}",
                    "direction": direction,
                    "offered_odds": odds,
                    "break_even_probability": 1.0 / odds,
                    "market_fair_probability": (
                        fair_over if direction == "over" else 1.0 - fair_over
                    ),
                    "is_win": is_win,
                    "settlement_result": result,
                    "realized_roi_units": realized,
                    "sample_weight": sample_weight,
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


class LineClassifier(Protocol):
    name: str

    def predict_probability(self, frame: pd.DataFrame) -> np.ndarray: ...


@dataclass
class StaticProbabilityClassifier:
    name: str
    column: str

    def predict_probability(self, frame: pd.DataFrame) -> np.ndarray:
        return np.clip(
            pd.to_numeric(frame[self.column], errors="coerce")
            .fillna(0.5)
            .to_numpy(dtype=float),
            1e-6,
            1.0 - 1e-6,
        )


@dataclass
class PipelineProbabilityClassifier:
    name: str
    pipeline: Pipeline

    def predict_probability(self, frame: pd.DataFrame) -> np.ndarray:
        return self.pipeline.predict_proba(frame)[:, 1]


def _classifier_preprocessor(
    frame: pd.DataFrame,
    *,
    scale_numeric: bool,
) -> ColumnTransformer:
    categorical = [
        column
        for column in CLASSIFIER_CATEGORICAL_COLUMNS
        if column in frame.columns
    ]
    numeric = [
        column
        for column in frame.columns
        if column not in CLASSIFIER_EXCLUDED_COLUMNS
        and column not in categorical
        and pd.api.types.is_numeric_dtype(frame[column])
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


def fit_line_classifier(
    name: str,
    training_frame: pd.DataFrame,
) -> LineClassifier:
    if name == "market_probability":
        return StaticProbabilityClassifier(
            name=name,
            column="market_fair_probability",
        )

    trainable = training_frame[training_frame["is_win"].notna()].copy()
    y = trainable["is_win"].to_numpy(dtype=int)
    sample_weight = trainable["sample_weight"].to_numpy(dtype=float)
    if name == "logistic":
        pipeline = Pipeline(
            [
                (
                    "features",
                    _classifier_preprocessor(trainable, scale_numeric=True),
                ),
                (
                    "model",
                    LogisticRegression(
                        C=0.5,
                        max_iter=1000,
                        random_state=42,
                    ),
                ),
            ]
        )
        pipeline.fit(trainable, y, model__sample_weight=sample_weight)
        return PipelineProbabilityClassifier(name=name, pipeline=pipeline)
    if name == "hgb_classifier":
        pipeline = Pipeline(
            [
                (
                    "features",
                    _classifier_preprocessor(trainable, scale_numeric=False),
                ),
                (
                    "model",
                    HistGradientBoostingClassifier(
                        learning_rate=0.05,
                        max_iter=180,
                        max_leaf_nodes=15,
                        min_samples_leaf=30,
                        l2_regularization=1.0,
                        random_state=42,
                    ),
                ),
            ]
        )
        pipeline.fit(trainable, y, model__sample_weight=sample_weight)
        return PipelineProbabilityClassifier(name=name, pipeline=pipeline)
    raise ValueError(f"unknown line classifier: {name}")
