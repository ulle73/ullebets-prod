from datetime import UTC, datetime
from pathlib import Path

from ullebets_v2.fixtures.replay import build_fixture_documents, iter_target_dates
from ullebets_v2.support.schemas import build_support_documents, slugify


def test_slugify_removes_diacritics_for_support_keys() -> None:
    assert slugify("Brasileirão Série A") == "brasileirao-serie-a"


def test_build_fixture_documents_maps_support_ids_and_slugs() -> None:
    support_docs = build_support_documents(
        leagues={
            "Brasileirão Série A": {
                "leagueId": 325,
                "categoryId": 13,
                "seasonId": 72034,
                "slug": "brasileirao-serie-a",
                "teams": [
                    {"id": 1977, "name": "Atlético Mineiro", "slug": "atletico-mineiro"},
                    {"id": 1959, "name": "Sport Recife", "slug": "sport-recife"},
                ],
            }
        },
        league_urls={"Brasileirão Série A": "https://example.test/brasileirao"},
        ranking_rows=[],
        captured_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
    )
    payload = {
        "date": "2025-10-08",
        "savedAt": "2025-10-08T19:53:08.599Z",
        "matches": [
            {
                "id": 14689178,
                "startTimestamp": 1759960800,
                "slug": "atletico-mineiro-sport-recife",
                "status": {"type": "notstarted"},
                "season": {"id": 72034},
                "tournament": {
                    "id": 83,
                    "name": "Brasileirão Betano",
                    "slug": "brasileirao-serie-a",
                    "category": {"id": 13, "name": "Brazil"},
                    "uniqueTournament": {
                        "id": 325,
                        "name": "Brasileirão Betano",
                        "slug": "brasileirao-serie-a",
                    },
                },
                "homeTeam": {"id": 1977, "name": "Atlético Mineiro", "slug": "atletico-mineiro"},
                "awayTeam": {"id": 1959, "name": "Sport Recife", "slug": "sport-recife"},
            }
        ],
    }

    docs = build_fixture_documents(
        payload=payload,
        support_docs=support_docs,
        source_path=Path(r"C:\dev\frontend\ullebets-vecel\matches-for-date\fixtures-2025-10-08.json"),
    )

    assert docs["raw"]["source_date"] == "2025-10-08"
    assert docs["raw"]["match_count"] == 1
    assert docs["canonical"][0]["match_key"] == "sofascore:14689178"
    assert docs["canonical"][0]["league_key"] == "brasileirao-serie-a"
    assert docs["canonical"][0]["home_team_key"] == "brasileirao-serie-a:1977"
    assert docs["canonical"][0]["away_team_key"] == "brasileirao-serie-a:1959"
    assert docs["canonical"][0]["mapping_confidence"] == "exact_support_ids"
    assert docs["canonical"][0]["status_type"] == "notstarted"


def test_iter_target_dates_builds_closed_window() -> None:
    assert iter_target_dates("2026-06-21", "2026-06-23") == [
        "2026-06-21",
        "2026-06-22",
        "2026-06-23",
    ]
