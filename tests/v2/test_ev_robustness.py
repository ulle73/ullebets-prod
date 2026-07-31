from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.robustness import build_robustness_report


def test_robustness_report_applies_policy_and_reports_calibration() -> None:
    predictions = pd.DataFrame(
        [
            {
                "model_name": "logistic_market",
                "sample_key": f"sample-{index}",
                "exposure_match_id": f"match-{index}",
                "match_start_time": f"2026-01-0{index + 1}T12:00:00Z",
                "league_name_normalized": "Test League",
                "direction": "over",
                "expected_roi_units": edge,
                "predicted_win_probability": probability,
                "market_fair_probability_over": 0.5,
                "offered_odds": 2.0,
                "settlement_result": result,
                "realized_roi_units": pnl,
            }
            for index, (edge, probability, result, pnl) in enumerate(
                [
                    (0.08, 0.54, "win", 1.0),
                    (0.12, 0.56, "loss", -1.0),
                    (0.20, 0.60, "win", 1.0),
                    (0.30, 0.70, "loss", -1.0),
                ]
            )
        ]
    )

    report = build_robustness_report(
        predictions,
        minimum_ev=0.075,
        maximum_ev=0.25,
        threshold_grid=(0.075,),
        odds_haircuts=(0.0, 0.05),
    )

    assert report["performance"]["bets"] == 3
    assert report["performance"]["roi_pct"] == pytest.approx(100 / 3)
    assert report["policy"]["rejected_above_maximum_ev"] == 1
    assert report["calibration"]["actual_win_rate"] == pytest.approx(2 / 3)
    assert report["calibration"]["mean_market_probability"] == 0.5
    assert report["threshold_sensitivity"][0]["bets"] == 3
    assert report["odds_haircut_sensitivity"][1]["roi_pct"] < (
        report["odds_haircut_sensitivity"][0]["roi_pct"]
    )
