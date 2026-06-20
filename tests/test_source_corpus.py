import pandas as pd

from ullebets_v1.audit.source_corpus import build_source_corpus_summary


def test_build_source_corpus_summary_prefers_broadest_settled_primary_corpus():
    unibet = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "match_date": "2026-01-01",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 9.5,
                "direction": "over",
                "settlement_result": "win",
            },
            {
                "match_id": "m1",
                "match_date": "2026-01-01",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 9.5,
                "direction": "under",
                "settlement_result": "loss",
            },
            {
                "match_id": "m2",
                "match_date": "2026-01-02",
                "stat_key": "shotsOnGoal",
                "period": "ALL",
                "scope": "home",
                "line_value": 4.5,
                "direction": "over",
                "settlement_result": "win",
            },
        ]
    )
    ai_generated = pd.DataFrame(
        [
            {
                "match_id": "m3",
                "match_date": "2026-01-03",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "total",
                "line_value": 10.5,
                "direction": "over",
                "settlement_result": "win",
            }
        ]
    )
    auto_analysis = pd.DataFrame(
        [
            {
                "match_id": "m4",
                "match_date": "2026-01-04",
                "stat_key": "cornerKicks",
                "period": "ALL",
                "scope": "home",
                "line_value": 5.5,
                "direction": "over",
                "result": None,
            }
        ]
    )

    summary = build_source_corpus_summary(
        {
            "unibet_backtest_lines": unibet,
            "ai_generated_bet_lines": ai_generated,
            "auto_analysis_bets": auto_analysis,
        }
    )

    assert summary["chosen_primary_historical_corpus_key"] == "unibet_backtest_lines"
    assert "cornerKicks" in summary["model_ready_primary_stats_from_chosen_corpus"]
    assert "shotsOnGoal" in summary["model_ready_primary_stats_from_chosen_corpus"]
