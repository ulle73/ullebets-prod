from datetime import UTC, datetime
from ullebets_v2.matchup_evaluation.legacy import build_legacy_matchup_evaluation_docs


def row(direction: str, score: float) -> dict:
    return {"entry_key": direction, "snapshot_date": "2026-08-22", "match_key": "m1", "stat_key": "cornerKicks", "period": "ALL", "scope": "total", "condition": direction, "score": score, "forecast": {"leagueBaseline": 11.7}, "outcome_status": "resolved", "actual_value": 14}


def test_legacy_is_deduplicated_and_never_forward_proof() -> None:
    observations, results = build_legacy_matchup_evaluation_docs(score_rows=[row("over", 82), row("under", 18)], generated_at=datetime(2026, 8, 29, tzinfo=UTC))
    assert len(observations) == len(results) == 1
    assert observations[0]["evidence_class"] == "legacy_descriptive"
    assert observations[0]["valid_for_predictor"] is False
    assert results[0]["predictor_verdict"] == "hit"


def test_legacy_tie_is_not_guessed() -> None:
    assert build_legacy_matchup_evaluation_docs(score_rows=[row("over", 50), row("under", 50)], generated_at=datetime(2026, 8, 29, tzinfo=UTC)) == ([], [])
