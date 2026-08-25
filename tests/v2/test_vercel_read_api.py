from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from importlib import import_module, reload
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from pymongo.errors import ServerSelectionTimeoutError
from urllib.error import HTTPError
from urllib.request import Request, urlopen


FUNCTION_PATH = Path(__file__).resolve().parents[2] / "api" / "v1" / "[resource].py"
DETAIL_FUNCTION_PATH = FUNCTION_PATH.parent / "[resource]" / "[resource_id].py"
VERCEL_CONFIG_PATH = FUNCTION_PATH.parents[2] / "vercel.json"


def _load_function_module(function_path: Path = FUNCTION_PATH):
    spec = spec_from_file_location("ullebets_vercel_read_api", function_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_adapter_module():
    return reload(import_module("ullebets_v2.read_api.vercel_adapter"))


class FakeDatabase:
    def command(self, command: str):
        assert command == "ping"
        return {"ok": 1}

    def __getitem__(self, collection_name: str):
        return EmptyCollection()


class EmptyCollection:
    def find_one(self, query: dict[str, str], projection: dict[str, int] | None = None):
        return None


def test_vercel_read_functions_allow_cold_formula_aggregation_to_finish() -> None:
    config = json.loads(VERCEL_CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["functions"]["api/**/*.py"]["maxDuration"] >= 30


def _request(url: str, *, method: str = "GET"):
    try:
        return urlopen(Request(url, method=method), timeout=5)
    except HTTPError as error:
        return error


def test_vercel_read_adapter_exposes_health_with_edge_cache_policy() -> None:
    module = _load_adapter_module()
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
    module = _load_adapter_module()
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
    module = _load_adapter_module()
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
    module = _load_adapter_module()
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


def test_vercel_single_segment_function_reaches_the_read_api_dispatcher() -> None:
    """Keep dashboard and other single-segment endpoints inside the Vercel function."""
    assert FUNCTION_PATH.is_file(), "single-segment URLs need a Vercel dynamic-function entrypoint"
    module = _load_function_module()
    adapter = _load_adapter_module()
    adapter._database = FakeDatabase()
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        response = _request(f"http://127.0.0.1:{server.server_port}/api/v1/health")

        assert response.status == 200
        assert response.read() == b'{"status":"ok"}'
    finally:
        adapter._database = None
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_vercel_detail_function_reaches_the_read_api_dispatcher() -> None:
    """Protect drilldowns from Vercel returning its own filesystem 404."""
    assert DETAIL_FUNCTION_PATH.is_file(), "detail URLs need a Vercel dynamic-function entrypoint"
    module = _load_function_module(DETAIL_FUNCTION_PATH)
    adapter = import_module("ullebets_v2.read_api.vercel_adapter")
    adapter._database = FakeDatabase()
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        response = _request(f"http://127.0.0.1:{server.server_port}/api/v1/leagues/not-a-real-league")

        assert response.status == 404
        assert response.read() == b'{"error":"league_not_found"}'
    finally:
        adapter._database = None
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
