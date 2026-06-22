from __future__ import annotations

from statistics import median
from typing import Any


DATASET_SPLITS = ("train", "val", "test")
FEATURE_MODES = ("strict", "extended")
FORMULA_FEATURE_KEYS = (
    "evPctMultifactor",
    "evPctUniversalOptimized",
    "evPctOptaCombined",
    "evPctLeagueAvg",
    "evPctOptaRating",
    "evPctBase",
    "evPctPoisson",
)
EXTRA_PROFILE_KEYS = (
    "ballPossession",
    "passes",
    "accuratePasses",
    "finalThirdEntries",
    "touchesInOppBox",
    "expectedGoals",
    "bigChanceCreated",
    "bigChanceMissed",
    "bigChanceScored",
    "shotsOffGoal",
    "totalShotsInsideBox",
    "totalShotsOutsideBox",
    "accurateCross",
    "accurateLongBalls",
    "ballRecovery",
    "interceptionWon",
    "dispossessed",
    "blockedScoringAttempt",
    "duelWonPercent",
    "groundDuelsPercentage",
    "aerialDuelsPercentage",
    "cleanSheets",
    "goalsConceded",
    "tackles",
    "clearances",
    "dribbles",
    "dribblesCompleted",
    "touches",
    "duels",
    "groundDuels",
    "aerialDuels",
)


def build_dataset_key(stat_key: str, scope: str, period: str) -> str:
    return f"{stat_key}_{scope}_{period}"


def build_feature_names(feature_mode: str) -> list[str]:
    names = [
        "market_line",
        "market_over_odds",
        "market_implied_over",
        "market_under_odds",
        "market_implied_under",
        "market_margin",
        "quality_home_opta_rank",
        "quality_home_opta_rating",
        "quality_away_opta_rank",
        "quality_away_opta_rating",
        "quality_opta_rank_diff",
        "quality_opta_rating_diff",
        "wma_home_for_recent",
        "wma_home_for_medium",
        "wma_home_for_long",
        "wma_away_for_recent",
        "wma_away_for_medium",
        "wma_away_for_long",
        "wma_home_against_recent",
        "wma_home_against_medium",
        "wma_home_against_long",
        "wma_away_against_recent",
        "wma_away_against_medium",
        "wma_away_against_long",
        *[f"formula_{key}" for key in FORMULA_FEATURE_KEYS],
        "consensus_count",
        "consensus_mean",
        "consensus_std",
        "consensus_range",
        "consensus_max",
        "consensus_min",
        "consensus_median",
        "flag_no_odds",
        "flag_supervised",
        "flag_has_formulas",
        "flag_scope_home",
        "flag_scope_away",
        "flag_scope_total",
        "flag_period_all",
        "flag_period_1st",
        "flag_period_2nd",
    ]
    if feature_mode == "extended":
        names.extend(
            [
                "profile_home_value",
                "profile_home_rank",
                "profile_away_value",
                "profile_away_rank",
                "profile_home_rank_for",
                "profile_home_rank_against",
                "profile_away_rank_for",
                "profile_away_rank_against",
                "profile_matchup_score",
                "profile_home_score_first_pct",
                "profile_away_score_first_pct",
                "profile_score_first_diff",
                "profile_home_shots_per_min_leading",
                "profile_home_shots_per_min_trailing",
                "profile_home_shots_per_min_tied",
                "profile_away_shots_per_min_leading",
                "profile_away_shots_per_min_trailing",
                "profile_away_shots_per_min_tied",
                "profile_home_shots_per_ten",
                "profile_away_shots_per_ten",
            ]
        )
        for key in EXTRA_PROFILE_KEYS:
            names.extend(
                [
                    f"profile_extra_home_for_{key}",
                    f"profile_extra_away_for_{key}",
                    f"profile_extra_home_against_{key}",
                    f"profile_extra_away_against_{key}",
                ]
            )
    return names


def _to_number(value: Any, fallback: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback
    return numeric if numeric == numeric else fallback


def _std_dev(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return variance ** 0.5


def _get_extra_value(profile: dict[str, Any], direction: str, key: str) -> float:
    if direction == "for":
        candidate = profile.get("extraFor", {}).get(key)
    else:
        candidate = profile.get("extraAgainst", {}).get(key)
    if isinstance(candidate, dict):
        return _to_number(candidate.get("ALL", {}).get("value", candidate.get("value", 0)))
    return _to_number(candidate)


def build_sample_bundle(base_context: dict[str, Any], feature_mode: str) -> dict[str, Any]:
    stat_key = str(base_context["statKey"])
    scope = str(base_context["scope"])
    period = str(base_context["period"])
    target = _to_number(base_context.get("target"))
    market = base_context.get("market", {})
    teams = base_context.get("teams", {})
    home = teams.get("home", {})
    away = teams.get("away", {})
    home_profile = home.get("profile", {})
    away_profile = away.get("profile", {})
    formula_predictions = dict(base_context.get("formulaPredictions", {}))
    metadata = dict(base_context.get("metadata", {}))

    over_odds = _to_number(market.get("overOdds", market.get("odds")))
    under_odds = _to_number(market.get("underOdds"))
    implied_over = 1 / over_odds if over_odds > 0 else 0.0
    implied_under = 1 / under_odds if under_odds > 0 else 0.0
    margin = implied_over + implied_under - 1 if implied_over > 0 and implied_under > 0 else 0.0

    numeric_formula_values = [_to_number(value) for value in formula_predictions.values()]
    numeric_formula_values = [value for value in numeric_formula_values if value == value]
    consensus_mean = sum(numeric_formula_values) / len(numeric_formula_values) if numeric_formula_values else 0.0
    consensus_std = _std_dev(numeric_formula_values)
    consensus_range = max(numeric_formula_values) - min(numeric_formula_values) if numeric_formula_values else 0.0
    consensus_max = max(numeric_formula_values) if numeric_formula_values else 0.0
    consensus_min = min(numeric_formula_values) if numeric_formula_values else 0.0
    consensus_median = float(median(numeric_formula_values)) if numeric_formula_values else 0.0

    raw_features = [
        _to_number(market.get("line")),
        over_odds,
        implied_over,
        under_odds,
        implied_under,
        margin,
        _to_number(home.get("optaRank"), 100.0),
        _to_number(home.get("optaRating"), 80.0),
        _to_number(away.get("optaRank"), 100.0),
        _to_number(away.get("optaRating"), 80.0),
        _to_number(home.get("optaRank"), 100.0) - _to_number(away.get("optaRank"), 100.0),
        _to_number(home.get("optaRating"), 80.0) - _to_number(away.get("optaRating"), 80.0),
        _to_number(home.get("wmaFor", {}).get("recent")),
        _to_number(home.get("wmaFor", {}).get("medium")),
        _to_number(home.get("wmaFor", {}).get("long")),
        _to_number(away.get("wmaFor", {}).get("recent")),
        _to_number(away.get("wmaFor", {}).get("medium")),
        _to_number(away.get("wmaFor", {}).get("long")),
        _to_number(home.get("wmaAgainst", {}).get("recent")),
        _to_number(home.get("wmaAgainst", {}).get("medium")),
        _to_number(home.get("wmaAgainst", {}).get("long")),
        _to_number(away.get("wmaAgainst", {}).get("recent")),
        _to_number(away.get("wmaAgainst", {}).get("medium")),
        _to_number(away.get("wmaAgainst", {}).get("long")),
        *[_to_number(formula_predictions.get(key)) for key in FORMULA_FEATURE_KEYS],
        float(len(numeric_formula_values)),
        consensus_mean,
        consensus_std,
        consensus_range,
        consensus_max,
        consensus_min,
        consensus_median,
        0.0 if over_odds > 0 else 1.0,
        1.0 if metadata.get("supervised") else 0.0,
        1.0 if numeric_formula_values else 0.0,
        1.0 if scope == "home" else 0.0,
        1.0 if scope == "away" else 0.0,
        1.0 if scope == "total" else 0.0,
        1.0 if period == "ALL" else 0.0,
        1.0 if period == "1ST" else 0.0,
        1.0 if period == "2ND" else 0.0,
    ]

    if feature_mode == "extended":
        raw_features.extend(
            [
                _to_number(home_profile.get("statValue")),
                _to_number(home_profile.get("statRank"), 50.0),
                _to_number(away_profile.get("statValue")),
                _to_number(away_profile.get("statRank"), 50.0),
                _to_number(home_profile.get("rankFor"), 50.0),
                _to_number(home_profile.get("rankAgainst"), 50.0),
                _to_number(away_profile.get("rankFor"), 50.0),
                _to_number(away_profile.get("rankAgainst"), 50.0),
                _to_number(home_profile.get("rankFor"), 50.0) / max(1.0, _to_number(away_profile.get("rankAgainst"), 50.0)),
                _to_number(home_profile.get("scoreFirstPct"), 50.0),
                _to_number(away_profile.get("scoreFirstPct"), 50.0),
                _to_number(home_profile.get("scoreFirstPct"), 50.0) - _to_number(away_profile.get("scoreFirstPct"), 50.0),
                _to_number(home_profile.get("shotsPerMinute", {}).get("leading")),
                _to_number(home_profile.get("shotsPerMinute", {}).get("trailing")),
                _to_number(home_profile.get("shotsPerMinute", {}).get("tied")),
                _to_number(away_profile.get("shotsPerMinute", {}).get("leading")),
                _to_number(away_profile.get("shotsPerMinute", {}).get("trailing")),
                _to_number(away_profile.get("shotsPerMinute", {}).get("tied")),
                _to_number(home_profile.get("shotsPerTenMinutes")),
                _to_number(away_profile.get("shotsPerTenMinutes")),
            ]
        )
        for key in EXTRA_PROFILE_KEYS:
            raw_features.extend(
                [
                    _get_extra_value(home_profile, "for", key),
                    _get_extra_value(away_profile, "for", key),
                    _get_extra_value(home_profile, "against", key),
                    _get_extra_value(away_profile, "against", key),
                ]
            )

    expected_length = len(build_feature_names(feature_mode))
    if len(raw_features) != expected_length:
        raise ValueError(f"Feature length mismatch for {build_dataset_key(stat_key, scope, period)}:{feature_mode}: {len(raw_features)} != {expected_length}")

    return {
        "raw_features": raw_features,
        "formula_predictions": formula_predictions,
        "consensus_features": {
            "formula_count": len(numeric_formula_values),
            "formula_std": consensus_std,
            "formula_median": consensus_median,
        },
        "historical_win_rates": {},
        "target": target,
        "metadata": {
            **metadata,
            "statKey": stat_key,
            "scope": scope,
            "period": period,
            "featureMode": feature_mode,
        },
        "feature_flags": {
            "includeProfileFeatures": feature_mode == "extended",
            "includeExtendedProfileFeatures": feature_mode == "extended",
        },
    }
