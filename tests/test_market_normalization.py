from ullebets_v1.normalize.market_lines import normalize_market_line, resolve_filter_reason


def test_normalize_market_line_maps_condition_to_direction():
    row = normalize_market_line(
        {
            "matchId": 1,
            "league": "Premier League",
            "homeTeam": "A",
            "awayTeam": "B",
        },
        {
            "betKey": "k1",
            "statKey": "cornerKicks",
            "period": "ALL",
            "scope": "total",
            "condition": "över",
            "line": 9.5,
            "odds": 1.9,
            "actual": 10,
            "win": True,
        },
    )
    assert row["direction"] == "over"
    assert row["settlement_result"] == "win"


def test_resolve_filter_reason_flags_missing_outcome():
    reason = resolve_filter_reason(
        stat_key="cornerKicks",
        period="ALL",
        scope="total",
        line_value=9.5,
        odds_decimal=1.9,
        settlement_result=None,
        has_teamstats_match=True,
    )
    assert reason == "missing_outcome"
