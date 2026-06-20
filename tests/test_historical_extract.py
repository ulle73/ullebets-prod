import pandas as pd

from ullebets_v1.extract.historical_extract import flatten_ai_generated_bets, flatten_unibet_backtest_docs


def test_flatten_unibet_backtest_docs_emits_line_rows():
    docs = [
        {
            "matchId": 1,
            "league": "Premier League",
            "lines": [
                {
                    "betKey": "k1",
                    "statKey": "cornerKicks",
                    "period": "ALL",
                    "scope": "total",
                    "condition": "over",
                    "line": 9.5,
                    "odds": 1.95,
                    "actual": 11,
                    "win": True,
                }
            ],
        }
    ]
    rows = flatten_unibet_backtest_docs(docs)
    frame = pd.DataFrame(rows)
    assert frame.loc[0, "bet_key"] == "k1"
    assert frame.loc[0, "settlement_result"] == "win"


def test_flatten_ai_generated_bets_emits_directional_rows():
    docs = [
        {
            "slug": "doc-1",
            "generatedAt": "2026-01-01T12:00:00Z",
            "matchDate": "2026-01-02",
            "league": "Premier League",
            "homeTeam": "Home",
            "awayTeam": "Away",
            "lines": [
                {
                    "betKey": "k2",
                    "matchId": "m2",
                    "statKey": "shotsOnGoal",
                    "scope": "total",
                    "period": "ALL",
                    "direction": "over",
                    "line": 8.5,
                    "odds": 1.9,
                    "primaryEv": 4.2,
                    "actual": 9,
                    "win": True,
                }
            ],
        }
    ]
    rows = flatten_ai_generated_bets(docs)
    frame = pd.DataFrame(rows)
    assert frame.loc[0, "bet_key"] == "k2"
    assert frame.loc[0, "direction"] == "over"
    assert frame.loc[0, "settlement_result"] == "win"
