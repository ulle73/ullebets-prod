from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.model_snapshots.runtime_parity import run_model_snapshot_runtime_parity_audit

from tests.v2.test_odds_ingest import (
    FakeHistoricalCollection,
    FakeHistoricalDatabase,
    build_legacy_backtest_doc,
    build_support_docs,
)


def build_target_match() -> dict:
    return {
        "match_key": "match-legacy-present",
        "source_match_id": 14689178,
        "league_key": "premier-league",
        "league_name": "Premier League",
        "home_team_name": "Arsenal",
        "away_team_name": "Bournemouth",
        "start_time": datetime(2025, 10, 8, 18, 0, tzinfo=UTC),
        "source_date": "2025-10-08",
    }


class ExactParityOracle:
    def build_match_lines(self, *, match_info: dict, offers: list[dict], defaults: dict | None = None) -> dict:  # noqa: ARG002
        lines: list[dict] = []
        for offer in offers:
            for direction, condition in (("over", "över"), ("under", "under")):
                odds_value = offer.get("odds", {}).get(direction)
                if not isinstance(odds_value, (int, float)) or odds_value <= 1:
                    continue
                lines.append(
                    {
                        "betKey": "|".join(
                            [
                                str(match_info["matchId"]),
                                str(offer["statKey"]),
                                str(offer["scope"]),
                                str(offer["period"]),
                                direction,
                                str(offer["line"]),
                            ]
                        ),
                        "statKey": offer["statKey"],
                        "line": offer["line"],
                        "condition": condition,
                        "direction": direction,
                        "period": offer["period"],
                        "scope": offer["scope"],
                        "odds": odds_value,
                        "value": 1.5,
                        "evDetails": {"evPctUniversalOptimized": 1.5},
                        "primaryFormulaKey": "universalOptimized",
                        "primaryValueKey": "evPctUniversalOptimized",
                        "sampleSize": 12,
                        "homeTeam": match_info["homeTeam"],
                        "awayTeam": match_info["awayTeam"],
                        "actual": None,
                        "win": None,
                    }
                )
        return {"lines": lines, "errors": []}


class MissingLineOracle(ExactParityOracle):
    def build_match_lines(self, *, match_info: dict, offers: list[dict], defaults: dict | None = None) -> dict:  # noqa: ARG002
        built = super().build_match_lines(match_info=match_info, offers=offers, defaults=defaults)
        return {"lines": built["lines"][:-1], "errors": []}


def test_runtime_parity_audit_reports_exact_match_for_backtest_lines() -> None:
    legacy_database = FakeHistoricalDatabase()
    legacy_database["unibet-backtest"] = FakeHistoricalCollection([build_legacy_backtest_doc()])

    summary = run_model_snapshot_runtime_parity_audit(
        targets=[build_target_match()],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-backtests.yml",
        snapshot_mode="backtest",
        legacy_backtest_database=legacy_database,
        model_oracle=ExactParityOracle(),
        dry_run=True,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["target_matches"] == 1
    assert summary["comparable_matches"] == 1
    assert summary["target_source"] == "replay-fixtures"
    assert summary["reference_lines"] == 3
    assert summary["generated_lines"] == 3
    assert summary["matched_lines"] == 3
    assert summary["missing_lines"] == 0
    assert summary["extra_lines"] == 0
    assert summary["match_error_count"] == 0
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_runtime_parity_audit_flags_missing_generated_line() -> None:
    legacy_database = FakeHistoricalDatabase()
    legacy_database["unibet-backtest"] = FakeHistoricalCollection([build_legacy_backtest_doc()])

    summary = run_model_snapshot_runtime_parity_audit(
        targets=[build_target_match()],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-backtests.yml",
        snapshot_mode="backtest",
        legacy_backtest_database=legacy_database,
        model_oracle=MissingLineOracle(),
        dry_run=True,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["reference_lines"] == 3
    assert summary["generated_lines"] == 2
    assert summary["matched_lines"] == 2
    assert summary["missing_lines"] == 1
    assert summary["parity_status_counts"] == {"mismatch": 1}
    assert summary["audit_status_counts"] == {"warn": 1}
    assert summary["health_status_counts"] == {"warn": 1}
    assert summary["match_rows"][0]["comparison"]["missing_signatures"] == ["totalShots|home|ALL|over|11.5"]


def test_runtime_parity_audit_handles_empty_target_window() -> None:
    legacy_database = FakeHistoricalDatabase()
    legacy_database["unibet-backtest"] = FakeHistoricalCollection([])

    summary = run_model_snapshot_runtime_parity_audit(
        targets=[],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-backtests.yml",
        snapshot_mode="backtest",
        legacy_backtest_database=legacy_database,
        model_oracle=ExactParityOracle(),
        dry_run=True,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["target_matches"] == 0
    assert summary["comparable_matches"] == 0
    assert summary["reference_lines"] == 0
    assert summary["generated_lines"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"warn": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_runtime_parity_audit_exposes_legacy_backtest_target_source() -> None:
    legacy_database = FakeHistoricalDatabase()
    legacy_database["unibet-backtest"] = FakeHistoricalCollection([build_legacy_backtest_doc()])

    summary = run_model_snapshot_runtime_parity_audit(
        targets=[build_target_match()],
        support_docs=build_support_docs(),
        source_workflow="run-unibet-backtests.yml",
        snapshot_mode="backtest",
        legacy_backtest_database=legacy_database,
        model_oracle=ExactParityOracle(),
        target_source="legacy-backtest",
        dry_run=True,
        return_documents=True,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["target_source"] == "legacy-backtest"
    assert summary["documents"]["parity_rows"][0]["old_workflow"] == "run-unibet-backtests.yml#runtime-parity#legacy-backtest"
    assert summary["documents"]["audit_rows"][0]["scope_key"] == "run-unibet-backtests.yml:backtest:legacy-backtest"
    assert summary["documents"]["health_rows"][0]["job_name"] == "audit_model_snapshot_runtime_parity:legacy-backtest"
