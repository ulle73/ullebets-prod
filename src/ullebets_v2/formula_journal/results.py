from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import math
from typing import Any, Iterable

from pymongo import UpdateOne

from ullebets_v2.clv_tracking.service import build_clv_tracking_docs
from ullebets_v2.formula_journal.observations import JS_OBSERVATION_SCHEMA_VERSION
from ullebets_v2.settlement.service import (
    FORMULA_OBSERVATION_SELECTION_SOURCE,
    build_settled_docs,
)
from ullebets_v2.storage.collections import (
    CLOSING_LINES,
    FORMULA_OBSERVATIONS,
    FORMULA_RESULTS,
    MATCH_RESULTS_CANONICAL,
    MATCH_STATS_CANONICAL,
)


class FormulaResultConflict(RuntimeError):
    """A settled formula result would be changed by a later refresh."""


RESULT_FINGERPRINT_EXCLUDED_FIELDS = {
    "_id",
    "refreshed_at",
    "result_fingerprint_sha256",
}
SETTLED_IMMUTABLE_FIELDS = {
    "settlement_status",
    "settlement_result",
    "actual_value",
    "home_value",
    "away_value",
    "win",
    "stake_units",
    "pnl_units",
}


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _result_fingerprint(row: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in row.items()
        if key not in RESULT_FINGERPRINT_EXCLUDED_FIELDS
    }
    encoded = json.dumps(
        _json_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tracking_doc(observation: dict[str, Any]) -> dict[str, Any]:
    key = str(observation["observation_key"])
    return {
        **observation,
        "prediction_key": key,
        "selection_key": key,
        "tracking_key": key,
        "clv_key": key,
        "tracking_source": FORMULA_OBSERVATIONS,
        "prediction_type": "formula_shadow_observation",
        "selected_odds": observation.get("offered_odds"),
        "saved_odds": observation.get("offered_odds"),
        "saved_at": observation.get("odds_snapshot_time"),
        "stake_units": 1.0,
        "invalid_for_model": False,
        "valid_for_forward_evaluation": True,
    }


def _excluded_result(
    observation: dict[str, Any],
    *,
    refreshed_at: datetime,
) -> dict[str, Any]:
    return {
        **observation,
        "result_key": observation["observation_key"],
        "settlement_status": "excluded",
        "settlement_result": None,
        "actual_value": None,
        "home_value": None,
        "away_value": None,
        "win": None,
        "stake_units": 0.0,
        "pnl_units": 0.0,
        "roi_units": None,
        "valid_for_performance": False,
        "settlement_valid_for_calibration": False,
        "clv_status": "excluded",
        "official_clv": False,
        "clv_pct": None,
        "beat_closing_line": None,
        "refreshed_at": refreshed_at,
    }


def _settlement_eligible_observation(observation: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(observation)
    if (
        normalized.get("source_type") == "js_formula"
        and normalized.get("observation_schema_version")
        != JS_OBSERVATION_SCHEMA_VERSION
    ):
        normalized.update(
            {
                "valid_for_comparison": False,
                "is_positive_ev": False,
                "shadow_stake_units": 0.0,
                "exclusion_reason": "superseded_js_observation_schema",
            }
        )
    return normalized


def build_formula_result_docs(
    *,
    observations: list[dict[str, Any]],
    match_stats_canonical: list[dict[str, Any]],
    match_results_canonical: list[dict[str, Any]],
    closing_line_docs: list[dict[str, Any]],
    refreshed_at: datetime,
) -> list[dict[str, Any]]:
    normalized_observations = [
        _settlement_eligible_observation(row) for row in observations
    ]
    valid_observations = [
        row
        for row in normalized_observations
        if row.get("valid_for_comparison") is True
    ]
    tracking_docs = [_tracking_doc(row) for row in valid_observations]
    settled_docs = build_settled_docs(
        selection_docs=tracking_docs,
        match_stats_canonical=match_stats_canonical,
        match_results_canonical=match_results_canonical,
        selection_source=FORMULA_OBSERVATION_SELECTION_SOURCE,
        settled_at=refreshed_at,
    )
    clv_docs = build_clv_tracking_docs(
        tracked_bet_docs=tracking_docs,
        closing_line_docs=closing_line_docs,
        refreshed_at=refreshed_at,
    )
    settled_by_key = {
        str(row["observation_key"]): row
        for row in settled_docs
    }
    clv_by_key = {
        str(row["selection_key"]): row
        for row in clv_docs
        if row.get("selection_key")
    }
    results: list[dict[str, Any]] = []
    for observation in normalized_observations:
        key = str(observation["observation_key"])
        if observation.get("valid_for_comparison") is not True:
            result = _excluded_result(observation, refreshed_at=refreshed_at)
            result["result_fingerprint_sha256"] = _result_fingerprint(result)
            results.append(result)
            continue
        settlement = settled_by_key[key]
        clv = clv_by_key.get(key, {})
        positive = (
            observation.get("is_positive_ev") is True
            and float(observation.get("shadow_stake_units") or 0.0) > 0.0
        )
        probability = observation.get("predicted_win_probability")
        probability_valid = (
            isinstance(probability, (int, float))
            and not isinstance(probability, bool)
            and math.isfinite(float(probability))
            and 0.0 <= float(probability) <= 1.0
        )
        settlement_result = settlement.get("settlement_result")
        valid_for_calibration = (
            settlement.get("settlement_status") == "settled"
            and settlement_result in {"win", "loss"}
            and probability_valid
        )
        result = {
            **observation,
            "result_key": key,
            "settlement_status": settlement.get("settlement_status"),
            "settlement_result": settlement_result,
            "actual_value": settlement.get("actual_value"),
            "home_value": settlement.get("home_value"),
            "away_value": settlement.get("away_value"),
            "win": settlement.get("win"),
            "stake_units": float(observation.get("shadow_stake_units") or 0.0),
            "pnl_units": settlement.get("pnl_units") if positive else 0.0,
            "roi_units": settlement.get("roi_units") if positive else None,
            "actual_source": settlement.get("actual_source"),
            "actual_source_status": settlement.get("actual_source_status"),
            "timing_status": settlement.get("timing_status"),
            "valid_for_performance": (
                positive and settlement.get("valid_for_performance") is True
            ),
            "settlement_valid_for_calibration": valid_for_calibration,
            "clv_status": clv.get("clv_status") or "missing_closing_line",
            "official_clv": bool(clv.get("official_clv")),
            "clv_pct": clv.get("clv_pct"),
            "implied_edge_delta": clv.get("implied_edge_delta"),
            "beat_closing_line": clv.get("beat_closing_line"),
            "closing_odds": clv.get("closing_odds"),
            "closing_snapshot_label": clv.get("closing_snapshot_label"),
            "closing_snapshot_time": clv.get("closing_snapshot_time"),
            "closing_quality": clv.get("closing_quality"),
            "refreshed_at": refreshed_at,
        }
        result["result_fingerprint_sha256"] = _result_fingerprint(result)
        results.append(result)
    return results


def _settled_fields_changed(existing: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return any(existing.get(field) != candidate.get(field) for field in SETTLED_IMMUTABLE_FIELDS)


def persist_formula_results(
    collection: Any,
    docs: Iterable[dict[str, Any]],
) -> dict[str, int]:
    metrics = {
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "conflicts": 0,
    }
    prepared: dict[str, dict[str, Any]] = {}
    for source in docs:
        doc = dict(source)
        key = str(doc.get("observation_key") or "")
        if not key:
            raise ValueError("formula result requires observation_key")
        doc["result_fingerprint_sha256"] = _result_fingerprint(doc)
        duplicate = prepared.get(key)
        if duplicate is not None and _result_fingerprint(duplicate) != _result_fingerprint(doc):
            metrics["conflicts"] += 1
            raise FormulaResultConflict(f"duplicate formula result conflict: {key}")
        prepared[key] = doc

    prepared_items = list(prepared.items())
    batch_size = 500
    for offset in range(0, len(prepared_items), batch_size):
        batch = prepared_items[offset : offset + batch_size]
        batch_by_key = dict(batch)
        existing_by_key = {
            str(row.get("observation_key") or ""): row
            for row in collection.find(
                {"observation_key": {"$in": list(batch_by_key)}},
                projection={"_id": 0},
            )
        }
        inserts: list[tuple[str, dict[str, Any]]] = []
        updates: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for key, doc in batch:
            existing = existing_by_key.get(key)
            if existing is None:
                inserts.append((key, doc))
                continue
            if existing.get("settlement_status") == "settled" and _settled_fields_changed(existing, doc):
                metrics["conflicts"] += 1
                raise FormulaResultConflict(f"settled formula result conflict: {key}")
            if _result_fingerprint(existing) == _result_fingerprint(doc):
                metrics["unchanged"] += 1
                continue
            updates.append((key, existing, doc))

        if inserts:
            result = collection.bulk_write(
                [
                    UpdateOne(
                        {"observation_key": key},
                        {"$setOnInsert": doc},
                        upsert=True,
                    )
                    for key, doc in inserts
                ],
                ordered=False,
            )
            inserted = int(result.upserted_count)
            raced = len(inserts) - inserted
            metrics["inserted"] += inserted
            metrics["unchanged"] += raced
            if raced:
                raced_by_key = {
                    str(row.get("observation_key") or ""): row
                    for row in collection.find(
                        {"observation_key": {"$in": [key for key, _ in inserts]}},
                        projection={"_id": 0},
                    )
                }
                for key, doc in inserts:
                    stored = raced_by_key.get(key)
                    if stored is None or _result_fingerprint(stored) != _result_fingerprint(doc):
                        metrics["conflicts"] += 1
                        raise FormulaResultConflict(
                            f"formula result conflict after concurrent insert: {key}"
                        )

        if updates:
            result = collection.bulk_write(
                [
                    UpdateOne(
                        {
                            "observation_key": key,
                            "result_fingerprint_sha256": existing.get(
                                "result_fingerprint_sha256"
                            ),
                        },
                        {"$set": doc},
                        upsert=False,
                    )
                    for key, existing, doc in updates
                ],
                ordered=False,
            )
            if int(result.matched_count) != len(updates):
                metrics["conflicts"] += 1
                raise FormulaResultConflict(
                    "formula result changed concurrently during refresh"
                )
            metrics["updated"] += len(updates)
    return metrics


def _find_rows(collection: Any, query: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in collection.find(query, projection={"_id": 0})
    ]


def refresh_formula_results(
    *,
    database: Any,
    refreshed_at: datetime | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    timestamp = refreshed_at or datetime.now(tz=UTC)
    observations = _find_rows(
        database[FORMULA_OBSERVATIONS],
        {
            "$or": [
                {"source_type": "frozen_ml_model"},
                {
                    "source_type": "js_formula",
                    "observation_schema_version": JS_OBSERVATION_SCHEMA_VERSION,
                },
            ]
        },
    )
    match_keys = sorted(
        {str(row["match_key"]) for row in observations if row.get("match_key")}
    )
    match_query = {"match_key": {"$in": match_keys}} if match_keys else {}
    stats = _find_rows(database[MATCH_STATS_CANONICAL], match_query)
    match_results = _find_rows(database[MATCH_RESULTS_CANONICAL], match_query)
    closing_lines = _find_rows(database[CLOSING_LINES], match_query)
    result_docs = build_formula_result_docs(
        observations=observations,
        match_stats_canonical=stats,
        match_results_canonical=match_results,
        closing_line_docs=closing_lines,
        refreshed_at=timestamp,
    )
    persistence = {
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "conflicts": 0,
    }
    if not dry_run:
        persistence = persist_formula_results(
            database[FORMULA_RESULTS],
            result_docs,
        )
    return {
        "observations": len(observations),
        "match_keys": len(match_keys),
        "match_stats": len(stats),
        "match_results": len(match_results),
        "closing_lines": len(closing_lines),
        "result_docs": len(result_docs),
        "settled": sum(
            1 for row in result_docs if row.get("settlement_status") == "settled"
        ),
        "pending": sum(
            1
            for row in result_docs
            if row.get("settlement_status") in {"pending_result", "missing_actual"}
        ),
        "excluded": sum(
            1 for row in result_docs if row.get("settlement_status") == "excluded"
        ),
        "official_clv": sum(
            1 for row in result_docs if row.get("official_clv") is True
        ),
        "persistence": persistence,
        "dry_run": dry_run,
    }
