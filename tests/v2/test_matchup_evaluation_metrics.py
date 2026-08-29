import pytest
from ullebets_v2.matchup_evaluation.metrics import build_matchup_evaluation_summary


def result(key: str, verdict: str, *, market: str | None = None, rank: int = 1) -> dict:
    return {"observation_key": key, "match_key": key, "fixture_date_stockholm": "2026-08-22", "evidence_class": "forward", "valid_for_predictor": True, "predictor_verdict": verdict, "score": 90, "rank_position": rank, "signed_residual": 1 if verdict == "hit" else -1, "valid_for_market": market is not None, "market_verdict": market, "stake_units": 1 if market else 0, "pnl_units": .95 if market == "win" else -1 if market == "loss" else 0}


def test_predictor_and_market_denominators_are_independent() -> None:
    summary = build_matchup_evaluation_summary([result("a", "hit"), result("b", "miss", market="loss"), result("c", "hit", market="win")], bootstrap_iterations=20)
    assert summary["predictor"]["resolved"] == 3
    assert summary["predictor"]["nonPushHitRatePct"] == pytest.approx(66.6667)
    assert summary["market"]["resolved"] == 2
    assert summary["market"]["roiPct"] == pytest.approx(-2.5)


def test_legacy_is_separate() -> None:
    legacy = {**result("legacy", "miss"), "evidence_class": "legacy_descriptive", "valid_for_predictor": False}
    summary = build_matchup_evaluation_summary([result("a", "hit"), legacy], bootstrap_iterations=20)
    assert summary["predictor"]["resolved"] == 1
    assert summary["legacyDescriptive"]["resolved"] == 1
