from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.linear_model import LogisticRegression


def _beta_features(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1.0 - 1e-6)
    return np.column_stack((np.log(clipped), np.log1p(-clipped)))


@dataclass
class BetaProbabilityCalibrator:
    min_samples: int = 100
    model: LogisticRegression | None = field(default=None, init=False)

    def fit(
        self,
        raw_probabilities: np.ndarray,
        outcomes: np.ndarray,
    ) -> "BetaProbabilityCalibrator":
        probabilities = np.asarray(raw_probabilities, dtype=float)
        targets = np.asarray(outcomes, dtype=float)
        valid = np.isfinite(probabilities) & np.isfinite(targets)
        probabilities = probabilities[valid]
        targets = targets[valid]
        if len(probabilities) < self.min_samples or len(np.unique(targets)) < 2:
            self.model = None
            return self
        self.model = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
        self.model.fit(_beta_features(probabilities), targets.astype(int))
        return self

    def predict(self, raw_probabilities: np.ndarray) -> np.ndarray:
        probabilities = np.clip(
            np.asarray(raw_probabilities, dtype=float),
            1e-6,
            1.0 - 1e-6,
        )
        if self.model is None:
            return probabilities
        return self.model.predict_proba(_beta_features(probabilities))[:, 1]
