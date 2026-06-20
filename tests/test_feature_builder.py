import pandas as pd

from ullebets_v1.features.rolling import last_n_average
from ullebets_v1.features.builder import build_market_points
from ullebets_v1.backtest.metrics import poisson_probabilities_for_line


def test_last_n_average_uses_only_rows_before_cutoff():
    rows = [
        {"kickoff_ts": 10, "value": 5},
        {"kickoff_ts": 20, "value": 7},
        {"kickoff_ts": 30, "value": 9},
    ]
    assert last_n_average(rows, cutoff_ts=25, n=2, value_key="value") == 6.0


def test_poisson_probabilities_for_half_line_sum_to_one():
    p_over, p_under, p_push = poisson_probabilities_for_line(10.0, 9.5)
    assert round(p_over + p_under + p_push, 8) == 1.0
    assert p_push == 0.0


def test_build_market_points_marks_canonical_lines_for_two_sided_and_over_only_markets():
    market_lines = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "resolved_teamstats_match_id": "ts1",
                "match_date": "2026-01-01",
                "league_name": "Premier League",
                "home_team_name": "Home",
                "away_team_name": "Away",
                "period": "ALL",
                "scope": "total",
                "stat_key": "cornerKicks",
                "line_value": 9.5,
                "direction": "over",
                "odds_decimal": 1.91,
                    "actual_value": 10.0,
                    "settlement_result": "win",
                    "has_clv": False,
                    "match_mapping_method": "exact_match_id",
                    "filter_reason": None,
                    "is_primary_target": True,
                },
            {
                "match_id": "m1",
                "resolved_teamstats_match_id": "ts1",
                "match_date": "2026-01-01",
                "league_name": "Premier League",
                "home_team_name": "Home",
                "away_team_name": "Away",
                "period": "ALL",
                "scope": "total",
                "stat_key": "cornerKicks",
                "line_value": 9.5,
                "direction": "under",
                "odds_decimal": 1.91,
                    "actual_value": 10.0,
                    "settlement_result": "loss",
                    "has_clv": False,
                    "match_mapping_method": "exact_match_id",
                    "filter_reason": None,
                    "is_primary_target": True,
                },
            {
                "match_id": "m1",
                "resolved_teamstats_match_id": "ts1",
                "match_date": "2026-01-01",
                "league_name": "Premier League",
                "home_team_name": "Home",
                "away_team_name": "Away",
                "period": "ALL",
                "scope": "total",
                "stat_key": "cornerKicks",
                "line_value": 10.5,
                "direction": "over",
                "odds_decimal": 1.72,
                    "actual_value": 10.0,
                    "settlement_result": "loss",
                    "has_clv": False,
                    "match_mapping_method": "exact_match_id",
                    "filter_reason": None,
                    "is_primary_target": True,
                },
            {
                "match_id": "m1",
                "resolved_teamstats_match_id": "ts1",
                "match_date": "2026-01-01",
                "league_name": "Premier League",
                "home_team_name": "Home",
                "away_team_name": "Away",
                "period": "ALL",
                "scope": "total",
                "stat_key": "cornerKicks",
                "line_value": 10.5,
                "direction": "under",
                "odds_decimal": 2.15,
                    "actual_value": 10.0,
                    "settlement_result": "win",
                    "has_clv": False,
                    "match_mapping_method": "exact_match_id",
                    "filter_reason": None,
                    "is_primary_target": True,
                },
            {
                "match_id": "m2",
                "resolved_teamstats_match_id": "ts2",
                "match_date": "2026-01-02",
                "league_name": "Premier League",
                "home_team_name": "Home2",
                "away_team_name": "Away2",
                "period": "ALL",
                "scope": "home",
                "stat_key": "shotsOnGoal",
                "line_value": 4.5,
                "direction": "over",
                "odds_decimal": 2.02,
                    "actual_value": 5.0,
                    "settlement_result": "win",
                    "has_clv": False,
                    "match_mapping_method": "exact_match_id",
                    "filter_reason": None,
                    "is_primary_target": True,
                },
            {
                "match_id": "m2",
                "resolved_teamstats_match_id": "ts2",
                "match_date": "2026-01-02",
                "league_name": "Premier League",
                "home_team_name": "Home2",
                "away_team_name": "Away2",
                "period": "ALL",
                "scope": "home",
                "stat_key": "shotsOnGoal",
                "line_value": 3.5,
                "direction": "over",
                "odds_decimal": 1.55,
                    "actual_value": 5.0,
                    "settlement_result": "win",
                    "has_clv": False,
                    "match_mapping_method": "exact_match_id",
                    "filter_reason": None,
                    "is_primary_target": True,
                },
            {
                "match_id": "m2",
                "resolved_teamstats_match_id": "ts2",
                "match_date": "2026-01-02",
                "league_name": "Premier League",
                "home_team_name": "Home2",
                "away_team_name": "Away2",
                "period": "ALL",
                "scope": "home",
                "stat_key": "shotsOnGoal",
                "line_value": 5.5,
                "direction": "over",
                "odds_decimal": 2.65,
                    "actual_value": 5.0,
                    "settlement_result": "loss",
                    "has_clv": False,
                    "match_mapping_method": "exact_match_id",
                    "filter_reason": None,
                    "is_primary_target": True,
                },
        ]
    )
    line_clv = pd.DataFrame(
        columns=["match_id", "stat_key", "period", "scope", "direction", "line_value", "clv_pct", "closing_odds"]
    )

    points = build_market_points(market_lines=market_lines, line_clv=line_clv)

    canonical = points[(points["match_id"] == "m1") & (points["is_canonical_line"] == True)]
    assert len(canonical) == 1
    assert canonical.iloc[0]["line_value"] == 9.5
    assert canonical.iloc[0]["line_rank_in_segment"] == 1

    one_sided = points[(points["match_id"] == "m2") & (points["line_value"] == 4.5)].iloc[0]
    assert one_sided["has_both_sides"] == False
    assert one_sided["market_side_policy"] == "over_only"
    assert one_sided["is_model_eligible_segment"] == True
    assert one_sided["is_canonical_line"] == True
    assert one_sided["line_rank_in_segment"] == 1
