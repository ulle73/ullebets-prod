from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from ullebets_v2.ev_model.line_classifier import (
    build_line_classifier_frame,
    fit_line_classifier,
)


def _market_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "sample_key": "match-1|cornerKicks|ALL|total",
        "exposure_match_id": "match-1",
        "match_date": "2026-01-01",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "total",
        "line_value": 10.5,
        "actual_value": 12.0,
        "over_odds": 1.9,
        "under_odds": 1.9,
    }
    row.update(overrides)
    return row


def test_two_sided_market_creates_complementary_line_rows() -> None:
    markets = pd.DataFrame([_market_row()])
    features = pd.DataFrame(
        {
            "market_fair_probability_over": [0.5],
            "history_role_expected_10": [11.0],
            "stat_key": ["cornerKicks"],
        }
    )

    lines = build_line_classifier_frame(markets, features)

    assert lines["direction"].tolist() == ["over", "under"]
    assert lines["is_win"].tolist() == [1.0, 0.0]
    assert lines["sample_weight"].tolist() == [0.5, 0.5]


def test_over_only_market_creates_no_synthetic_under_row() -> None:
    markets = pd.DataFrame(
        [_market_row(stat_key="shotsOnGoal", scope="home", under_odds=None)]
    )
    features = pd.DataFrame(
        {
            "market_fair_probability_over": [1 / 1.9],
            "stat_key": ["shotsOnGoal"],
        }
    )

    lines = build_line_classifier_frame(markets, features)

    assert lines["direction"].tolist() == ["over"]
    assert lines["sample_weight"].tolist() == [1.0]


def test_push_row_is_not_trainable_as_a_loss() -> None:
    markets = pd.DataFrame([_market_row(line_value=10.0, actual_value=10.0)])
    features = pd.DataFrame(
        {
            "market_fair_probability_over": [0.5],
            "stat_key": ["cornerKicks"],
        }
    )

    lines = build_line_classifier_frame(markets, features)

    assert lines["is_win"].isna().all()


def test_market_probability_classifier_returns_market_feature() -> None:
    frame = pd.DataFrame(
        {
            "market_fair_probability": [0.42, 0.58],
            "is_win": [0.0, 1.0],
            "sample_weight": [1.0, 1.0],
        }
    )

    model = fit_line_classifier("market_probability", frame)

    assert model.predict_probability(frame).tolist() == pytest.approx([0.42, 0.58])


def test_logistic_classifier_learns_directional_feature() -> None:
    values = np.linspace(-2.0, 2.0, 200)
    frame = pd.DataFrame(
        {
            "history_edge": values,
            "market_fair_probability": np.full(200, 0.5),
            "direction": ["over"] * 200,
            "stat_key": ["cornerKicks"] * 200,
            "period": ["ALL"] * 200,
            "scope": ["total"] * 200,
            "league_name_normalized": ["Premier League"] * 200,
            "is_win": (values > 0).astype(float),
            "sample_weight": np.ones(200),
        }
    )

    model = fit_line_classifier("logistic", frame)
    probabilities = model.predict_probability(frame.iloc[[0, -1]])

    assert probabilities[0] < 0.2
    assert probabilities[1] > 0.8
