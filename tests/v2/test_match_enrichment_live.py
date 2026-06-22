from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.enrichment.live import (
    EnrichmentSourceConfig,
    HttpJsonResponse,
    build_live_match_enrichment_source_rows,
)
from ullebets_v2.enrichment.replay import build_match_enrichment_documents
from ullebets_v2.enrichment.service import run_live_match_enrichment_window
from ullebets_v2.support.schemas import build_support_documents


def build_support_docs() -> dict:
    return build_support_documents(
        leagues={
            "A-League Men": {
                "leagueId": 136,
                "categoryId": 34,
                "seasonId": 82603,
                "slug": "a-league-men",
                "teams": [
                    {"id": 2946, "name": "Adelaide United", "slug": "adelaide-united"},
                    {"id": 42210, "name": "Melbourne City", "slug": "melbourne-city"},
                ],
            }
        },
        league_urls={"A-League Men": "https://example.test/a-league-men"},
        ranking_rows=[],
        captured_at=datetime(2026, 6, 23, 10, 0, tzinfo=UTC),
    )


def build_fixture_target() -> dict:
    return {
        "match_key": "sofascore:14671649",
        "source_match_id": 14671649,
        "source_date": "2025-11-21",
        "start_time": datetime(2025, 11, 21, 8, 35, tzinfo=UTC),
        "league_key": "a-league-men",
        "league_name": "A-League Men",
        "home_team_name": "Adelaide United",
        "away_team_name": "Melbourne City",
        "source_path": r"C:\dev\frontend\ullebets-vecel\matches-for-date\fixtures-2025-11-21.json",
    }


def test_build_live_match_enrichment_source_rows_preserves_raw_metadata() -> None:
    def transport(url: str, headers: dict[str, str], timeout_seconds: int) -> HttpJsonResponse:  # noqa: ARG001
        if url.endswith("/event/14671649"):
            return HttpJsonResponse(
                status=200,
                headers={"content-type": "application/json"},
                data={
                    "event": {
                        "homeTeam": {"id": 2946, "name": "Adelaide United"},
                        "awayTeam": {"id": 42210, "name": "Melbourne City"},
                        "homeScore": {"current": 2},
                        "awayScore": {"current": 1},
                    }
                },
            )
        if url.endswith("/event/14671649/statistics"):
            return HttpJsonResponse(
                status=200,
                headers={"content-type": "application/json"},
                data={
                    "statistics": [
                        {
                            "period": "ALL",
                            "groups": [
                                {
                                    "groupName": "Match overview",
                                    "statisticsItems": [
                                        {"key": "totalShotsOnGoal", "homeValue": 11, "awayValue": 10},
                                        {"key": "shotsOnGoal", "homeValue": 4, "awayValue": 3},
                                        {"key": "cornerKicks", "homeValue": 6, "awayValue": 5},
                                    ],
                                }
                            ],
                        }
                    ]
                },
            )
        if url.endswith("/event/14671649/incidents"):
            return HttpJsonResponse(
                status=200,
                headers={"content-type": "application/json"},
                data={"incidents": [{"incidentType": "goal", "homeScore": 1, "awayScore": 0, "time": 5}]},
            )
        if url.endswith("/event/14671649/shotmap"):
            return HttpJsonResponse(
                status=200,
                headers={"content-type": "application/json"},
                data={"shotmap": [{"isHome": True, "time": 10}]},
            )
        return HttpJsonResponse(status=404, headers={}, data=None)

    live_rows = build_live_match_enrichment_source_rows(
        targets=[build_fixture_target()],
        source_config=EnrichmentSourceConfig.from_env({}),
        transport=transport,
        fetched_at=datetime(2026, 6, 23, 10, 5, tzinfo=UTC),
    )

    assert len(live_rows["source_rows"]) == 1
    assert live_rows["match_rows"][0]["error"] is None

    docs = build_match_enrichment_documents(
        source_rows=live_rows["source_rows"],
        support_docs=build_support_docs(),
    )

    assert docs["raw_match_statistics"][0]["source_name"] == "sofascore-public-statistics"
    assert docs["raw_incidents"][0]["source_name"] == "sofascore-public-incidents"
    assert docs["raw_shotmaps"][0]["source_name"] == "sofascore-public-shotmap"
    assert docs["raw_results"][0]["source_name"] == "sofascore-public-event"
    assert docs["match_results"][0]["home_score"] == 2
    assert docs["match_results"][0]["away_score"] == 1


def test_run_live_match_enrichment_window_flags_missing_statistics() -> None:
    def transport(url: str, headers: dict[str, str], timeout_seconds: int) -> HttpJsonResponse:  # noqa: ARG001
        if url.endswith("/event/14671649"):
            return HttpJsonResponse(
                status=200,
                headers={"content-type": "application/json"},
                data={
                    "event": {
                        "homeTeam": {"id": 2946, "name": "Adelaide United"},
                        "awayTeam": {"id": 42210, "name": "Melbourne City"},
                    }
                },
            )
        return HttpJsonResponse(status=404, headers={}, data=None)

    summary = run_live_match_enrichment_window(
        targets=[build_fixture_target()],
        support_docs=build_support_docs(),
        source_workflow="update-teamstats-and-teamprofiles.yml",
        source_config=EnrichmentSourceConfig.from_env({}),
        dry_run=True,
        transport=transport,
    )

    assert summary["target_matches"] == 1
    assert summary["matched_targets"] == 0
    assert summary["errors"] == 1
    assert summary["raw_match_statistics"] == 0
    assert summary["match_results_canonical"] == 0
    assert summary["parity_status_counts"] == {"mismatch": 1}
    assert summary["audit_status_counts"] == {"warn": 1}


def test_run_live_match_enrichment_window_recovers_scores_from_incidents() -> None:
    def transport(url: str, headers: dict[str, str], timeout_seconds: int) -> HttpJsonResponse:  # noqa: ARG001
        if url.endswith("/event/14671649"):
            return HttpJsonResponse(status=403, headers={}, data=None)
        if url.endswith("/event/14671649/statistics"):
            return HttpJsonResponse(
                status=200,
                headers={"content-type": "application/json"},
                data={
                    "statistics": [
                        {
                            "period": "ALL",
                            "groups": [
                                {
                                    "groupName": "Match overview",
                                    "statisticsItems": [
                                        {"key": "cornerKicks", "homeValue": 6, "awayValue": 5},
                                    ],
                                }
                            ],
                        }
                    ]
                },
            )
        if url.endswith("/event/14671649/incidents"):
            return HttpJsonResponse(
                status=200,
                headers={"content-type": "application/json"},
                data={
                    "incidents": [
                        {"text": "HT", "homeScore": 1, "awayScore": 0, "time": 45, "addedTime": 999},
                        {"text": "FT", "homeScore": 2, "awayScore": 1, "time": 90, "addedTime": 999},
                    ]
                },
            )
        if url.endswith("/event/14671649/shotmap"):
            return HttpJsonResponse(
                status=200,
                headers={"content-type": "application/json"},
                data={"shotmap": [{"isHome": True, "time": 10}]},
            )
        return HttpJsonResponse(status=404, headers={}, data=None)

    summary = run_live_match_enrichment_window(
        targets=[build_fixture_target()],
        support_docs=build_support_docs(),
        source_workflow="update-teamstats-and-teamprofiles.yml",
        source_config=EnrichmentSourceConfig.from_env({}),
        dry_run=True,
        transport=transport,
    )

    assert summary["errors"] == 0
    assert summary["matched_targets"] == 1
    assert summary["match_results_canonical"] == 1
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["match_rows"][0]["result_source"] == "sofascore-public-incidents"
    assert summary["match_rows"][0]["has_scores"] == True
