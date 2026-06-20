from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


@dataclass
class PoissonCountModel:
    pipeline: Pipeline
    feature_columns: list[str]
    categorical_columns: list[str]

    def predict_lambda(self, frame: pd.DataFrame):
        return self.pipeline.predict(frame[self.feature_columns + self.categorical_columns])


def train_poisson_model(
    frame: pd.DataFrame,
    *,
    feature_columns: list[str],
    categorical_columns: list[str],
    alpha: float = 0.5,
) -> PoissonCountModel:
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, feature_columns),
            ("cat", categorical_transformer, categorical_columns),
        ]
    )
    pipeline = Pipeline(
        steps=[
            ("prep", preprocessor),
            ("model", PoissonRegressor(alpha=alpha, max_iter=500)),
        ]
    )
    y = frame["actual_value"].clip(lower=0)
    pipeline.fit(frame[feature_columns + categorical_columns], y)
    return PoissonCountModel(
        pipeline=pipeline,
        feature_columns=feature_columns,
        categorical_columns=categorical_columns,
    )
