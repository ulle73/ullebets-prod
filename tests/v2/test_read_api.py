from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import ullebets_v2.read_api.service as read_service
from ullebets_v2.read_api.service import read_auto, read_dashboard, read_match_detail, read_results


class FakeCursor(list):
    def sort(self, spec):
        rows = list(self)
        for field, direction in reversed(spec):
            rows.sort(key=lambda row: row.get(field) or "", reverse=direction < 0)
        return FakeCursor(rows)

    def skip(self, value: int):
        return FakeCursor(self[value:])

    def limit(self, value: int):
        return FakeCursor(self[:value])


class FakeCollection:
    def __init__(self, rows=()):
        self.rows = list(rows)

    @staticmethod
    def _matches(row, query):
        for key, expected in query.items():
            actual = row.get(key)
            if isinstance(expected, dict):
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
            elif isinstance(expected, dict) and "$lte" in expected:
                if actual is None or actual > expected["$lte"]:
                    return False
            elif actual != expected:
                return False
        return True

    def find(self, query=None, projection=None):
        del projection
        query = query or {}
        return FakeCursor([row.copy() for row in self.rows if self._matches(row, query)])

    def find_one(self, query=None, projection=None, sort=None):
        cursor = self.find(query, projection)
        if sort:
            cursor = cursor.sort(sort)
        return cursor[0] if cursor else None

    def count_documents(self, query=None):
        query = query or {}
        return sum(1 for row in self.rows if self._matches(row, query))

    def distinct(self, field, query=None):
        query = query or {}
        return list(dict.fromkeys(row.get(field) for row in self.rows if self._matches(row, query) and row.get(field) is not None))


class FakeDatabase(dict):
    def __getitem__(self, key):
        return self.get(key, FakeCollection())


class QueryCapturingCollection(FakeCollection):
    def __init__(self, rows):
        super().__init__(rows)
        self.last_query = None

    def find(self, query=None, projection=None):
        self.last_query = query or {}
        return super().find(query, projection)


def fixture_row(*, source_date: str = "2026-08-09", start_time: datetime | None = None) -> dict:
    kickoff = start_time or datetime(2026, 8, 9, 18, 0, tzinfo=UTC)
    return {
        "match_key": "sofascore:123",
        "source_date": source_date,
        "fixture_date_stockholm": kickoff.astimezone(ZoneInfo("Europe/Stockholm")).date().isoformat(),
        "start_time": kickoff,
        "league_key": "test-league",
        "league_name": "Test League",
        "home_team_key": "home",
        "away_team_key": "away",
        "home_team_name": "Home FC",
        "away_team_name": "Away FC",
        "status_type": "notstarted",
    }


def test_match_detail_resolves_neutral_public_match_identifier() -> None:
    fixture = {**fixture_row(), "source_match_id": 123}
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([fixture]),
        matchups_score=FakeCollection([]),
        matchups_league_avg=FakeCollection([]),
        market_snapshots=FakeCollection([]),
        teamprofiles=FakeCollection([]),
    )

    payload = read_match_detail(database, "match-123")

    assert payload is not None
    assert payload["match"]["matchKey"] == "sofascore:123"


def matchup_row(*, snapshot_date: str = "2026-08-09") -> dict:
    return {
        "entry_key": "row-1",
        "snapshot_date": snapshot_date,
        "match_key": "sofascore:123",
        "league_key": "test-league",
        "league_name": "Test League",
        "home_team_name": "Home FC",
        "away_team_name": "Away FC",
        "stat_key": "fouls",
        "stat_label": "Fouls",
        "period": "ALL",
        "period_label": "Hela matchen",
        "scope": "away",
        "condition": "over",
        "score": 73.4,
        "rank_position": 1,
        "is_top_50": True,
        "ranking_method": "rolling_12_weighted_45d",
        "ranking_window_matches": 12,
        "ranking_recency_half_life_days": 45.0,
        "market_bias": None,
        "forecast": {"leagueBaseline": 12.6},
    }


def profile(team_key: str, match_type: str, profile_date: str, value: float) -> dict:
    return {
        "team_key": team_key,
        "league_key": "test-league",
        "match_type": match_type,
        "profile_date": profile_date,
        "generated_at": datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
        "games": [{"match_key": f"history-{team_key}"}] * 6,
        "statistics": {
            "for": {"fouls": {"ALL": {"value": value, "rank": 1}}},
            "against": {"fouls": {"ALL": {"value": value - 1, "rank": 2}}},
            "leagueAverage": {
                "for": {"fouls": {"ALL": {"value": 11.0}}},
                "against": {"fouls": {"ALL": {"value": 10.0}}},
            },
        },
        "specials": {
            "shotsPerMinute": {
                "for": {"leading": 0.11, "drawing": 0.19, "trailing": 0.22},
                "against": {"leading": 0.08, "drawing": 0.17, "trailing": 0.15},
            },
            "shotsPerTenMinutes": {
                "for": {"0-10": 1.88, "11-20": 0.64},
                "against": {"0-10": 1.56, "11-20": 1.56},
            },
            "firstGoal": {
                "scoreFirstPercentage": 0.727,
                "concedeFirstPercentage": 0.273,
                "averageTimeScoredFirst": 28.2,
                "averageTimeConcededFirst": 24.1,
                "rank-scoreFirstPercentage": 9,
                "rank-concedeFirstPercentage": 15,
            },
            "leagueAverage": {
                "shotsPerMinute": {
                    "for": {"leading": 0.15, "drawing": 0.14, "trailing": 0.14},
                    "against": {"leading": 0.15, "drawing": 0.14, "trailing": 0.14},
                },
                "shotsPerTenMinutes": {
                    "for": {"0-10": 1.1, "11-20": 1.0},
                    "against": {"0-10": 1.0, "11-20": 1.1},
                },
                "firstGoal": {
                    "scoreFirstPercentage": 0.5,
                    "concedeFirstPercentage": 0.5,
                    "averageTimeScoredFirst": 26.0,
                    "averageTimeConcededFirst": 26.0,
                },
            },
        },
    }


def test_dashboard_reads_persisted_matchups_instead_of_recomputing(monkeypatch) -> None:
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([fixture_row()]),
        matchups_score=FakeCollection([matchup_row()]),
    )

    def fail_if_called(**_kwargs):
        raise AssertionError("persisted matchups must win over read-time computation")

    monkeypatch.setattr(read_service, "build_matchups_score_docs", fail_if_called, raising=False)
    payload = read_dashboard(database, source_date="2026-08-09")

    assert payload["selectedDate"] == "2026-08-09"
    assert payload["matches"][0]["homeTeamName"] == "Home FC"
    assert payload["matchups"][0]["score"] == 73.4
    assert payload["matchups"][0]["leagueBaseline"] == 12.6
    assert payload["matchups"][0]["condition"] == "OVER"
    assert payload["matchups"][0]["rankingMethod"] == "rolling_12_weighted_45d"
    assert payload["matchups"][0]["rankingWindowMatches"] == 12
    assert payload["matchupSource"] == "persisted"


def test_dashboard_filters_by_stockholm_fixture_date_not_source_provenance() -> None:
    fixtures = QueryCapturingCollection(
        [
            {
                **fixture_row(source_date="2026-08-22", start_time=datetime(2026, 8, 21, 19, 0, tzinfo=UTC)),
                "match_key": "arsenal-21",
                "fixture_date_stockholm": "2026-08-21",
            },
            {
                **fixture_row(source_date="2026-08-22", start_time=datetime(2026, 8, 22, 11, 30, tzinfo=UTC)),
                "match_key": "hull-22",
                "fixture_date_stockholm": "2026-08-22",
            },
            {
                **fixture_row(source_date="2026-08-22", start_time=datetime(2026, 8, 23, 14, 0, tzinfo=UTC)),
                "match_key": "tomorrow-23",
                "fixture_date_stockholm": "2026-08-23",
            },
        ]
    )
    database = FakeDatabase(
        fixtures_canonical=fixtures,
        matchups_score=FakeCollection([]),
    )

    payload = read_dashboard(database, source_date="2026-08-22")

    assert fixtures.last_query == {"fixture_date_stockholm": "2026-08-22"}
    assert [row["matchKey"] for row in payload["matches"]] == ["hull-22"]


def test_dashboard_reranks_current_fixture_rows_after_stale_global_ranks() -> None:
    matchup_rows = []
    for condition in ("over", "under"):
        for rank in range(1, 26):
            matchup_rows.append(
                {
                    **matchup_row(),
                    "entry_key": f"{condition}-{rank}",
                    "condition": condition,
                    "rank_position": rank,
                    "score": 100 - rank,
                }
            )
    matchups = QueryCapturingCollection(matchup_rows)
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([fixture_row()]),
        matchups_score=matchups,
    )

    payload = read_dashboard(database, source_date="2026-08-09")

    assert len(payload["matchups"]) == 40
    assert [row["rankPosition"] for row in payload["matchups"][:20]] == list(range(1, 21))
    assert [row["rankPosition"] for row in payload["matchups"][20:]] == list(range(1, 21))
    assert "rank_position" not in matchups.last_query


def test_dashboard_can_compute_upcoming_matchups_read_only_from_current_profiles(monkeypatch) -> None:
    future_date = "2099-01-01"
    future_start = datetime(2099, 1, 1, 18, 0, tzinfo=UTC)
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([fixture_row(source_date=future_date, start_time=future_start)]),
        matchups_score=FakeCollection([]),
        teamprofiles=FakeCollection(
            [
                profile("home", "home", "current", 10.0),
                profile("away", "away", "current", 12.0),
            ]
        ),
    )
    captured = {}

    def fake_builder(*, target_matches, teamprofile_docs, snapshot_date, **_kwargs):
        captured["target_matches"] = target_matches
        captured["teamprofile_docs"] = teamprofile_docs
        captured["snapshot_date"] = snapshot_date
        return [matchup_row(snapshot_date=future_date)], []

    monkeypatch.setattr(read_service, "build_matchups_score_docs", fake_builder, raising=False)
    payload = read_dashboard(database, source_date=future_date)

    assert payload["matchupSource"] == "computed_read_only"
    assert payload["matchups"][0]["score"] == 73.4
    assert captured["snapshot_date"] == future_date
    assert [row["profile_date"] for row in captured["teamprofile_docs"]] == ["current", "current"]
    assert captured["target_matches"][0]["match_key"] == "sofascore:123"


def test_dashboard_never_recomputes_started_or_historical_matchups(monkeypatch) -> None:
    historical_date = "2000-01-01"
    database = FakeDatabase(
        fixtures_canonical=FakeCollection(
            [fixture_row(source_date=historical_date, start_time=datetime(2000, 1, 1, 18, 0, tzinfo=UTC))]
        ),
        matchups_score=FakeCollection([]),
        teamprofiles=FakeCollection(
            [
                profile("home", "home", "current", 99.0),
                profile("away", "away", "current", 88.0),
            ]
        ),
    )

    def fail_if_called(**_kwargs):
        raise AssertionError("historical matchups must never use today's profiles")

    monkeypatch.setattr(read_service, "build_matchups_score_docs", fail_if_called, raising=False)
    payload = read_dashboard(database, source_date=historical_date)

    assert payload["matchups"] == []
    assert payload["matchupSource"] == "missing"


def test_dashboard_has_no_synthetic_fallback_when_date_has_no_rows() -> None:
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([]),
        matchups_score=FakeCollection([]),
    )

    payload = read_dashboard(database, source_date="2099-01-01")

    assert payload["selectedDate"] == "2099-01-01"
    assert payload["timezone"] == "Europe/Stockholm"
    assert payload["generatedAt"].endswith("Z")
    assert payload["matches"] == []
    assert payload["matchups"] == []
    assert payload["matchupSource"] == "missing"


def test_historical_match_detail_uses_profile_as_of_match_date_not_current_profile() -> None:
    historical_date = "2000-01-01"
    database = FakeDatabase(
        fixtures_canonical=FakeCollection(
            [fixture_row(source_date=historical_date, start_time=datetime(2000, 1, 1, 18, 0, tzinfo=UTC))]
        ),
        matchups_score=FakeCollection([]),
        matchups_league_avg=FakeCollection([]),
        market_snapshots=FakeCollection([]),
        teamprofiles=FakeCollection(
            [
                profile("home", "home", "current", 99.0),
                profile("home", "home", historical_date, 10.0),
                profile("away", "away", "current", 88.0),
                profile("away", "away", historical_date, 12.0),
            ]
        ),
    )

    payload = read_match_detail(database, "sofascore:123")

    assert payload is not None
    assert payload["teamStats"][0]["homeValue"] == 10.0
    assert payload["teamStats"][0]["awayValue"] == 12.0


def test_match_detail_exposes_complete_teamprofile_presentation_contract() -> None:
    historical_date = "2000-01-01"
    database = FakeDatabase(
        fixtures_canonical=FakeCollection(
            [fixture_row(source_date=historical_date, start_time=datetime(2000, 1, 1, 18, 0, tzinfo=UTC))]
        ),
        matchups_score=FakeCollection([]),
        matchups_league_avg=FakeCollection([]),
        market_snapshots=FakeCollection([]),
        support_teams=FakeCollection(
            [
                {"team_key": "home", "team_image_url": "/images/teams/home.png"},
                {"team_key": "away", "team_image_url": "/images/teams/away.png"},
            ]
        ),
        teamprofiles=FakeCollection(
            [
                profile("home", "home", historical_date, 10.0),
                profile("away", "away", historical_date, 12.0),
            ]
        ),
    )

    payload = read_match_detail(database, "sofascore:123")

    assert payload is not None
    assert payload["match"]["homeTeamImageUrl"] == "/images/teams/home.png"
    assert payload["match"]["awayTeamImageUrl"] == "/images/teams/away.png"
    stat = payload["teamStats"][0]
    assert stat == {
        "statKey": "fouls",
        "period": "ALL",
        "homeValue": 10.0,
        "awayValue": 12.0,
        "homeRank": 1,
        "awayRank": 1,
        "homeLeagueAverage": 11.0,
        "awayLeagueAverage": 11.0,
        "homeForValue": 10.0,
        "homeAgainstValue": 9.0,
        "awayForValue": 12.0,
        "awayAgainstValue": 11.0,
        "homeForRank": 1,
        "homeAgainstRank": 2,
        "awayForRank": 1,
        "awayAgainstRank": 2,
        "homeForLeagueAverage": 11.0,
        "homeAgainstLeagueAverage": 10.0,
        "awayForLeagueAverage": 11.0,
        "awayAgainstLeagueAverage": 10.0,
    }
    assert payload["teamProfiles"]["home"]["profileDate"] == historical_date
    assert payload["teamProfiles"]["home"]["sampleSize"] == 6
    assert payload["teamProfiles"]["home"]["specials"]["shotsPerMinute"]["for"]["drawing"] == 0.19
    assert payload["teamProfiles"]["away"]["specials"]["shotsPerTenMinutes"]["against"]["0-10"] == 1.56
    assert payload["teamProfiles"]["home"]["specials"]["firstGoal"]["averageTimeScoredFirst"] == 28.2


def test_match_detail_only_loads_matchups_for_requested_match() -> None:
    source_date = "2026-08-09"
    requested = fixture_row(source_date=source_date)
    other = {
        **fixture_row(source_date=source_date),
        "match_key": "sofascore:456",
        "home_team_key": "other-home",
        "away_team_key": "other-away",
    }
    matchups = QueryCapturingCollection(
        [
            matchup_row(snapshot_date=source_date),
            {
                **matchup_row(snapshot_date=source_date),
                "entry_key": "row-2",
                "match_key": "sofascore:456",
            },
        ]
    )
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([requested, other]),
        matchups_score=matchups,
        matchups_league_avg=FakeCollection([]),
        market_snapshots=FakeCollection([]),
        teamprofiles=FakeCollection([]),
    )

    payload = read_match_detail(database, "sofascore:123")

    assert payload is not None
    assert [row["entryKey"] for row in payload["matchups"]] == ["row-1"]
    assert matchups.last_query.get("match_key") == {"$in": ["sofascore:123"]}


def test_match_detail_exposes_canonical_forward_selection_and_settlement_evidence() -> None:
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([fixture_row()]),
        matchups_score=FakeCollection([]),
        matchups_league_avg=FakeCollection([]),
        market_snapshots=FakeCollection([]),
        teamprofiles=FakeCollection([]),
        forward_bets=FakeCollection(
            [
                {
                    "prediction_key": "prediction-1",
                    "match_key": "sofascore:123",
                    "stat_key": "cornerKicks",
                    "scope": "away",
                    "period": "ALL",
                    "direction": "over",
                    "line_value": 4.5,
                    "selected_odds": 2.0,
                    "predicted_win_probability": 0.6,
                    "expected_roi_units": 0.2,
                    "model_id": "v6",
                    "prediction_type": "ev_registered_score_policy",
                    "selection_policy_id": "v6_corners",
                    "valid_for_forward_evaluation": True,
                    "match_start_time": datetime(2026, 8, 9, 18, tzinfo=UTC),
                    "prediction_created_at": datetime(2026, 8, 9, 12, tzinfo=UTC),
                    "odds_snapshot_time": datetime(2026, 8, 9, 11, tzinfo=UTC),
                }
            ]
        ),
        forward_results=FakeCollection(
            [
                {
                    "result_loop_key": "prediction-1",
                    "prediction_key": "prediction-1",
                    "match_key": "sofascore:123",
                    "stat_key": "cornerKicks",
                    "scope": "away",
                    "period": "ALL",
                    "direction": "over",
                    "line_value": 4.5,
                    "settlement_status": "settled",
                    "settlement_result": "win",
                    "actual_value": 6,
                    "pnl_units": 1.0,
                    "stake_units": 1.0,
                    "valid_for_performance": True,
                    "official_clv": True,
                    "clv_pct": 5.5,
                }
            ]
        ),
    )

    payload = read_match_detail(database, "sofascore:123")

    assert payload is not None
    assert payload["forwardSelections"][0]["selectionFamily"] == "v6"
    assert payload["forwardSelections"][0]["settlementResult"] == "win"
    assert payload["forwardResults"][0]["actualValue"] == 6
    assert payload["forwardResults"][0]["clvPct"] == 5.5


def test_auto_count_covers_full_collection_even_when_rows_are_limited() -> None:
    database = FakeDatabase(
        forward_bets=FakeCollection(
            [
                {"selection_key": "s1", "match_key": "m1", "match_start_time": datetime(2026, 8, 9, 12, tzinfo=UTC)},
                {"selection_key": "s2", "match_key": "m2", "match_start_time": datetime(2026, 8, 8, 12, tzinfo=UTC)},
            ]
        ),
        forward_results=FakeCollection([]),
        fixtures_canonical=FakeCollection([]),
    )

    payload = read_auto(database, limit=1)

    assert payload["summary"]["total"] == 2
    assert payload["page"] == {"limit": 1, "offset": 0, "hasMore": True}
    assert len(payload["selections"]) == 1


def test_auto_joins_settlement_and_classifies_v6_from_frozen_provenance() -> None:
    database = FakeDatabase(
        forward_bets=FakeCollection(
            [
                {
                    "prediction_key": "prediction-v6",
                    "match_key": "sofascore:123",
                    "match_start_time": datetime(2026, 8, 9, 18, tzinfo=UTC),
                    "stat_key": "cornerKicks",
                    "period": "ALL",
                    "scope": "away",
                    "direction": "over",
                    "line_value": 4.5,
                    "selected_odds": 1.91,
                    "predicted_win_probability": 0.61,
                    "expected_roi_units": 0.165,
                    "prediction_type": "ev_registered_score_policy",
                    "model_id": "ev_scope_interaction_recency45_asof_capped_v6_shadow",
                    "selection_policy_id": "v6_corners_away_total_forward_v1",
                    "selection_policy_registry_id": "forward_policy_registry_v1",
                    "valid_for_forward_evaluation": True,
                    "invalid_for_model": False,
                }
            ]
        ),
        forward_results=FakeCollection(
            [
                {
                    "result_loop_key": "prediction-v6",
                    "prediction_key": "prediction-v6",
                    "result_loop_status": "settled",
                    "settlement_status": "settled",
                    "settlement_result": "win",
                    "actual_value": 6,
                    "pnl_units": 0.91,
                    "stake_units": 1.0,
                    "valid_for_performance": True,
                }
            ]
        ),
        fixtures_canonical=FakeCollection([fixture_row()]),
    )

    payload = read_auto(database)

    expected = {
        "selectionKey": "prediction-v6",
        "matchKey": "sofascore:123",
        "homeTeamName": "Home FC",
        "awayTeamName": "Away FC",
        "leagueName": "Test League",
        "statKey": "cornerKicks",
        "period": "ALL",
        "scope": "away",
        "direction": "over",
        "lineValue": 4.5,
        "selectedOdds": 1.91,
        "predictedWinProbability": 0.61,
        "expectedRoiUnits": 0.165,
        "modelId": "ev_scope_interaction_recency45_asof_capped_v6_shadow",
        "modelStatus": None,
        "policyId": "v6_corners_away_total_forward_v1",
        "selectionFamily": "v6",
        "matchStartTime": "2026-08-09T18:00:00Z",
        "validForForwardEvaluation": True,
        "invalidForModel": False,
        "resultStatus": "settled",
        "settlementStatus": "settled",
        "settlementResult": "win",
        "actualValue": 6,
        "pnlUnits": 0.91,
        "stakeUnits": 1.0,
        "validForPerformance": True,
    }
    selection = payload["selections"][0]
    assert {key: selection[key] for key in expected} == expected


def test_auto_excludes_combo_legs_and_collapses_replayed_legacy_exposure() -> None:
    shared = {
        "selection_key": "legacy-selection",
        "match_key": "sofascore:123",
        "match_start_time": datetime(2026, 8, 9, 18, tzinfo=UTC),
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "away",
        "direction": "over",
        "line_value": 4.5,
        "saved_odds": 1.91,
        "invalid_for_model": False,
    }
    database = FakeDatabase(
        forward_bets=FakeCollection(
            [
                shared | {"prediction_key": "legacy-first", "prediction_type": "single", "saved_at": datetime(2026, 8, 9, 10, tzinfo=UTC)},
                shared | {"prediction_key": "legacy-replay", "prediction_type": "single", "saved_at": datetime(2026, 8, 9, 11, tzinfo=UTC)},
                shared | {"prediction_key": "combo-leg", "prediction_type": "combo", "export_mode": "combos", "saved_at": datetime(2026, 8, 9, 10, tzinfo=UTC)},
                shared
                | {
                    "prediction_key": "v6-prediction",
                    "selection_key": "v6-prediction",
                    "prediction_type": "ev_registered_score_policy",
                    "model_id": "ev_scope_interaction_recency45_asof_capped_v6",
                    "model_status": "forward_test_only",
                    "selection_policy_id": "v6_corners_away_total_forward_v1",
                    "selection_policy_registry_id": "forward_policy_registry_v1",
                    "selected_odds": 1.95,
                    "predicted_win_probability": 0.61,
                    "expected_roi_units": 0.165,
                    "odds_snapshot_time": datetime(2026, 8, 9, 12, tzinfo=UTC),
                    "prediction_created_at": datetime(2026, 8, 9, 12, 1, tzinfo=UTC),
                    "valid_for_forward_evaluation": True,
                },
            ]
        ),
        forward_results=FakeCollection([]),
        fixtures_canonical=FakeCollection([fixture_row()]),
    )

    payload = read_auto(database)

    assert payload["rawCount"] == 4
    assert payload["count"] == 2
    assert payload["excludedComboLegCount"] == 1
    assert payload["collapsedDuplicateCount"] == 1
    assert [row["selectionKey"] for row in payload["selections"]] == [
        "v6-prediction",
        "legacy-first",
    ]
    assert [row["selectionFamily"] for row in payload["selections"]] == [
        "v6",
        "legacy",
    ]


def test_results_summary_covers_full_collection_even_when_rows_are_limited() -> None:
    database = FakeDatabase(
        forward_results=FakeCollection(
            [
                {"result_loop_key": "r1", "settlement_status": "settled", "valid_for_performance": True, "win": True, "match_start_time": datetime(2026, 8, 9, 12, tzinfo=UTC)},
                {"result_loop_key": "r2", "settlement_status": "settled", "valid_for_performance": False, "win": False, "match_start_time": datetime(2026, 8, 8, 12, tzinfo=UTC)},
            ]
        )
    )

    payload = read_results(database, limit=1)

    assert payload["summary"] == {"rows": 2, "settled": 1, "wins": 1, "losses": 0, "pushes": 0, "excluded": 1}
    assert payload["page"] == {"limit": 1, "offset": 0, "hasMore": True}
    assert len(payload["rows"]) == 1
