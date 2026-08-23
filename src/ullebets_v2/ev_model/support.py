from __future__ import annotations

from typing import Any


V6_MODEL_ID = "ev_scope_interaction_recency45_asof_capped_v6_shadow"
V6_STAT_DIRECTIONS: dict[str, tuple[str, ...]] = {
    "cornerKicks": ("over", "under"),
    "shotsOnGoal": ("over",),
    "totalShots": ("over",),
}
V6_SCOPES = frozenset({"home", "away", "total"})
V6_PERIODS = frozenset({"1ST", "2ND", "ALL"})


def classify_v6_market_support(
    stat_key: Any,
    scope: Any,
    period: Any,
) -> dict[str, object]:
    normalized_stat = str(stat_key or "")
    normalized_scope = str(scope or "").lower()
    normalized_period = str(period or "").upper()
    directions = V6_STAT_DIRECTIONS.get(normalized_stat)
    if directions is None:
        return {
            "status": "model_missing",
            "reason": "stat_key_not_trained",
            "directions": [],
        }
    if normalized_scope not in V6_SCOPES:
        return {
            "status": "model_missing",
            "reason": "scope_not_trained",
            "directions": [],
        }
    if normalized_period not in V6_PERIODS:
        return {
            "status": "model_missing",
            "reason": "period_not_trained",
            "directions": [],
        }
    return {
        "status": (
            "supported"
            if directions == ("over", "under")
            else "partially_supported"
        ),
        "reason": (
            "v6_supported"
            if directions == ("over", "under")
            else "v6_over_only"
        ),
        "directions": list(directions),
    }
