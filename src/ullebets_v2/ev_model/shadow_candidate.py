from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.market_classifier import (
    MarketClassifier,
    expand_market_predictions_to_sides,
    fit_market_classifier,
)
from ullebets_v2.ev_model.market_walk_forward import (
    select_market_classifier_bets,
)


TRAIN_WINDOW_DAYS = 90
RECENCY_HALF_LIFE_DAYS = 45.0
MINIMUM_EV = 0.075


@dataclass
class ShadowCandidateBundle:
    model: MarketClassifier
    training_start: str
    training_end: str
    training_rows: int
    train_window_days: int = TRAIN_WINDOW_DAYS
    recency_half_life_days: float = RECENCY_HALF_LIFE_DAYS
    minimum_ev: float = MINIMUM_EV


def train_shadow_candidate(
    market_frame: pd.DataFrame,
    *,
    cutoff_date: date | str,
) -> ShadowCandidateBundle:
    cutoff = pd.Timestamp(cutoff_date).normalize()
    training_start = cutoff - pd.Timedelta(days=TRAIN_WINDOW_DAYS)
    training_end = cutoff - pd.Timedelta(days=1)
    frame = market_frame.copy()
    frame["_match_day"] = pd.to_datetime(
        frame["match_date"],
        errors="raise",
    ).dt.normalize()
    training = frame[
        frame["_match_day"].ge(training_start)
        & frame["_match_day"].lt(cutoff)
        & frame["is_over_win"].notna()
    ].copy()
    if training.empty:
        raise ValueError("no eligible rows in shadow candidate training window")
    age_days = (
        cutoff - training["_match_day"]
    ).dt.total_seconds() / 86_400.0
    training["training_weight"] = np.power(
        0.5,
        age_days / RECENCY_HALF_LIFE_DAYS,
    )
    model = fit_market_classifier("logistic_market", training)
    return ShadowCandidateBundle(
        model=model,
        training_start=training_start.date().isoformat(),
        training_end=training_end.date().isoformat(),
        training_rows=len(training),
    )


def score_shadow_candidate_sides(
    bundle: ShadowCandidateBundle,
    market_frame: pd.DataFrame,
) -> pd.DataFrame:
    predictions = market_frame.copy()
    required_timing = {"odds_snapshot_time", "match_start_time"}
    missing_timing = sorted(required_timing.difference(predictions.columns))
    if missing_timing:
        raise ValueError(
            f"shadow scoring requires timing columns: {missing_timing}"
        )
    snapshot_time = pd.to_datetime(
        predictions["odds_snapshot_time"],
        errors="coerce",
        utc=True,
    )
    match_start_time = pd.to_datetime(
        predictions["match_start_time"],
        errors="coerce",
        utc=True,
    )
    if snapshot_time.isna().any() or match_start_time.isna().any():
        raise ValueError("shadow scoring requires valid prematch timing")
    if snapshot_time.ge(match_start_time).any():
        raise ValueError(
            "odds snapshot must be strictly before match start"
        )
    predictions["model_name"] = "shadow_logistic_market"
    predictions["predicted_over_probability"] = (
        bundle.model.predict_probability_over(predictions)
    )
    return expand_market_predictions_to_sides(predictions)


def score_shadow_candidate(
    bundle: ShadowCandidateBundle,
    market_frame: pd.DataFrame,
    *,
    minimum_ev: float | None = None,
    maximum_ev: float | None = None,
) -> pd.DataFrame:
    sides = score_shadow_candidate_sides(bundle, market_frame)
    return select_market_classifier_bets(
        sides,
        minimum_ev=(
            bundle.minimum_ev if minimum_ev is None else minimum_ev
        ),
        maximum_ev=maximum_ev,
    )
