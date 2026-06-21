from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any
import unicodedata


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    asciiish = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    parts = re.findall(r"[a-z0-9]+", asciiish)
    return "-".join(parts)


def build_support_documents(
    leagues: dict[str, dict[str, Any]],
    league_urls: dict[str, str],
    ranking_rows: list[dict[str, Any]],
    *,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    now = captured_at or utc_now()
    source_doc = {
        "source_type": "support_sync",
        "source_version": "v2-foundation",
        "captured_at": now,
        "league_count": len(leagues),
        "ranking_count": len(ranking_rows),
    }

    league_docs: list[dict[str, Any]] = []
    team_docs: list[dict[str, Any]] = []
    ranking_docs: list[dict[str, Any]] = []

    for league_name, payload in leagues.items():
        league_key = slugify(league_name)
        league_docs.append(
            {
                "league_key": league_key,
                "league_name": league_name,
                "league_id": payload.get("leagueId"),
                "category_id": payload.get("categoryId"),
                "season_id": payload.get("seasonId"),
                "league_slug": payload.get("slug"),
                "country": payload.get("country"),
                "unibet_league_url": league_urls.get(league_name),
                "source_type": "support_sync",
                "captured_at": now,
            }
        )

        for team in payload.get("teams", []):
            team_id = team.get("id")
            team_docs.append(
                {
                    "team_key": f"{league_key}:{team_id}",
                    "league_key": league_key,
                    "team_id": team_id,
                    "team_name": team.get("name"),
                    "team_slug": team.get("slug"),
                    "team_image_url": team.get("imageUrl"),
                    "source_type": "support_sync",
                    "captured_at": now,
                    "opta_id": team.get("optaId"),
                    "opta_rank": None,
                    "opta_rating": None,
                }
            )

    for ranking_row in ranking_rows:
        league_name = ranking_row.get("league", "")
        ranking_docs.append(
            {
                "league_key": slugify(league_name),
                "league_name": league_name,
                "ranking_type": "league_support",
                "ranking": ranking_row.get("ranking", {}),
                "source_type": "support_sync",
                "captured_at": now,
            }
        )

    return {
        "source": source_doc,
        "leagues": league_docs,
        "teams": team_docs,
        "rankings": ranking_docs,
    }
