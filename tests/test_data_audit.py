import pandas as pd

from ullebets_v1.audit.data_audit import build_audit_summary, summarize_filter_reasons


def test_summarize_filter_reasons_counts_rows():
    rows = [
        {"filter_reason": None},
        {"filter_reason": "missing_outcome"},
        {"filter_reason": "missing_outcome"},
    ]
    summary = summarize_filter_reasons(rows)
    assert summary["kept"] == 1
    assert summary["filtered"]["missing_outcome"] == 2


def test_build_audit_summary_surfaces_two_sided_primary_market_completeness():
    market_lines = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "over",
                "filter_reason": None,
                "is_primary_target": True,
                "has_clv": False,
                "has_teamstats_match": True,
                "match_mapping_method": "exact_match_id",
            },
            {
                "match_id": "m1",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "direction": "under",
                "filter_reason": None,
                "is_primary_target": True,
                "has_clv": False,
                "has_teamstats_match": True,
                "match_mapping_method": "exact_match_id",
            },
            {
                "match_id": "m2",
                "stat_key": "shotsOnGoal",
                "period": "ALL",
                "scope": "home",
                "direction": "over",
                "filter_reason": None,
                "is_primary_target": True,
                "has_clv": False,
                "has_teamstats_match": True,
                "match_mapping_method": "exact_match_id",
            },
        ]
    )
    coverage = pd.DataFrame(
        [
            {"filter_reason": None},
            {"filter_reason": None},
            {"filter_reason": None},
        ]
    )
    team_stats_long = pd.DataFrame([{"stat_item_key": "cornerKicks"}])

    summary = build_audit_summary(
        market_lines=market_lines,
        coverage=coverage,
        team_stats_long=team_stats_long,
    )

    assert summary["primary_target_market_completeness"]["cornerKicks"]["two_sided_segments"] == 1
    assert summary["primary_target_market_completeness"]["shotsOnGoal"]["over_only_segments"] == 1
    assert summary["primary_target_market_completeness"]["shotsOnGoal"]["market_side_policy"] == "over_only"
    assert summary["primary_target_market_completeness"]["shotsOnGoal"]["model_ready_segments"] == 1
    assert "shotsOnGoal" in summary["primary_target_model_ready_stat_keys"]
