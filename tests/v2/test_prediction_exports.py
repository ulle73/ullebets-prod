from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.prediction_exports.service import run_prediction_export_pipeline
from tests.v2.test_auto_analysis import FakeAnalysisOracle, FakeReadCollection, FakeReadDatabase, build_stored_model_snapshot_docs
from tests.v2.test_model_snapshots import FakeModelOracle
from tests.v2.test_odds_ingest import (
    FakeDatabase,
    FakeUpdateResult,
    FakeHistoricalCollection,
    FakeHistoricalDatabase,
    build_legacy_backtest_doc,
    build_support_docs,
    fake_transport,
)


def build_analysis_run() -> dict:
    return {
        "run_id": "2026-06-22:balanced:manual",
        "run_key": "2026-06-22:balanced:manual",
        "date": "2026-06-22",
        "strategy_id": "balanced",
        "strategy_label": "balanced",
        "source_workflow": "ai-user-daily.yml",
    }


class InsertableFakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict] = []

    def _matches(self, doc: dict, query: dict) -> bool:
        return all(doc.get(key) == value for key, value in query.items())

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> FakeUpdateResult:
        for doc in self.docs:
            if self._matches(doc, query):
                doc.update(update.get("$set", {}))
                return FakeUpdateResult(upserted=False)
        if not upsert:
            return FakeUpdateResult(upserted=False)
        new_doc = dict(query)
        new_doc.update(update.get("$set", {}))
        self.docs.append(new_doc)
        return FakeUpdateResult(upserted=True)

    def insert_one(self, doc: dict) -> None:
        self.docs.append(dict(doc))

    def count_documents(self, query: dict | None = None) -> int:
        if not query:
            return len(self.docs)
        return sum(1 for doc in self.docs if self._matches(doc, query))

    def find(self, query: dict | None = None, projection: dict | None = None):  # noqa: ARG002
        query = query or {}
        rows = list(self.docs)
        for key, value in query.items():
            if isinstance(value, dict) and "$in" in value:
                allowed = {str(item) for item in value["$in"]}
                rows = [row for row in rows if str(row.get(key)) in allowed]
            else:
                rows = [row for row in rows if row.get(key) == value]
        return rows

    def find_one(self, query: dict | None = None, projection: dict | None = None):  # noqa: ARG002
        rows = self.find(query=query, projection=projection)
        return rows[0] if rows else None


class InsertableFakeDatabase(FakeDatabase):
    def __getitem__(self, collection_name: str) -> InsertableFakeCollection:
        if collection_name not in self:
            self[collection_name] = InsertableFakeCollection()
        return dict.__getitem__(self, collection_name)


def build_candidate(
    *,
    selection_key: str,
    match_key: str,
    source_match_id: str,
    home_team: str,
    away_team: str,
    odds: float,
    ev: float,
    score: float,
    best: bool = True,
) -> dict:
    return {
        "candidate_key": f"run|{selection_key}",
        "selection_key": selection_key,
        "match_key": match_key,
        "source_match_id": source_match_id,
        "offer_key": f"{match_key}|offer",
        "homeTeamName": home_team,
        "awayTeamName": away_team,
        "leagueName": "Premier League",
        "matchDate": "2026-06-22T18:00:00Z",
        "headline": f"over 10.5 cornerKicks {home_team}-{away_team}",
        "primaryEv": ev,
        "strategyScore": score,
        "is_best_bet_for_match": best,
        "passes_strategy_filters": True,
        "bet": {
            "statKey": "cornerKicks",
            "scope": "total",
            "period": "ALL",
            "direction": "over",
            "line": 10.5,
            "odds": odds,
        },
    }


def build_target(*, match_key: str, home_team: str, away_team: str) -> dict:
    return {
        "match_key": match_key,
        "source_match_id": match_key,
        "league_key": "premier-league",
        "league_name": "Premier League",
        "home_team_name": home_team,
        "away_team_name": away_team,
        "start_time": datetime(2026, 6, 22, 18, 0, tzinfo=UTC),
    }


def test_run_prediction_export_pipeline_dry_run_builds_single_exports_and_forward_bets() -> None:
    summary = run_prediction_export_pipeline(
        export_mode="daily",
        source_workflow="ai-bets-daily.yml",
        analysis_run_doc=build_analysis_run(),
        analysis_candidate_docs=[
            build_candidate(
                selection_key="sel-1",
                match_key="match-1",
                source_match_id="match-1",
                home_team="Arsenal",
                away_team="Bournemouth",
                odds=1.9,
                ev=8.2,
                score=82,
                best=True,
            )
        ],
        dry_run=True,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["analysis_candidates"] == 1
    assert summary["source_candidates"] == 1
    assert summary["prediction_exports"] == 1
    assert summary["forward_bets"] == 1
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_prediction_export_pipeline_dry_run_builds_combo_exports() -> None:
    summary = run_prediction_export_pipeline(
        export_mode="combos",
        source_workflow="ai-user-combos.yml",
        analysis_run_doc=build_analysis_run(),
        analysis_candidate_docs=[
            build_candidate(
                selection_key="sel-1",
                match_key="match-1",
                source_match_id="match-1",
                home_team="Arsenal",
                away_team="Bournemouth",
                odds=1.5,
                ev=8.2,
                score=82,
                best=True,
            ),
            build_candidate(
                selection_key="sel-2",
                match_key="match-2",
                source_match_id="match-2",
                home_team="Chelsea",
                away_team="Fulham",
                odds=1.4,
                ev=7.1,
                score=79,
                best=True,
            ),
        ],
        dry_run=True,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["analysis_candidates"] == 2
    assert summary["source_candidates"] == 2
    assert summary["prediction_exports"] == 1
    assert summary["forward_bets"] == 2
    assert summary["parity_status_counts"] == {"matched": 1}


def test_run_prediction_export_pipeline_dry_run_handles_empty_candidates() -> None:
    summary = run_prediction_export_pipeline(
        export_mode="daily",
        source_workflow="ai-bets-daily.yml",
        analysis_run_doc=build_analysis_run(),
        analysis_candidate_docs=[],
        dry_run=True,
    )

    assert summary["analysis_candidates"] == 0
    assert summary["source_candidates"] == 0
    assert summary["prediction_exports"] == 0
    assert summary["forward_bets"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_prediction_export_pipeline_uses_internal_analysis_oracle_by_default() -> None:
    summary = run_prediction_export_pipeline(
        export_mode="daily",
        source_workflow="ai-user-daily.yml",
        targets=[
            {
                "match_key": "match-1",
                "source_match_id": "match-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": datetime(2026, 6, 22, 18, 0, tzinfo=UTC),
            }
        ],
        support_docs=build_support_docs(),
        dry_run=True,
        transport=fake_transport,
        odds_oracle=None,
        model_oracle=FakeModelOracle(),
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["analysis_candidates"] == 2
    assert summary["source_candidates"] == 0
    assert summary["prediction_exports"] == 0
    assert summary["forward_bets"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}


def test_run_prediction_export_pipeline_can_read_stored_model_snapshots_from_db() -> None:
    read_database = FakeReadDatabase(
        {
            "model_snapshots": FakeReadCollection(build_stored_model_snapshot_docs()),
        }
    )

    summary = run_prediction_export_pipeline(
        export_mode="daily",
        source_workflow="ai-bets-daily.yml",
        targets=[
            {
                "match_key": "match-1",
                "source_match_id": "match-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": datetime(2026, 6, 22, 18, 0, tzinfo=UTC),
            }
        ],
        support_docs=build_support_docs(),
        dry_run=True,
        snapshot_source="db",
        snapshot_read_database=read_database,
    )

    assert summary["analysis_candidates"] == 2
    assert summary["source_candidates"] == 0
    assert summary["prediction_exports"] == 0
    assert summary["forward_bets"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}


def test_run_prediction_export_pipeline_prefers_stored_analysis_outputs_from_db() -> None:
    read_database = InsertableFakeDatabase()
    read_database["analysis_runs"].docs = [
        {
            "run_id": "2026-06-22:balanced:manual",
            "run_key": "2026-06-22:balanced:manual",
            "date": "2026-06-22",
            "strategy_id": "balanced",
            "strategy_label": "balanced",
            "source_workflow": "run-auto-analysis-checkpoints.yml",
        }
    ]
    read_database["analysis_candidates"].docs = [
        build_candidate(
            selection_key="sel-1",
            match_key="match-1",
            source_match_id="match-1",
            home_team="Arsenal",
            away_team="Bournemouth",
            odds=1.9,
            ev=8.2,
            score=82,
            best=True,
        )
        | {
            "run_id": "2026-06-22:balanced:manual",
            "candidate_key": "2026-06-22:balanced:manual|sel-1",
        }
    ]

    summary = run_prediction_export_pipeline(
        export_mode="daily",
        source_workflow="ai-bets-daily.yml",
        targets=[
            {
                "match_key": "match-1",
                "source_match_id": "match-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": datetime(2026, 6, 22, 18, 0, tzinfo=UTC),
            }
        ],
        support_docs=build_support_docs(),
        dry_run=True,
        database=None,
        snapshot_source="db",
        snapshot_read_database=read_database,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["analysis_source"] == "db"
    assert summary["analysis_candidates"] == 1
    assert summary["source_candidates"] == 1
    assert summary["prediction_exports"] == 1
    assert summary["forward_bets"] == 1
    assert summary["parity_status_counts"] == {"matched": 1}


def test_run_prediction_export_pipeline_rebuilds_when_stored_analysis_misses_target_match() -> None:
    read_database = InsertableFakeDatabase()
    read_database["analysis_runs"].docs = [
        {
            "run_id": "2026-06-22:balanced:manual",
            "run_key": "2026-06-22:balanced:manual",
            "date": "2026-06-22",
            "strategy_id": "balanced",
            "strategy_label": "balanced",
            "source_workflow": "run-auto-analysis-checkpoints.yml",
            "analyzedMatches": 2,
            "candidateCount": 4,
        }
    ]
    read_database["analysis_candidates"].docs = [
        build_candidate(
            selection_key="sel-1",
            match_key="match-1",
            source_match_id="match-1",
            home_team="Arsenal",
            away_team="Bournemouth",
            odds=1.9,
            ev=8.2,
            score=82,
            best=True,
        )
        | {
            "run_id": "2026-06-22:balanced:manual",
            "candidate_key": "2026-06-22:balanced:manual|sel-1",
        }
    ]

    summary = run_prediction_export_pipeline(
        export_mode="daily",
        source_workflow="ai-bets-daily.yml",
        targets=[
            build_target(match_key="match-1", home_team="Arsenal", away_team="Bournemouth"),
            build_target(match_key="match-2", home_team="Chelsea", away_team="Fulham"),
        ],
        support_docs=build_support_docs(),
        dry_run=True,
        snapshot_source="build",
        snapshot_read_database=read_database,
        analysis_oracle=FakeAnalysisOracle(),
        transport=fake_transport,
        odds_oracle=None,
        model_oracle=FakeModelOracle(),
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["analysis_source"] == "build"
    assert summary["analysis_candidates"] == 2
    assert summary["source_candidates"] == 1
    assert summary["prediction_exports"] == 1
    assert summary["forward_bets"] == 1


def test_run_prediction_export_pipeline_rebuilds_when_stored_analysis_is_incomplete_for_same_matchset() -> None:
    read_database = InsertableFakeDatabase()
    read_database["analysis_runs"].docs = [
        {
            "run_id": "2026-06-22:balanced:manual",
            "run_key": "2026-06-22:balanced:manual",
            "date": "2026-06-22",
            "strategy_id": "balanced",
            "strategy_label": "balanced",
            "source_workflow": "run-auto-analysis-checkpoints.yml",
            "analyzedMatches": 1,
            "candidateCount": 2,
        }
    ]
    read_database["analysis_candidates"].docs = [
        build_candidate(
            selection_key="sel-1",
            match_key="match-1",
            source_match_id="match-1",
            home_team="Arsenal",
            away_team="Bournemouth",
            odds=1.9,
            ev=8.2,
            score=82,
            best=True,
        )
        | {
            "run_id": "2026-06-22:balanced:manual",
            "candidate_key": "2026-06-22:balanced:manual|sel-1",
        }
    ]

    summary = run_prediction_export_pipeline(
        export_mode="daily",
        source_workflow="ai-bets-daily.yml",
        targets=[build_target(match_key="match-1", home_team="Arsenal", away_team="Bournemouth")],
        support_docs=build_support_docs(),
        dry_run=True,
        snapshot_source="build",
        snapshot_read_database=read_database,
        analysis_oracle=FakeAnalysisOracle(),
        transport=fake_transport,
        odds_oracle=None,
        model_oracle=FakeModelOracle(),
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["analysis_source"] == "build"
    assert summary["analysis_candidates"] == 2
    assert summary["source_candidates"] == 1
    assert summary["prediction_exports"] == 1
    assert summary["forward_bets"] == 1


def test_run_prediction_export_pipeline_replays_historical_backtest_without_live_fetch() -> None:
    historical_database = FakeHistoricalDatabase()
    historical_database["unibet-backtest"] = FakeHistoricalCollection([build_legacy_backtest_doc()])

    def failing_transport(url: str, headers: dict[str, str], timeout_seconds: int):  # noqa: ARG001
        raise AssertionError(f"live transport should not be used in replay export mode: {url}")

    summary = run_prediction_export_pipeline(
        export_mode="daily",
        source_workflow="ai-bets-daily.yml",
        targets=[
            {
                "match_key": "match-legacy-present",
                "source_match_id": 14689178,
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": datetime(2025, 10, 8, 18, 0, tzinfo=UTC),
                "source_date": "2025-10-08",
            }
        ],
        support_docs=build_support_docs(),
        dry_run=True,
        strategy_id="balanced",
        snapshot_mode="backtest",
        analysis_oracle=FakeAnalysisOracle(),
        transport=failing_transport,
        legacy_backtest_database=historical_database,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["analysis_candidates"] == 3
    assert summary["source_candidates"] == 1
    assert summary["prediction_exports"] == 1
    assert summary["forward_bets"] == 1
    assert summary["parity_status_counts"] == {"matched": 1}


def test_run_prediction_export_pipeline_can_route_legacy_snapshot_tuples_through_model_oracle() -> None:
    historical_database = FakeHistoricalDatabase()
    historical_database["unibet-backtest"] = FakeHistoricalCollection([build_legacy_backtest_doc()])

    summary = run_prediction_export_pipeline(
        export_mode="daily",
        source_workflow="ai-bets-daily.yml",
        targets=[
            {
                "match_key": "match-legacy-present",
                "source_match_id": 14689178,
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": datetime(2025, 10, 8, 18, 0, tzinfo=UTC),
                "source_date": "2025-10-08",
            }
        ],
        support_docs=build_support_docs(),
        dry_run=True,
        strategy_id="balanced",
        snapshot_mode="backtest",
        analysis_oracle=FakeAnalysisOracle(),
        model_oracle=FakeModelOracle(),
        legacy_backtest_database=historical_database,
        use_legacy_snapshot_lines=False,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["analysis_candidates"] == 3
    assert summary["source_candidates"] == 1
    assert summary["prediction_exports"] == 1
    assert summary["forward_bets"] == 1
    assert summary["parity_status_counts"] == {"matched": 1}


def test_run_prediction_export_pipeline_does_not_persist_analysis_collections_when_building_exports() -> None:
    database = InsertableFakeDatabase()

    summary = run_prediction_export_pipeline(
        export_mode="user-daily",
        source_workflow="ai-user-daily.yml",
        targets=[
            {
                "match_key": "match-1",
                "source_match_id": "match-1",
                "league_key": "premier-league",
                "league_name": "Premier League",
                "home_team_name": "Arsenal",
                "away_team_name": "Bournemouth",
                "start_time": datetime(2026, 6, 22, 18, 0, tzinfo=UTC),
            }
        ],
        support_docs=build_support_docs(),
        database=database,
        dry_run=False,
        analysis_oracle=FakeAnalysisOracle(),
        transport=fake_transport,
        model_oracle=FakeModelOracle(),
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["analysis_candidates"] == 2
    assert summary["source_candidates"] == 1
    assert summary["prediction_exports"] == 1
    assert summary["forward_bets"] == 1
    assert database["analysis_runs"].count_documents() == 0
    assert database["analysis_snapshots"].count_documents() == 0
    assert database["analysis_candidates"].count_documents() == 0
    assert database["prediction_exports"].count_documents() == 1
    assert database["forward_bets"].count_documents() == 1
