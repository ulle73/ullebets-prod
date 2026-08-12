from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from ullebets_v2.read_api.drilldowns import read_league, read_match_detail, read_team
from ullebets_v2.read_api.service import (
    DEFAULT_PAGE_LIMIT,
    read_auto,
    read_dashboard,
    read_matches,
    read_model,
    read_results,
    read_system_status,
)


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


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


def dispatch_get(database: Any, path: str, query: dict[str, list[str]]) -> tuple[HTTPStatus, Any]:
    normalized_path = path.rstrip("/") or "/"
    if normalized_path == "/api/v1/health":
        database.command("ping")
        return HTTPStatus.OK, {"status": "ok"}
    if normalized_path == "/api/v1/dashboard":
        return HTTPStatus.OK, read_dashboard(database, source_date=_first(query, "date"))
    if normalized_path == "/api/v1/matches":
        return HTTPStatus.OK, read_matches(database, match_keys=_match_keys(query))
    if normalized_path == "/api/v1/auto":
        return HTTPStatus.OK, read_auto(database, limit=_positive_int(query,"limit",DEFAULT_PAGE_LIMIT,minimum=1), offset=_positive_int(query,"offset",0), stat_key=_first(query,"stat"), period=_first(query,"period"), scope=_first(query,"scope"), direction=_first(query,"direction"), model_id=_first(query,"model"), policy_id=_first(query,"policy"), league_key=_first(query,"league"))
    if normalized_path == "/api/v1/results":
        return HTTPStatus.OK, read_results(database, limit=_positive_int(query,"limit",DEFAULT_PAGE_LIMIT,minimum=1), offset=_positive_int(query,"offset",0), status=_first(query,"status"), stat_key=_first(query,"stat"), period=_first(query,"period"), scope=_first(query,"scope"), direction=_first(query,"direction"), league_key=_first(query,"league"))
    if normalized_path == "/api/v1/model": return HTTPStatus.OK, read_model(database)
    if normalized_path == "/api/v1/system": return HTTPStatus.OK, read_system_status(database)
    if normalized_path.startswith("/api/v1/matches/"):
        payload=read_match_detail(database,unquote(normalized_path.removeprefix("/api/v1/matches/")))
        return (HTTPStatus.OK,payload) if payload is not None else (HTTPStatus.NOT_FOUND,{"error":"match_not_found"})
    if normalized_path.startswith("/api/v1/teams/"):
        payload=read_team(database,unquote(normalized_path.removeprefix("/api/v1/teams/")))
        return (HTTPStatus.OK,payload) if payload is not None else (HTTPStatus.NOT_FOUND,{"error":"team_not_found"})
    if normalized_path.startswith("/api/v1/leagues/"):
        payload=read_league(database,unquote(normalized_path.removeprefix("/api/v1/leagues/")))
        return (HTTPStatus.OK,payload) if payload is not None else (HTTPStatus.NOT_FOUND,{"error":"league_not_found"})
    return HTTPStatus.NOT_FOUND,{"error":"not_found"}


def build_handler(database: Any) -> type[BaseHTTPRequestHandler]:
    class ReadApiHandler(BaseHTTPRequestHandler):
        server_version="UllebetsReadAPI/1.0"
        def _write_json(self,status:HTTPStatus,payload:Any)->None:
            body=_json_bytes(payload);self.send_response(status.value);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(body)));self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff");self.end_headers()
            if self.command!="HEAD": self.wfile.write(body)
        def _dispatch_get(self)->tuple[HTTPStatus,Any]:
            parsed=urlparse(self.path);return dispatch_get(database,parsed.path,parse_qs(parsed.query))
        def do_GET(self)->None:  # noqa: N802
            try: status,payload=self._dispatch_get()
            except Exception as exc:  # pragma: no cover
                self.log_error("Read API failure: %s",exc);self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR,{"error":"read_api_failure"});return
            self._write_json(status,payload)
        def do_HEAD(self)->None: self.do_GET()  # noqa: N802
        def _method_not_allowed(self)->None: self._write_json(HTTPStatus.METHOD_NOT_ALLOWED,{"error":"read_only_api"})
        do_POST=_method_not_allowed  # type: ignore[assignment]
        do_PUT=_method_not_allowed  # type: ignore[assignment]
        do_PATCH=_method_not_allowed  # type: ignore[assignment]
        do_DELETE=_method_not_allowed  # type: ignore[assignment]
    return ReadApiHandler


def serve(database:Any,*,host:str="127.0.0.1",port:int=8787,server_factory:Callable[...,ThreadingHTTPServer]=ThreadingHTTPServer)->None:
    server=server_factory((host,port),build_handler(database))
    try: server.serve_forever()
    finally: server.server_close()
