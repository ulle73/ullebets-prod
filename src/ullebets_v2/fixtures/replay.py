from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from ullebets_v2.support.schemas import slugify


def parse_iso_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(tz=UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def iter_target_dates(start_date: str, end_date: str) -> list[str]:
    start = parse_date(start_date)
    end = parse_date(end_date)
    if start > end:
        raise ValueError("start_date must be <= end_date")
    current = start
    dates: list[str] = []
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


@dataclass(frozen=True)
class SupportLookup:
    leagues_by_id: dict[str, dict[str, Any]]
    leagues_by_slug: dict[str, dict[str, Any]]
    leagues_by_name: dict[str, dict[str, Any]]
    teams_by_league_and_id: dict[tuple[str, str], dict[str, Any]]
    teams_by_id: dict[str, dict[str, Any]]
    teams_by_league_and_slug: dict[tuple[str, str], dict[str, Any]]
    teams_by_league_and_name: dict[tuple[str, str], dict[str, Any]]


def build_support_lookup(support_docs: dict[str, Any]) -> SupportLookup:
    leagues_by_id: dict[str, dict[str, Any]] = {}
    leagues_by_slug: dict[str, dict[str, Any]] = {}
    leagues_by_name: dict[str, dict[str, Any]] = {}
    teams_by_league_and_id: dict[tuple[str, str], dict[str, Any]] = {}
    teams_by_id: dict[str, dict[str, Any]] = {}
    teams_by_league_and_slug: dict[tuple[str, str], dict[str, Any]] = {}
    teams_by_league_and_name: dict[tuple[str, str], dict[str, Any]] = {}

    for league in support_docs.get("leagues", []):
        league_key = league["league_key"]
        if league.get("league_id") is not None:
            leagues_by_id[str(league["league_id"])] = league
        for raw in (league.get("league_slug"), league.get("league_name"), league_key):
            if raw:
                leagues_by_slug[slugify(str(raw))] = league
        if league.get("league_name"):
            leagues_by_name[slugify(str(league["league_name"]))] = league

    for team in support_docs.get("teams", []):
        league_key = str(team["league_key"])
        team_id = team.get("team_id")
        if team_id is not None:
            teams_by_league_and_id[(league_key, str(team_id))] = team
            teams_by_id[str(team_id)] = team
        if team.get("team_slug"):
            teams_by_league_and_slug[(league_key, slugify(str(team["team_slug"])))] = team
        if team.get("team_name"):
            teams_by_league_and_name[(league_key, slugify(str(team["team_name"])))] = team

    return SupportLookup(
        leagues_by_id=leagues_by_id,
        leagues_by_slug=leagues_by_slug,
        leagues_by_name=leagues_by_name,
        teams_by_league_and_id=teams_by_league_and_id,
        teams_by_id=teams_by_id,
        teams_by_league_and_slug=teams_by_league_and_slug,
        teams_by_league_and_name=teams_by_league_and_name,
    )


def canonical_json_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def load_fixture_payload(source_path: Path) -> dict[str, Any]:
    return json.loads(source_path.read_text(encoding="utf-8"))


def _extract_tournament(event: dict[str, Any]) -> dict[str, Any]:
    return event.get("tournament") or event.get("event", {}).get("tournament") or {}


def _extract_unique_tournament(tournament: dict[str, Any]) -> dict[str, Any]:
    return tournament.get("uniqueTournament") or {}


def _extract_team(event: dict[str, Any], side: str) -> dict[str, Any]:
    return event.get(side) or event.get("event", {}).get(side) or {}


def _match_league(event: dict[str, Any], lookup: SupportLookup) -> dict[str, Any] | None:
    tournament = _extract_tournament(event)
    unique_tournament = _extract_unique_tournament(tournament)
    candidates = [
        unique_tournament.get("id"),
        tournament.get("id"),
        tournament.get("category", {}).get("id"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        found = lookup.leagues_by_id.get(str(candidate))
        if found:
            return found

    slug_candidates = [
        unique_tournament.get("slug"),
        tournament.get("slug"),
        unique_tournament.get("name"),
        tournament.get("name"),
    ]
    for candidate in slug_candidates:
        if not candidate:
            continue
        normalized = slugify(str(candidate))
        found = lookup.leagues_by_slug.get(normalized) or lookup.leagues_by_name.get(normalized)
        if found:
            return found
    return None


def _match_team(team_payload: dict[str, Any], league_key: str, lookup: SupportLookup) -> tuple[dict[str, Any] | None, str]:
    if team_payload.get("id") is not None:
        found = lookup.teams_by_league_and_id.get((league_key, str(team_payload["id"])))
        if found:
            return found, "id"
        found = lookup.teams_by_id.get(str(team_payload["id"]))
        if found:
            return found, "global_id"

    if team_payload.get("slug"):
        found = lookup.teams_by_league_and_slug.get((league_key, slugify(str(team_payload["slug"]))))
        if found:
            return found, "slug"

    if team_payload.get("name"):
        found = lookup.teams_by_league_and_name.get((league_key, slugify(str(team_payload["name"]))))
        if found:
            return found, "name"

    return None, "fallback"


def _fallback_team_key(league_key: str, team_payload: dict[str, Any]) -> str:
    if team_payload.get("id") is not None:
        return f"{league_key}:{team_payload['id']}"
    if team_payload.get("slug"):
        return f"{league_key}:{slugify(str(team_payload['slug']))}"
    return f"{league_key}:unknown-team"


def _determine_mapping_confidence(league_found: bool, home_match_type: str, away_match_type: str) -> str:
    if league_found and home_match_type in {"id", "global_id"} and away_match_type in {"id", "global_id"}:
        return "exact_support_ids"
    if league_found and home_match_type != "fallback" and away_match_type != "fallback":
        return "support_names"
    if league_found:
        return "league_only"
    return "unmatched"


def build_fixture_documents(
    *,
    payload: dict[str, Any],
    support_docs: dict[str, Any],
    source_path: Path,
) -> dict[str, Any]:
    lookup = build_support_lookup(support_docs)
    payload_date = str(payload.get("date"))
    saved_at = parse_iso_datetime(payload.get("savedAt"))
    payload_hash = canonical_json_hash(payload)
    raw_doc = {
        "payload_hash": payload_hash,
        "source_type": "fixtures_replay",
        "source_date": payload_date,
        "source_path": str(source_path),
        "fetched_at": saved_at,
        "match_count": len(payload.get("matches", [])),
        "payload": payload,
    }

    canonical_docs: list[dict[str, Any]] = []
    for event in payload.get("matches", []):
        tournament = _extract_tournament(event)
        unique_tournament = _extract_unique_tournament(tournament)
        league_doc = _match_league(event, lookup)
        league_key = (
            str(league_doc["league_key"])
            if league_doc
            else slugify(
                str(
                    unique_tournament.get("slug")
                    or tournament.get("slug")
                    or unique_tournament.get("name")
                    or tournament.get("name")
                    or "unknown-league"
                )
            )
        )

        home_payload = _extract_team(event, "homeTeam")
        away_payload = _extract_team(event, "awayTeam")
        home_team, home_match_type = _match_team(home_payload, league_key, lookup)
        away_team, away_match_type = _match_team(away_payload, league_key, lookup)

        source_match_id = event.get("id") or event.get("event", {}).get("id")
        start_timestamp = event.get("startTimestamp") or event.get("event", {}).get("startTimestamp") or 0
        start_time = datetime.fromtimestamp(int(start_timestamp), tz=UTC) if start_timestamp else None
        identity_time = start_time.isoformat().replace("+00:00", "Z") if start_time else payload_date
        home_team_key = home_team["team_key"] if home_team else _fallback_team_key(league_key, home_payload)
        away_team_key = away_team["team_key"] if away_team else _fallback_team_key(league_key, away_payload)
        identity_key = "|".join([league_key, identity_time, home_team_key, away_team_key])
        match_key = f"sofascore:{source_match_id}" if source_match_id is not None else f"fixture:{identity_key}"

        canonical_docs.append(
            {
                "match_key": match_key,
                "identity_key": identity_key,
                "source_match_id": source_match_id,
                "source_type": "sofascore_scheduled_matches",
                "raw_payload_hash": payload_hash,
                "source_date": payload_date,
                "start_time": start_time,
                "league_key": league_key,
                "league_id": league_doc.get("league_id") if league_doc else unique_tournament.get("id"),
                "league_name": (league_doc or {}).get("league_name")
                or unique_tournament.get("name")
                or tournament.get("name"),
                "home_team_key": home_team_key,
                "away_team_key": away_team_key,
                "home_team_name": (home_team or {}).get("team_name") or home_payload.get("name"),
                "away_team_name": (away_team or {}).get("team_name") or away_payload.get("name"),
                "status_type": event.get("status", {}).get("type"),
                "season_id": event.get("season", {}).get("id") or (league_doc or {}).get("season_id"),
                "mapping_confidence": _determine_mapping_confidence(
                    league_doc is not None,
                    home_match_type,
                    away_match_type,
                ),
                "source_path": str(source_path),
            }
        )

    return {
        "raw": raw_doc,
        "canonical": canonical_docs,
    }
