from datetime import UTC, datetime

from tests.v2.test_teamprofiles import FakeCollection, FakeDatabase
from ullebets_v2.matchup_evaluation.materialize import materialize_matchup_observations
from ullebets_v2.matchup_evaluation.observations import build_matchup_observation_docs
from ullebets_v2.storage.collections import (
    FIXTURES_CANONICAL,
    MARKET_SNAPSHOTS,
    MATCHUP_OBSERVATIONS,
    MATCHUPS_SCORE,
)


def test_materializer_skips_already_frozen_observation_on_later_capture() -> None:
    fixture = {
        "match_key": "m1",
        "fixture_date_stockholm": "2026-09-05",
        "start_time": datetime(2026, 9, 5, 20, tzinfo=UTC),
    }
    matchup_rows = [
        {
            "match_key": "m1",
            "snapshot_date": "2026-09-05",
            "stat_key": "cornerKicks",
            "period": "1ST",
            "scope": "away",
            "condition": direction,
            "score": score,
            "rank_position": 1,
            "forecast": {"leagueBaseline": 2.5},
            "ranking_method": "rolling_12_weighted_45d",
        }
        for direction, score in (("over", 70), ("under", 30))
    ]
    snapshot = {
        "snapshot_key": "s1",
        "offer_key": "o1",
        "match_key": "m1",
        "stat_key": "cornerKicks",
        "period": "1ST",
        "scope": "away",
        "snapshot_label": "T_MINUS_1D",
        "snapshot_time": datetime(2026, 9, 4, 20, tzinfo=UTC),
        "match_start_time": fixture["start_time"],
        "line": 2.5,
        "over_odds": 1.95,
        "under_odds": 1.9,
        "invalid_for_model": False,
    }
    first_capture = datetime(2026, 9, 4, 18, tzinfo=UTC)
    [frozen] = build_matchup_observation_docs(
        fixture=fixture,
        matchup_rows=matchup_rows,
        market_snapshot_rows=[snapshot],
        captured_at=first_capture,
    )
    database = FakeDatabase(
        {
            FIXTURES_CANONICAL: FakeCollection([fixture]),
            MARKET_SNAPSHOTS: FakeCollection([snapshot]),
            MATCHUPS_SCORE: FakeCollection(matchup_rows),
            MATCHUP_OBSERVATIONS: FakeCollection([frozen]),
        }
    )

    summary = materialize_matchup_observations(
        database=database,
        match_keys=["m1"],
        captured_at=datetime(2026, 9, 4, 19, tzinfo=UTC),
    )

    assert summary["observation_docs"] == 1
    assert summary["frozen_observations"] == 1
    assert summary["new_observation_docs"] == 0
    assert summary["persistence"] == {"inserted": 0, "existing": 1, "conflicts": 0}
    assert database[MATCHUP_OBSERVATIONS].docs == [frozen]
