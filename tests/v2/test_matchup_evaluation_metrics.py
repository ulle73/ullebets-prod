import pytest
from ullebets_v2.matchup_evaluation.metrics import build_matchup_evaluation_summary


def result(
    key: str,
    verdict: str,
    *,
    market: str | None = None,
    rank: int = 1,
    score: float = 90,
    residual: float | None = None,
    direction: str = "over",
) -> dict:
    return {
        "observation_key": key,
        "match_key": key,
        "fixture_date_stockholm": "2026-08-22",
        "evidence_class": "forward",
        "valid_for_predictor": True,
        "predictor_verdict": verdict,
        "selected_direction": direction,
        "score": score,
        "rank_position": rank,
        "signed_residual": residual if residual is not None else (1 if verdict == "hit" else 0 if verdict == "push" else -1),
        "valid_for_market": market is not None,
        "market_verdict": market,
        "stake_units": 1 if market else 0,
        "pnl_units": .95 if market == "win" else -1 if market == "loss" else 0,
    }


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


def test_predictor_summary_compares_with_best_constant_direction() -> None:
    rows = [
        result("over-hit", "hit", direction="over", residual=2),
        result("under-hit", "hit", direction="under", residual=4),
        result("push", "push", direction="over", residual=0),
    ]

    predictor = build_matchup_evaluation_summary(rows, bootstrap_iterations=20)["predictor"]

    assert predictor["medianSignedResidual"] == pytest.approx(2)
    assert predictor["constantDirectionBaseline"] == {
        "overHitRatePct": pytest.approx(50),
        "underHitRatePct": pytest.approx(50),
        "bestDirection": "tie",
        "bestHitRatePct": pytest.approx(50),
        "liftPctPoints": pytest.approx(50),
    }


def test_predictor_summary_groups_fixed_score_buckets_with_sample_sizes() -> None:
    rows = [
        result("95-hit", "hit", score=95, residual=3),
        result("90-miss", "miss", score=90, residual=-1),
        result("85-hit", "hit", score=85, residual=2),
        result("75-push", "push", score=75, residual=0),
    ]

    buckets = build_matchup_evaluation_summary(rows, bootstrap_iterations=20)["predictor"]["scoreBuckets"]

    assert buckets == [
        {"key": "90_100", "label": "90–100", "resolved": 2, "nonPush": 2, "hits": 1, "misses": 1, "pushes": 0, "nonPushHitRatePct": pytest.approx(50), "medianSignedResidual": pytest.approx(1)},
        {"key": "80_89", "label": "80–89,9", "resolved": 1, "nonPush": 1, "hits": 1, "misses": 0, "pushes": 0, "nonPushHitRatePct": pytest.approx(100), "medianSignedResidual": pytest.approx(2)},
        {"key": "70_79", "label": "70–79,9", "resolved": 1, "nonPush": 0, "hits": 0, "misses": 0, "pushes": 1, "nonPushHitRatePct": None, "medianSignedResidual": pytest.approx(0)},
        {"key": "under_70", "label": "Under 70", "resolved": 0, "nonPush": 0, "hits": 0, "misses": 0, "pushes": 0, "nonPushHitRatePct": None, "medianSignedResidual": None},
    ]
