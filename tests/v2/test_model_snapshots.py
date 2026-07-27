from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from ullebets_v2.enrichment.replay import build_match_enrichment_documents
from ullebets_v2.model_snapshots.oracle import V2JsModelOracle
from ullebets_v2.model_snapshots.service import run_model_snapshot_build
from ullebets_v2.support.schemas import build_support_documents
from ullebets_v2.teamprofiles.service import build_teamprofile_docs

from tests.v2.test_odds_ingest import (
    FakeHistoricalCollection,
    FakeHistoricalDatabase,
    build_legacy_backtest_doc,
    build_support_docs,
    fake_transport,
)
from tests.v2.test_match_enrichment import FakeReadCollection, FakeReadDatabase
from tests.v2.test_support_sync import build_fixture_support_inputs


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


def build_v2_model_support_docs() -> dict:
    leagues, league_urls, opta_rows, ranking_rows, _ = build_fixture_support_inputs()
    return build_support_documents(leagues, league_urls, ranking_rows, opta_rows=opta_rows)


def build_v2_model_history_match() -> dict:
    return {
        "matchId": 14689170,
        "timestamp": int(datetime(2026, 6, 20, 18, 0, tzinfo=UTC).timestamp()),
        "date": "2026-06-20",
        "savedAt": "2026-06-20T20:55:00Z",
        "homeTeamId": 100,
        "homeTeamName": "Arsenal",
        "awayTeamId": 101,
        "awayTeamName": "Bournemouth",
        "homeScore": 2,
        "awayScore": 1,
        "matchDetails": {
            "statistics": [
                {
                    "period": "ALL",
                    "groups": [
                        {
                            "groupName": "Match overview",
                            "statisticsItems": [
                                {"key": "totalShotsOnGoal", "homeValue": 13, "awayValue": 8},
                                {"key": "shotsOnGoal", "homeValue": 5, "awayValue": 3},
                                {"key": "cornerKicks", "homeValue": 7, "awayValue": 4},
                            ],
                        }
                    ],
                }
            ]
        },
    }


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


def test_v2_js_model_oracle_builds_lines_from_v2_profiles_and_raw_history() -> None:
    support_docs = build_v2_model_support_docs()
    source_rows = [
        {
            "source_file": "arsenal_home_match_stats.json",
            "source_path": "C:/tmp/arsenal_home_match_stats.json",
            "source_role": "home",
            "matches": [build_v2_model_history_match()],
        }
    ]
    docs = build_match_enrichment_documents(
        source_rows=source_rows,
        support_docs=support_docs,
    )
    fixture_doc = {
        "match_key": "sofascore:14689170",
        "source_match_id": "14689170",
        "source_date": "2026-06-20",
        "start_time": datetime(2026, 6, 20, 18, 0, tzinfo=UTC),
        "league_key": "premier-league",
        "league_name": "Premier League",
        "home_team_key": "premier-league:100",
        "away_team_key": "premier-league:101",
        "home_team_name": "Arsenal",
        "away_team_name": "Bournemouth",
    }
    teamprofiles = build_teamprofile_docs(
        match_stats_canonical=docs["match_stats_canonical"],
        match_results_canonical=docs["match_results"],
        raw_incidents=[],
        raw_shotmaps=[],
        support_docs=support_docs,
        profile_date="2026-06-22",
        generated_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
    )
    read_database = FakeReadDatabase(
        {
            "teamprofiles_v2": FakeReadCollection(teamprofiles),
            "match_results_canonical": FakeReadCollection(docs["match_results"]),
            "raw_match_statistics": FakeReadCollection(docs["raw_match_statistics"]),
            "fixtures_canonical": FakeReadCollection([fixture_doc]),
        }
    )
    oracle = V2JsModelOracle(read_database, support_docs)

    built = oracle.build_match_lines(
        match_info={
            "matchId": "future-arsenal-bournemouth",
            "matchKey": "future-arsenal-bournemouth",
            "homeTeam": "Arsenal",
            "awayTeam": "Bournemouth",
            "homeTeamKey": "premier-league:100",
            "awayTeamKey": "premier-league:101",
            "sourceDate": "2026-06-22",
            "startTime": datetime(2026, 6, 22, 18, 0, tzinfo=UTC),
        },
        offers=[
            {
                "statKey": "totalShots",
                "scope": "total",
                "period": "ALL",
                "line": 20.5,
                "odds": {"over": 1.82, "under": 2.02},
            }
        ],
    )

    assert built["errors"] == []
    assert len(built["lines"]) == 2
    assert {row["direction"] for row in built["lines"]} == {"over", "under"}
    assert all(row["sampleSize"] == 1 for row in built["lines"])
    assert all(row["betKey"].startswith("future-arsenal-bournemouth|arsenal|bournemouth|totalShots|total|ALL|") for row in built["lines"])
    assert all(row["homeTeam"] == "Arsenal" for row in built["lines"])
    assert all(row["awayTeam"] == "Bournemouth" for row in built["lines"])


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


def test_run_model_snapshot_build_accepts_empty_historical_offer_set() -> None:
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
        legacy_backtest_database=historical_database,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["matched_events"] == 1
    assert summary["model_snapshots"] == 0
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_model_snapshot_build_replays_historical_backtest_lines() -> None:
    historical_database = FakeHistoricalDatabase()
    historical_database["unibet-backtest"] = FakeHistoricalCollection([build_legacy_backtest_doc()])

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
        legacy_backtest_database=historical_database,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
        return_documents=True,
    )

    assert summary["matched_events"] == 1
    assert summary["market_offers"] == 2
    assert summary["model_snapshots"] == 3
    assert summary["oracle_error_count"] == 0
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
    model_snapshot_doc = summary["documents"]["model_snapshot_docs"][0]
    assert model_snapshot_doc["invalid_for_model"] is False
    assert model_snapshot_doc["snapshot_time_source"] == "legacy_doc.generatedAt"


def test_run_model_snapshot_build_replays_latest_forward_snapshot() -> None:
    historical_database = FakeHistoricalDatabase()
    historical_database["unibet-backtest"] = FakeHistoricalCollection([build_legacy_backtest_doc(with_snapshots=True)])

    summary = run_model_snapshot_build(
        targets=[
            {
                "match_key": "match-legacy-forward",
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
        source_workflow="run-unibet-forward.yml",
        snapshot_mode="forward",
        dry_run=True,
        legacy_backtest_database=historical_database,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
        return_documents=True,
    )

    assert summary["matched_events"] == 1
    assert summary["model_snapshots"] == 1
    assert summary["parity_status_counts"] == {"matched": 1}
    model_snapshot_doc = summary["documents"]["model_snapshot_docs"][0]
    assert model_snapshot_doc["selected_odds"] == 1.89
    assert model_snapshot_doc["snapshot_time_source"] == "legacy_snapshot.fetchedAt"
    assert model_snapshot_doc["invalid_for_model"] is False


def test_run_model_snapshot_build_preserves_legacy_settlement_reference_from_root_lines() -> None:
    historical_database = FakeHistoricalDatabase()
    legacy_doc = build_legacy_backtest_doc(with_snapshots=True)
    for line in legacy_doc["lines"]:
        if line["statKey"] == "cornerKicks" and line["scope"] == "total" and line["period"] == "ALL":
            if line["condition"] == "över":
                line["actual"] = 9
                line["win"] = False
            else:
                line["actual"] = 9
                line["win"] = True
    for snapshot in legacy_doc["snapshots"]:
        snapshot["lines"] = [deepcopy(line) for line in snapshot.get("lines", [])]
        for line in snapshot["lines"]:
            line.pop("actual", None)
            line.pop("win", None)
    historical_database["unibet-backtest"] = FakeHistoricalCollection([legacy_doc])

    summary = run_model_snapshot_build(
        targets=[
            {
                "match_key": "match-legacy-backtest-reference",
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
        legacy_backtest_database=historical_database,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
        return_documents=True,
    )

    doc = next(
        row
        for row in summary["documents"]["model_snapshot_docs"]
        if row["stat_key"] == "cornerKicks" and row["scope"] == "total" and row["direction"] == "over"
    )
    assert doc["legacy_actual_value"] == 9
    assert doc["legacy_settlement_result"] == "loss"
    assert doc["legacy_win"] is False
