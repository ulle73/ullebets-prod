from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.model_snapshots.service import run_model_snapshot_build

from tests.v2.test_odds_ingest import (
    FakeHistoricalCollection,
    FakeHistoricalDatabase,
    build_support_docs,
    fake_transport,
)


class FakeModelOracle:
    def build_match_lines(self, *, match_info: dict, offers: list[dict], defaults: dict | None = None) -> dict:  # noqa: ARG002
        lines = []
        for offer in offers:
            over_odds = offer.get("odds", {}).get("over")
            if over_odds:
                lines.append(
                    {
                        "betKey": f"{match_info['matchId']}|{offer['statKey']}|{offer['scope']}|{offer['period']}|over|{offer['line']}",
                        "statKey": offer["statKey"],
                        "line": offer["line"],
                        "condition": "över",
                        "direction": "over",
                        "period": offer["period"],
                        "scope": offer["scope"],
                        "odds": over_odds,
                        "value": 7.25,
                        "evDetails": {"evPctUniversalOptimized": 7.25},
                        "primaryFormulaKey": "universalOptimized",
                        "primaryValueKey": "evPctUniversalOptimized",
                        "homeTeam": match_info["homeTeam"],
                        "awayTeam": match_info["awayTeam"],
                        "actual": None,
                        "win": None,
                    }
                )
            under_odds = offer.get("odds", {}).get("under")
            if under_odds:
                lines.append(
                    {
                        "betKey": f"{match_info['matchId']}|{offer['statKey']}|{offer['scope']}|{offer['period']}|under|{offer['line']}",
                        "statKey": offer["statKey"],
                        "line": offer["line"],
                        "condition": "under",
                        "direction": "under",
                        "period": offer["period"],
                        "scope": offer["scope"],
                        "odds": under_odds,
                        "value": -1.5,
                        "evDetails": {"evPctUniversalOptimized": -1.5},
                        "primaryFormulaKey": "universalOptimized",
                        "primaryValueKey": "evPctUniversalOptimized",
                        "homeTeam": match_info["homeTeam"],
                        "awayTeam": match_info["awayTeam"],
                        "actual": None,
                        "win": None,
                    }
                )
        return {"lines": lines, "errors": []}


def test_run_model_snapshot_build_dry_run_builds_directed_lines() -> None:
    summary = run_model_snapshot_build(
        targets=[
            {
                "match_key": "match-1",
                "source_match_id": "match-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": datetime(2026, 6, 22, 18, 0, tzinfo=UTC),
            }
        ],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-forward.yml",
        snapshot_mode="forward",
        snapshot_label="CURRENT",
        dry_run=True,
        transport=fake_transport,
        odds_oracle=None,
        model_oracle=FakeModelOracle(),
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["matched_events"] == 1
    assert summary["model_snapshots"] == 2
    assert summary["oracle_error_count"] == 0
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
    assert summary["match_rows"][0]["generated_line_count"] == 2


def test_run_model_snapshot_build_dry_run_handles_empty_target_window() -> None:
    summary = run_model_snapshot_build(
        targets=[],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-forward.yml",
        snapshot_mode="forward",
        dry_run=True,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["target_matches"] == 0
    assert summary["model_snapshots"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_model_snapshot_build_dry_run_accepts_offerless_match_as_clean_empty_output() -> None:
    def offerless_transport(url: str, headers: dict[str, str], timeout_seconds: int):  # noqa: ARG001
        class Response:
            def __init__(self, status: int, data: dict) -> None:
                self.status = status
                self.data = data
                self.headers = {}

        if "betoffer/event/" in url:
            return Response(200, {"betOffers": []})
        return Response(
            200,
            {
                "events": [
                    {
                        "event": {
                            "id": "evt-1",
                            "homeName": "Arsenal",
                            "awayName": "Bournemouth",
                            "start": "2026-06-22T18:00:00Z",
                            "group": "Premier League",
                        }
                    }
                ]
            },
        )

    summary = run_model_snapshot_build(
        targets=[
            {
                "match_key": "match-1",
                "source_match_id": "match-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": datetime(2026, 6, 22, 18, 0, tzinfo=UTC),
            }
        ],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-forward.yml",
        snapshot_mode="forward",
        dry_run=True,
        transport=offerless_transport,
        odds_oracle=None,
        model_oracle=FakeModelOracle(),
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["matched_events"] == 1
    assert summary["market_offers"] == 0
    assert summary["model_snapshots"] == 0
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_model_snapshot_build_marks_historical_source_gap_as_mismatch() -> None:
    historical_database = FakeHistoricalDatabase()
    historical_database["unibet-backtest"] = FakeHistoricalCollection(
        [
            {
                "matchDate": "2025-10-08",
                "matchId": 14689178,
                "league": "Premier League",
                "homeTeam": "Arsenal",
                "awayTeam": "Bournemouth",
                "eventId": "evt-legacy",
            }
        ]
    )

    summary = run_model_snapshot_build(
        targets=[
            {
                "match_key": "match-legacy-present",
                "source_match_id": 14689178,
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": datetime(2025, 10, 8, 18, 0, tzinfo=UTC),
                "source_date": "2025-10-08",
            }
        ],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-backtests.yml",
        snapshot_mode="backtest",
        dry_run=True,
        transport=fake_transport,
        model_oracle=FakeModelOracle(),
        legacy_backtest_database=historical_database,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["matched_events"] == 0
    assert summary["model_snapshots"] == 0
    assert summary["parity_status_counts"] == {"mismatch": 1}
    assert summary["audit_status_counts"] == {"warn": 1}
    assert summary["health_status_counts"] == {"warn": 1}
