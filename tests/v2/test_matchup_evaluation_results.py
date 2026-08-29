from datetime import UTC, datetime
import pytest

from ullebets_v2.matchup_evaluation.results import MatchupResultConflict, build_matchup_result_docs, merge_matchup_result

NOW = datetime(2026, 9, 1, 21, tzinfo=UTC)


def observation(market: bool = True) -> dict:
    return {"observation_key": "obs", "match_key": "m1", "stat_key": "cornerKicks", "period": "ALL", "scope": "total", "selected_direction": "over", "league_baseline": 10.7, "market_eligibility": "eligible" if market else "no_exact_market", "line_value": 10.5 if market else None, "selected_odds": 1.95 if market else None, "valid_for_predictor": True, "evidence_class": "forward"}


def build(market: bool = True, closings: list[dict] | None = None) -> dict:
    return build_matchup_result_docs(observations=[observation(market)], match_stats_canonical=[{"match_key": "m1", "stat_key": "cornerKicks", "period": "ALL", "scope": "all", "actual_value": 12}], match_results_canonical=[{"match_key": "m1", "home_score": 1, "away_score": 0}], closing_line_docs=closings or [], refreshed_at=NOW)[0]


def test_predictor_and_market_denominators_stay_separate() -> None:
    predictor_only = build(False)
    assert predictor_only["lifecycle_status"] == "resolved_predictor_only"
    assert predictor_only["predictor_verdict"] == "hit"
    assert predictor_only["market_verdict"] is None
    assert predictor_only["stake_units"] == 0
    assert build(True)["market_verdict"] == "win"


def test_t10_same_line_preferred_for_clv() -> None:
    rows = [{"match_key": "m1", "stat_key": "cornerKicks", "period": "ALL", "scope": "total", "line": 10.5, "closing_quality": "t30_fallback", "closing_snapshot_time": NOW, "closing_over_odds": 1.88}, {"match_key": "m1", "stat_key": "cornerKicks", "period": "ALL", "scope": "total", "line": 10.5, "closing_quality": "t10", "closing_snapshot_time": NOW, "closing_over_odds": 1.84}]
    result = build(True, rows)
    assert result["closing_quality"] == "t10"
    assert result["clv_pct"] == pytest.approx((1.95 / 1.84 - 1) * 100)


def test_terminal_conflict_fails_closed() -> None:
    original = {"observation_key": "obs", "lifecycle_status": "resolved_market", "actual_value": 12, "market_verdict": "win"}
    changed = {**original, "actual_value": 8, "market_verdict": "loss"}
    with pytest.raises(MatchupResultConflict): merge_matchup_result(original, changed)
