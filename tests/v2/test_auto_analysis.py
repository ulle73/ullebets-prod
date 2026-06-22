from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.analysis.service import run_auto_analysis_pipeline

from tests.v2.test_model_snapshots import FakeModelOracle
from tests.v2.test_odds_ingest import build_support_docs, fake_transport


class FakeAnalysisOracle:
    def rank_model_snapshots(
        self,
        *,
        model_snapshot_docs: list[dict],
        run_meta: dict,
        learning_profile: dict | None = None,  # noqa: ARG002
    ) -> dict:
        shortlist = []
        candidates = []
        by_match: dict[str, list[dict]] = {}
        for snapshot in model_snapshot_docs:
            candidate = {
                "runId": run_meta["runId"],
                "runKey": run_meta["runKey"],
                "date": run_meta["date"],
                "strategyId": run_meta["strategyId"],
                "strategyLabel": run_meta["strategyLabel"],
                "trackingKey": snapshot["selection_key"],
                "matchId": snapshot["source_match_id"] or snapshot["match_key"],
                "homeTeamName": snapshot["home_team_name"],
                "awayTeamName": snapshot["away_team_name"],
                "leagueName": snapshot["league_name"],
                "headline": f"{snapshot['direction']} {snapshot['line_value']} {snapshot['stat_key']}",
                "primaryEv": snapshot["primary_ev"],
                "confidenceScore": 70 if snapshot["direction"] == "over" else 45,
                "agreementPct": 65 if snapshot["direction"] == "over" else 30,
                "sampleSize": snapshot.get("sample_size"),
                "strategyScore": 81 if snapshot["direction"] == "over" else 20,
                "passesStrategyFilters": snapshot["direction"] == "over",
                "isBestBetForMatch": False,
                "bet": {
                    "key": snapshot["bet_key"],
                    "statKey": snapshot["stat_key"],
                    "line": snapshot["line_value"],
                    "direction": snapshot["direction"],
                    "scope": snapshot["scope"],
                    "period": snapshot["period"],
                    "odds": snapshot["selected_odds"],
                    "homeTeam": snapshot["home_team_name"],
                    "awayTeam": snapshot["away_team_name"],
                },
                "selectionKey": snapshot["selection_key"],
                "matchKey": snapshot["match_key"],
                "sourceMatchId": snapshot["source_match_id"] or snapshot["match_key"],
                "offerKey": snapshot["offer_key"],
                "proof": {"historicalReady": False},
                "riskFlags": [],
                "rankReasons": [],
                "entries": [],
                "rationale": "synthetic",
                "createdAt": datetime(2026, 6, 22, 10, 0, tzinfo=UTC).isoformat(),
                "updatedAt": datetime(2026, 6, 22, 10, 0, tzinfo=UTC).isoformat(),
            }
            candidates.append(candidate)
            by_match.setdefault(snapshot["match_key"], []).append(candidate)

        for bucket in by_match.values():
            qualifying = [row for row in bucket if row["passesStrategyFilters"]]
            if not qualifying:
                continue
            best = sorted(qualifying, key=lambda row: (row["strategyScore"], row["primaryEv"]), reverse=True)[0]
            best["isBestBetForMatch"] = True
            shortlist.append(best)

        return {
            "run": {
                "runId": run_meta["runId"],
                "runKey": run_meta["runKey"],
                "date": run_meta["date"],
                "strategyId": run_meta["strategyId"],
                "strategyLabel": run_meta["strategyLabel"],
                "source": run_meta["source"],
                "checkpointKey": run_meta["checkpointKey"],
                "checkpointLabel": run_meta["checkpointLabel"],
                "checkpointTargetDays": run_meta["checkpointTargetDays"],
                "analyzedMatches": len(by_match),
                "marketCount": len(candidates),
                "candidateCount": len(candidates),
                "qualifyingCandidateCount": len([row for row in candidates if row["passesStrategyFilters"]]),
                "shortlistCount": len(shortlist),
                "provenCount": 0,
                "createdAt": datetime(2026, 6, 22, 10, 0, tzinfo=UTC).isoformat(),
                "updatedAt": datetime(2026, 6, 22, 10, 0, tzinfo=UTC).isoformat(),
            },
            "candidates": candidates,
            "shortlist": shortlist,
            "snapshot": {
                "runId": run_meta["runId"],
                "runKey": run_meta["runKey"],
                "date": run_meta["date"],
                "strategyId": run_meta["strategyId"],
                "strategyLabel": run_meta["strategyLabel"],
                "checkpointKey": run_meta["checkpointKey"],
                "checkpointLabel": run_meta["checkpointLabel"],
                "checkpointTargetDays": run_meta["checkpointTargetDays"],
                "analyzedMatches": len(by_match),
                "shortlist": shortlist,
                "createdAt": datetime(2026, 6, 22, 10, 0, tzinfo=UTC).isoformat(),
            },
        }


def test_run_auto_analysis_pipeline_dry_run_builds_candidates_and_shortlist() -> None:
    summary = run_auto_analysis_pipeline(
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
        source_workflow="run-auto-analysis-checkpoints.yml",
        strategy_id="balanced",
        analysis_oracle=FakeAnalysisOracle(),
        dry_run=True,
        transport=fake_transport,
        odds_oracle=None,
        model_oracle=FakeModelOracle(),
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["matched_events"] == 1
    assert summary["model_snapshots"] == 2
    assert summary["valid_model_snapshots"] == 2
    assert summary["analysis_candidates"] == 2
    assert summary["qualifying_candidates"] == 1
    assert summary["analysis_shortlist"] == 1
    assert summary["parity_status_counts"] == {"matched": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}


def test_run_auto_analysis_pipeline_dry_run_handles_empty_target_window() -> None:
    summary = run_auto_analysis_pipeline(
        targets=[],
        support_docs=build_support_docs(),
        source_workflow="run-auto-analysis-checkpoints.yml",
        strategy_id="balanced",
        dry_run=True,
        fetched_at=datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
    )

    assert summary["target_matches"] == 0
    assert summary["model_snapshots"] == 0
    assert summary["analysis_candidates"] == 0
    assert summary["analysis_shortlist"] == 0
    assert summary["parity_status_counts"] == {"no_targets": 1}
    assert summary["audit_status_counts"] == {"ok": 1}
    assert summary["health_status_counts"] == {"ok": 1}
