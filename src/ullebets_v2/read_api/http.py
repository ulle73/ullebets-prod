from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from ullebets_v2.read_api.service import (
    read_auto,
    read_dashboard,
    read_match_detail,
    read_model,
    read_results,
    read_system_status,
    read_team,
)


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def build_handler(database: Any) -> type[BaseHTTPRequestHandler]:
    class ReadApiHandler(BaseHTTPRequestHandler):
        server_version = "UllebetsReadAPI/1.0"

        def _write_json(self, status: HTTPStatus, payload: Any) -> None:
            body = _json_bytes(payload)
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _dispatch_get(self) -> tuple[HTTPStatus, Any]:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)

            if path == "/api/v1/health":
                database.command("ping")
                return HTTPStatus.OK, {"status": "ok"}
            if path == "/api/v1/dashboard":
                requested_date = query.get("date", [None])[0]
                return HTTPStatus.OK, read_dashboard(database, source_date=requested_date)
            if path == "/api/v1/auto":
                return HTTPStatus.OK, read_auto(database)
            if path == "/api/v1/results":
                return HTTPStatus.OK, read_results(database)
            if path == "/api/v1/model":
                return HTTPStatus.OK, read_model(database)
            if path == "/api/v1/system":
                return HTTPStatus.OK, read_system_status(database)
            if path.startswith("/api/v1/matches/"):
                match_key = unquote(path.removeprefix("/api/v1/matches/"))
                payload = read_match_detail(database, match_key)
                return (HTTPStatus.OK, payload) if payload is not None else (HTTPStatus.NOT_FOUND, {"error": "match_not_found"})
            if path.startswith("/api/v1/teams/"):
                team_key = unquote(path.removeprefix("/api/v1/teams/"))
                payload = read_team(database, team_key)
                return (HTTPStatus.OK, payload) if payload["profiles"] else (HTTPStatus.NOT_FOUND, {"error": "team_not_found"})
            return HTTPStatus.NOT_FOUND, {"error": "not_found"}

        def do_GET(self) -> None:  # noqa: N802
            try:
                status, payload = self._dispatch_get()
            except Exception as exc:  # pragma: no cover - transport safety net
                self.log_error("Read API failure: %s", exc)
                self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "read_api_failure"})
                return
            self._write_json(status, payload)

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
