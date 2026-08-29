from copy import deepcopy
from datetime import UTC, datetime

import pytest

from tests.v2.test_teamprofiles import FakeCollection
from ullebets_v2.matchup_evaluation.observations import (
    ImmutableMatchupObservationConflict, build_matchup_observation_docs,
    observation_fingerprint, observation_key, persist_matchup_observations,
    select_comparable_offer,
)

NOW = datetime(2026, 8, 31, 18, tzinfo=UTC)


def matchup(direction: str, score: float) -> dict:
    return {"match_key": "m1", "stat_key": "cornerKicks", "period": "ALL", "scope": "total", "condition": direction, "score": score, "rank_position": 1, "forecast": {"leagueBaseline": 10.7}, "ranking_method": "rolling_12_weighted_45d"}


def snapshot(key: str, odds: float, line: float) -> dict:
    return {"snapshot_key": key, "offer_key": key, "match_key": "m1", "stat_key": "cornerKicks", "period": "ALL", "scope": "total", "snapshot_label": "T_MINUS_1D", "snapshot_time": NOW, "match_start_time": datetime(2026, 9, 1, 18, tzinfo=UTC), "line": line, "over_odds": odds, "under_odds": 1.9, "invalid_for_model": False}


def test_freezes_one_direction_and_nearest_comparable_offer() -> None:
    selected = select_comparable_offer([snapshot("b", 2.02, 11.5), snapshot("a", 1.98, 12.5)], "over")
    assert selected and selected["offer_key"] == "b"
    docs = build_matchup_observation_docs(fixture={"match_key": "m1", "fixture_date_stockholm": "2026-09-01", "start_time": "2026-09-01T18:00:00Z"}, matchup_rows=[matchup("over", 82), matchup("under", 18)], market_snapshot_rows=[snapshot("a", 1.98, 12.5)], captured_at=NOW)
    assert len(docs) == 1
    assert docs[0]["selected_direction"] == "over"
    assert docs[0]["valid_for_predictor"] is True
    assert docs[0]["selected_odds"] == 1.98


def test_tie_and_late_capture_are_excluded() -> None:
    tied = build_matchup_observation_docs(fixture={"match_key": "m1", "fixture_date_stockholm": "2026-09-01", "start_time": "2026-09-01T18:00:00Z"}, matchup_rows=[matchup("over", 50), matchup("under", 50)], market_snapshot_rows=[], captured_at=NOW)[0]
    assert tied["exclusion_reason"] == "direction_tie"
    late = build_matchup_observation_docs(fixture={"match_key": "m1", "fixture_date_stockholm": "2026-09-01", "start_time": "2026-09-01T18:00:00Z"}, matchup_rows=[matchup("over", 80), matchup("under", 20)], market_snapshot_rows=[], captured_at=datetime(2026, 9, 1, 4, tzinfo=UTC))[0]
    assert late["exclusion_reason"] == "outside_t1d_window"


def test_immutable_replay_and_conflict() -> None:
    collection = FakeCollection([])
    doc = {"observation_key": observation_key("m1", "cornerKicks", "ALL", "total"), "score": 82}
    doc["observation_fingerprint_sha256"] = observation_fingerprint(doc)
    assert persist_matchup_observations(collection, [doc])["inserted"] == 1
    assert persist_matchup_observations(collection, [deepcopy(doc)])["existing"] == 1
    changed = deepcopy(doc); changed["score"] = 81; changed["observation_fingerprint_sha256"] = observation_fingerprint(changed)
    with pytest.raises(ImmutableMatchupObservationConflict): persist_matchup_observations(collection, [changed])
