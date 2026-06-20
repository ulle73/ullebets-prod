from __future__ import annotations

from math import isnan
from typing import Any

from ullebets_v1.registry.stats import get_stat_definition


def _is_missing_numeric(value: Any) -> bool:
    return value is None or (isinstance(value, float) and isnan(value))


def resolve_filter_reason(
    *,
    stat_key: str | None,
    period: str | None,
    scope: str | None,
    line_value: Any,
    odds_decimal: Any,
    settlement_result: str | None,
    has_teamstats_match: bool,
) -> str | None:
    if not stat_key:
        return "missing_stat_key"
    if not get_stat_definition(stat_key):
        return "unknown_stat_key"
    if not period:
        return "missing_period"
    if not scope:
        return "missing_scope"
    if _is_missing_numeric(line_value):
        return "missing_line"
    if _is_missing_numeric(odds_decimal):
        return "missing_odds"
    if not settlement_result:
        return "missing_outcome"
    if not has_teamstats_match:
        return "missing_teamstats_match"
    return None


def normalize_market_line(doc: dict, line: dict) -> dict:
    condition = str(line.get("condition") or "").lower()
    direction = "under" if "under" in condition else "over"
    settlement_result = "win" if line.get("win") is True else "loss" if line.get("win") is False else None
    return {
        "match_id": str(doc.get("matchId")) if doc.get("matchId") is not None else None,
        "league_name": doc.get("league"),
        "home_team_name": doc.get("homeTeam"),
        "away_team_name": doc.get("awayTeam"),
        "bet_key": line.get("betKey"),
        "stat_key": line.get("statKey"),
        "period": line.get("period"),
        "scope": line.get("scope"),
        "direction": direction,
        "line_value": line.get("line"),
        "odds_decimal": line.get("odds"),
        "actual_value": line.get("actual"),
        "settlement_result": settlement_result,
    }
