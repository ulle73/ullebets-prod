from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.evaluation import score_market_rows


def test_scoring_selects_best_positive_ev_side_and_settles_it() -> None:
    frame = pd.DataFrame(
        {
            "sample_key": ["match-1|cornerKicks|ALL|total"],
            "exposure_match_id": ["match-1"],
            "match_date": ["2026-01-01"],
            "stat_key": ["cornerKicks"],
            "period": ["ALL"],
            "scope": ["total"],
            "line_value": [10.5],
            "actual_value": [12.0],
            "over_odds": [2.0],
            "under_odds": [1.8],
        }
    )

    scored = score_market_rows(frame, predicted_means=[12.0], minimum_ev=0.0)

    assert len(scored) == 1
    assert scored.iloc[0]["direction"] == "over"
    assert scored.iloc[0]["settlement_result"] == "win"
    assert scored.iloc[0]["realized_roi_units"] == pytest.approx(1.0)


def test_scoring_does_not_create_under_bet_for_over_only_market() -> None:
    frame = pd.DataFrame(
        {
            "sample_key": ["match-1|shotsOnGoal|ALL|home"],
            "exposure_match_id": ["match-1"],
            "match_date": ["2026-01-01"],
            "stat_key": ["shotsOnGoal"],
            "period": ["ALL"],
            "scope": ["home"],
            "line_value": [5.5],
            "actual_value": [3.0],
            "over_odds": [1.9],
            "under_odds": [None],
        }
    )

    scored = score_market_rows(frame, predicted_means=[3.0], minimum_ev=-1.0)

    assert scored.iloc[0]["direction"] == "over"


def test_scoring_marks_integer_line_as_push() -> None:
    frame = pd.DataFrame(
        {
            "sample_key": ["match-1|cornerKicks|ALL|total"],
            "exposure_match_id": ["match-1"],
            "match_date": ["2026-01-01"],
            "stat_key": ["cornerKicks"],
            "period": ["ALL"],
            "scope": ["total"],
            "line_value": [10.0],
            "actual_value": [10.0],
            "over_odds": [2.0],
            "under_odds": [2.0],
        }
    )

    scored = score_market_rows(frame, predicted_means=[15.0], minimum_ev=-1.0)

    assert scored.iloc[0]["settlement_result"] == "push"
    assert scored.iloc[0]["realized_roi_units"] == 0.0


def test_scoring_can_use_row_specific_negative_binomial_dispersion() -> None:
    frame = pd.DataFrame(
        {
            "sample_key": ["match-1|cornerKicks|ALL|total"],
            "exposure_match_id": ["match-1"],
            "match_date": ["2026-01-01"],
            "stat_key": ["cornerKicks"],
            "period": ["ALL"],
            "scope": ["total"],
            "line_value": [10.5],
            "actual_value": [12.0],
            "over_odds": [2.0],
            "under_odds": [2.0],
        }
    )

    scored = score_market_rows(
        frame,
        predicted_means=[12.0],
        minimum_ev=-1.0,
        distribution="negative_binomial",
        dispersions=[3.0],
    )

    assert scored.iloc[0]["distribution"] == "negative_binomial"
    assert scored.iloc[0]["dispersion"] == 3.0
