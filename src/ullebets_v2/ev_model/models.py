from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ullebets_v2.ev_model.engineering import CATEGORICAL_COLUMNS


class CountModel(Protocol):
    name: str

    def predict(self, features: pd.DataFrame) -> np.ndarray: ...


@dataclass
class StaticColumnCountModel:
    name: str
    column: str

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        return np.clip(
            pd.to_numeric(features[self.column], errors="coerce")
            .fillna(0.0)
            .to_numpy(dtype=float),
            0.0,
            None,
        )


@dataclass
class PipelineCountModel:
    name: str
    pipeline: Pipeline

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        return np.clip(self.pipeline.predict(features), 0.0, None)


@dataclass
class ResidualCountModel:
    name: str
    pipeline: Pipeline
    anchor_column: str = "market_anchor_lambda"

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        anchor = pd.to_numeric(
            features[self.anchor_column],
            errors="coerce",
        ).fillna(0.0).to_numpy(dtype=float)
        residual = self.pipeline.predict(features)
        return np.clip(np.expm1(np.log1p(anchor) + residual), 0.0, None)


def _feature_columns(features: pd.DataFrame) -> tuple[list[str], list[str]]:
    categorical = [
        column
        for column in CATEGORICAL_COLUMNS
        if column in features.columns
    ]
    numeric = [
        column
        for column in features.columns
        if column not in categorical
        and pd.api.types.is_numeric_dtype(features[column])
    ]
    return numeric, categorical


def _preprocessor(
    features: pd.DataFrame,
    *,
    scale_numeric: bool,
) -> ColumnTransformer:
    numeric, categorical = _feature_columns(features)
    numeric_steps: list[tuple[str, object]] = [
        ("imputer", SimpleImputer(strategy="median")),
    ]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))
    return ColumnTransformer(
        transformers=[
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


def _hgb(*, loss: str) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss=loss,
        learning_rate=0.05,
        max_iter=180,
        max_leaf_nodes=15,
        min_samples_leaf=30,
        l2_regularization=1.0,
        random_state=42,
    )


def fit_count_candidate(
    name: str,
    features: pd.DataFrame,
    targets: np.ndarray,
    *,
    sample_weight: np.ndarray | None = None,
) -> CountModel:
    y = np.clip(np.asarray(targets, dtype=float), 0.0, None)
    fit_kwargs: dict[str, np.ndarray] = {}
    if sample_weight is not None:
        weights = np.asarray(sample_weight, dtype=float)
        if (
            weights.shape != y.shape
            or not np.isfinite(weights).all()
            or (weights < 0.0).any()
            or float(weights.sum()) <= 0.0
        ):
            raise ValueError(
                "sample_weight must match targets and contain "
                "finite non-negative values with positive total weight"
            )
        fit_kwargs["model__sample_weight"] = sample_weight
    if name == "market_anchor":
        return StaticColumnCountModel(name=name, column="market_anchor_lambda")
    if name == "historical_baseline":
        return StaticColumnCountModel(name=name, column="baseline_lambda")
    if name == "poisson_glm":
        pipeline = Pipeline(
            [
                ("features", _preprocessor(features, scale_numeric=True)),
                ("model", PoissonRegressor(alpha=0.5, max_iter=1000)),
            ]
        )
        pipeline.fit(features, y, **fit_kwargs)
        return PipelineCountModel(name=name, pipeline=pipeline)
    if name == "hgb_poisson":
        pipeline = Pipeline(
            [
                ("features", _preprocessor(features, scale_numeric=False)),
                ("model", _hgb(loss="poisson")),
            ]
        )
        pipeline.fit(features, y, **fit_kwargs)
        return PipelineCountModel(name=name, pipeline=pipeline)
    if name == "hgb_market_residual":
        anchor = pd.to_numeric(
            features["market_anchor_lambda"],
            errors="coerce",
        ).fillna(0.0).to_numpy(dtype=float)
        residual_targets = np.log1p(y) - np.log1p(np.clip(anchor, 0.0, None))
        pipeline = Pipeline(
            [
                ("features", _preprocessor(features, scale_numeric=False)),
                ("model", _hgb(loss="squared_error")),
            ]
        )
        pipeline.fit(features, residual_targets, **fit_kwargs)
        return ResidualCountModel(name=name, pipeline=pipeline)
    raise ValueError(f"unknown count model candidate: {name}")
