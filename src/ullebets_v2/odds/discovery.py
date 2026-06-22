from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ullebets_v2.odds.fetch import UNIBET_EVENT_BASE_URL
from ullebets_v2.odds.naming import (
    build_alias_map,
    build_league_map,
    canonicalize_league_name,
    canonicalize_team_name,
    normalize_league_name,
    normalize_team_name,
)
from ullebets_v2.support.schemas import stable_json_hash


SIX_HOURS_MS = 6 * 60 * 60 * 1000


@dataclass(frozen=True)
class DiscoveredEvent:
    event_id: str
    event_url: str
    start: str | None
    league_name: str | None
    home_team_name: str
    away_team_name: str
    score: float
    diff_ms: int | None


def _to_timestamp_ms(value: Any) -> int | None:
    if isinstance(value, datetime):
        timestamp = int(value.timestamp() * 1000)
        return timestamp if timestamp > 0 else None
    if isinstance(value, (int, float)):
        if value <= 0:
            return None
        return int(value if value > 1e12 else value * 1000)
    if isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            numeric = float(text)
        except ValueError:
            numeric = None
        if numeric is not None:
            return int(numeric if numeric > 1e12 else numeric * 1000)
        try:
            return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            return None
    return None


def extract_event_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    events = payload.get("events")
    if not isinstance(events, list):
        return []
    extracted: list[dict[str, Any]] = []
    for entry in events:
        if not isinstance(entry, dict):
            continue
        event = entry.get("event")
        extracted.append(event if isinstance(event, dict) else entry)
    return [
        event
        for event in extracted
        if event.get("id") and event.get("homeName") and event.get("awayName")
    ]


def extract_league_name(event: dict[str, Any]) -> str | None:
    return (
        event.get("group")
        or event.get("groupName")
        or (event.get("tournament") or {}).get("name")
        or event.get("eventGroup")
        or None
    )


def resolve_unibet_league(support_docs: dict[str, Any], league_key: str | None = None, league_name: str | None = None) -> dict[str, Any] | None:
    leagues = support_docs.get("leagues", [])
    if league_key:
        for league in leagues:
            if league.get("league_key") == league_key:
                return league

    if league_name:
        lookup = normalize_league_name(league_name)
        for league in leagues:
            candidates = [
                league.get("league_name"),
                league.get("unibet_league_slug"),
                *league.get("unibet_lookup_slugs", []),
            ]
            for candidate in candidates:
                if normalize_league_name(candidate) == lookup:
                    return league
    return None


def build_list_view_raw_doc(
    *,
    league_doc: dict[str, Any],
    source_url: str,
    payload: Any,
    fetched_at: datetime,
) -> dict[str, Any]:
    payload_hash = stable_json_hash(payload)
    return {
        "raw_key": "|".join(
            [
                "list_view",
                str(league_doc.get("league_key") or ""),
                fetched_at.isoformat(),
                payload_hash,
            ]
        ),
        "payload_hash": payload_hash,
        "payload_kind": "list_view",
        "source_provider": "kambi",
        "source_url": source_url,
        "fetched_at": fetched_at,
        "match_key": None,
        "event_id": None,
        "league_key": league_doc.get("league_key"),
        "league_name": league_doc.get("league_name"),
        "payload": payload,
        "event_count": len(extract_event_list(payload)),
    }


def find_unibet_event_for_match(
    *,
    match: dict[str, Any],
    list_view_events: list[dict[str, Any]],
    support_docs: dict[str, Any],
) -> DiscoveredEvent | None:
    alias_map = build_alias_map(support_docs)
    league_map = build_league_map(support_docs)

    match_home = canonicalize_team_name(match.get("home_team_name"), alias_map) or str(match.get("home_team_name") or "")
    match_away = canonicalize_team_name(match.get("away_team_name"), alias_map) or str(match.get("away_team_name") or "")
    match_home_norm = normalize_team_name(match_home)
    match_away_norm = normalize_team_name(match_away)
    match_league = canonicalize_league_name(match.get("league_name"), league_map)
    match_league_norm = normalize_league_name(match_league)
    target_timestamp = _to_timestamp_ms(match.get("start_time"))

    candidates: list[DiscoveredEvent] = []
    for event in list_view_events:
        event_home = canonicalize_team_name(event.get("homeName"), alias_map)
        event_away = canonicalize_team_name(event.get("awayName"), alias_map)
        event_home_norm = normalize_team_name(event_home or event.get("homeName"))
        event_away_norm = normalize_team_name(event_away or event.get("awayName"))
        matches_exact_order = event_home_norm == match_home_norm and event_away_norm == match_away_norm
        matches_swapped_order = event_home_norm == match_away_norm and event_away_norm == match_home_norm
        if not matches_exact_order and not matches_swapped_order:
            continue

        event_start_ms = _to_timestamp_ms(event.get("start"))
        diff_ms = abs(event_start_ms - target_timestamp) if target_timestamp and event_start_ms else None
        if diff_ms is not None and diff_ms > SIX_HOURS_MS:
            continue

        event_league = canonicalize_league_name(extract_league_name(event), league_map)
        event_league_norm = normalize_league_name(event_league)
        score = 0.0
        if diff_ms is not None:
            score += max(0.0, SIX_HOURS_MS - diff_ms) / (60 * 60 * 1000)
        if match_league_norm and event_league_norm == match_league_norm:
            score += 5.0
        canonical_home = (event_home or event.get("homeName") or "").strip()
        canonical_away = (event_away or event.get("awayName") or "").strip()
        if matches_swapped_order:
            canonical_home, canonical_away = canonical_away, canonical_home

        candidates.append(
            DiscoveredEvent(
                event_id=str(event["id"]),
                event_url=f"{UNIBET_EVENT_BASE_URL.rstrip('/')}/{event['id']}",
                start=event.get("start"),
                league_name=event_league,
                home_team_name=canonical_home,
                away_team_name=canonical_away,
                score=score,
                diff_ms=diff_ms,
            )
        )

    if not candidates:
        return None
    return max(candidates, key=lambda item: item.score)
