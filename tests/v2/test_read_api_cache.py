from __future__ import annotations

import gzip
from http.server import ThreadingHTTPServer
import json
from threading import Thread
from time import monotonic, sleep
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ullebets_v2.read_api.http import _CachePolicy, build_handler


class CountingCursor(list):
    def sort(self, _spec):
        return self


class CountingCollection:
    def __init__(self, rows=None) -> None:
        self.find_calls = 0
        self.rows = list(rows or [])

    def find(self, _query=None, projection=None):
        del projection
        self.find_calls += 1
        return CountingCursor(row.copy() for row in self.rows)


class CountingDatabase(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


class SlowRefreshCollection(CountingCollection):
    def find(self, _query=None, projection=None):
        del projection
        self.find_calls += 1
        if self.find_calls > 1:
            sleep(0.35)
        return CountingCursor(row.copy() for row in self.rows)


def _request(url: str, *, etag: str | None = None, accept_encoding: str | None = None):
    headers = {"If-None-Match": etag} if etag else {}
    if accept_encoding:
        headers["Accept-Encoding"] = accept_encoding
    try:
        return urlopen(Request(url, headers=headers), timeout=5)
    except HTTPError as error:
        return error


def test_dashboard_reuses_cached_json_and_honors_if_none_match() -> None:
    fixtures = CountingCollection()
    database = CountingDatabase(
        fixtures_canonical=fixtures,
        matchups_score=CountingCollection(),
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(database))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        url = f"http://127.0.0.1:{server.server_port}/api/v1/dashboard?date=2026-08-10"
        first = _request(url)
        first_etag = first.headers.get("ETag")

        assert first.status == 200
        assert first.headers.get("Cache-Control") == "private, max-age=30, stale-while-revalidate=300"
        assert first_etag
        assert fixtures.find_calls == 1

        second = _request(url, etag=first_etag)

        assert second.status == 304
        assert fixtures.find_calls == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_dashboard_revalidates_unchanged_json_after_server_cache_expires() -> None:
    fixtures = CountingCollection()
    database = CountingDatabase(
        fixtures_canonical=fixtures,
        matchups_score=CountingCollection(),
    )
    with patch(
        "ullebets_v2.read_api.http._cache_policy",
        return_value=_CachePolicy(max_age=0, stale_while_revalidate=0),
    ):
        server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(database))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            url = f"http://127.0.0.1:{server.server_port}/api/v1/dashboard?date=2026-08-10"
            first = _request(url)
            first_etag = first.headers.get("ETag")

            second = _request(url, etag=first_etag)

            assert second.status == 304
            assert fixtures.find_calls == 2
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def test_dashboard_serves_stale_json_while_one_background_refresh_runs() -> None:
    fixtures = SlowRefreshCollection()
    database = CountingDatabase(
        fixtures_canonical=fixtures,
        matchups_score=CountingCollection(),
    )
    with patch(
        "ullebets_v2.read_api.http._cache_policy",
        return_value=_CachePolicy(max_age=0, stale_while_revalidate=30),
    ):
        server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(database))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            url = f"http://127.0.0.1:{server.server_port}/api/v1/dashboard?date=2026-08-10"
            first = _request(url)
            first.read()

            started_at = monotonic()
            stale = _request(url)
            stale.read()
            elapsed = monotonic() - started_at
            duplicate_stale = _request(url)
            duplicate_stale.read()

            assert stale.status == 200
            assert stale.headers.get("X-Cache") == "STALE"
            assert duplicate_stale.headers.get("X-Cache") == "STALE"
            assert elapsed < 0.2
            sleep(0.5)
            assert fixtures.find_calls == 2
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def test_large_json_response_uses_gzip_when_client_accepts_it() -> None:
    fixtures = [
        {
            "match_key": f"sofascore:{index}",
            "source_date": "2026-08-10",
            "home_team_name": f"Home team with a long display name {index}",
            "away_team_name": f"Away team with a long display name {index}",
        }
        for index in range(50)
    ]
    database = CountingDatabase(
        fixtures_canonical=CountingCollection(fixtures),
        matchups_score=CountingCollection(),
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(database))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        url = f"http://127.0.0.1:{server.server_port}/api/v1/dashboard?date=2026-08-10"
        response = _request(url, accept_encoding="gzip")
        payload = json.loads(gzip.decompress(response.read()))

        assert response.headers.get("Content-Encoding") == "gzip"
        assert response.headers.get("Vary") == "Accept-Encoding"
        assert len(payload["matches"]) == 50
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
