from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ullebets_v2.ev_model.market_classifier import (
    CategoricalInteractionMarketClassifier,
    StaticMarketClassifier,
    WeightedEnsembleMarketClassifier,
    build_market_classifier_frame,
    build_market_prediction_frame,
    expand_market_predictions_to_sides,
    fit_market_classifier,
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


def test_two_sided_market_is_one_training_row_with_one_target() -> None:
    markets = pd.DataFrame([_market_row()])
    features = pd.DataFrame(
        {
            "market_fair_probability_over": [0.5],
            "history_role_expected_10": [11.0],
            "stat_key": ["cornerKicks"],
        }
    )

    frame = build_market_classifier_frame(markets, features)

    assert len(frame) == 1
    assert frame.iloc[0]["is_over_win"] == 1.0
    assert frame.iloc[0]["training_weight"] == 1.0


def test_prediction_frame_does_not_require_an_outcome() -> None:
    markets = pd.DataFrame(
        [
            {
                key: value
                for key, value in _market_row().items()
                if key != "actual_value"
            }
        ]
    )
    features = pd.DataFrame(
        {
            "market_fair_probability_over": [0.5],
            "history_role_expected_10": [11.0],
            "stat_key": ["cornerKicks"],
        }
    )

    frame = build_market_prediction_frame(markets, features)

    assert len(frame) == 1
    assert "actual_value" not in frame
    assert "is_over_win" not in frame


def test_push_is_not_trainable_as_a_loss() -> None:
    markets = pd.DataFrame([_market_row(line_value=10.0, actual_value=10.0)])
    features = pd.DataFrame(
        {
            "market_fair_probability_over": [0.5],
            "stat_key": ["cornerKicks"],
        }
    )

    frame = build_market_classifier_frame(markets, features)

    assert pd.isna(frame.iloc[0]["is_over_win"])
    assert frame.iloc[0]["over_settlement_result"] == "push"
    assert frame.iloc[0]["under_settlement_result"] == "push"


def test_market_prediction_expands_to_complementary_available_sides() -> None:
    frame = build_market_classifier_frame(
        pd.DataFrame([_market_row()]),
        pd.DataFrame(
            {
                "market_fair_probability_over": [0.5],
                "stat_key": ["cornerKicks"],
            }
        ),
    )
    frame["model_name"] = "test"
    frame["predicted_over_probability"] = 0.62

    sides = expand_market_predictions_to_sides(frame)

    assert sides["direction"].tolist() == ["over", "under"]
    assert sides["predicted_win_probability"].tolist() == pytest.approx(
        [0.62, 0.38]
    )


def test_over_only_market_never_creates_under_side() -> None:
    frame = build_market_classifier_frame(
        pd.DataFrame(
            [_market_row(stat_key="shotsOnGoal", under_odds=None)]
        ),
        pd.DataFrame(
            {
                "market_fair_probability_over": [1 / 1.9],
                "stat_key": ["shotsOnGoal"],
            }
        ),
    )
    frame["model_name"] = "test"
    frame["predicted_over_probability"] = 0.62

    sides = expand_market_predictions_to_sides(frame)

    assert sides["direction"].tolist() == ["over"]


def test_empirical_bayes_classifier_returns_line_history_probability() -> None:
    frame = pd.DataFrame(
        {
            "line_history_all_posterior_over_20": [0.44, 0.61],
            "is_over_win": [0.0, 1.0],
            "training_weight": [1.0, 1.0],
        }
    )

    model = fit_market_classifier("empirical_bayes_line", frame)

    assert model.predict_probability_over(frame).tolist() == pytest.approx(
        [0.44, 0.61]
    )


def test_market_residual_model_learns_correction_to_market_probability() -> None:
    values = np.linspace(-2.0, 2.0, 240)
    frame = pd.DataFrame(
        {
            "history_edge": values,
            "market_fair_probability_over": np.full(240, 0.5),
            "stat_key": ["cornerKicks"] * 240,
            "period": ["ALL"] * 240,
            "scope": ["total"] * 240,
            "league_name_normalized": ["Premier League"] * 240,
            "is_over_win": (values > 0).astype(float),
            "training_weight": np.ones(240),
        }
    )

    model = fit_market_classifier("market_residual_hgb", frame)
    probabilities = model.predict_probability_over(frame.iloc[[0, -1]])

    assert probabilities[0] < 0.35
    assert probabilities[1] > 0.65


def test_logistic_market_accepts_explicit_regularization_strength() -> None:
    values = np.linspace(-2.0, 2.0, 120)
    frame = pd.DataFrame(
        {
            "history_edge": values,
            "market_fair_probability_over": np.full(120, 0.5),
            "stat_key": ["cornerKicks"] * 120,
            "period": ["ALL"] * 120,
            "scope": ["total"] * 120,
            "league_name_normalized": ["Premier League"] * 120,
            "is_over_win": (values > 0).astype(float),
            "training_weight": np.ones(120),
        }
    )

    model = fit_market_classifier(
        "logistic_market",
        frame,
        logistic_c=0.05,
    )

    assert model.pipeline.named_steps["model"].C == 0.05


def test_hierarchical_logistic_allows_opposite_stat_relationships() -> None:
    values = np.tile(np.linspace(-2.0, 2.0, 240), 2)
    stats = np.repeat(["cornerKicks", "shotsOnGoal"], 240)
    outcomes = np.concatenate(
        [
            (values[:240] > 0).astype(float),
            (values[240:] < 0).astype(float),
        ]
    )
    frame = pd.DataFrame(
        {
            "history_edge": values,
            "market_fair_probability_over": np.full(480, 0.5),
            "stat_key": stats,
            "period": ["ALL"] * 480,
            "scope": ["total"] * 480,
            "league_name_normalized": ["Premier League"] * 480,
            "is_over_win": outcomes,
            "training_weight": np.ones(480),
        }
    )

    model = fit_market_classifier("hierarchical_logistic_market", frame)
    test = pd.DataFrame(
        {
            "history_edge": [2.0, 2.0],
            "market_fair_probability_over": [0.5, 0.5],
            "stat_key": ["cornerKicks", "shotsOnGoal"],
            "period": ["ALL", "ALL"],
            "scope": ["total", "total"],
            "league_name_normalized": [
                "Premier League",
                "Premier League",
            ],
        }
    )
    probabilities = model.predict_probability_over(test)

    assert probabilities[0] > 0.8
    assert probabilities[1] < 0.2


def test_weighted_ensemble_combines_probabilities() -> None:
    frame = pd.DataFrame(
        {
            "v3_probability": [0.60, 0.40],
            "v4_probability": [0.80, 0.20],
        }
    )
    ensemble = WeightedEnsembleMarketClassifier(
        name="v3_v4_ensemble",
        models=(
            StaticMarketClassifier(
                name="v3",
                column="v3_probability",
            ),
            StaticMarketClassifier(
                name="v4",
                column="v4_probability",
            ),
        ),
        weights=(0.75, 0.25),
    )

    assert ensemble.predict_probability_over(
        frame
    ).tolist() == pytest.approx([0.65, 0.35])


def test_weighted_ensemble_rejects_invalid_weights() -> None:
    model = StaticMarketClassifier(
        name="v3",
        column="probability",
    )

    with pytest.raises(ValueError, match="sum to one"):
        WeightedEnsembleMarketClassifier(
            name="invalid",
            models=(model,),
            weights=(0.9,),
        )


def test_categorical_interaction_wrapper_engineers_before_scoring() -> None:
    interaction_column = (
        "category_interaction__scope__home__line_value"
    )
    model = CategoricalInteractionMarketClassifier(
        name="scope_interaction",
        model=StaticMarketClassifier(
            name="interaction_value",
            column=interaction_column,
        ),
        category_column="scope",
        source_columns=("line_value",),
        deviation_values=("home",),
    )
    frame = pd.DataFrame(
        {
            "scope": ["home", "away"],
            "line_value": [0.7, 0.4],
        }
    )

    assert model.predict_probability_over(
        frame
    ).tolist() == pytest.approx([0.7, 1e-6])
