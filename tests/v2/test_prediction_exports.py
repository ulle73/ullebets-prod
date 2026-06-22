from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.prediction_exports.service import run_prediction_export_pipeline


def build_analysis_run() -> dict:
    return {
        "run_id": "2026-06-22:balanced:manual",
        "run_key": "2026-06-22:balanced:manual",
        "date": "2026-06-22",
        "strategy_id": "balanced",
        "strategy_label": "balanced",
        "source_workflow": "ai-user-daily.yml",
    }


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
