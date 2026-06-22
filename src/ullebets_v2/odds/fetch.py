from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json


LIST_VIEW_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.unibet.se/",
    "X-Requested-With": "XMLHttpRequest",
}

EVENT_ODDS_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.unibet.se/",
    "X-Requested-With": "XMLHttpRequest",
}

UNIBET_EVENT_BASE_URL = "https://www.unibet.se/betting/sports/event"
EVENT_ODDS_BASE_URL = "https://eu1.offering-api.kambicdn.com/offering/v2018/ubse/betoffer/event"


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class HttpJsonResponse:
    status: int
    headers: dict[str, str]
    data: Any


Transport = Callable[[str, dict[str, str], int], HttpJsonResponse]


def default_transport(url: str, headers: dict[str, str], timeout_seconds: int) -> HttpJsonResponse:
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read().decode("utf-8")
        data = json.loads(payload) if payload else None
        return HttpJsonResponse(
            status=response.status,
            headers=dict(response.headers.items()),
            data=data,
        )


def build_list_view_url(base_url: str, *, ncid: str | None = None) -> str:
    params = {
        "lang": "sv_SE",
        "market": "SE",
        "client_id": "2",
        "channel_id": "1",
        "useCombined": "true",
        "ncid": ncid or str(int(utc_now().timestamp() * 1000)),
    }
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"


def build_event_odds_url(event_id: str | int, *, ncid: str | None = None) -> str:
    params = {
        "lang": "sv_SE",
        "market": "SE",
        "client_id": "2",
        "channel_id": "3",
        "includeParticipants": "true",
        "ncid": ncid or str(int(utc_now().timestamp() * 1000)),
    }
    return f"{EVENT_ODDS_BASE_URL}/{event_id}.json?{urlencode(params)}"


def fetch_list_view_payload(
    base_url: str,
    *,
    transport: Transport | None = None,
    timeout_seconds: int = 30,
) -> tuple[str, Any]:
    url = build_list_view_url(base_url)
    response = (transport or default_transport)(url, LIST_VIEW_REQUEST_HEADERS, timeout_seconds)
    if response.status != 200:
        raise RuntimeError(f"Unibet listView returned HTTP {response.status}")
    return url, response.data


def fetch_event_odds_payload(
    event_id: str | int,
    *,
    transport: Transport | None = None,
    timeout_seconds: int = 30,
) -> tuple[str, Any]:
    url = build_event_odds_url(event_id)
    response = (transport or default_transport)(url, EVENT_ODDS_REQUEST_HEADERS, timeout_seconds)
    if response.status != 200:
        raise RuntimeError(f"Unibet event odds returned HTTP {response.status} for {event_id}")
    return url, response.data
