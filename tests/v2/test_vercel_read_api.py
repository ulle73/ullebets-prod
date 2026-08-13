from __future__ import annotations

from http.server import ThreadingHTTPServer
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from pymongo.errors import ServerSelectionTimeoutError
from urllib.error import HTTPError
from urllib.request import Request, urlopen


FUNCTION_PATH = Path(__file__).resolve().parents[2] / "api" / "v1" / "[...path].py"


def _load_function_module():
    spec = spec_from_file_location("ullebets_vercel_read_api", FUNCTION_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeDatabase:
    def command(self, command: str):
        assert command == "ping"
        return {"ok": 1}


def _request(url: str, *, method: str = "GET"):
    try:
        return urlopen(Request(url, method=method), timeout=5)
    except HTTPError as error:
        return error


def test_vercel_read_adapter_exposes_health_with_edge_cache_policy() -> None:
    module = _load_function_module()
    module._database = FakeDatabase()
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        response = _request(f"http://127.0.0.1:{server.server_port}/api/v1/health")

        assert response.status == 200
        assert response.read() == b'{"status":"ok"}'
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["ETag"]
        assert response.headers["X-Content-Type-Options"] == "nosniff"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_vercel_read_adapter_rejects_writes() -> None:
    module = _load_function_module()
    module._database = FakeDatabase()
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        response = _request(f"http://127.0.0.1:{server.server_port}/api/v1/health", method="POST")

        assert response.status == 405
        assert response.headers["Allow"] == "GET, HEAD"
        assert response.read() == b'{"error":"read_only_api"}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_vercel_read_adapter_reports_missing_database_configuration_without_details() -> None:
    module = _load_function_module()
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with patch.object(module, "_get_database", side_effect=module.ReadApiConfigurationError("private details")):
            response = _request(f"http://127.0.0.1:{server.server_port}/api/v1/health")

        assert response.status == 503
        assert response.read() == b'{"error":"read_api_unconfigured"}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_vercel_read_adapter_reports_database_availability_without_connection_details() -> None:
    module = _load_function_module()
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with patch.object(module, "_get_database", side_effect=ServerSelectionTimeoutError("private details")):
            response = _request(f"http://127.0.0.1:{server.server_port}/api/v1/health")

        assert response.status == 503
        assert response.read() == b'{"error":"read_api_database_unavailable"}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
