from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.source_connectivity.service import run_source_connectivity_audit


class FakeResponse:
    def __init__(self, status: int, data) -> None:
        self.status = status
        self.status_text = ""
        self.data = data


def test_run_source_connectivity_audit_dry_run_reports_success() -> None:
    def transport(url: str, headers: dict[str, str], timeout_seconds: int):  # noqa: ARG001
        if "/scheduled-events/" in url or "get-scheduled-events" in url or "/tournaments/scheduled-events" in url:
            return FakeResponse(200, {"events": [{"id": "evt-1"}]})
        if "/statistics" in url:
            return FakeResponse(200, {"statistics": {"shots": []}})
        if "/event/" in url:
            return FakeResponse(200, {"event": {"id": "evt-1"}})
        return FakeResponse(200, {"data": [1]})

    summary = run_source_connectivity_audit(
        source_workflow="debug-rapidapi-endpoints.yml",
        test_date="2026-06-21",
        category_id="34",
        match_ids=["123"],
        max_keys=1,
        env={"RAPIDAPI_KEY": "secret-key-1234"},
        transport=transport,
        dry_run=True,
        generated_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert len(summary["endpoint_results"]) == 11
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
    assert summary["audit_rows"][0]["metrics"]["success_count"] == 11


def test_run_source_connectivity_audit_dry_run_reports_missing_keys() -> None:
    summary = run_source_connectivity_audit(
        source_workflow="debug-rapidapi-endpoints.yml",
        test_date="2026-06-21",
        match_ids=["123"],
        env={},
        dry_run=True,
        generated_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["audit_status_counts"] == {"warn": 1}
    assert "missing_rapidapi_keys" in summary["audit_rows"][0]["findings"]
