from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetSpec:
    stat_key: str
    team_stats_key: str
    modeled_directions: tuple[str, ...] = ("over", "under")


TARGET_SPECS: dict[str, TargetSpec] = {
    "totalShots": TargetSpec(
        stat_key="totalShots",
        team_stats_key="totalShotsOnGoal",
        modeled_directions=("over",),
    ),
    "shotsOnGoal": TargetSpec(
        stat_key="shotsOnGoal",
        team_stats_key="shotsOnGoal",
        modeled_directions=("over",),
    ),
    "cornerKicks": TargetSpec(
        stat_key="cornerKicks",
        team_stats_key="cornerKicks",
    ),
}

PRIMARY_TARGETS = tuple(TARGET_SPECS.keys())
CONTEXT_STAT_KEYS = (
    "totalShotsOnGoal",
    "shotsOnGoal",
    "cornerKicks",
    "ballPossession",
    "expectedGoals",
    "bigChanceCreated",
    "yellowCards",
    "fouls",
)
TARGET_WINDOWS = (3, 5, 10, 20)
CONTEXT_WINDOWS = (5, 10)


def get_target_spec(stat_key: str) -> TargetSpec:
    return TARGET_SPECS[stat_key]


def get_modeled_directions(stat_key: str) -> tuple[str, ...]:
    spec = TARGET_SPECS.get(stat_key)
    return spec.modeled_directions if spec else ("over", "under")


def get_market_side_policy(stat_key: str) -> str:
    directions = get_modeled_directions(stat_key)
    if directions == ("over",):
        return "over_only"
    if directions == ("under",):
        return "under_only"
    return "two_sided"


def segment_shape_from_flags(*, has_over: bool, has_under: bool) -> str:
    if has_over and has_under:
        return "two_sided"
    if has_over:
        return "over_only"
    if has_under:
        return "under_only"
    return "missing_direction"


def is_segment_model_ready(
    stat_key: str,
    *,
    has_over: bool,
    has_under: bool,
) -> bool:
    available = {
        "over": bool(has_over),
        "under": bool(has_under),
    }
    return all(available.get(direction, False) for direction in get_modeled_directions(stat_key))
