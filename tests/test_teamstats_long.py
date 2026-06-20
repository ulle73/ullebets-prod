from ullebets_v1.normalize.teamstats_long import extract_stat_rows


def test_extract_stat_rows_preserves_all_period_stat_keys():
    match = {
        "matchId": 1,
        "timestamp": 1700000000,
        "date": "2024-01-01",
        "homeTeamName": "A",
        "awayTeamName": "B",
        "matchDetails": {
            "statistics": [
                {
                    "period": "ALL",
                    "groups": [
                        {
                            "groupName": "Shots",
                            "statisticsItems": [
                                {
                                    "key": "totalShots",
                                    "name": "Total shots",
                                    "homeValue": 10,
                                    "awayValue": 7,
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    }
    rows = extract_stat_rows(match)
    assert rows[0]["period"] == "ALL"
    assert rows[0]["stat_item_key"] == "totalShots"
    assert rows[0]["total_value"] == 17.0
    assert rows[0]["team_role"] == "home"
    assert rows[1]["team_role"] == "away"
