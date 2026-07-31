from __future__ import annotations

from ullebets_v2.closing import downstream


def test_refresh_closing_dependents_skips_when_no_closing_lines() -> None:
    result = downstream.refresh_closing_dependents(
        database=object(),
        closing_summary={"closing_line_docs": []},
        dry_run=False,
    )

    assert result == {
        "status": "skipped",
        "reason": "no_closing_lines_materialized",
    }


def test_refresh_closing_dependents_runs_clv_before_forward_results(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []
    closing_lines = [{"closing_key": "offer-1"}]
    clv_docs = [{"clv_key": "bet-1"}]

    def fake_clv_refresh(**kwargs):
        calls.append(("clv", kwargs))
        return {"job": "refresh_clv_tracking", "clv_docs": clv_docs}

    def fake_forward_refresh(**kwargs):
        calls.append(("forward", kwargs))
        return {"job": "refresh_forward_results", "result_docs": []}

    monkeypatch.setattr(downstream, "run_clv_tracking_refresh", fake_clv_refresh)
    monkeypatch.setattr(downstream, "run_forward_result_refresh", fake_forward_refresh)

    database = object()
    result = downstream.refresh_closing_dependents(
        database=database,
        closing_summary={"closing_line_docs": closing_lines},
        dry_run=True,
    )

    assert [name for name, _ in calls] == ["clv", "forward"]
    assert calls[0][1] == {
        "closing_line_docs": closing_lines,
        "database": database,
        "dry_run": True,
    }
    assert calls[1][1] == {
        "clv_tracking_docs": clv_docs,
        "closing_line_docs": closing_lines,
        "database": database,
        "dry_run": True,
    }
    assert result == {
        "status": "refreshed",
        "clv": {"job": "refresh_clv_tracking"},
        "forward_results": {"job": "refresh_forward_results"},
    }
