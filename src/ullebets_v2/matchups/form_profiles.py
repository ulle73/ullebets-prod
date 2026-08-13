from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from math import isfinite
from typing import Any


# Matchup cards are a separate presentation/ranking layer.  The immutable
# teamprofile values continue to feed model training and forward scoring.
MATCHUP_FORM_METHOD = "rolling_12_weighted_45d"
MATCHUP_FORM_WINDOW_MATCHES = 12
MATCHUP_FORM_RECENCY_HALF_LIFE_DAYS = 45.0


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _timestamp(value: Any) -> float | None:
    if isinstance(value, datetime):
        timestamp = value if value.tzinfo else value.replace(tzinfo=UTC)
        return timestamp.timestamp()
    number = _number(value)
    if number is not None:
        return number
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


def _history_rows(history: Any) -> list[dict[str, Any]]:
    if not isinstance(history, list):
        return []
    rows = [row for row in history if isinstance(row, dict)]
    ordered = sorted(
        enumerate(rows),
        key=lambda item: (
            _timestamp(item[1].get("timestamp")) or _timestamp(item[1].get("date")) or float("-inf"),
            str(item[1].get("date") or ""),
            -item[0],
        ),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    seen_matches: set[str] = set()
    for index, row in ordered:
        match_id = row.get("matchId") or row.get("match_key")
        dedupe_key = str(match_id) if match_id is not None else f"{row.get('date')}:{row.get('timestamp')}:{index}"
        if dedupe_key in seen_matches:
            continue
        seen_matches.add(dedupe_key)
        selected.append(row)
        if len(selected) == MATCHUP_FORM_WINDOW_MATCHES:
            break
    return selected


def _weighted_form(history: Any, value_key: str) -> tuple[float | None, dict[str, Any] | None]:
    rows = _history_rows(history)
    samples: list[tuple[float, float | None, dict[str, Any]]] = []
    for row in rows:
        value = _number(row.get(value_key))
        if value is None:
            continue
        samples.append((value, _timestamp(row.get("timestamp")) or _timestamp(row.get("date")), row))
    if not samples:
        return None, None

    latest_timestamp = max((timestamp for _, timestamp, _ in samples if timestamp is not None), default=None)
    weights: list[float] = []
    weighted_sum = 0.0
    for value, timestamp, _ in samples:
        age_days = 0.0
        if latest_timestamp is not None and timestamp is not None:
            age_days = max(0.0, (latest_timestamp - timestamp) / 86_400.0)
        weight = 0.5 ** (age_days / MATCHUP_FORM_RECENCY_HALF_LIFE_DAYS)
        weighted_sum += value * weight
        weights.append(weight)
    total_weight = sum(weights)
    if total_weight <= 0:
        return None, None
    latest_row = max(samples, key=lambda item: item[1] if item[1] is not None else float("-inf"))[2]
    return weighted_sum / total_weight, {
        "method": MATCHUP_FORM_METHOD,
        "windowMatches": MATCHUP_FORM_WINDOW_MATCHES,
        "sampleSize": len(samples),
        "effectiveSampleSize": (total_weight * total_weight) / sum(weight * weight for weight in weights),
        "recencyHalfLifeDays": MATCHUP_FORM_RECENCY_HALF_LIFE_DAYS,
        "latestMatchDate": latest_row.get("date"),
    }


def _rerank_profiles(profiles: list[dict[str, Any]]) -> None:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for profile in profiles:
        league_key = str(profile.get("league_key") or "")
        match_type = str(profile.get("match_type") or "")
        if league_key and match_type:
            groups.setdefault((league_key, match_type), []).append(profile)

    for rows in groups.values():
        metric_keys: set[tuple[str, str, str]] = set()
        for profile in rows:
            statistics = profile.get("statistics") if isinstance(profile.get("statistics"), dict) else {}
            for orientation in ("for", "against"):
                for stat_key, periods in (statistics.get(orientation) or {}).items():
                    if not isinstance(periods, dict):
                        continue
                    for period_key, node in periods.items():
                        if isinstance(node, dict):
                            metric_keys.add((orientation, str(stat_key), str(period_key)))

        for orientation, stat_key, period_key in metric_keys:
            values: list[tuple[dict[str, Any], dict[str, Any], float]] = []
            for profile in rows:
                node = (
                    profile.get("statistics", {})
                    .get(orientation, {})
                    .get(stat_key, {})
                    .get(period_key)
                )
                if not isinstance(node, dict):
                    continue
                value = _number(node.get("value"))
                if value is not None:
                    values.append((profile, node, value))
            if not values:
                continue
            league_average = sum(value for _, _, value in values) / len(values)
            ranked = sorted(values, key=lambda item: (-item[2], str(item[0].get("team_key") or "")))
            for rank, (profile, node, _) in enumerate(ranked, start=1):
                node["rank"] = rank
                average_node = (
                    profile.setdefault("statistics", {})
                    .setdefault("leagueAverage", {})
                    .setdefault(orientation, {})
                    .setdefault(stat_key, {})
                    .setdefault(period_key, {})
                )
                average_node["value"] = league_average


def build_matchup_form_profiles(teamprofile_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Clone teamprofiles and derive matchup-only recency-weighted form values.

    The source profiles are deliberately not mutated because they are shared by
    model/backtest code.  Home profiles only contain home history and away
    profiles only contain away history, so the 12-match window preserves scope.
    """

    profiles = deepcopy(teamprofile_docs)
    for profile in profiles:
        profile["matchup_form"] = {
            "method": MATCHUP_FORM_METHOD,
            "window_matches": MATCHUP_FORM_WINDOW_MATCHES,
            "recency_half_life_days": MATCHUP_FORM_RECENCY_HALF_LIFE_DAYS,
        }
        statistics = profile.get("statistics")
        if not isinstance(statistics, dict):
            continue
        for orientation, value_key in (("for", "val"), ("against", "oppVal")):
            for periods in (statistics.get(orientation) or {}).values():
                if not isinstance(periods, dict):
                    continue
                for node in periods.values():
                    if not isinstance(node, dict):
                        continue
                    value, form = _weighted_form(node.get("history"), value_key)
                    if value is not None and form is not None:
                        node["value"] = value
                        node["form"] = form
    _rerank_profiles(profiles)
    return profiles
