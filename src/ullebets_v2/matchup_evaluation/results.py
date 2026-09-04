from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from math import isfinite
from typing import Any, Iterable

from pymongo import UpdateOne

from ullebets_v2.settlement.common import (
    build_result_lookup,
    build_stat_scope_lookup,
    build_stats_lookup,
    resolve_actual_context,
)
from ullebets_v2.storage.collections import (
    CLOSING_LINES,
    MARKET_SNAPSHOTS,
    MATCHUP_OBSERVATIONS,
    MATCHUP_RESULTS,
    MATCH_RESULTS_CANONICAL,
    MATCH_STATS_CANONICAL,
)


class MatchupResultConflict(RuntimeError):
    pass


TERMINAL_PREFIX = "resolved_"
RESULT_FINGERPRINT_EXCLUDED = {"_id", "refreshed_at", "result_fingerprint_sha256"}
TERMINAL_FIELDS = {
    "actual_value", "home_value", "away_value", "predictor_verdict", "signed_residual",
    "market_verdict", "stake_units", "pnl_units",
}
DATABASE_QUERY_BATCH_SIZE = 100


def filter_refreshable_observations(
    observations: Iterable[dict[str, Any]],
    existing_results: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    terminal_keys = {
        str(row.get("observation_key"))
        for row in existing_results
        if str(row.get("lifecycle_status") or "").startswith(TERMINAL_PREFIX)
    }
    return [
        row
        for row in observations
        if row.get("evidence_class") != "legacy_descriptive"
        and str(row.get("observation_key") or "") not in terminal_keys
    ]


def _find_by_values(
    collection: Any,
    *,
    field: str,
    values: Iterable[str],
    projection: dict[str, int],
) -> list[dict[str, Any]]:
    requested = sorted({str(value) for value in values if value})
    rows: list[dict[str, Any]] = []
    for start in range(0, len(requested), DATABASE_QUERY_BATCH_SIZE):
        batch = requested[start : start + DATABASE_QUERY_BATCH_SIZE]
        rows.extend(collection.find({field: {"$in": batch}}, projection=projection))
    return rows


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return (_time(value) or value).isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def result_fingerprint(doc: dict[str, Any]) -> str:
    payload = {key: value for key, value in doc.items() if key not in RESULT_FINGERPRINT_EXCLUDED}
    encoded = json.dumps(_json_value(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def predictor_result(direction: str, actual: float, baseline: float) -> tuple[float, str]:
    residual = actual - baseline if direction == "over" else baseline - actual
    return residual, "hit" if residual > 0 else "miss" if residual < 0 else "push"


def market_result(direction: str, actual: float, line: float, odds: float) -> tuple[str, float, float]:
    delta = actual - line if direction == "over" else line - actual
    verdict = "win" if delta > 0 else "loss" if delta < 0 else "push"
    pnl = odds - 1.0 if verdict == "win" else -1.0 if verdict == "loss" else 0.0
    return verdict, 1.0, pnl


def _same_context(observation: dict[str, Any], row: dict[str, Any]) -> bool:
    return all(str(observation.get(field) or "") == str(row.get(field) or "") for field in ("match_key", "stat_key", "period", "scope"))


def same_line_closing(observation: dict[str, Any], closing_rows: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    selected_line = _number(observation.get("line_value"))
    exact = [
        row for row in closing_rows
        if _same_context(observation, row)
        and selected_line is not None
        and _number(row.get("line")) == selected_line
        and row.get("closing_quality") in {"t10", "t30_fallback"}
        and row.get("accepted_for_product_clv") is not False
    ]
    preferred = [row for row in exact if row.get("closing_quality") == "t10"]
    pool = preferred or [row for row in exact if row.get("closing_quality") == "t30_fallback"]
    return max(pool, key=lambda row: str(row.get("closing_snapshot_time") or "")) if pool else None


def _different_line_close(observation: dict[str, Any], closing_rows: Iterable[dict[str, Any]]) -> float | None:
    selected_line = _number(observation.get("line_value"))
    candidates = [row for row in closing_rows if _same_context(observation, row) and row.get("closing_quality") in {"t10", "t30_fallback"} and _number(row.get("line")) != selected_line]
    if not candidates:
        return None
    preferred = [row for row in candidates if row.get("closing_quality") == "t10"] or candidates
    return _number(max(preferred, key=lambda row: str(row.get("closing_snapshot_time") or "")).get("line"))


def _odds_history(observation: dict[str, Any], snapshots: Iterable[dict[str, Any]], closing: dict[str, Any] | None) -> list[dict[str, Any]]:
    direction = str(observation.get("selected_direction") or "")
    line = _number(observation.get("line_value"))
    rows = []
    for snapshot in snapshots:
        if not _same_context(observation, snapshot) or _number(snapshot.get("line")) != line:
            continue
        odds = _number(snapshot.get(f"{direction}_odds"))
        observed_at = _time(snapshot.get("snapshot_time"))
        kickoff = _time(snapshot.get("match_start_time"))
        if odds is None or observed_at is None or (kickoff is not None and observed_at >= kickoff):
            continue
        rows.append({
            "snapshotLabel": snapshot.get("snapshot_label"),
            "observedAt": observed_at,
            "odds": odds,
            "lineValue": line,
            "selected": snapshot.get("snapshot_key") == observation.get("snapshot_key"),
            "closing": bool(closing and snapshot.get("snapshot_label") == closing.get("closing_snapshot_label")),
        })
    return sorted(rows, key=lambda row: (row["observedAt"], str(row.get("snapshotLabel") or "")))


def build_matchup_result_docs(
    *,
    observations: Iterable[dict[str, Any]],
    match_stats_canonical: list[dict[str, Any]],
    match_results_canonical: list[dict[str, Any]],
    closing_line_docs: list[dict[str, Any]],
    refreshed_at: datetime,
    market_snapshot_docs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    result_lookup = build_result_lookup(match_results_canonical)
    stats_lookup = build_stats_lookup(match_stats_canonical)
    scopes = build_stat_scope_lookup(match_stats_canonical)
    docs = []
    for observation in observations:
        actual = resolve_actual_context(row=observation, result_lookup=result_lookup, stats_lookup=stats_lookup, stat_scope_lookup=scopes)
        direction = str(observation.get("selected_direction") or "")
        baseline = _number(observation.get("league_baseline"))
        actual_value = _number(actual.get("actual_value"))
        lifecycle = "pending_result"
        predictor_verdict = None
        residual = None
        market_verdict = None
        stake = 0.0
        pnl = 0.0
        valid_predictor = bool(observation.get("valid_for_predictor"))
        valid_market = False
        if not valid_predictor:
            lifecycle = "excluded_timing" if observation.get("exclusion_reason") == "outside_t1d_window" else "excluded_mapping"
        elif actual.get("actual_resolution_status") == "missing_actual":
            lifecycle = "missing_actual"
        elif actual.get("actual_resolution_status") == "resolved" and actual_value is not None and baseline is not None and direction in {"over", "under"}:
            residual, predictor_verdict = predictor_result(direction, actual_value, baseline)
            line = _number(observation.get("line_value"))
            odds = _number(observation.get("selected_odds"))
            if observation.get("market_eligibility") == "eligible" and line is not None and odds is not None:
                market_verdict, stake, pnl = market_result(direction, actual_value, line, odds)
                valid_market = True
                lifecycle = "resolved_market"
            else:
                lifecycle = "resolved_predictor_only"
        closing = same_line_closing(observation, closing_line_docs) if valid_market else None
        closing_odds = _number(closing.get(f"closing_{direction}_odds")) if closing else None
        selected_odds = _number(observation.get("selected_odds"))
        clv_pct = (selected_odds / closing_odds - 1.0) * 100.0 if selected_odds and closing_odds else None
        doc = {
            **{field: observation.get(field) for field in ("observation_key", "match_key", "fixture_date_stockholm", "match_start_time", "league_key", "league_name", "stat_key", "stat_label", "period", "period_label", "scope", "selected_direction", "score", "rank_position", "ranking_method", "policy_version", "evidence_class")},
            "lifecycle_status": lifecycle,
            "actual_value": actual_value,
            "home_value": actual.get("home_value"),
            "away_value": actual.get("away_value"),
            "actual_source_status": actual.get("actual_source_status"),
            "predictor_verdict": predictor_verdict,
            "signed_residual": residual,
            "market_verdict": market_verdict,
            "stake_units": stake,
            "pnl_units": pnl,
            "valid_for_predictor": valid_predictor,
            "valid_for_market": valid_market,
            "closing_quality": closing.get("closing_quality") if closing else None,
            "closing_snapshot_label": closing.get("closing_snapshot_label") if closing else None,
            "closing_snapshot_time": closing.get("closing_snapshot_time") if closing else None,
            "closing_odds": closing_odds,
            "clv_pct": clv_pct,
            "beat_closing_line": clv_pct > 0 if clv_pct is not None else None,
            "different_line_close": _different_line_close(observation, closing_line_docs) if valid_market else None,
            "odds_history": _odds_history(observation, market_snapshot_docs or [], closing),
            "refreshed_at": refreshed_at,
        }
        doc["result_fingerprint_sha256"] = result_fingerprint(doc)
        docs.append(doc)
    return docs


def merge_matchup_result(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if existing is None:
        return "insert", incoming
    if result_fingerprint(existing) == result_fingerprint(incoming):
        return "unchanged", existing
    if str(existing.get("lifecycle_status") or "").startswith(TERMINAL_PREFIX) and any(existing.get(field) != incoming.get(field) for field in TERMINAL_FIELDS):
        raise MatchupResultConflict(f"terminal matchup result conflict: {incoming.get('observation_key')}")
    return "replace_pending", incoming


def persist_matchup_results(collection: Any, docs: Iterable[dict[str, Any]]) -> dict[str, int]:
    prepared = {str(doc["observation_key"]): dict(doc) for doc in docs}
    existing = {
        str(row.get("observation_key")): row
        for row in _find_by_values(
            collection,
            field="observation_key",
            values=prepared,
            projection={"_id": 0},
        )
    }
    decisions = []
    metrics = {"inserted": 0, "updated": 0, "unchanged": 0, "conflicts": 0}
    try:
        for key, doc in prepared.items():
            decisions.append((key, *merge_matchup_result(existing.get(key), doc)))
    except MatchupResultConflict:
        metrics["conflicts"] += 1
        raise
    operations = []
    for key, action, doc in decisions:
        if action == "unchanged":
            metrics["unchanged"] += 1
        elif action == "insert":
            operations.append(UpdateOne({"observation_key": key}, {"$setOnInsert": doc}, upsert=True))
            metrics["inserted"] += 1
        else:
            operations.append(UpdateOne({"observation_key": key}, {"$set": doc}, upsert=False))
            metrics["updated"] += 1
    if operations:
        bulk_write = getattr(collection, "bulk_write", None)
        if callable(bulk_write):
            for start in range(0, len(operations), 100):
                bulk_write(operations[start : start + 100], ordered=False)
        elif hasattr(collection, "docs"):
            by_key = {str(row.get("observation_key")): row for row in collection.docs}
            for key, action, doc in decisions:
                if action == "insert":
                    collection.docs.append(dict(doc))
                elif action == "replace_pending":
                    by_key[key].clear()
                    by_key[key].update(dict(doc))
        else:
            raise TypeError("result collection must support bulk_write")
    return metrics


def refresh_matchup_results(*, database: Any, refreshed_at: datetime, date_from: str | None = None, date_to: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if date_from or date_to:
        date_filter: dict[str, str] = {}
        if date_from:
            date_filter["$gte"] = date_from
        if date_to:
            date_filter["$lte"] = date_to
        query["fixture_date_stockholm"] = date_filter
    candidate_observations = list(
        database[MATCHUP_OBSERVATIONS].find(query, projection={"_id": 0})
    )
    existing_results = _find_by_values(
        database[MATCHUP_RESULTS],
        field="observation_key",
        values=(str(row.get("observation_key") or "") for row in candidate_observations),
        projection={"_id": 0, "observation_key": 1, "lifecycle_status": 1},
    )
    observations = filter_refreshable_observations(candidate_observations, existing_results)
    legacy_skipped = sum(row.get("evidence_class") == "legacy_descriptive" for row in candidate_observations)
    terminal_keys = {
        str(row.get("observation_key"))
        for row in existing_results
        if str(row.get("lifecycle_status") or "").startswith(TERMINAL_PREFIX)
    }
    terminal_skipped = sum(
        row.get("evidence_class") != "legacy_descriptive"
        and str(row.get("observation_key") or "") in terminal_keys
        for row in candidate_observations
    )
    match_keys = sorted({str(row.get("match_key")) for row in observations if row.get("match_key")})
    result_docs = build_matchup_result_docs(
        observations=observations,
        match_stats_canonical=_find_by_values(database[MATCH_STATS_CANONICAL], field="match_key", values=match_keys, projection={"_id": 0}),
        match_results_canonical=_find_by_values(database[MATCH_RESULTS_CANONICAL], field="match_key", values=match_keys, projection={"_id": 0}),
        closing_line_docs=_find_by_values(database[CLOSING_LINES], field="match_key", values=match_keys, projection={"_id": 0}),
        market_snapshot_docs=_find_by_values(database[MARKET_SNAPSHOTS], field="match_key", values=match_keys, projection={"_id": 0}),
        refreshed_at=refreshed_at,
    ) if match_keys else []
    persistence = {"inserted": 0, "updated": 0, "unchanged": 0, "conflicts": 0} if dry_run else persist_matchup_results(database[MATCHUP_RESULTS], result_docs)
    return {
        "candidate_observations": len(candidate_observations),
        "observations": len(observations),
        "legacy_observations_skipped": legacy_skipped,
        "terminal_results_skipped": terminal_skipped,
        "results": len(result_docs),
        "lifecycle": {status: sum(row.get("lifecycle_status") == status for row in result_docs) for status in sorted({str(row.get("lifecycle_status")) for row in result_docs})},
        "persistence": persistence,
        "docs": result_docs if dry_run else [],
    }
