from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from ullebets_v2.ev_model.market_calibration import (
    sequentially_calibrate_market_predictions,
)


def test_market_calibration_preserves_complementary_probabilities() -> None:
    rows = []
    for offset in range(140):
        match_date = date(2026, 1, 1) + timedelta(days=offset // 4)
        test_start = "2026-01-01" if offset < 120 else "2026-02-15"
        is_over_win = float(offset % 2 == 0)
        for direction in ("over", "under"):
            rows.append(
                {
                    "sample_key": f"match-{offset}|cornerKicks|ALL|total",
                    "side_key": (
                        f"match-{offset}|cornerKicks|ALL|total|{direction}"
                    ),
                    "exposure_match_id": f"match-{offset}",
                    "match_date": match_date.isoformat(),
                    "test_start": test_start,
                    "model_name": "logistic_market",
                    "stat_key": "cornerKicks",
                    "period": "ALL",
                    "scope": "total",
                    "direction": direction,
                    "offered_odds": 1.9,
                    "predicted_over_probability": 0.6,
                    "predicted_win_probability": (
                        0.6 if direction == "over" else 0.4
                    ),
                    "is_over_win": is_over_win,
                    "settlement_result": (
                        "win"
                        if (direction == "over") == bool(is_over_win)
                        else "loss"
                    ),
                    "realized_roi_units": 0.9,
                }
            )

    calibrated = sequentially_calibrate_market_predictions(
        pd.DataFrame(rows),
        minimum_history_markets=100,
        minimum_group_markets=100,
    )
    eligible = calibrated[
        calibrated["test_start"].eq("2026-02-15")
        & calibrated["calibration_eligible"].eq(True)
    ]
    pivot = eligible.pivot(
        index=["model_name", "sample_key"],
        columns="direction",
        values="calibrated_win_probability",
    )

    assert not eligible.empty
    assert (pivot["over"] + pivot["under"]).tolist() == pytest.approx(
        [1.0] * len(pivot)
    )
