import pandas as pd

from ullebets_v1.normalize.outcomes import annotate_market_line_outcomes, authoritative_settlement_result


def test_authoritative_settlement_result_handles_push():
    assert authoritative_settlement_result(5, 4.5, "over") == "win"
    assert authoritative_settlement_result(4, 4.5, "over") == "loss"
    assert authoritative_settlement_result(4.5, 4.5, "over") == "push"
    assert authoritative_settlement_result(5, 4.5, "under") == "loss"
    assert authoritative_settlement_result(4, 4.5, "under") == "win"
    assert authoritative_settlement_result(4.5, 4.5, "under") == "push"


def test_annotate_market_line_outcomes_regrades_primary_target_from_teamstats():
    market_lines = pd.DataFrame(
        [
            {
                "match_id": None,
                "resolved_teamstats_match_id": "ts1",
                "match_date": "2026-01-01",
                "home_team_name": "Home",
                "away_team_name": "Away",
                "bet_key": "b1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "away",
                "direction": "over",
                "line_value": 0.5,
                "odds_decimal": 1.9,
                "actual_value": 1.0,
                "settlement_result": "loss",
            }
        ]
    )
    team_stats_long = pd.DataFrame(
        [
            {
                "match_id": "ts1",
                "period": "ALL",
                "stat_item_key": "cornerKicks",
                "team_role": "home",
                "team_value": 2.0,
                "total_value": 3.0,
            },
            {
                "match_id": "ts1",
                "period": "ALL",
                "stat_item_key": "cornerKicks",
                "team_role": "away",
                "team_value": 1.0,
                "total_value": 3.0,
            },
        ]
    )

    enriched = annotate_market_line_outcomes(market_lines, team_stats_long)

    row = enriched.iloc[0]
    assert row["exposure_match_id"] == "ts1"
    assert row["teamstats_actual_value"] == 1.0
    assert row["actual_value"] == 1.0
    assert row["legacy_settlement_result"] == "loss"
    assert row["settlement_result"] == "win"
    assert row["verified_settlement_result"] == "win"
    assert row["outcome_verification_status"] == "verified_legacy_settlement_mismatch"
    assert bool(row["has_authoritative_teamstats_outcome"]) is True


def test_annotate_market_line_outcomes_excludes_unverifiable_primary_target_rows():
    market_lines = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "resolved_teamstats_match_id": "ts1",
                "match_date": "2026-01-01",
                "home_team_name": "Home",
                "away_team_name": "Away",
                "bet_key": "b1",
                "stat_key": "shotsOnGoal",
                "period": "ALL",
                "scope": "home",
                "direction": "over",
                "line_value": 3.5,
                "odds_decimal": 1.9,
                "actual_value": 4.0,
                "settlement_result": "win",
            }
        ]
    )

    enriched = annotate_market_line_outcomes(market_lines, pd.DataFrame())

    row = enriched.iloc[0]
    assert pd.isna(row["actual_value"])
    assert row["settlement_result"] is None
    assert row["outcome_verification_status"] == "missing_teamstats_actual"
    assert bool(row["has_authoritative_teamstats_outcome"]) is False
