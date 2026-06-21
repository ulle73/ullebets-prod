from ullebets_v2.support.opta import merge_opta_fields
from ullebets_v2.support.schemas import build_support_documents


def test_build_support_documents_creates_leagues_and_teams() -> None:
    leagues = {
        "Premier League": {
            "leagueId": 17,
            "categoryId": 1,
            "seasonId": 61627,
            "teams": [
                {"id": 100, "name": "Arsenal", "slug": "arsenal"},
                {"id": 101, "name": "Chelsea", "slug": "chelsea"},
            ],
        }
    }
    league_urls = {"Premier League": "https://example.test/premier-league"}
    ranking_rows = [{"league": "Premier League", "ranking": {"cornerKicks": {"avg": 9.9}}}]

    docs = build_support_documents(leagues, league_urls, ranking_rows)

    assert docs["source"]["source_type"] == "support_sync"
    assert docs["leagues"][0]["league_key"] == "premier-league"
    assert docs["leagues"][0]["unibet_league_url"] == "https://example.test/premier-league"
    assert docs["teams"][0]["team_key"] == "premier-league:100"
    assert docs["rankings"][0]["league_key"] == "premier-league"


def test_merge_opta_fields_updates_matching_team() -> None:
    teams = [
        {
            "team_key": "premier-league:100",
            "team_name": "Arsenal",
            "opta_id": 42,
            "opta_rank": None,
            "opta_rating": None,
        }
    ]
    opta_rows = [
        {"optaId": 42, "rank": 11, "currentRating": 88.7},
    ]

    merged = merge_opta_fields(teams, opta_rows)

    assert merged[0]["opta_rank"] == 11
    assert merged[0]["opta_rating"] == 88.7
