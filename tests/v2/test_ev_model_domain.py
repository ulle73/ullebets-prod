from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ullebets_v2.ev_model.domain import (
    audit_score_domain,
    extract_categorical_training_domain,
)
from ullebets_v2.ev_model.market_classifier import (
    CategoricalInteractionMarketClassifier,
    WeightedEnsembleMarketClassifier,
)


def test_extracts_fitted_onehot_training_domain() -> None:
    frame = pd.DataFrame(
        {
            "league_name_normalized": ["Serie A", "Premier League"],
            "scope": ["home", "away"],
        }
    )
    features = ColumnTransformer(
        [
            (
                "categorical",
                Pipeline(
                    [
                        (
                            "onehot",
                            OneHotEncoder(
                                handle_unknown="ignore",
                                sparse_output=False,
                            ),
                        )
                    ]
                ),
                ["league_name_normalized", "scope"],
            )
        ]
    )
    features.fit(frame)
    artifact = SimpleNamespace(
        model=SimpleNamespace(
            pipeline=Pipeline([("features", features)])
        )
    )

    domain = extract_categorical_training_domain(artifact)

    assert domain == {
        "league_name_normalized": (
            "Premier League",
            "Serie A",
        ),
        "scope": ("away", "home"),
    }


def test_domain_audit_excludes_unknown_category() -> None:
    scores = [
        {
            "score_key": "known",
            "feature_values": {
                "league_name_normalized": "Serie A",
                "scope": "total",
            },
        },
        {
            "score_key": "unknown",
            "feature_values": {
                "league_name_normalized": "Brasileirão Série A",
                "scope": "total",
            },
        },
    ]

    eligible, report = audit_score_domain(
        scores,
        {
            "league_name_normalized": ("Serie A",),
            "scope": ("total",),
        },
    )

    assert [row["score_key"] for row in eligible] == ["known"]
    assert report["scores_in_domain"] == 1
    assert report["scores_out_of_domain"] == 1
    assert report["unknown_category_counts"] == {
        "league_name_normalized": {
            "Brasileirão Série A": 1
        }
    }


def test_ensemble_domain_is_component_intersection() -> None:
    def component(leagues: list[str]) -> SimpleNamespace:
        frame = pd.DataFrame(
            {
                "league_name_normalized": leagues,
                "scope": ["total"] * len(leagues),
            }
        )
        features = ColumnTransformer(
            [
                (
                    "categorical",
                    Pipeline(
                        [
                            (
                                "onehot",
                                OneHotEncoder(
                                    handle_unknown="ignore",
                                    sparse_output=False,
                                ),
                            )
                        ]
                    ),
                    ["league_name_normalized", "scope"],
                )
            ]
        )
        features.fit(frame)
        return SimpleNamespace(
            pipeline=Pipeline([("features", features)])
        )

    ensemble = WeightedEnsembleMarketClassifier(
        name="ensemble",
        models=(
            component(["Serie A", "Premier League"]),
            component(["Serie A", "Bundesliga"]),
        ),
        weights=(0.75, 0.25),
    )

    assert extract_categorical_training_domain(ensemble) == {
        "league_name_normalized": ("Serie A",),
        "scope": ("total",),
    }


def test_interaction_wrapper_preserves_fitted_domain() -> None:
    frame = pd.DataFrame(
        {
            "league_name_normalized": [
                "Serie A",
                "Premier League",
            ],
            "scope": ["home", "away"],
        }
    )
    features = ColumnTransformer(
        [
            (
                "categorical",
                Pipeline(
                    [
                        (
                            "onehot",
                            OneHotEncoder(
                                handle_unknown="ignore",
                                sparse_output=False,
                            ),
                        )
                    ]
                ),
                ["league_name_normalized", "scope"],
            )
        ]
    )
    features.fit(frame)
    wrapped = CategoricalInteractionMarketClassifier(
        name="scope_interaction",
        model=SimpleNamespace(
            pipeline=Pipeline([("features", features)])
        ),
        category_column="scope",
        source_columns=("line_value",),
        deviation_values=("home", "away"),
    )

    assert extract_categorical_training_domain(wrapped) == {
        "league_name_normalized": (
            "Premier League",
            "Serie A",
        ),
        "scope": ("away", "home"),
    }
