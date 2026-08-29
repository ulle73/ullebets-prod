from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from .observations import MATCHUP_EVALUATION_POLICY_VERSION, observation_fingerprint
from .results import predictor_result, result_fingerprint


def build_legacy_matchup_evaluation_docs(*, score_rows: Iterable[dict[str, Any]], generated_at: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    for row in score_rows:
        key = tuple(str(row.get(field) or "") for field in ("snapshot_date", "match_key", "stat_key", "period", "scope"))
        grouped.setdefault(key, []).append(dict(row))
    observations = []
    results = []
    for (snapshot_date, match_key, stat_key, period, scope), rows in sorted(grouped.items()):
        directional = {str(row.get("condition") or "").lower(): row for row in rows if str(row.get("condition") or "").lower() in {"over", "under"}}
        over = directional.get("over")
        under = directional.get("under")
        if over is None or under is None:
            continue
        try:
            over_score, under_score = float(over["score"]), float(under["score"])
        except (KeyError, TypeError, ValueError):
            continue
        if over_score == under_score or max(over_score, under_score) == 50.0:
            continue
        selected = over if over_score > under_score else under
        if selected.get("outcome_status") != "resolved" or selected.get("actual_value") is None:
            continue
        forecast = selected.get("forecast") if isinstance(selected.get("forecast"), dict) else {}
        baseline = forecast.get("leagueBaseline")
        if baseline is None:
            continue
        key = f"{MATCHUP_EVALUATION_POLICY_VERSION}|legacy|{selected.get('entry_key')}"
        observation = {
            "observation_key": key,
            "policy_version": MATCHUP_EVALUATION_POLICY_VERSION,
            "checkpoint_label": "LEGACY_PREJOURNAL",
            "evidence_class": "legacy_descriptive",
            "match_key": match_key,
            "fixture_date_stockholm": snapshot_date,
            "match_start_time": selected.get("match_start_time"),
            "league_key": selected.get("league_key"),
            "league_name": selected.get("league_name"),
            "stat_key": stat_key,
            "stat_label": selected.get("stat_label"),
            "period": period,
            "period_label": selected.get("period_label"),
            "scope": scope,
            "selected_direction": str(selected.get("condition")).lower(),
            "score": float(selected["score"]),
            "rank_position": selected.get("rank_position"),
            "league_baseline": float(baseline),
            "ranking_method": selected.get("ranking_method"),
            "market_eligibility": "legacy_unknown",
            "line_value": None,
            "selected_odds": None,
            "valid_for_predictor": False,
            "valid_for_market": False,
            "exclusion_reason": "legacy_prejournal",
            "captured_at": generated_at,
            "journaled_at": generated_at,
        }
        observation["observation_fingerprint_sha256"] = observation_fingerprint(observation)
        residual, verdict = predictor_result(observation["selected_direction"], float(selected["actual_value"]), float(baseline))
        result = {
            **{field: observation.get(field) for field in ("observation_key", "match_key", "fixture_date_stockholm", "match_start_time", "league_key", "league_name", "stat_key", "stat_label", "period", "period_label", "scope", "selected_direction", "score", "rank_position", "ranking_method", "policy_version", "evidence_class")},
            "lifecycle_status": "resolved_predictor_only",
            "actual_value": float(selected["actual_value"]),
            "home_value": selected.get("home_value"),
            "away_value": selected.get("away_value"),
            "predictor_verdict": verdict,
            "signed_residual": residual,
            "market_verdict": None,
            "stake_units": 0.0,
            "pnl_units": 0.0,
            "valid_for_predictor": False,
            "valid_for_market": False,
            "closing_quality": None,
            "closing_odds": None,
            "clv_pct": None,
            "odds_history": [],
            "refreshed_at": generated_at,
        }
        result["result_fingerprint_sha256"] = result_fingerprint(result)
        observations.append(observation)
        results.append(result)
    return observations, results
