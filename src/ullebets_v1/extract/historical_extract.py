from __future__ import annotations

import json
from typing import Any

import pandas as pd


PRIMARY_MODELED_STATS = {"totalShots", "shotsOnGoal", "cornerKicks"}


def _map_condition_to_direction(raw_condition: Any) -> str:
    condition = str(raw_condition or "").strip().lower()
    if "under" in condition:
        return "under"
    return "over"


def _map_win_to_result(value: Any) -> str | None:
    if value is True:
        return "win"
    if value is False:
        return "loss"
    return None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def flatten_unibet_backtest_docs(docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for doc in docs:
        for line in doc.get("lines") or []:
            rows.append(
                {
                    "match_id": _as_str(doc.get("matchId")),
                    "event_id": _as_str(doc.get("eventId")),
                    "match_date": doc.get("matchDate"),
                    "league_name": doc.get("league"),
                    "home_team_name": doc.get("homeTeam"),
                    "away_team_name": doc.get("awayTeam"),
                    "generated_at": doc.get("generatedAt"),
                    "updated_at": doc.get("updatedAt"),
                    "url": doc.get("url"),
                    "bet_key": _as_str(line.get("betKey")),
                    "stat_key": line.get("statKey"),
                    "period": line.get("period"),
                    "scope": line.get("scope"),
                    "direction": _map_condition_to_direction(line.get("condition")),
                    "condition_label": line.get("condition"),
                    "line_value": line.get("line"),
                    "odds_decimal": line.get("odds"),
                    "actual_value": line.get("actual"),
                    "settlement_result": _map_win_to_result(line.get("win")),
                    "win_flag": line.get("win"),
                    "legacy_ev_value": line.get("value"),
                    "ev_details": _as_json(line.get("evDetails")),
                    "is_primary_modeled_stat": line.get("statKey") in PRIMARY_MODELED_STATS,
                }
            )
    return rows


def flatten_unibet_snapshot_lines(docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for doc in docs:
        for snapshot in doc.get("snapshots") or []:
            fetched_at = snapshot.get("fetchedAt")
            for line in snapshot.get("lines") or []:
                rows.append(
                    {
                        "match_id": _as_str(snapshot.get("matchId", doc.get("matchId"))),
                        "event_id": _as_str(snapshot.get("eventId", doc.get("eventId"))),
                        "match_date": snapshot.get("matchDate", doc.get("matchDate")),
                        "league_name": snapshot.get("league", doc.get("league")),
                        "home_team_name": snapshot.get("homeTeam", doc.get("homeTeam")),
                        "away_team_name": snapshot.get("awayTeam", doc.get("awayTeam")),
                        "snapshot_type": snapshot.get("type"),
                        "snapshot_fetched_at": fetched_at,
                        "bet_key": _as_str(line.get("betKey")),
                        "stat_key": line.get("statKey"),
                        "period": line.get("period"),
                        "scope": line.get("scope"),
                        "direction": _map_condition_to_direction(line.get("condition")),
                        "condition_label": line.get("condition"),
                        "line_value": line.get("line"),
                        "odds_decimal": line.get("odds"),
                        "legacy_ev_value": line.get("value"),
                        "is_primary_modeled_stat": line.get("statKey") in PRIMARY_MODELED_STATS,
                    }
                )
    return rows


def flatten_analysis_snapshot_shortlist(docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for doc in docs:
        for item in doc.get("shortlist") or []:
            bet = item.get("bet") or {}
            rows.append(
                {
                    "snapshot_created_at": doc.get("createdAt"),
                    "strategy_id": doc.get("strategyId"),
                    "strategy_label": doc.get("strategyLabel"),
                    "snapshot_date": doc.get("date"),
                    "match_id": _as_str(item.get("matchId")),
                    "bet_key": _as_str(bet.get("key")),
                    "stat_key": bet.get("statKey"),
                    "period": bet.get("period"),
                    "scope": bet.get("scope"),
                    "direction": bet.get("direction"),
                    "line_value": bet.get("line"),
                    "odds_decimal": bet.get("odds"),
                    "headline": item.get("headline"),
                    "primary_ev": item.get("primaryEv"),
                    "strategy_score": item.get("strategyScore"),
                }
            )
    return rows


def flatten_auto_analysis_bets(docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for doc in docs:
        bet = doc.get("bet") or {}
        ranking = doc.get("ranking") or {}
        proof = doc.get("proof") or {}
        rows.append(
            {
                "run_id": _as_str(doc.get("runId")),
                "run_key": doc.get("runKey"),
                "date": doc.get("date"),
                "strategy_id": doc.get("strategyId"),
                "strategy_label": doc.get("strategyLabel"),
                "source": doc.get("source"),
                "tracking_key": _as_str(doc.get("trackingKey")),
                "comparison_key": _as_str(doc.get("comparisonKey")),
                "match_id": _as_str(doc.get("matchId")),
                "home_team_name": doc.get("homeTeamName"),
                "away_team_name": doc.get("awayTeamName"),
                "league_name": doc.get("leagueName"),
                "match_date": doc.get("matchDate"),
                "timestamp": doc.get("timestamp"),
                "checkpoint_key": doc.get("checkpointKey"),
                "checkpoint_label": doc.get("checkpointLabel"),
                "checkpoint_target_days": doc.get("checkpointTargetDays"),
                "headline": doc.get("headline"),
                "primary_ev": doc.get("primaryEv"),
                "confidence_score": doc.get("confidenceScore"),
                "agreement_pct": doc.get("agreementPct"),
                "sample_size": doc.get("sampleSize"),
                "strategy_score": doc.get("strategyScore"),
                "market_count": doc.get("marketCount"),
                "stake_units": doc.get("stakeUnits"),
                "expected_units": doc.get("expectedUnits"),
                "event_url": doc.get("eventUrl"),
                "status": doc.get("status"),
                "result": doc.get("result"),
                "actual_value": doc.get("actualValue"),
                "roi_units": doc.get("roiUnits"),
                "pnl_units": doc.get("pnlUnits"),
                "is_positive_ev": doc.get("isPositiveEv"),
                "passes_strategy_filters": doc.get("passesStrategyFilters"),
                "is_best_bet_for_match": doc.get("isBestBetForMatch"),
                "was_shown_in_ui": doc.get("wasShownInUi"),
                "proof_score": proof.get("proofScore"),
                "proof_historical_ready": proof.get("historicalReady"),
                "ranking_edge_score": ranking.get("edgeScore"),
                "ranking_confidence_score": ranking.get("confidenceScore"),
                "ranking_consensus_score": ranking.get("consensusScore"),
                "ranking_sample_score": ranking.get("sampleScore"),
                "ranking_price_score": ranking.get("priceScore"),
                "ranking_market_score": ranking.get("marketScore"),
                "ranking_formula_spread": ranking.get("formulaSpread"),
                "ranking_formula_deviation": ranking.get("formulaDeviation"),
                "bet_key": _as_str(bet.get("key")),
                "stat_key": bet.get("statKey"),
                "period": bet.get("period"),
                "scope": bet.get("scope"),
                "direction": bet.get("direction"),
                "line_value": bet.get("line"),
                "odds_decimal": bet.get("odds"),
                "created_at": doc.get("createdAt"),
                "updated_at": doc.get("updatedAt"),
            }
        )
    return rows


def flatten_auto_analysis_runs(docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for doc in docs:
        rows.append(
            {
                "run_id": _as_str(doc.get("runId")),
                "run_key": doc.get("runKey"),
                "date": doc.get("date"),
                "strategy_id": doc.get("strategyId"),
                "strategy_label": doc.get("strategyLabel"),
                "source": doc.get("source"),
                "checkpoint_key": doc.get("checkpointKey"),
                "checkpoint_label": doc.get("checkpointLabel"),
                "checkpoint_target_days": doc.get("checkpointTargetDays"),
                "analyzed_matches": doc.get("analyzedMatches"),
                "market_count": doc.get("marketCount"),
                "candidate_count": doc.get("candidateCount"),
                "qualifying_candidate_count": doc.get("qualifyingCandidateCount"),
                "shortlist_count": doc.get("shortlistCount"),
                "proven_count": doc.get("provenCount"),
                "created_at": doc.get("createdAt"),
                "updated_at": doc.get("updatedAt"),
            }
        )
    return rows


def flatten_ai_generated_bets(docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for doc in docs:
        for line in doc.get("lines") or []:
            rows.append(
                {
                    "doc_id": doc.get("slug"),
                    "generated_at": doc.get("generatedAt"),
                    "updated_at": doc.get("updatedAt"),
                    "match_date": doc.get("matchDate"),
                    "event_id": _as_str(doc.get("eventId")),
                    "match_id": _as_str(line.get("matchId", doc.get("matchId"))),
                    "league_name": doc.get("league"),
                    "home_team_name": doc.get("homeTeam"),
                    "away_team_name": doc.get("awayTeam"),
                    "source": doc.get("source"),
                    "doc_type": doc.get("type"),
                    "horizon_days": doc.get("horizonDays"),
                    "total_bets": doc.get("totalBets"),
                    "bet_key": _as_str(line.get("betKey")),
                    "stat_key": line.get("statKey"),
                    "period": line.get("period"),
                    "scope": line.get("scope"),
                    "direction": line.get("direction"),
                    "line_value": line.get("line"),
                    "odds_decimal": line.get("odds"),
                    "primary_ev": line.get("primaryEv"),
                    "legacy_ev_pct": line.get("legacyEvPct"),
                    "combo_score": line.get("comboScore"),
                    "combo_rank": line.get("comboRank"),
                    "actual_value": line.get("actual"),
                    "settlement_result": _map_win_to_result(line.get("win")),
                    "win_flag": line.get("win"),
                    "has_snapshots": bool(doc.get("snapshots")),
                }
            )
    return rows


def flatten_ai_generated_snapshots(docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for doc in docs:
        for snapshot in doc.get("snapshots") or []:
            for line in snapshot.get("lines") or []:
                rows.append(
                    {
                        "doc_id": doc.get("slug"),
                        "snapshot_type": snapshot.get("type"),
                        "run_date": snapshot.get("runDate"),
                        "snapshot_fetched_at": snapshot.get("fetchedAt"),
                        "horizon_days": snapshot.get("horizonDays"),
                        "event_id": _as_str(snapshot.get("eventId", doc.get("eventId"))),
                        "match_id": _as_str(line.get("matchId", snapshot.get("matchId", doc.get("matchId")))),
                        "match_date": snapshot.get("matchDate", doc.get("matchDate")),
                        "league_name": snapshot.get("league", doc.get("league")),
                        "home_team_name": snapshot.get("homeTeam", doc.get("homeTeam")),
                        "away_team_name": snapshot.get("awayTeam", doc.get("awayTeam")),
                        "source": snapshot.get("source", doc.get("source")),
                        "bet_key": _as_str(line.get("betKey")),
                        "stat_key": line.get("statKey"),
                        "period": line.get("period"),
                        "scope": line.get("scope"),
                        "direction": line.get("direction"),
                        "line_value": line.get("line"),
                        "odds_decimal": line.get("odds"),
                        "primary_ev": line.get("primaryEv"),
                        "actual_value": line.get("actual"),
                        "settlement_result": _map_win_to_result(line.get("win")),
                        "win_flag": line.get("win"),
                    }
                )
    return rows


def flatten_result_loop_bets(docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for doc in docs:
        bet = doc.get("bet") or {}
        ranking = doc.get("ranking") or {}
        rows.append(
            {
                "tracking_key": _as_str(doc.get("trackingKey")),
                "created_at": doc.get("createdAt"),
                "updated_at": doc.get("updatedAt"),
                "match_id": _as_str(doc.get("matchId")),
                "league_name": doc.get("leagueName"),
                "home_team_name": doc.get("homeTeamName"),
                "away_team_name": doc.get("awayTeamName"),
                "source": doc.get("source"),
                "headline": doc.get("headline"),
                "stake_units": doc.get("stakeUnits"),
                "primary_ev": doc.get("primaryEv"),
                "strategy_score": doc.get("strategyScore"),
                "confidence_score": doc.get("confidenceScore"),
                "bet_key": _as_str(bet.get("key")),
                "stat_key": bet.get("statKey"),
                "period": bet.get("period"),
                "scope": bet.get("scope"),
                "direction": bet.get("direction"),
                "line_value": bet.get("line"),
                "odds_decimal": bet.get("odds"),
                "ranking_agreement_pct": ranking.get("agreementPct"),
                "ranking_confidence_score": ranking.get("confidenceScore"),
                "ranking_market_score": ranking.get("marketScore"),
            }
        )
    return rows


def flatten_closing_line_tracking(docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for doc in docs:
        bet = doc.get("bet") or {}
        rows.append(
            {
                "tracking_key": _as_str(doc.get("trackingKey")),
                "created_at": doc.get("createdAt"),
                "updated_at": doc.get("updatedAt"),
                "match_id": _as_str(doc.get("matchId")),
                "event_id": _as_str(doc.get("eventId")),
                "event_url": doc.get("eventUrl"),
                "event_timestamp_ms": doc.get("eventTimestampMs"),
                "event_started": doc.get("eventStarted"),
                "league_name": doc.get("leagueName"),
                "home_team_name": doc.get("homeTeamName"),
                "away_team_name": doc.get("awayTeamName"),
                "headline": doc.get("headline"),
                "opening_odds": doc.get("openingOdds"),
                "closing_odds": doc.get("closingOdds"),
                "latest_observed_odds": doc.get("latestObservedOdds"),
                "opening_observed_at": doc.get("openingObservedAt"),
                "closing_observed_at": doc.get("closingObservedAt"),
                "latest_observed_at": doc.get("latestObservedAt"),
                "prematch_observation_count": doc.get("prematchObservationCount"),
                "clv_pct": doc.get("clvPct"),
                "beat_closing_line": doc.get("beatClosingLine"),
                "bet_key": _as_str(bet.get("key")),
                "stat_key": bet.get("statKey"),
                "period": bet.get("period"),
                "scope": bet.get("scope"),
                "direction": bet.get("direction"),
                "line_value": bet.get("line"),
                "odds_decimal": bet.get("odds"),
                "price_history": _as_json(doc.get("priceHistory")),
            }
        )
    return rows


def dataframe_from_rows(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows if rows else [])
    for column in frame.columns:
        if frame[column].dtype != "object":
            continue
        if frame[column].map(lambda value: isinstance(value, (dict, list))).any():
            frame[column] = frame[column].map(_as_json)
    return frame
