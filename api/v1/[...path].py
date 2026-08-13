from __future__ import annotations

from gzip import compress as gzip_compress
from hashlib import sha256
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import parse_qs, urlparse


# Vercel executes the function from the project root, while local import-based
# tests execute it from the repository checkout. Support both execution models.
REPOSITORY_ROOT = Path.cwd()


def _configure_source_path() -> None:
    candidates = [REPOSITORY_ROOT / "src"]
    candidates.extend(parent / "src" for parent in Path(__file__).resolve().parents)
    for candidate in candidates:
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            return


_configure_source_path()


_database: Any | None = None


class ReadApiConfigurationError(RuntimeError):
    """Raised when the serverless read API has no safe database target."""


def _get_database() -> Any:
    global _database
    if _database is None:
        from ullebets_v2.config import V2Config
        from ullebets_v2.storage.mongo import get_database

        config = V2Config.from_env(REPOSITORY_ROOT)
        if not config.mongo_uri:
            raise ReadApiConfigurationError("MONGODB_URI is not configured")
        if config.mongo_db != "ullebets_v2":
            raise ReadApiConfigurationError("MONGODB_DB must target ullebets_v2")
        # get_database enforces the ullebets_v2-only write boundary even though
        # this function itself exposes only read methods.
        _database = get_database(config)
    return _database


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def _semantic_etag_body(body: bytes) -> bytes:
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return body
    if not isinstance(payload, dict) or "generatedAt" not in payload:
        return body
    return _json_bytes({key: value for key, value in payload.items() if key != "generatedAt"})


def _edge_cache_control(path: str) -> str:
    from ullebets_v2.read_api.http import _cache_policy

    policy = _cache_policy(path)
    if policy is None:
        return "no-store"
    return (
        "public, max-age=0, "
        f"s-maxage={policy.max_age}, stale-while-revalidate={policy.stale_while_revalidate}"
    )


class handler(BaseHTTPRequestHandler):
    """Read-only Vercel adapter for the existing V2 HTTP routing contract."""

    server_version = "UllebetsVercelReadAPI/1.0"

    def _write_body(self, status: HTTPStatus, body: bytes, *, cache_control: str, etag: str | None = None) -> None:
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
        self.send_header("X-Content-Type-Options", "nosniff")
        if content_encoding:
            self.send_header("Content-Encoding", content_encoding)
        if etag:
            self.send_header("ETag", etag)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(response_body)

    def _write_json(self, status: HTTPStatus, payload: Any, *, cache_control: str = "no-store") -> None:
        self._write_body(status, _json_bytes(payload), cache_control=cache_control)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            from ullebets_v2.read_api.http import dispatch_get
            from pymongo.errors import PyMongoError

            status, payload = dispatch_get(_get_database(), parsed.path, parse_qs(parsed.query))
        except ReadApiConfigurationError:  # pragma: no cover - Vercel environment guard
            self._write_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "read_api_unconfigured"})
            return
        except PyMongoError as exc:  # pragma: no cover - Vercel infrastructure guard
            print(f"V2 read API database error: {type(exc).__name__}", file=sys.stderr)
            self._write_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "read_api_database_unavailable"})
            return
        except Exception as exc:  # pragma: no cover - production transport safety net
            self.log_error("V2 read API request failed: %s", type(exc).__name__)
            self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "read_api_failure"})
            return

        body = _json_bytes(payload)
        etag = f'W/"{sha256(_semantic_etag_body(body)).hexdigest()}"'
        cache_control = _edge_cache_control(self.path) if status == HTTPStatus.OK else "no-store"
        if self.headers.get("If-None-Match") == etag:
            self._write_body(HTTPStatus.NOT_MODIFIED, b"", cache_control=cache_control, etag=etag)
            return
        self._write_body(status, body, cache_control=cache_control, etag=etag)

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def _method_not_allowed(self) -> None:
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED.value)
        self.send_header("Allow", "GET, HEAD")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        body = _json_bytes({"error": "read_only_api"})
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_POST = _method_not_allowed  # type: ignore[assignment]
    do_PUT = _method_not_allowed  # type: ignore[assignment]
    do_PATCH = _method_not_allowed  # type: ignore[assignment]
    do_DELETE = _method_not_allowed  # type: ignore[assignment]
