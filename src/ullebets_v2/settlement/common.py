from __future__ import annotations

from typing import Any


def normalize_scope(scope: str | None) -> str:
    value = str(scope or "").lower()
    if value in {"total", "all"}:
        return "all"
    if value in {"home", "away"}:
        return value
    return value or "all"


def result_is_finished(result_row: dict[str, Any] | None) -> bool:
    if result_row is None:
        return False
    return result_row.get("home_score") is not None and result_row.get("away_score") is not None


def build_stats_lookup(match_stats_canonical: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in match_stats_canonical:
        key = (
            str(row.get("match_key") or ""),
            str(row.get("stat_key") or ""),
            str(row.get("period") or ""),
            normalize_scope(row.get("scope")),
        )
        lookup[key] = row
    return lookup


def build_stat_scope_lookup(match_stats_canonical: list[dict[str, Any]]) -> dict[tuple[str, str, str], set[str]]:
    lookup: dict[tuple[str, str, str], set[str]] = {}
    for row in match_stats_canonical:
        key = (
            str(row.get("match_key") or ""),
            str(row.get("stat_key") or ""),
            str(row.get("period") or ""),
        )
        lookup.setdefault(key, set()).add(normalize_scope(row.get("scope")))
    return lookup


def build_result_lookup(match_results_canonical: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("match_key")): row
        for row in match_results_canonical
        if row.get("match_key") is not None
    }


def resolve_actual_context(
    *,
    row: dict[str, Any],
    result_lookup: dict[str, dict[str, Any]],
    stats_lookup: dict[tuple[str, str, str, str], dict[str, Any]],
    stat_scope_lookup: dict[tuple[str, str, str], set[str]],
) -> dict[str, Any]:
    match_key = str(row.get("match_key") or "")
    stat_key = str(row.get("stat_key") or "")
    period = str(row.get("period") or "")
    scope = normalize_scope(row.get("scope"))
    result_row = result_lookup.get(match_key)
    if not result_is_finished(result_row):
        return {
            "actual_resolution_status": "pending_result",
            "actual_value": None,
            "home_value": None,
            "away_value": None,
            "actual_source": None,
            "actual_source_status": "missing_match_result_source",
        }

    home_row = stats_lookup.get((match_key, stat_key, period, "home"))
    away_row = stats_lookup.get((match_key, stat_key, period, "away"))
    total_row = stats_lookup.get((match_key, stat_key, period, "all"))

    home_value = home_row.get("actual_value") if home_row else None
    away_value = away_row.get("actual_value") if away_row else None
    if scope == "home":
        actual_value = home_value
        source_row = home_row
    elif scope == "away":
        actual_value = away_value
        source_row = away_row
    else:
        actual_value = total_row.get("actual_value") if total_row else (
            (home_value + away_value)
            if isinstance(home_value, (int, float)) and isinstance(away_value, (int, float))
            else None
        )
        source_row = total_row

    if actual_value is None:
        available_scopes = stat_scope_lookup.get((match_key, stat_key, period), set())
        if not available_scopes:
            actual_source_status = "stat_not_in_canonical_source"
        elif scope not in available_scopes:
            actual_source_status = "scope_not_in_canonical_source"
        else:
            actual_source_status = "missing_actual_source_row"
        return {
            "actual_resolution_status": "missing_actual",
            "actual_value": None,
            "home_value": home_value,
            "away_value": away_value,
            "actual_source": None,
            "actual_source_status": actual_source_status,
        }

    actual_source = None
    if source_row is not None:
        actual_source = ":".join(
            [
                str(source_row.get("match_key") or ""),
                str(source_row.get("stat_key") or ""),
                str(source_row.get("period") or ""),
                str(source_row.get("scope") or ""),
            ]
        )
    elif scope == "all":
        actual_source = f"{match_key}:{stat_key}:{period}:derived_total"

    return {
        "actual_resolution_status": "resolved",
        "actual_value": actual_value,
        "home_value": home_value,
        "away_value": away_value,
        "actual_source": actual_source,
        "actual_source_status": "resolved",
    }
