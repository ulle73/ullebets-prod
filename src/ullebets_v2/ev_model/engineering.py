from __future__ import annotations

from functools import lru_cache
import math
from typing import Any

import pandas as pd

from ullebets_v2.ev_model.market import (
    fair_over_probability,
    infer_poisson_mean,
)


TEAM_STATS_KEYS = {
    "cornerKicks": "cornerKicks",
    "shotsOnGoal": "shotsOnGoal",
    "totalShots": "totalShotsOnGoal",
}

CONTEXT_STAT_KEYS = (
    "ballPossession",
    "bigChanceCreated",
    "cornerKicks",
    "expectedGoals",
    "fouls",
    "shotsOnGoal",
    "totalShotsOnGoal",
    "yellowCards",
)

CATEGORICAL_COLUMNS = (
    "league_name_normalized",
    "period",
    "scope",
    "stat_key",
)


def _number(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return math.nan
    return numeric if math.isfinite(numeric) else math.nan


@lru_cache(maxsize=4096)
def _cached_anchor(line: float, over_odds: float, under_odds: float | None) -> tuple[float, float]:
    probability = fair_over_probability(
        over_odds=over_odds,
        under_odds=under_odds,
    )
    mean = infer_poisson_mean(
        line=line,
        win_probability=probability,
        direction="over",
    )
    return probability, mean


def _market_features(row: pd.Series) -> dict[str, float]:
    line = _number(row.get("line_value"))
    over_odds = _number(row.get("over_odds"))
    under_odds_value = _number(row.get("under_odds"))
    under_odds = under_odds_value if math.isfinite(under_odds_value) else None
    fair_probability = math.nan
    anchor_mean = math.nan
    if math.isfinite(line) and math.isfinite(over_odds) and over_odds > 1.0:
        fair_probability, anchor_mean = _cached_anchor(
            round(line, 6),
            round(over_odds, 6),
            round(under_odds, 6) if under_odds is not None else None,
        )

    lead_minutes = _number(row.get("latest_snapshot_minutes_before_kickoff"))
    return {
        "line_value": line,
        "over_odds": over_odds,
        "under_odds": under_odds_value,
        "market_fair_probability_over": fair_probability,
        "market_anchor_lambda": anchor_mean,
        "market_overround": (
            (1.0 / over_odds) + (1.0 / under_odds) - 1.0
            if under_odds is not None and over_odds > 1.0 and under_odds > 1.0
            else math.nan
        ),
        "baseline_lambda": _number(row.get("baseline_lambda")),
        "snapshot_lead_hours": lead_minutes / 60.0 if math.isfinite(lead_minutes) else math.nan,
    }


def _history_value(
    row: pd.Series,
    *,
    team: str,
    stat_key: str,
    orientation: str,
    mode: str,
    window: int,
) -> float:
    return _number(
        row.get(f"{team}__{stat_key}__team_{orientation}_{mode}_avg_{window}")
    )


def _history_features(
    row: pd.Series,
    *,
    mode: str,
    window: int,
) -> dict[str, float]:
    source_key = TEAM_STATS_KEYS[str(row["stat_key"])]
    scope = str(row["scope"])
    home_for = _history_value(
        row,
        team="home",
        stat_key=source_key,
        orientation="for",
        mode=mode,
        window=window,
    )
    away_for = _history_value(
        row,
        team="away",
        stat_key=source_key,
        orientation="for",
        mode=mode,
        window=window,
    )
    home_against = _history_value(
        row,
        team="home",
        stat_key=source_key,
        orientation="against",
        mode=mode,
        window=window,
    )
    away_against = _history_value(
        row,
        team="away",
        stat_key=source_key,
        orientation="against",
        mode=mode,
        window=window,
    )

    if scope == "home":
        attack = home_for
        defense = away_against
        expected = (attack + defense) / 2.0
    elif scope == "away":
        attack = away_for
        defense = home_against
        expected = (attack + defense) / 2.0
    else:
        attack = home_for + away_for
        defense = home_against + away_against
        expected = ((home_for + away_against) / 2.0) + ((away_for + home_against) / 2.0)

    prefix = f"history_{mode}"
    return {
        f"{prefix}_attack_{window}": attack,
        f"{prefix}_defense_{window}": defense,
        f"{prefix}_expected_{window}": expected,
    }


def build_compact_model_features(
    frame: pd.DataFrame,
    *,
    windows: tuple[int, ...] = (3, 5, 10, 20),
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, source_row in frame.iterrows():
        row: dict[str, Any] = {
            column: source_row.get(column)
            for column in CATEGORICAL_COLUMNS
            if column in frame.columns
        }
        row.update(_market_features(source_row))
        for mode in ("role", "all"):
            for window in windows:
                row.update(
                    _history_features(
                        source_row,
                        mode=mode,
                        window=window,
                    )
                )
        for mode in ("role", "all"):
            short_key = f"history_{mode}_expected_3"
            long_key = f"history_{mode}_expected_10"
            if short_key in row and long_key in row:
                row[f"history_{mode}_trend_3_10"] = row[short_key] - row[long_key]
        rows.append(row)
    return pd.DataFrame(rows, index=frame.index)


def _snapshot_horizon_bucket(lead_hours: float) -> str:
    if not math.isfinite(lead_hours) or lead_hours < 0.0:
        return "UNKNOWN"
    boundaries = (
        (0.25, "LT_15M"),
        (1.0, "M15_TO_1H"),
        (3.0, "H1_TO_3H"),
        (6.0, "H3_TO_6H"),
        (12.0, "H6_TO_12H"),
        (18.0, "H12_TO_18H"),
        (36.0, "H18_TO_36H"),
        (60.0, "H36_TO_60H"),
        (84.0, "H60_TO_84H"),
        (168.0, "H84_TO_168H"),
    )
    return next(
        (
            label
            for upper_bound, label in boundaries
            if lead_hours < upper_bound
        ),
        "GTE_168H",
    )


def add_snapshot_horizon_features(
    features: pd.DataFrame,
) -> pd.DataFrame:
    enriched = features.copy()
    lead_hours = pd.to_numeric(
        enriched["snapshot_lead_hours"],
        errors="coerce",
    )
    enriched["snapshot_horizon_bucket"] = lead_hours.map(
        _snapshot_horizon_bucket
    )
    enriched["snapshot_horizon_log1p_hours"] = lead_hours.map(
        lambda value: (
            math.log1p(max(float(value), 0.0))
            if pd.notna(value)
            else math.nan
        )
    )
    return enriched


def build_horizon_model_features(
    frame: pd.DataFrame,
    *,
    windows: tuple[int, ...] = (3, 5, 10, 20),
) -> pd.DataFrame:
    return add_snapshot_horizon_features(
        build_compact_model_features(
            frame,
            windows=windows,
        )
    )


def build_context_model_features(
    frame: pd.DataFrame,
    *,
    windows: tuple[int, ...] = (5, 10),
) -> pd.DataFrame:
    features = build_compact_model_features(frame)
    context_rows: list[dict[str, float]] = []
    for index, source_row in frame.iterrows():
        context: dict[str, float] = {}
        for stat_key in CONTEXT_STAT_KEYS:
            for mode in ("all", "role"):
                for team in ("home", "away"):
                    for orientation in ("for", "against"):
                        for window in windows:
                            column = (
                                f"context_{stat_key}_{mode}_{team}_"
                                f"{orientation}_{window}"
                            )
                            context[column] = _number(
                                source_row.get(
                                    f"{team}__{stat_key}__team_{orientation}_"
                                    f"{mode}_avg_{window}"
                                )
                            )

        line = _number(source_row.get("line_value"))
        market_anchor = _number(features.loc[index, "market_anchor_lambda"])
        for mode in ("role", "all"):
            for window in (5, 10):
                expected = _number(
                    features.loc[index, f"history_{mode}_expected_{window}"]
                )
                context[f"history_{mode}_expected_minus_line_{window}"] = (
                    expected - line
                )
                context[
                    f"history_{mode}_expected_minus_market_{window}"
                ] = expected - market_anchor

        probability = _number(
            features.loc[index, "market_fair_probability_over"]
        )
        context["market_logit_over"] = (
            math.log(probability / (1.0 - probability))
            if 0.0 < probability < 1.0
            else math.nan
        )
        context_rows.append(context)
    context_frame = pd.DataFrame(context_rows, index=features.index)
    return pd.concat([features, context_frame], axis=1)
