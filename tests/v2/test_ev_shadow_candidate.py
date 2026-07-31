from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import joblib
import pandas as pd
import pytest

from ullebets_v2.ev_model.shadow_candidate import (
    score_shadow_candidate,
    score_shadow_candidate_sides,
    train_shadow_candidate,
)


def test_shadow_candidate_trains_on_prior_90_days_and_scores_one_side(
    tmp_path: Path,
) -> None:
    start = date(2026, 1, 1)
    rows = []
    for offset in range(110):
        rows.append(
            {
                "sample_key": f"m-{offset}|cornerKicks|ALL|total",
                "exposure_match_id": f"m-{offset}",
                "match_date": (start + timedelta(days=offset)).isoformat(),
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 10.5,
                "over_odds": 2.0,
                "under_odds": 2.0,
                "market_fair_probability_over": 0.5,
                "history_role_expected_10": 12.0 if offset % 2 else 9.0,
                "is_over_win": float(offset % 2 == 1),
                "training_weight": 1.0,
            }
        )
    frame = pd.DataFrame(rows)
    cutoff = date(2026, 4, 21)

    bundle = train_shadow_candidate(frame, cutoff_date=cutoff)
    future = frame.tail(1).drop(
        columns=["is_over_win", "training_weight"]
    )
    future["match_date"] = "2026-04-21"
    future["odds_snapshot_time"] = "2026-04-21T12:00:00Z"
    future["match_start_time"] = "2026-04-21T14:00:00Z"
    selections = score_shadow_candidate(
        bundle,
        future,
        minimum_ev=-1.0,
    )
    artifact = tmp_path / "candidate.joblib"
    joblib.dump(bundle, artifact)
    restored = joblib.load(artifact)
    restored_selections = score_shadow_candidate(
        restored,
        future,
        minimum_ev=-1.0,
    )

    assert bundle.training_start == "2026-01-21"
    assert bundle.training_end == "2026-04-20"
    assert bundle.training_rows == 90
    assert len(selections) == 1
    assert restored_selections["predicted_win_probability"].tolist() == (
        selections["predicted_win_probability"].tolist()
    )


def test_shadow_candidate_sides_preserves_every_available_side() -> None:
    class StaticModel:
        def predict_probability_over(self, frame: pd.DataFrame):
            return [0.6] * len(frame)

    from ullebets_v2.ev_model.shadow_candidate import ShadowCandidateBundle

    bundle = ShadowCandidateBundle(
        model=StaticModel(),
        training_start="2026-01-01",
        training_end="2026-03-31",
        training_rows=100,
    )
    frame = pd.DataFrame(
        [
            {
                "sample_key": "m1|cornerKicks|ALL|total",
                "exposure_match_id": "m1",
                "match_date": "2026-04-01",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 10.5,
                "over_odds": 1.9,
                "under_odds": 1.9,
                "odds_snapshot_time": "2026-04-01T12:00:00Z",
                "match_start_time": "2026-04-01T14:00:00Z",
            }
        ]
    )

    sides = score_shadow_candidate_sides(bundle, frame)

    assert set(sides["direction"]) == {"over", "under"}
    assert sides["expected_roi_units"].notna().all()


def test_shadow_candidate_rejects_odds_at_or_after_kickoff() -> None:
    class StaticModel:
        def predict_probability_over(self, frame: pd.DataFrame):
            return [0.6] * len(frame)

    from ullebets_v2.ev_model.shadow_candidate import ShadowCandidateBundle

    bundle = ShadowCandidateBundle(
        model=StaticModel(),
        training_start="2026-01-01",
        training_end="2026-03-31",
        training_rows=100,
    )
    frame = pd.DataFrame(
        [
            {
                "sample_key": "m1|cornerKicks|ALL|total",
                "exposure_match_id": "m1",
                "match_date": "2026-04-01",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 10.5,
                "over_odds": 1.9,
                "under_odds": 1.9,
                "odds_snapshot_time": "2026-04-01T15:00:00Z",
                "match_start_time": "2026-04-01T14:00:00Z",
            }
        ]
    )

    with pytest.raises(ValueError, match="strictly before"):
        score_shadow_candidate(bundle, frame)


def test_shadow_candidate_applies_explicit_maximum_ev_policy() -> None:
    class StaticModel:
        def predict_probability_over(self, frame: pd.DataFrame):
            return [0.7] * len(frame)

    from ullebets_v2.ev_model.shadow_candidate import ShadowCandidateBundle

    bundle = ShadowCandidateBundle(
        model=StaticModel(),
        training_start="2026-01-01",
        training_end="2026-03-31",
        training_rows=100,
    )
    frame = pd.DataFrame(
        [
            {
                "sample_key": "m1|cornerKicks|ALL|total",
                "exposure_match_id": "m1",
                "match_date": "2026-04-01",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 10.5,
                "over_odds": 2.0,
                "under_odds": 2.0,
                "odds_snapshot_time": "2026-04-01T12:00:00Z",
                "match_start_time": "2026-04-01T14:00:00Z",
            }
        ]
    )

    selections = score_shadow_candidate(
        bundle,
        frame,
        minimum_ev=0.075,
        maximum_ev=0.25,
    )

    assert selections.empty
