from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from ullebets_v2.fixtures.replay import canonical_json_hash


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def trim_trailing_slash(value: str) -> str:
    return str(value).rstrip("/")


def join_url(base_url: str, path: str) -> str:
    clean_base = trim_trailing_slash(base_url)
    clean_path = str(path).lstrip("/")
    return f"{clean_base}/{clean_path}"


def append_query_params(url: str, params: dict[str, Any] | None) -> str:
    if not params:
        return url
    filtered = {key: value for key, value in params.items() if value is not None}
    return f"{url}?{urlencode(filtered)}"


def to_number(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def extract_event_league_id(event: dict[str, Any]) -> int | None:
    candidates = [
        event.get("tournament", {}).get("uniqueTournament", {}).get("id"),
        event.get("uniqueTournament", {}).get("id"),
        event.get("tournament", {}).get("id"),
        event.get("event", {}).get("tournament", {}).get("uniqueTournament", {}).get("id"),
        event.get("event", {}).get("tournament", {}).get("id"),
    ]
    for candidate in candidates:
        number = to_number(candidate)
        if number is not None:
            return number
    return None


@dataclass(frozen=True)
class HttpJsonResponse:
    status: int
    headers: dict[str, str]
    data: Any


Transport = Callable[[str, dict[str, str], int], HttpJsonResponse]


@dataclass(frozen=True)
class FixtureSourceConfig:
    rapidapi_keys: list[str]
    rapidapi_sportapi7_base_url: str
    rapidapi_sofascore_base_url: str
    rapidapi_sport_api_real_time_base_url: str
    rapidapi_sofascore_sport_api_base_url: str
    sofascore_public_api_base_url: str

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "FixtureSourceConfig":
        keys = [
            value.strip()
            for value in (
                env.get("RAPIDAPI_KEYS")
                or env.get("RAPIDAPI_KEY")
                or ""
            ).split(",")
            if value.strip()
        ]
        return cls(
            rapidapi_keys=keys,
            rapidapi_sportapi7_base_url=env["RAPIDAPI_SPORTAPI7_BASE_URL"],
            rapidapi_sofascore_base_url=env["RAPIDAPI_SOFASCORE_BASE_URL"],
            rapidapi_sport_api_real_time_base_url=env["RAPIDAPI_SPORT_API_REAL_TIME_BASE_URL"],
            rapidapi_sofascore_sport_api_base_url=env["RAPIDAPI_SOFASCORE_SPORT_API_BASE_URL"],
            sofascore_public_api_base_url=env["SOFASCORE_PUBLIC_API_BASE_URL"],
        )


def build_category_plan(support_docs: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[int, set[int]] = {}
    for league in support_docs.get("leagues", []):
        category_id = to_number(league.get("category_id"))
        league_id = to_number(league.get("league_id"))
        if category_id is None or league_id is None:
            continue
        grouped.setdefault(category_id, set()).add(league_id)
    return [
        {"category_id": category_id, "league_ids": sorted(league_ids)}
        for category_id, league_ids in sorted(grouped.items())
    ]


def build_scheduled_match_endpoints(
    date: str,
    category_id: int,
    source_config: FixtureSourceConfig,
    include_global_endpoint: bool = False,
) -> list[dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    if include_global_endpoint:
        endpoints.append(
            {
                "name": "sportapi7-scheduled",
                "provider": "rapidapi",
                "url": join_url(
                    source_config.rapidapi_sportapi7_base_url,
                    f"/api/v1/sport/football/scheduled-events/{date}",
                ),
                "host": "sportapi7.example",
                "query": None,
            }
        )

    endpoints.extend(
        [
            {
                "name": "sofascore-api-dojo-tournaments",
                "provider": "rapidapi",
                "url": join_url(
                    source_config.rapidapi_sofascore_base_url,
                    "/tournaments/get-scheduled-events",
                ),
                "host": "sofascore.example",
                "query": {"categoryId": category_id, "date": date},
            },
            {
                "name": "sport-api-real-time-tournaments",
                "provider": "rapidapi",
                "url": join_url(
                    source_config.rapidapi_sport_api_real_time_base_url,
                    "/tournaments/scheduled-events",
                ),
                "host": "realtime.example",
                "query": {"categoryId": category_id, "date": date},
            },
            {
                "name": "sofascore-sport-scheduled-events",
                "provider": "rapidapi",
                "url": join_url(
                    source_config.rapidapi_sofascore_sport_api_base_url,
                    f"/api/sport/football/scheduled-events/{date}",
                ),
                "host": "sportapi.example",
                "query": None,
            },
            {
                "name": "sofascore-public-scheduled-events",
                "provider": "sofascore",
                "url": join_url(
                    source_config.sofascore_public_api_base_url,
                    f"/sport/football/scheduled-events/{date}",
                ),
                "host": None,
                "query": None,
            },
        ]
    )
    return endpoints


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


def normalize_events(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        events = payload.get("events")
        if isinstance(events, list):
            return [item for item in events if isinstance(item, dict)]
    return []


def fetch_live_fixture_batches(
    *,
    date: str,
    support_docs: dict[str, Any],
    source_config: FixtureSourceConfig,
    transport: Transport | None = None,
    fetched_at: datetime | None = None,
) -> list[dict[str, Any]]:
    used_transport = transport or default_transport
    now = fetched_at or utc_now()
    category_plan = build_category_plan(support_docs)
    batches: list[dict[str, Any]] = []

    for entry in category_plan:
        category_id = int(entry["category_id"])
        league_ids = {int(league_id) for league_id in entry["league_ids"]}
        endpoints = build_scheduled_match_endpoints(date, category_id, source_config)
        matched_batch: dict[str, Any] | None = None

        for endpoint in endpoints:
            if endpoint["provider"] == "rapidapi":
                for api_key_slot, api_key in enumerate(source_config.rapidapi_keys):
                    headers = {
                        "x-rapidapi-key": api_key,
                    }
                    if endpoint["host"]:
                        headers["x-rapidapi-host"] = endpoint["host"]
                    source_url = append_query_params(endpoint["url"], endpoint["query"])
                    response = used_transport(source_url, headers, 15)
                    if response.status != 200:
                        continue
                    events = [
                        event
                        for event in normalize_events(response.data)
                        if extract_event_league_id(event) in league_ids
                    ]
                    matched_batch = {
                        "payload_hash": canonical_json_hash(
                            {
                                "date": date,
                                "category_id": category_id,
                                "source_name": endpoint["name"],
                                "events": response.data,
                            }
                        ),
                        "source_name": endpoint["name"],
                        "source_provider": endpoint["provider"],
                        "source_date": date,
                        "source_url": source_url,
                        "category_id": category_id,
                        "fetched_at": now,
                        "api_key_slot": api_key_slot,
                        "events": events,
                        "event_count": len(events),
                        "payload": response.data,
                    }
                    break
                if matched_batch is not None:
                    break
            else:
                source_url = append_query_params(endpoint["url"], endpoint["query"])
                response = used_transport(source_url, {}, 15)
                if response.status != 200:
                    continue
                events = [
                    event
                    for event in normalize_events(response.data)
                    if extract_event_league_id(event) in league_ids
                ]
                matched_batch = {
                    "payload_hash": canonical_json_hash(
                        {
                            "date": date,
                            "category_id": category_id,
                            "source_name": endpoint["name"],
                            "events": response.data,
                        }
                    ),
                    "source_name": endpoint["name"],
                    "source_provider": endpoint["provider"],
                    "source_date": date,
                    "source_url": source_url,
                    "category_id": category_id,
                    "fetched_at": now,
                    "api_key_slot": None,
                    "events": events,
                    "event_count": len(events),
                    "payload": response.data,
                }
                break

        if matched_batch is not None:
            batches.append(matched_batch)

    return batches


def build_aggregated_fixture_payload(
    *,
    date: str,
    live_batches: list[dict[str, Any]],
    fetched_at: datetime | None = None,
) -> dict[str, Any]:
    now = fetched_at or utc_now()
    matches_by_id: dict[str, dict[str, Any]] = {}
    for batch in live_batches:
        for event in batch.get("events", []):
            source_match_id = event.get("id") or event.get("event", {}).get("id")
            if source_match_id is None:
                continue
            matches_by_id.setdefault(str(source_match_id), event)

    return {
        "date": date,
        "savedAt": now.isoformat().replace("+00:00", "Z"),
        "calls": len(live_batches),
        "successes": len(live_batches),
        "failures": 0,
        "sources": [
            {
                "categoryId": str(batch.get("category_id")),
                "source": batch.get("source_name"),
                "provider": batch.get("source_provider"),
                "source_name": batch.get("source_name"),
                "source_url": batch.get("source_url"),
                "api_key_slot": batch.get("api_key_slot"),
            }
            for batch in live_batches
        ],
        "matches": list(matches_by_id.values()),
    }
