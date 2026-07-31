from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

from ullebets_v2.ev_model.models import fit_count_candidate


def _features(size: int = 80) -> pd.DataFrame:
    anchor = np.linspace(4.0, 12.0, size)
    return pd.DataFrame(
        {
            "market_anchor_lambda": anchor,
            "baseline_lambda": anchor + 0.5,
            "history_role_expected_10": anchor,
            "league_name_normalized": ["Premier League"] * size,
            "period": ["ALL"] * size,
            "scope": ["total"] * size,
            "stat_key": ["cornerKicks"] * size,
        }
    )


def test_market_anchor_candidate_returns_market_mean_without_fitting() -> None:
    features = _features(3)

    model = fit_count_candidate("market_anchor", features, np.array([1.0, 2.0, 3.0]))

    assert model.predict(features).tolist() == pytest.approx(
        features["market_anchor_lambda"].tolist()
    )


def test_residual_model_learns_no_adjustment_when_market_is_correct() -> None:
    features = _features()
    targets = features["market_anchor_lambda"].to_numpy()

    model = fit_count_candidate("hgb_market_residual", features, targets)
    predictions = model.predict(features.iloc[:5])

    assert predictions.tolist() == pytest.approx(targets[:5], rel=0.05)


def test_residual_model_passes_sample_weight_to_estimator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    features = _features()
    targets = features["market_anchor_lambda"].to_numpy()
    weights = np.linspace(0.1, 1.0, len(features))
    captured: dict[str, object] = {}

    def capture_fit(
        self: Pipeline,
        fit_features: pd.DataFrame,
        fit_targets: np.ndarray,
        **kwargs: object,
    ) -> Pipeline:
        captured.update(kwargs)
        return self

    monkeypatch.setattr(Pipeline, "fit", capture_fit)

    fit_count_candidate(
        "hgb_market_residual",
        features,
        targets,
        sample_weight=weights,
    )

    assert captured["model__sample_weight"] is weights


def test_count_candidate_rejects_invalid_sample_weight() -> None:
    features = _features()
    targets = features["market_anchor_lambda"].to_numpy()

    with pytest.raises(ValueError, match="sample_weight"):
        fit_count_candidate(
            "hgb_market_residual",
            features,
            targets,
            sample_weight=np.ones(len(features) - 1),
        )
