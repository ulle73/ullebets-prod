from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import json

from ullebets_v2.fixtures.replay import canonical_json_hash


DEFAULT_ENRICHMENT_BASE_URLS = {
    "sportapi7": "https://sportapi7.p.rapidapi.com",
    "sofascore": "https://sofascore.p.rapidapi.com",
    "sportApiRealTime": "https://sport-api-real-time.p.rapidapi.com",
    "sofascoreSportApi": "https://sofascore-sport-api.p.rapidapi.com",
    "sofasport": "https://sofasport.p.rapidapi.com",
    "sofascorePublic": "https://api.sofascore.com/api/v1",
}


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def trim_trailing_slash(value: str) -> str:
    return str(value or "").rstrip("/")


def join_url(base_url: str, path: str) -> str:
    return f"{trim_trailing_slash(base_url)}/{str(path).lstrip('/')}"


def append_query_params(url: str, params: dict[str, Any] | None = None) -> str:
    if not params:
        return url
    filtered = {key: value for key, value in params.items() if value not in (None, "", [])}
    return f"{url}?{urlencode(filtered)}" if filtered else url


def extract_host(value: str) -> str | None:
    host = urlparse(str(value or "")).netloc.strip()
    return host or None


def _load_rapidapi_keys(env: dict[str, str], max_keys: int = 20) -> list[str]:
    raw = [
        env.get("RAPIDAPI_KEY", ""),
        *str(env.get("RAPIDAPI_KEYS", "")).split(","),
        *(env.get(f"RAPIDAPI_KEY_{index}", "") for index in range(1, 21)),
    ]
    output: list[str] = []
    seen: set[str] = set()
    for value in raw:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output[:max_keys]


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, dict):
        return len(value) == 0
    return False


def _to_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None
    return None


def _resolve_timestamp_seconds(*values: Any) -> int | None:
    for value in values:
        parsed_int = _to_int(value)
        if parsed_int is not None:
            return parsed_int
        parsed_dt = _parse_datetime(value)
        if parsed_dt is not None:
            return int(parsed_dt.timestamp())
    return None


def format_match_details(stats: Any) -> Any:
    if stats is None:
        return None
    if isinstance(stats, dict) and "statistics" in stats:
        return stats
    return {"statistics": stats}


@dataclass(frozen=True)
class HttpJsonResponse:
    status: int
    headers: dict[str, str]
    data: Any


Transport = Callable[[str, dict[str, str], int], HttpJsonResponse]


@dataclass(frozen=True)
class EnrichmentSourceConfig:
    rapidapi_keys: list[str]
    rapidapi_sportapi7_base_url: str
    rapidapi_sofascore_base_url: str
    rapidapi_sport_api_real_time_base_url: str
    rapidapi_sofascore_sport_api_base_url: str
    rapidapi_sofasport_base_url: str
    sofascore_public_api_base_url: str

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "EnrichmentSourceConfig":
        return cls(
            rapidapi_keys=_load_rapidapi_keys(env),
            rapidapi_sportapi7_base_url=env.get(
                "RAPIDAPI_SPORTAPI7_BASE_URL",
                DEFAULT_ENRICHMENT_BASE_URLS["sportapi7"],
            ),
            rapidapi_sofascore_base_url=env.get(
                "RAPIDAPI_SOFASCORE_BASE_URL",
                DEFAULT_ENRICHMENT_BASE_URLS["sofascore"],
            ),
            rapidapi_sport_api_real_time_base_url=env.get(
                "RAPIDAPI_SPORT_API_REAL_TIME_BASE_URL",
                DEFAULT_ENRICHMENT_BASE_URLS["sportApiRealTime"],
            ),
            rapidapi_sofascore_sport_api_base_url=env.get(
                "RAPIDAPI_SOFASCORE_SPORT_API_BASE_URL",
                DEFAULT_ENRICHMENT_BASE_URLS["sofascoreSportApi"],
            ),
            rapidapi_sofasport_base_url=env.get(
                "RAPIDAPI_SOFASPORT_BASE_URL",
                DEFAULT_ENRICHMENT_BASE_URLS["sofasport"],
            ),
            sofascore_public_api_base_url=env.get(
                "SOFASCORE_PUBLIC_API_BASE_URL",
                DEFAULT_ENRICHMENT_BASE_URLS["sofascorePublic"],
            ),
        )


@dataclass(frozen=True)
class FetchResult:
    success: bool
    data: Any
    source_name: str | None
    source_provider: str | None
    source_url: str | None
    source_endpoint: str | None
    api_key_slot: int | None
    http_status: int | None
    calls: int
    empty: bool


def default_transport(url: str, headers: dict[str, str], timeout_seconds: int) -> HttpJsonResponse:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8", errors="replace")
            data = json.loads(payload) if payload else None
            return HttpJsonResponse(
                status=int(getattr(response, "status", 200)),
                headers=dict(response.headers.items()),
                data=data,
            )
    except HTTPError as exc:
        return HttpJsonResponse(status=exc.code, headers=dict(exc.headers.items()), data=None)
    except URLError:
        return HttpJsonResponse(status=0, headers={}, data=None)


def _rapidapi_fetch(
    *,
    endpoints: list[dict[str, Any]],
    match_id: str,
    source_config: EnrichmentSourceConfig,
    transport: Transport | None = None,
    allow_empty: bool,
) -> FetchResult:
    used_transport = transport or default_transport
    calls = 0
    for endpoint in endpoints:
        query = endpoint["query"](match_id) if callable(endpoint.get("query")) else endpoint.get("query")
        url = append_query_params(str(endpoint["url"]), query)
        for api_key_slot, api_key in enumerate(source_config.rapidapi_keys):
            headers = {
                "accept": "application/json, text/plain, */*",
                "user-agent": "ullebets-v2-enrichment/1.0",
                "x-rapidapi-key": api_key,
            }
            host = endpoint.get("host") or extract_host(url)
            if host:
                headers["x-rapidapi-host"] = host
            calls += 1
            response = used_transport(url, headers, int(endpoint.get("timeout_seconds", 15)))
            transformed = endpoint["transform"](response.data)
            empty = _is_empty(transformed)
            if response.status == 200 and (allow_empty or not empty):
                return FetchResult(
                    success=True,
                    data=transformed,
                    source_name=str(endpoint["name"]),
                    source_provider="rapidapi",
                    source_url=url,
                    source_endpoint=str(endpoint["name"]),
                    api_key_slot=api_key_slot,
                    http_status=response.status,
                    calls=calls,
                    empty=empty,
                )
    return FetchResult(
        success=False,
        data=None,
        source_name=None,
        source_provider=None,
        source_url=None,
        source_endpoint=None,
        api_key_slot=None,
        http_status=None,
        calls=calls,
        empty=True,
    )


def _public_fetch(
    *,
    source_name: str,
    url: str,
    transform,
    transport: Transport | None = None,
    allow_empty: bool,
) -> FetchResult:
    used_transport = transport or default_transport
    response = used_transport(
        url,
        {
            "accept": "application/json, text/plain, */*",
            "user-agent": "ullebets-v2-enrichment/1.0",
        },
        15,
    )
    transformed = transform(response.data)
    empty = _is_empty(transformed)
    success = response.status == 200 and (allow_empty or not empty)
    return FetchResult(
        success=success,
        data=transformed if success else None,
        source_name=source_name if success else None,
        source_provider="sofascore" if success else None,
        source_url=url if success else None,
        source_endpoint=source_name if success else None,
        api_key_slot=None,
        http_status=response.status,
        calls=1,
        empty=empty,
    )


def _extract_event_info(data: Any) -> Any:
    if isinstance(data, dict):
        return data.get("event") or data.get("data") or data
    return data


def _extract_statistics(data: Any) -> Any:
    if isinstance(data, dict):
        return data.get("statistics") or data.get("data") or data
    return data


def _extract_incidents(data: Any) -> Any:
    if isinstance(data, dict):
        return data.get("incidents") or data.get("data") or data
    return data


def _extract_shotmap(data: Any) -> Any:
    if isinstance(data, dict):
        return data.get("shotmap") or data.get("data") or data
    return data


def fetch_match_event_info(
    *,
    match_id: str,
    source_config: EnrichmentSourceConfig,
    transport: Transport | None = None,
) -> FetchResult:
    return _public_fetch(
        source_name="sofascore-public-event",
        url=join_url(source_config.sofascore_public_api_base_url, f"/event/{match_id}"),
        transform=_extract_event_info,
        transport=transport,
        allow_empty=False,
    )


def fetch_match_statistics(
    *,
    match_id: str,
    source_config: EnrichmentSourceConfig,
    transport: Transport | None = None,
) -> FetchResult:
    rapid_result = _rapidapi_fetch(
        endpoints=[
            {
                "name": "sportapi7-event-statistics",
                "url": join_url(source_config.rapidapi_sportapi7_base_url, f"/api/v1/event/{match_id}/statistics"),
                "transform": _extract_statistics,
            },
            {
                "name": "sofascore-event-statistics",
                "url": join_url(source_config.rapidapi_sofascore_base_url, "/matches/get-statistics"),
                "query": {"matchId": match_id},
                "transform": _extract_statistics,
            },
            {
                "name": "sport-api-real-time-event-statistics",
                "url": join_url(source_config.rapidapi_sport_api_real_time_base_url, "/matches/statistics"),
                "query": {"matchId": match_id},
                "transform": _extract_statistics,
            },
            {
                "name": "sofascore-sport-event-statistics",
                "url": join_url(source_config.rapidapi_sofascore_sport_api_base_url, f"/api/event/{match_id}/statistics"),
                "transform": _extract_statistics,
            },
            {
                "name": "sofasport-event-statistics",
                "url": join_url(source_config.rapidapi_sofasport_base_url, "/v1/events/statistics"),
                "query": {"event_id": match_id},
                "transform": _extract_statistics,
            },
        ],
        match_id=match_id,
        source_config=source_config,
        transport=transport,
        allow_empty=False,
    )
    if rapid_result.success:
        return rapid_result
    public_result = _public_fetch(
        source_name="sofascore-public-statistics",
        url=join_url(source_config.sofascore_public_api_base_url, f"/event/{match_id}/statistics"),
        transform=_extract_statistics,
        transport=transport,
        allow_empty=False,
    )
    return FetchResult(
        success=public_result.success,
        data=public_result.data,
        source_name=public_result.source_name,
        source_provider=public_result.source_provider,
        source_url=public_result.source_url,
        source_endpoint=public_result.source_endpoint,
        api_key_slot=public_result.api_key_slot,
        http_status=public_result.http_status,
        calls=rapid_result.calls + public_result.calls,
        empty=public_result.empty,
    )


def fetch_match_incidents(
    *,
    match_id: str,
    source_config: EnrichmentSourceConfig,
    transport: Transport | None = None,
) -> FetchResult:
    rapid_result = _rapidapi_fetch(
        endpoints=[
            {
                "name": "sportapi7-incidents",
                "url": join_url(source_config.rapidapi_sportapi7_base_url, f"/api/v1/event/{match_id}/incidents"),
                "transform": _extract_incidents,
            },
            {
                "name": "sofascore-incidents",
                "url": join_url(source_config.rapidapi_sofascore_base_url, "/matches/get-incidents"),
                "query": {"matchId": match_id},
                "transform": _extract_incidents,
            },
            {
                "name": "sport-api-real-time-incidents",
                "url": join_url(source_config.rapidapi_sport_api_real_time_base_url, "/matches/incidents"),
                "query": {"matchId": match_id},
                "transform": _extract_incidents,
            },
            {
                "name": "sofascore-sport-incidents",
                "url": join_url(source_config.rapidapi_sofascore_sport_api_base_url, f"/api/event/{match_id}/incidents"),
                "transform": _extract_incidents,
            },
            {
                "name": "sofasport-incidents",
                "url": join_url(source_config.rapidapi_sofasport_base_url, "/v1/events/incidents"),
                "query": {"event_id": match_id},
                "transform": _extract_incidents,
            },
        ],
        match_id=match_id,
        source_config=source_config,
        transport=transport,
        allow_empty=False,
    )
    if rapid_result.success:
        return rapid_result
    public_result = _public_fetch(
        source_name="sofascore-public-incidents",
        url=join_url(source_config.sofascore_public_api_base_url, f"/event/{match_id}/incidents"),
        transform=_extract_incidents,
        transport=transport,
        allow_empty=True,
    )
    return FetchResult(
        success=public_result.success,
        data=public_result.data if public_result.success else None,
        source_name=public_result.source_name,
        source_provider=public_result.source_provider,
        source_url=public_result.source_url,
        source_endpoint=public_result.source_endpoint,
        api_key_slot=public_result.api_key_slot,
        http_status=public_result.http_status,
        calls=rapid_result.calls + public_result.calls,
        empty=public_result.empty,
    )


def fetch_match_shotmap(
    *,
    match_id: str,
    source_config: EnrichmentSourceConfig,
    transport: Transport | None = None,
) -> FetchResult:
    rapid_result = _rapidapi_fetch(
        endpoints=[
            {
                "name": "sportapi7-shotmap",
                "url": join_url(source_config.rapidapi_sportapi7_base_url, f"/api/v1/event/{match_id}/shotmap"),
                "transform": _extract_shotmap,
            },
            {
                "name": "sofasport-shotmap",
                "url": join_url(source_config.rapidapi_sofasport_base_url, "/v1/events/shotmap"),
                "query": {"event_id": match_id},
                "transform": _extract_shotmap,
            },
        ],
        match_id=match_id,
        source_config=source_config,
        transport=transport,
        allow_empty=False,
    )
    if rapid_result.success:
        return rapid_result
    public_result = _public_fetch(
        source_name="sofascore-public-shotmap",
        url=join_url(source_config.sofascore_public_api_base_url, f"/event/{match_id}/shotmap"),
        transform=_extract_shotmap,
        transport=transport,
        allow_empty=True,
    )
    return FetchResult(
        success=public_result.success,
        data=public_result.data if public_result.success else None,
        source_name=public_result.source_name,
        source_provider=public_result.source_provider,
        source_url=public_result.source_url,
        source_endpoint=public_result.source_endpoint,
        api_key_slot=public_result.api_key_slot,
        http_status=public_result.http_status,
        calls=rapid_result.calls + public_result.calls,
        empty=public_result.empty,
    )


def resolve_score_value(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        return _to_int(stripped)
    if isinstance(value, dict):
        for key in ("current", "display", "value", "home", "away", "score", "result"):
            if key not in value:
                continue
            resolved = resolve_score_value(value[key])
            if resolved is not None:
                return resolved
    return None


def extract_scores_from_event(event: Any) -> tuple[int | None, int | None]:
    if not isinstance(event, dict):
        return None, None
    home_candidates = [
        event.get("homeScore"),
        event.get("homeResult"),
        event.get("homeTeamScore"),
        event.get("score", {}).get("home") if isinstance(event.get("score"), dict) else None,
        event.get("scores", {}).get("home") if isinstance(event.get("scores"), dict) else None,
        event.get("result", {}).get("home") if isinstance(event.get("result"), dict) else None,
        event.get("home"),
        event.get("event", {}).get("homeScore") if isinstance(event.get("event"), dict) else None,
        event.get("event", {}).get("homeResult") if isinstance(event.get("event"), dict) else None,
        event.get("event", {}).get("homeTeamScore") if isinstance(event.get("event"), dict) else None,
    ]
    away_candidates = [
        event.get("awayScore"),
        event.get("awayResult"),
        event.get("awayTeamScore"),
        event.get("score", {}).get("away") if isinstance(event.get("score"), dict) else None,
        event.get("scores", {}).get("away") if isinstance(event.get("scores"), dict) else None,
        event.get("result", {}).get("away") if isinstance(event.get("result"), dict) else None,
        event.get("away"),
        event.get("event", {}).get("awayScore") if isinstance(event.get("event"), dict) else None,
        event.get("event", {}).get("awayResult") if isinstance(event.get("event"), dict) else None,
        event.get("event", {}).get("awayTeamScore") if isinstance(event.get("event"), dict) else None,
    ]
    home_score = next((resolved for resolved in (resolve_score_value(value) for value in home_candidates) if resolved is not None), None)
    away_score = next((resolved for resolved in (resolve_score_value(value) for value in away_candidates) if resolved is not None), None)
    return home_score, away_score


def resolve_final_scores(primary: Any, secondary: Any) -> tuple[int | None, int | None]:
    primary_home, primary_away = extract_scores_from_event(primary)
    secondary_home, secondary_away = extract_scores_from_event(secondary)
    return (
        primary_home if primary_home is not None else secondary_home,
        primary_away if primary_away is not None else secondary_away,
    )


def _extract_team_payload(event: Any, side: str) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {}
    return event.get(side) or event.get("event", {}).get(side) or {}


def _build_raw_source_meta(
    *,
    artifact_type: str,
    match_key: str,
    payload: Any,
    fetch_result: FetchResult,
    fetched_at: datetime,
) -> dict[str, Any]:
    payload_hash = canonical_json_hash(payload)
    source_name = fetch_result.source_name or "unknown-source"
    return {
        "raw_key": canonical_json_hash(
            {
                "match_key": match_key,
                "artifact_type": artifact_type,
                "payload_hash": payload_hash,
                "source_name": source_name,
            }
        ),
        "payload_hash": payload_hash,
        "fetched_at": fetched_at,
        "source_name": source_name,
        "source_provider": fetch_result.source_provider,
        "source_url": fetch_result.source_url,
        "source_endpoint": fetch_result.source_endpoint,
        "api_key_slot": fetch_result.api_key_slot,
        "http_status": fetch_result.http_status,
        "source_status": "ok" if fetch_result.success else "failed",
    }


def build_live_match_enrichment_source_rows(
    *,
    targets: list[dict[str, Any]],
    source_config: EnrichmentSourceConfig,
    transport: Transport | None = None,
    fetched_at: datetime | None = None,
) -> dict[str, Any]:
    now = fetched_at or utc_now()
    source_rows: list[dict[str, Any]] = []
    match_rows: list[dict[str, Any]] = []

    for target in targets:
        match_key = str(target.get("match_key") or "")
        source_match_id = target.get("source_match_id")
        source_match_id_str = str(source_match_id) if source_match_id is not None else None
        source_date = str(
            target.get("source_date")
            or (_parse_datetime(target.get("start_time")) or now).date().isoformat()
        )
        row: dict[str, Any] = {
            "match_key": match_key,
            "source_match_id": source_match_id_str,
            "source_date": source_date,
            "stats_source": None,
            "incidents_source": None,
            "shotmap_source": None,
            "result_source": None,
            "error": None,
        }
        if source_match_id_str is None:
            row["error"] = {"type": "missing_source_match_id", "message": "Fixture target is missing source_match_id."}
            match_rows.append(row)
            continue

        event_result = fetch_match_event_info(
            match_id=source_match_id_str,
            source_config=source_config,
            transport=transport,
        )
        stats_result = fetch_match_statistics(
            match_id=source_match_id_str,
            source_config=source_config,
            transport=transport,
        )
        incidents_result = fetch_match_incidents(
            match_id=source_match_id_str,
            source_config=source_config,
            transport=transport,
        )
        shotmap_result = fetch_match_shotmap(
            match_id=source_match_id_str,
            source_config=source_config,
            transport=transport,
        )

        row["stats_source"] = stats_result.source_name
        row["incidents_source"] = incidents_result.source_name
        row["shotmap_source"] = shotmap_result.source_name
        row["result_source"] = event_result.source_name

        if not stats_result.success or _is_empty(stats_result.data):
            row["error"] = {
                "type": "missing_statistics",
                "message": f"No statistics payload could be fetched for match {source_match_id_str}.",
            }
            match_rows.append(row)
            continue

        event_payload = event_result.data if event_result.success else {}
        home_payload = _extract_team_payload(event_payload, "homeTeam")
        away_payload = _extract_team_payload(event_payload, "awayTeam")
        home_score, away_score = resolve_final_scores(event_payload, target)
        match_timestamp = _resolve_timestamp_seconds(
            target.get("timestamp"),
            target.get("startTimestamp"),
            target.get("start_time"),
            target.get("kickoff_time"),
        )
        record: dict[str, Any] = {
            "matchId": source_match_id,
            "timestamp": match_timestamp,
            "date": source_date,
            "savedAt": now.isoformat(),
            "homeTeamId": home_payload.get("id") or target.get("home_team_id"),
            "homeTeamName": home_payload.get("name") or target.get("home_team_name"),
            "awayTeamId": away_payload.get("id") or target.get("away_team_id"),
            "awayTeamName": away_payload.get("name") or target.get("away_team_name"),
            "matchDetails": format_match_details(stats_result.data),
            "incidents": incidents_result.data if incidents_result.success else None,
            "shotmap": shotmap_result.data if shotmap_result.success else None,
            "_rawSources": {
                "matchDetails": _build_raw_source_meta(
                    artifact_type="match_statistics",
                    match_key=match_key,
                    payload=format_match_details(stats_result.data),
                    fetch_result=stats_result,
                    fetched_at=now,
                ),
                "result": _build_raw_source_meta(
                    artifact_type="result",
                    match_key=match_key,
                    payload=event_payload if event_result.success else {"homeScore": home_score, "awayScore": away_score},
                    fetch_result=event_result if event_result.success else FetchResult(
                        success=False,
                        data=None,
                        source_name="fixture-target",
                        source_provider="fixture",
                        source_url=target.get("source_path"),
                        source_endpoint="fixture-target",
                        api_key_slot=None,
                        http_status=None,
                        calls=0,
                        empty=False,
                    ),
                    fetched_at=now,
                ),
            },
        }
        if home_score is not None:
            record["homeScore"] = home_score
        if away_score is not None:
            record["awayScore"] = away_score
        if incidents_result.success:
            record["_rawSources"]["incidents"] = _build_raw_source_meta(
                artifact_type="incidents",
                match_key=match_key,
                payload=incidents_result.data,
                fetch_result=incidents_result,
                fetched_at=now,
            )
        if shotmap_result.success:
            record["_rawSources"]["shotmap"] = _build_raw_source_meta(
                artifact_type="shotmap",
                match_key=match_key,
                payload=shotmap_result.data,
                fetch_result=shotmap_result,
                fetched_at=now,
            )

        row["has_statistics"] = True
        row["has_incidents"] = incidents_result.success and incidents_result.data is not None
        row["has_shotmap"] = shotmap_result.success and shotmap_result.data is not None
        row["has_scores"] = home_score is not None and away_score is not None
        match_rows.append(row)
        source_rows.append(
            {
                "source_file": f"live:{source_date}:{source_match_id_str}",
                "source_path": str(target.get("source_path") or ""),
                "source_role": None,
                "matches": [record],
            }
        )

    return {"source_rows": source_rows, "match_rows": match_rows}
