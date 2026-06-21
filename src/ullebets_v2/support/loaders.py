from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import urllib.request

from .opta import OPTA_RANKINGS_URL
from .schemas import build_support_documents


DEFAULT_LEAGUE_RANKING_URL = "https://bettingmodel-backend.onrender.com/league_ranking.json"


@dataclass(frozen=True)
class LoadedSupportSource:
    source_name: str
    source_kind: str
    source_locator: str
    payload: Any | None
    error: str | None = None


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_json_url(url: str, *, timeout_seconds: int = 90) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.load(response)


def load_optional_json_source(
    *,
    source_name: str,
    file_path: Path | None = None,
    url: str | None = None,
    timeout_seconds: int = 90,
) -> LoadedSupportSource:
    if file_path is not None and file_path.exists():
        return LoadedSupportSource(
            source_name=source_name,
            source_kind="file",
            source_locator=str(file_path),
            payload=read_json(file_path),
        )
    if url:
        try:
            return LoadedSupportSource(
                source_name=source_name,
                source_kind="url",
                source_locator=url,
                payload=fetch_json_url(url, timeout_seconds=timeout_seconds),
            )
        except Exception as exc:
            return LoadedSupportSource(
                source_name=source_name,
                source_kind="url",
                source_locator=url,
                payload=None,
                error=str(exc),
            )
    return LoadedSupportSource(
        source_name=source_name,
        source_kind="missing",
        source_locator=str(file_path) if file_path is not None else "",
        payload=None,
        error="source_not_configured",
    )


def load_support_sync_sources(
    *,
    leagues_path: Path,
    league_urls_path: Path,
    opta_path: Path | None = None,
    opta_url: str = OPTA_RANKINGS_URL,
    league_ranking_path: Path | None = None,
    league_ranking_url: str = DEFAULT_LEAGUE_RANKING_URL,
    timeout_seconds: int = 90,
) -> dict[str, Any]:
    leagues_payload = read_json(leagues_path)
    league_urls_payload = read_json(league_urls_path)
    sources = [
        LoadedSupportSource(
            source_name="leagues-and-teams",
            source_kind="file",
            source_locator=str(leagues_path),
            payload=leagues_payload,
        ),
        LoadedSupportSource(
            source_name="unibet-league-urls",
            source_kind="file",
            source_locator=str(league_urls_path),
            payload=league_urls_payload,
        ),
        load_optional_json_source(
            source_name="opta-power-rankings",
            file_path=opta_path,
            url=opta_url,
            timeout_seconds=timeout_seconds,
        ),
        load_optional_json_source(
            source_name="league-ranking",
            file_path=league_ranking_path,
            url=league_ranking_url,
            timeout_seconds=timeout_seconds,
        ),
    ]
    source_by_name = {source.source_name: source for source in sources}
    return {
        "leagues_payload": leagues_payload,
        "league_urls_payload": league_urls_payload,
        "opta_payload": source_by_name["opta-power-rankings"].payload,
        "league_ranking_payload": source_by_name["league-ranking"].payload,
        "source_inputs": sources,
    }


def load_support_documents(
    *,
    leagues_path: Path,
    league_urls_path: Path | None = None,
    ranking_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    league_urls = read_json(league_urls_path) if league_urls_path and league_urls_path.exists() else {}
    return build_support_documents(
        leagues=read_json(leagues_path),
        league_urls=league_urls,
        ranking_rows=ranking_rows or [],
    )
