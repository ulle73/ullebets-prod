from __future__ import annotations

import json
from pathlib import Path

from ullebets_v2.historical_coverage.service import (
    build_historical_coverage_report,
    render_historical_coverage_markdown,
    run_historical_coverage_audit,
)


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = [dict(doc) for doc in (docs or [])]

    def _matches(self, doc: dict, query: dict | None) -> bool:
        if not query:
            return True
        for key, value in query.items():
            if doc.get(key) != value:
                return False
        return True

    def find(self, query: dict | None = None, projection: dict | None = None):
        for doc in self.docs:
            if not self._matches(doc, query):
                continue
            if not projection:
                yield dict(doc)
                continue
            row = {}
            for key, include in projection.items():
                if key == "_id" or not include:
                    continue
                if key in doc:
                    row[key] = doc[key]
            yield row

    def insert_one(self, doc: dict) -> None:
        self.docs.append(dict(doc))

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> None:
        for doc in self.docs:
            if self._matches(doc, query):
                doc.update(update.get("$set", {}))
                return
        if upsert:
            new_doc = dict(query)
            new_doc.update(update.get("$set", {}))
            self.docs.append(new_doc)
            return
        raise AssertionError(f"Missing document for query: {query}")


class FakeDatabase(dict):
    def __getitem__(self, collection_name: str) -> FakeCollection:
        if collection_name not in self:
            self[collection_name] = FakeCollection()
        return dict.__getitem__(self, collection_name)


def build_legacy_app_database() -> FakeDatabase:
    return FakeDatabase(
        {
            "match-for-date": FakeCollection(
                [
                    {
                        "full": [
                            {"date": "2025-11-21", "matches": [{}, {}]},
                            {"date": "2025-11-22", "matches": [{}]},
                        ]
                    }
                ]
            ),
            "unibet-backtest": FakeCollection(
                [
                    {"matchDate": "2025-11-21"},
                    {"matchDate": "2025-11-21"},
                    {"matchDate": "2025-11-22"},
                ]
            ),
        }
    )


def build_legacy_unibet_database() -> FakeDatabase:
    return FakeDatabase(
        {
            "raw_odds_snapshots": FakeCollection(
                [
                    {"payload": {"events": [{"start": "2025-11-21T20:00:00Z"}]}},
                    {"match_id": "league|2025-11-22|home|away"},
                ]
            )
        }
    )


def build_v2_database() -> FakeDatabase:
    return FakeDatabase(
        {
            "fixtures_canonical": FakeCollection(
                [
                    {"source_date": "2025-11-21"},
                    {"source_date": "2025-11-21"},
                ]
            ),
            "match_results_canonical": FakeCollection([{"source_date": "2025-11-21"}]),
            "match_stats_canonical": FakeCollection(
                [
                    {"source_date": "2025-11-21"},
                    {"source_date": "2025-11-21"},
                    {"source_date": "2025-11-21"},
                ]
            ),
            "raw_odds_kambi": FakeCollection(
                [
                    {"source_date": "2025-11-21", "source_provider": "legacy_unibet_backtest"},
                ]
            ),
            "unibet_event_links": FakeCollection(
                [
                    {"source_date": "2025-11-21", "source_provider": "legacy_unibet_backtest"},
                ]
            ),
            "market_offers": FakeCollection(
                [
                    {"source_date": "2025-11-21", "source_provider": "legacy_unibet_backtest"},
                    {"source_date": "2025-11-21", "source_provider": "legacy_unibet_backtest"},
                ]
            ),
            "teamprofiles": FakeCollection(
                [
                    {"profile_date": "2025-11-22", "team_key": "alpha", "match_type": "home"},
                    {"profile_date": "2025-11-22", "team_key": "alpha", "match_type": "away"},
                    {"profile_date": "2025-11-22", "team_key": "beta", "match_type": "home"},
                ]
            ),
        }
    )


def test_build_historical_coverage_report_flags_missing_v2_dates() -> None:
    report = build_historical_coverage_report(
        database=build_v2_database(),
        legacy_app_database=build_legacy_app_database(),
        legacy_unibet_database=build_legacy_unibet_database(),
        start_date="2025-11-21",
        end_date="2025-11-22",
    )

    assert report["source_inventory"]["legacy_fixture_dates_total"] == 2
    assert report["source_inventory"]["legacy_backtest_dates_total"] == 2
    assert report["source_inventory"]["legacy_raw_snapshot_dates_total"] == 2
    assert report["coverage_summary"]["fixture_backtest_overlap_dates_total"] == 2
    assert report["coverage_summary"]["ready_for_model_replay_dates_total"] == 1
    assert report["coverage_summary"]["missing_v2_fixture_dates_sample"] == ["2025-11-22"]
    assert report["coverage_summary"]["missing_v2_result_dates_sample"] == ["2025-11-22"]
    assert report["coverage_summary"]["missing_v2_stat_dates_sample"] == ["2025-11-22"]
    assert report["coverage_summary"]["missing_v2_odds_dates_sample"] == ["2025-11-22"]
    assert report["teamprofile_summary"]["teams_with_both"] == 1
    assert report["teamprofile_summary"]["teams_missing_away_sample"] == ["beta"]

    first_row = report["rows"][0]
    assert first_row["date"] == "2025-11-21"
    assert first_row["ready_for_model_replay"] is True


def test_render_historical_coverage_markdown_includes_gap_summary() -> None:
    report = build_historical_coverage_report(
        database=build_v2_database(),
        legacy_app_database=build_legacy_app_database(),
        legacy_unibet_database=build_legacy_unibet_database(),
        start_date="2025-11-21",
        end_date="2025-11-22",
    )

    markdown = render_historical_coverage_markdown(report)

    assert "# Historical Coverage Audit" in markdown
    assert "Missing V2 odds dates: `1`" in markdown
    assert "Teams missing away sample: `['beta']`" in markdown


def test_run_historical_coverage_audit_writes_reports_and_job_rows(tmp_path: Path) -> None:
    database = build_v2_database()
    summary = run_historical_coverage_audit(
        database=database,
        legacy_app_database=build_legacy_app_database(),
        legacy_unibet_database=build_legacy_unibet_database(),
        reports_dir=tmp_path,
        source_workflow="historical-coverage-audit",
        start_date="2025-11-21",
        end_date="2025-11-22",
        dry_run=False,
    )

    assert summary["status"] == "warn"
    assert (tmp_path / "historical_coverage_2025-11-21__2025-11-22.json").exists()
    assert (tmp_path / "historical_coverage_2025-11-21__2025-11-22.md").exists()
    assert (tmp_path / "historical_coverage_latest.json").exists()
    assert (tmp_path / "historical_coverage_latest.md").exists()

    report_payload = json.loads((tmp_path / "historical_coverage_latest.json").read_text(encoding="utf-8"))
    assert report_payload["coverage_summary"]["missing_v2_odds_dates_count"] == 1

    job_run = database["job_runs"].docs[0]
    assert job_run["job_name"] == "audit_historical_coverage"
    assert job_run["status"] == "succeeded"
    assert job_run["metrics"]["fixture_backtest_overlap_dates_total"] == 2

    audit_row = database["audit_reports"].docs[0]
    assert audit_row["audit_type"] == "historical_coverage"
    assert audit_row["status"] == "warn"

    health_row = database["health_reports"].docs[0]
    assert health_row["job_name"] == "audit_historical_coverage"
    assert health_row["status"] == "warn"
