from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import re
from typing import Any
import unicodedata

from .opta import merge_opta_fields


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    asciiish = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    parts = re.findall(r"[a-z0-9]+", asciiish)
    return "-".join(parts)


def stable_json_hash(value: Any) -> str:
    serialized = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def count_payload_records(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return len(payload["data"])
        return len(payload)
    return 0


def build_support_source_docs(
    *,
    source_payloads: list[dict[str, Any]],
    captured_at: datetime | None = None,
    source_version: str = "v2-support-sync",
) -> list[dict[str, Any]]:
    now = captured_at or utc_now()
    docs: list[dict[str, Any]] = []
    for source in source_payloads:
        payload = source.get("payload")
        if payload is None:
            continue
        payload_hash = stable_json_hash(payload)
        source_name = str(source["source_name"])
        docs.append(
            {
                "source_key": f"{source_name}:{payload_hash}",
                "source_name": source_name,
                "source_type": "support_sync",
                "source_version": source_version,
                "source_kind": source.get("source_kind"),
                "source_locator": source.get("source_locator"),
                "captured_at": now,
                "payload_hash": payload_hash,
                "record_count": count_payload_records(payload),
                "payload": payload,
            }
        )
    return docs


def _normalize_league_url_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        return {"baseUrl": payload}
    return {}


def _extract_ranking_league_name(ranking_row: dict[str, Any]) -> str:
    league_value = ranking_row.get("league")
    if isinstance(league_value, dict):
        return str(
            league_value.get("name")
            or league_value.get("leagueName")
            or league_value.get("slug")
            or ""
        )
    if isinstance(league_value, str):
        return league_value
    return str(ranking_row.get("leagueName") or "")


def _extract_ranking_payload(ranking_row: dict[str, Any]) -> dict[str, Any]:
    ranking = ranking_row.get("ranking")
    return ranking if isinstance(ranking, dict) else {}


def build_support_documents(
    leagues: dict[str, dict[str, Any]],
    league_urls: dict[str, Any],
    ranking_rows: list[dict[str, Any]],
    *,
    opta_rows: list[dict[str, Any]] | None = None,
    captured_at: datetime | None = None,
    source_version: str = "v2-support-sync",
) -> dict[str, Any]:
    now = captured_at or utc_now()
    league_docs: list[dict[str, Any]] = []
    team_seed_docs: list[dict[str, Any]] = []
    ranking_docs: list[dict[str, Any]] = []
    known_league_keys: set[str] = set()

    for league_name, payload in leagues.items():
        league_key = slugify(league_name)
        known_league_keys.add(league_key)
        league_url_config = _normalize_league_url_payload(league_urls.get(league_name))
        league_docs.append(
            {
                "league_key": league_key,
                "league_name": league_name,
                "league_id": payload.get("leagueId"),
                "category_id": payload.get("categoryId"),
                "season_id": payload.get("seasonId"),
                "group_id": payload.get("groupId"),
                "league_slug": payload.get("slug"),
                "country": payload.get("country"),
                "unibet_country_slug": league_url_config.get("countrySlug"),
                "unibet_league_slug": league_url_config.get("leagueSlug"),
                "unibet_base_url": league_url_config.get("baseUrl"),
                "unibet_lookup_slugs": list(league_url_config.get("lookupSlugs", [])),
                "source_type": "support_sync",
                "captured_at": now,
            }
        )

        for team in payload.get("teams", []):
            team_id = team.get("id")
            fallback_team_key = slugify(str(team.get("name") or "unknown-team"))
            team_seed_docs.append(
                {
                    "team_key": f"{league_key}:{team_id}" if team_id is not None else f"{league_key}:{fallback_team_key}",
                    "league_key": league_key,
                    "team_id": team_id,
                    "team_name": team.get("name"),
                    "team_slug": team.get("slug"),
                    "team_image_url": team.get("imageUrl"),
                    "source_type": "support_sync",
                    "captured_at": now,
                    "opta_id": team.get("optaId"),
                    "opta_rank": team.get("optaRank"),
                    "opta_rating": team.get("optaRating"),
                }
            )

    team_docs = merge_opta_fields(team_seed_docs, opta_rows or [])

    for ranking_row in ranking_rows:
        league_name = _extract_ranking_league_name(ranking_row)
        league_key = slugify(league_name) if league_name else "unknown-league"
        ranking_docs.append(
            {
                "league_key": league_key,
                "league_name": league_name,
                "ranking_type": str(ranking_row.get("ranking_type") or "league_support"),
                "league_avg_opta_rating": ranking_row.get("leagueAvgOptaRating"),
                "ranking": _extract_ranking_payload(ranking_row),
                "matched_support_league": league_key in known_league_keys,
                "source_type": "support_sync",
                "captured_at": now,
            }
        )

    source_doc = {
        "source_type": "support_sync",
        "source_version": source_version,
        "captured_at": now,
        "league_count": len(league_docs),
        "team_count": len(team_docs),
        "league_url_count": sum(1 for row in league_docs if row.get("unibet_base_url")),
        "ranking_count": len(ranking_docs),
        "opta_source_row_count": len(opta_rows or []),
        "opta_id_count": sum(1 for row in team_docs if row.get("opta_id") is not None),
        "opta_rank_count": sum(1 for row in team_docs if row.get("opta_rank") is not None),
        "opta_rating_count": sum(1 for row in team_docs if row.get("opta_rating") is not None),
        "opta_matched_team_count": sum(1 for row in team_docs if row.get("opta_source_status") == "matched"),
    }

    return {
        "source": source_doc,
        "sources": [],
        "leagues": league_docs,
        "teams": team_docs,
        "rankings": ranking_docs,
    }
