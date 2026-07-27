from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


def _clone_period_node(node: Any, *, include_market_bias: bool) -> dict[str, Any]:
    if not isinstance(node, dict):
        return {}
    cloned = deepcopy(node)
    if include_market_bias and "marketBias" not in cloned:
        cloned["marketBias"] = None
    return cloned


def _project_statistics(statistics: Any) -> dict[str, Any]:
    if not isinstance(statistics, dict):
        return {"for": {}, "against": {}, "leagueAverage": {}}

    projected: dict[str, Any] = {}
    for section_name, section_value in statistics.items():
        if not isinstance(section_value, dict):
            projected[section_name] = {}
            continue
        include_market_bias = section_name in {"for", "against"}
        projected_section: dict[str, Any] = {}
        for stat_key, stat_value in section_value.items():
            if not isinstance(stat_value, dict):
                projected_section[str(stat_key)] = {}
                continue
            projected_stat: dict[str, Any] = {}
            for period_key, period_value in stat_value.items():
                projected_stat[str(period_key)] = _clone_period_node(
                    period_value,
                    include_market_bias=include_market_bias,
                )
            projected_section[str(stat_key)] = projected_stat
        projected[section_name] = projected_section

    projected.setdefault("for", {})
    projected.setdefault("against", {})
    projected.setdefault("leagueAverage", {})
    return projected


def _serialize_generated_at(value: Any) -> Any:
    if isinstance(value, datetime):
        return value
    return value


def project_teamprofile_to_legacy_shape(profile_doc: dict[str, Any]) -> dict[str, Any]:
    meta = deepcopy(profile_doc.get("meta") or {})
    league_name = meta.get("leagueName") or profile_doc.get("league_name")

    return {
        "behaviour": deepcopy(profile_doc.get("behaviour") or {}),
        "games": deepcopy(profile_doc.get("games") or []),
        "generatedAt": _serialize_generated_at(profile_doc.get("generated_at")),
        "leagueName": league_name,
        "meta": {
            "lagnamn": meta.get("lagnamn"),
            "lagId": meta.get("lagId"),
            "ligaId": meta.get("ligaId"),
            "matchType": meta.get("matchType") or profile_doc.get("match_type"),
            "savedAt": meta.get("savedAt"),
            "categoryId": meta.get("categoryId"),
            "imageUrl": meta.get("imageUrl"),
        },
        "specials": deepcopy(profile_doc.get("specials") or {}),
        "statistics": _project_statistics(profile_doc.get("statistics")),
    }
