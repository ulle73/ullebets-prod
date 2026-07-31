from __future__ import annotations

import numpy as np
import pytest

from ullebets_v2.ev_model.calibration import BetaProbabilityCalibrator


def test_beta_calibration_corrects_repeated_overconfidence() -> None:
    raw_probabilities = np.full(100, 0.80)
    outcomes = np.array([0.0, 1.0] * 50)
    calibrator = BetaProbabilityCalibrator(min_samples=20)

    calibrator.fit(raw_probabilities, outcomes)
    calibrated = calibrator.predict(np.array([0.80]))

    assert calibrated[0] == pytest.approx(0.50, abs=0.03)


def test_beta_calibration_stays_identity_without_enough_history() -> None:
    calibrator = BetaProbabilityCalibrator(min_samples=20)

    calibrator.fit(np.array([0.8, 0.7]), np.array([1.0, 0.0]))

    assert calibrator.predict(np.array([0.8]))[0] == pytest.approx(0.8)
