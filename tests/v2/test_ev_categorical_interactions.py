from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.categorical_interactions import (
    add_categorical_interaction_features,
)


def test_categorical_interactions_add_reference_relative_slopes() -> None:
    frame = pd.DataFrame(
        {
            "scope": ["total", "home", "away"],
            "line_value": [10.5, 5.5, 4.5],
            "baseline_lambda": [10.0, 5.0, 4.0],
        }
    )

    result = add_categorical_interaction_features(
        frame,
        category_column="scope",
        source_columns=("line_value", "baseline_lambda"),
        deviation_values=("home", "away"),
    )

    assert result[
        "category_interaction__scope__home__line_value"
    ].tolist() == pytest.approx([0.0, 5.5, 0.0])
    assert result[
        "category_interaction__scope__away__baseline_lambda"
    ].tolist() == pytest.approx([0.0, 0.0, 4.0])


def test_categorical_interactions_validate_contract() -> None:
    frame = pd.DataFrame(
        {
            "scope": ["total"],
            "label": ["not numeric"],
        }
    )

    with pytest.raises(ValueError, match="category column"):
        add_categorical_interaction_features(
            frame,
            category_column="period",
            source_columns=("label",),
            deviation_values=("1ST",),
        )
    with pytest.raises(ValueError, match="must be numeric"):
        add_categorical_interaction_features(
            frame,
            category_column="scope",
            source_columns=("label",),
            deviation_values=("home",),
        )
