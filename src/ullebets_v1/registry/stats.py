from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatDefinition:
    stat_key: str
    modeled_in_v1: bool
    settlement_supported: bool
    aliases: tuple[str, ...]


STAT_DEFINITIONS: dict[str, StatDefinition] = {
    "shotsOnGoal": StatDefinition(
        stat_key="shotsOnGoal",
        modeled_in_v1=True,
        settlement_supported=True,
        aliases=("shots_on_target", "skott på mål"),
    ),
    "totalShots": StatDefinition(
        stat_key="totalShots",
        modeled_in_v1=True,
        settlement_supported=True,
        aliases=("shots", "skott"),
    ),
    "cornerKicks": StatDefinition(
        stat_key="cornerKicks",
        modeled_in_v1=True,
        settlement_supported=True,
        aliases=("corners", "hörnor"),
    ),
    "yellowCards": StatDefinition(
        stat_key="yellowCards",
        modeled_in_v1=False,
        settlement_supported=True,
        aliases=("cards", "kort"),
    ),
    "freeKicks": StatDefinition(
        stat_key="freeKicks",
        modeled_in_v1=False,
        settlement_supported=True,
        aliases=("frisparkar",),
    ),
    "fouls": StatDefinition(
        stat_key="fouls",
        modeled_in_v1=False,
        settlement_supported=True,
        aliases=("fouls",),
    ),
    "totalTackle": StatDefinition(
        stat_key="totalTackle",
        modeled_in_v1=False,
        settlement_supported=True,
        aliases=("tacklingar",),
    ),
    "offsides": StatDefinition(
        stat_key="offsides",
        modeled_in_v1=False,
        settlement_supported=True,
        aliases=("offside",),
    ),
}


PRIMARY_TARGET_STAT_KEYS = tuple(
    definition.stat_key for definition in STAT_DEFINITIONS.values() if definition.modeled_in_v1
)


def get_stat_definition(stat_key: str | None) -> StatDefinition | None:
    if not stat_key:
        return None
    return STAT_DEFINITIONS.get(stat_key)
