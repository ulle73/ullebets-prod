from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from gzip import compress as gzip_compress
from hashlib import sha256
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import RLock, Thread
from time import monotonic
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from ullebets_v2.read_api.service import (
    DEFAULT_PAGE_LIMIT,
    read_auto,
    read_dashboard,
    read_league,
    read_match_detail,
    read_matchup_evaluation,
    read_matches,
    read_model,
    read_results,
    read_system_status,
    read_team,
)
from ullebets_v2.read_api.formula_performance import read_formula_performance


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def _semantic_etag_body(body: bytes) -> bytes:
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return body
    if not isinstance(payload, dict) or "generatedAt" not in payload:
        return body
    # Response-generation time should not invalidate otherwise identical read data.
    return _json_bytes({key: value for key, value in payload.items() if key != "generatedAt"})


def _first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key) or []
    value = values[0].strip() if values else ""
    return value or None


def _positive_int(query: dict[str, list[str]], key: str, default: int, *, minimum: int = 0) -> int:
    value = _first(query, key)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, parsed)


def _match_keys(query: dict[str, list[str]]) -> list[str]:
    values = list(query.get("key") or [])
    joined = _first(query, "keys")
    if joined:
        values.extend(joined.split(","))
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


@dataclass(frozen=True)
class _CachePolicy:
    max_age: int
    stale_while_revalidate: int


@dataclass(frozen=True)
class _CachedResponse:
    body: bytes
    etag: str
    expires_at: float
    stale_until: float
    cache_control: str


class _ResponseCache:
    def __init__(self, *, max_entries: int = 256) -> None:
        self._max_entries = max_entries
        self._entries: OrderedDict[str, _CachedResponse] = OrderedDict()
        self._refreshing: set[str] = set()
        self._lock = RLock()

    def get(self, key: str) -> tuple[_CachedResponse, str] | None:
        now = monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.stale_until <= now:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return entry, "HIT" if entry.expires_at > now else "STALE"

    def put(self, key: str, body: bytes, *, policy: _CachePolicy) -> _CachedResponse:
        expires_at = monotonic() + policy.max_age
        entry = _CachedResponse(
            body=body,
            etag=f'W/"{sha256(_semantic_etag_body(body)).hexdigest()}"',
            expires_at=expires_at,
            stale_until=expires_at + policy.stale_while_revalidate,
            cache_control=(
                f"private, max-age={policy.max_age}, "
                f"stale-while-revalidate={policy.stale_while_revalidate}"
            ),
        )
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
        return entry

    def begin_refresh(self, key: str) -> bool:
        with self._lock:
            if key in self._refreshing:
                return False
            self._refreshing.add(key)
            return True

    def end_refresh(self, key: str) -> None:
        with self._lock:
            self._refreshing.discard(key)


def _cache_policy(path_with_query: str) -> _CachePolicy | None:
    parsed = urlparse(path_with_query)
    path = parsed.path.rstrip("/") or "/"
    if path == "/api/v1/dashboard":
        return _CachePolicy(max_age=30, stale_while_revalidate=300)
    if path == "/api/v1/system":
        return _CachePolicy(max_age=10, stale_while_revalidate=30)
    if path.startswith("/api/v1/teams/"):
        return _CachePolicy(max_age=300, stale_while_revalidate=900)
    if path in {"/api/v1/auto", "/api/v1/results", "/api/v1/model", "/api/v1/formula-performance", "/api/v1/matchups/evaluation"}:
        return _CachePolicy(max_age=30, stale_while_revalidate=120)
    if path.startswith("/api/v1/matches/"):
        return _CachePolicy(max_age=30, stale_while_revalidate=120)
    return None


def dispatch_get(database: Any, path: str, query: dict[str, list[str]]) -> tuple[HTTPStatus, Any]:
    normalized_path = path.rstrip("/") or "/"
    if normalized_path == "/api/v1/health":
        database.command("ping")
        return HTTPStatus.OK, {"status": "ok"}
    if normalized_path == "/api/v1/dashboard":
        return HTTPStatus.OK, read_dashboard(database, source_date=_first(query, "date"))
    if normalized_path == "/api/v1/matchups/evaluation":
        date_from = _first(query, "dateFrom")
        date_to = _first(query, "dateTo")
        if date_from and date_to and date_to < date_from:
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_date_range"}
        return HTTPStatus.OK, read_matchup_evaluation(
            database,
            date_from=date_from,
            date_to=date_to,
            league_key=_first(query, "league"),
            stat_key=_first(query, "stat"),
            period=_first(query, "period"),
            scope=_first(query, "scope"),
            ranking_method=_first(query, "method"),
            evidence_class=_first(query, "evidence"),
        )
    if normalized_path == "/api/v1/matches":
        return HTTPStatus.OK, read_matches(database, match_keys=_match_keys(query))
    if normalized_path == "/api/v1/auto":
        return HTTPStatus.OK, read_auto(
            database,
            limit=_positive_int(query, "limit", DEFAULT_PAGE_LIMIT, minimum=1),
            offset=_positive_int(query, "offset", 0),
            status=_first(query, "status"),
            stat_key=_first(query, "stat"),
            period=_first(query, "period"),
            scope=_first(query, "scope"),
            direction=_first(query, "direction"),
            model_id=_first(query, "model"),
            policy_id=_first(query, "policy"),
            league_key=_first(query, "league"),
            checkpoint=_first(query, "checkpoint"),
            source_date=_first(query, "date"),
        )
    if normalized_path == "/api/v1/results":
        return HTTPStatus.OK, read_results(
            database,
            limit=_positive_int(query, "limit", DEFAULT_PAGE_LIMIT, minimum=1),
            offset=_positive_int(query, "offset", 0),
            status=_first(query, "status"),
            stat_key=_first(query, "stat"),
            period=_first(query, "period"),
            scope=_first(query, "scope"),
            direction=_first(query, "direction"),
            model_id=_first(query, "model"),
            policy_id=_first(query, "policy"),
            league_key=_first(query, "league"),
            checkpoint=_first(query, "checkpoint"),
        )
    if normalized_path == "/api/v1/model":
        return HTTPStatus.OK, read_model(database)
    if normalized_path == "/api/v1/formula-performance":
        return HTTPStatus.OK, read_formula_performance(
            database,
            limit=_positive_int(query, "limit", 100, minimum=1),
            offset=_positive_int(query, "offset", 0),
            formula_id=_first(query, "formula"),
            family=_first(query, "family"),
            stat_key=_first(query, "stat"),
            scope=_first(query, "scope"),
            period=_first(query, "period"),
            direction=_first(query, "direction"),
            league_key=_first(query, "league"),
            checkpoint=_first(query, "checkpoint"),
            status=_first(query, "status"),
            mode=_first(query, "mode") or "positive_ev",
        )
    if normalized_path == "/api/v1/system":
        return HTTPStatus.OK, read_system_status(database)
    if normalized_path.startswith("/api/v1/matches/"):
        payload = read_match_detail(database, unquote(normalized_path.removeprefix("/api/v1/matches/")))
        return (HTTPStatus.OK, payload) if payload is not None else (HTTPStatus.NOT_FOUND, {"error": "match_not_found"})
    if normalized_path.startswith("/api/v1/teams/"):
        payload = read_team(database, unquote(normalized_path.removeprefix("/api/v1/teams/")))
        return (HTTPStatus.OK, payload) if payload is not None else (HTTPStatus.NOT_FOUND, {"error": "team_not_found"})
    if normalized_path.startswith("/api/v1/leagues/"):
        payload = read_league(database, unquote(normalized_path.removeprefix("/api/v1/leagues/")))
        return (HTTPStatus.OK, payload) if payload is not None else (HTTPStatus.NOT_FOUND, {"error": "league_not_found"})
    return HTTPStatus.NOT_FOUND, {"error": "not_found"}


def build_handler(database: Any) -> type[BaseHTTPRequestHandler]:
    response_cache = _ResponseCache()

    class ReadApiHandler(BaseHTTPRequestHandler):
        server_version = "UllebetsReadAPI/1.0"

        def _write_body(
            self,
            status: HTTPStatus,
            body: bytes,
            *,
            cache_control: str = "no-store",
            etag: str | None = None,
            cache_status: str | None = None,
        ) -> None:
            response_body = body
            content_encoding = None
            if (
                status != HTTPStatus.NOT_MODIFIED
                and len(body) >= 1024
                and "gzip" in self.headers.get("Accept-Encoding", "").lower()
            ):
                response_body = gzip_compress(body, compresslevel=5)
                content_encoding = "gzip"
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(response_body)))
            self.send_header("Cache-Control", cache_control)
            self.send_header("Vary", "Accept-Encoding")
            if content_encoding:
                self.send_header("Content-Encoding", content_encoding)
            if etag:
                self.send_header("ETag", etag)
            if cache_status:
                self.send_header("X-Cache", cache_status)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(response_body)

        def _write_json(self, status: HTTPStatus, payload: Any) -> None:
            self._write_body(status, _json_bytes(payload))

        def _refresh_cached_path(self, cache_key: str, policy: _CachePolicy) -> None:
            try:
                status, payload = self._dispatch_get()
                if status == HTTPStatus.OK:
                    response_cache.put(cache_key, _json_bytes(payload), policy=policy)
            except Exception as exc:  # pragma: no cover - transport safety net
                self.log_error("Read API cache refresh failure: %s", exc)
            finally:
                response_cache.end_refresh(cache_key)

        def _dispatch_get(self) -> tuple[HTTPStatus, Any]:
            parsed = urlparse(self.path)
            return dispatch_get(database, parsed.path, parse_qs(parsed.query))

        def do_GET(self) -> None:  # noqa: N802
            policy = _cache_policy(self.path)
            if policy is not None:
                cached_result = response_cache.get(self.path)
                if cached_result is not None:
                    cached, cache_status = cached_result
                    if cache_status == "STALE" and response_cache.begin_refresh(self.path):
                        Thread(
                            target=self._refresh_cached_path,
                            args=(self.path, policy),
                            daemon=True,
                            name="read-api-cache-refresh",
                        ).start()
                    if self.headers.get("If-None-Match") == cached.etag:
                        self._write_body(
                            HTTPStatus.NOT_MODIFIED,
                            b"",
                            cache_control=cached.cache_control,
                            etag=cached.etag,
                            cache_status=cache_status,
                        )
                        return
                    self._write_body(
                        HTTPStatus.OK,
                        cached.body,
                        cache_control=cached.cache_control,
                        etag=cached.etag,
                        cache_status=cache_status,
                    )
                    return
            try:
                status, payload = self._dispatch_get()
            except Exception as exc:  # pragma: no cover - transport safety net
                self.log_error("Read API failure: %s", exc)
                self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "read_api_failure"})
                return
            body = _json_bytes(payload)
            if policy is not None and status == HTTPStatus.OK:
                cached = response_cache.put(self.path, body, policy=policy)
                if self.headers.get("If-None-Match") == cached.etag:
                    self._write_body(
                        HTTPStatus.NOT_MODIFIED,
                        b"",
                        cache_control=cached.cache_control,
                        etag=cached.etag,
                        cache_status="REVALIDATED",
                    )
                    return
                self._write_body(
                    status,
                    body,
                    cache_control=cached.cache_control,
                    etag=cached.etag,
                    cache_status="MISS",
                )
                return
            self._write_body(status, body)

        def do_HEAD(self) -> None:  # noqa: N802
            self.do_GET()

        def _method_not_allowed(self) -> None:
            self._write_json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "read_only_api"})

        do_POST = _method_not_allowed  # type: ignore[assignment]
        do_PUT = _method_not_allowed  # type: ignore[assignment]
        do_PATCH = _method_not_allowed  # type: ignore[assignment]
        do_DELETE = _method_not_allowed  # type: ignore[assignment]

    return ReadApiHandler


def serve(database: Any, *, host: str = "127.0.0.1", port: int = 8787, server_factory: Callable[..., ThreadingHTTPServer] = ThreadingHTTPServer) -> None:
    server = server_factory((host, port), build_handler(database))
    try:
        server.serve_forever()
    finally:
        server.server_close()
