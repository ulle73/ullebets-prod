from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.stat_interactions import (
    add_stat_interaction_features,
)


def test_stat_interactions_add_regularizable_deviation_features() -> None:
    frame = pd.DataFrame(
        {
            "stat_key": [
                "cornerKicks",
                "shotsOnGoal",
                "totalShots",
            ],
            "market_fair_probability_over": [0.4, 0.5, 0.6],
            "history_role_expected_10": [8.0, 4.0, 11.0],
        }
    )

    result = add_stat_interaction_features(
        frame,
        source_columns=(
            "market_fair_probability_over",
            "history_role_expected_10",
        ),
        deviation_stat_keys=("shotsOnGoal", "totalShots"),
    )

    assert result[
        "stat_interaction__shotsOnGoal__"
        "market_fair_probability_over"
    ].tolist() == pytest.approx([0.0, 0.5, 0.0])
    assert result[
        "stat_interaction__totalShots__"
        "history_role_expected_10"
    ].tolist() == pytest.approx([0.0, 0.0, 11.0])
    assert result["market_fair_probability_over"].tolist() == (
        frame["market_fair_probability_over"].tolist()
    )


def test_stat_interactions_reject_missing_or_non_numeric_sources() -> None:
    frame = pd.DataFrame(
        {
            "stat_key": ["cornerKicks"],
            "label": ["not numeric"],
        }
    )

    with pytest.raises(ValueError, match="missing source"):
        add_stat_interaction_features(
            frame,
            source_columns=("unknown",),
        )
    with pytest.raises(ValueError, match="must be numeric"):
        add_stat_interaction_features(
            frame,
            source_columns=("label",),
        )
