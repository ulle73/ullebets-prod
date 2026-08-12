from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import math
from typing import Any, Iterable

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.forward_predictions import OUTCOME_COLUMNS


FINGERPRINT_EXCLUDED_COLUMNS = {
    "score_created_at",
    "score_fingerprint_sha256",
}
FLOAT_EQUIVALENCE_ABS_TOLERANCE = 1e-12


def _value(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if value is None or (
        isinstance(value, float) and np.isnan(value)
    ):
        return None
    return value


def _json_value(value: Any) -> Any:
    value = _value(value)
    if isinstance(value, datetime):
        normalized = (
            value
            if value.tzinfo is not None
            else value.replace(tzinfo=UTC)
        )
        return normalized.astimezone(UTC).isoformat()
    if isinstance(value, dict):
        return {
            str(key): _json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _sha256_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        _json_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _score_fingerprint(doc: dict[str, Any]) -> str:
    return _sha256_json(
        {
            key: value
            for key, value in doc.items()
            if key not in FINGERPRINT_EXCLUDED_COLUMNS
        }
    )


def _normalize_datetime_utc(value: datetime) -> datetime:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC)


def _score_values_equivalent(left: Any, right: Any) -> bool:
    left = _value(left)
    right = _value(right)
    if isinstance(left, datetime) or isinstance(right, datetime):
        if not isinstance(left, datetime) or not isinstance(right, datetime):
            return False
        return _normalize_datetime_utc(left) == _normalize_datetime_utc(right)
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(
            float(left),
            float(right),
            rel_tol=0.0,
            abs_tol=FLOAT_EQUIVALENCE_ABS_TOLERANCE,
        )
    if isinstance(left, dict) or isinstance(right, dict):
        if not isinstance(left, dict) or not isinstance(right, dict):
            return False
        return left.keys() == right.keys() and all(
            _score_values_equivalent(left[key], right[key])
            for key in left
        )
    if isinstance(left, (list, tuple)) or isinstance(right, (list, tuple)):
        if not isinstance(left, (list, tuple)) or not isinstance(right, (list, tuple)):
            return False
        return len(left) == len(right) and all(
            _score_values_equivalent(item_left, item_right)
            for item_left, item_right in zip(left, right, strict=True)
        )
    return left == right


def _score_documents_equivalent(existing: dict[str, Any], candidate: dict[str, Any]) -> bool:
    excluded_columns = {*FINGERPRINT_EXCLUDED_COLUMNS, "_id"}
    existing_values = {
        key: value
        for key, value in existing.items()
        if key not in excluded_columns
    }
    candidate_values = {
        key: value
        for key, value in candidate.items()
        if key not in excluded_columns
    }
    return _score_values_equivalent(existing_values, candidate_values)


def audit_forward_score_docs(
    rows: list[dict[str, Any]],
    *,
    model_id: str,
) -> dict[str, object]:
    model_rows = [
        row for row in rows
        if str(row.get("model_id")) == model_id
    ]
    seen_score_keys: set[str] = set()
    missing_timing = 0
    timing_violations = 0
    outcome_mutation_rows = 0
    duplicate_score_keys = 0
    fingerprint_mismatches = 0
    invalid_policy_rows = 0
    valid_scores = 0

    for row in model_rows:
        row_is_valid = True
        score_key = str(row.get("score_key") or "")
        if not score_key or score_key in seen_score_keys:
            duplicate_score_keys += 1
            row_is_valid = False
        if score_key:
            seen_score_keys.add(score_key)

        snapshot_time = pd.to_datetime(
            row.get("odds_snapshot_time"),
            errors="coerce",
            utc=True,
        )
        created_at = pd.to_datetime(
            row.get("score_created_at"),
            errors="coerce",
            utc=True,
        )
        match_start = pd.to_datetime(
            row.get("match_start_time"),
            errors="coerce",
            utc=True,
        )
        if (
            pd.isna(snapshot_time)
            or pd.isna(created_at)
            or pd.isna(match_start)
        ):
            missing_timing += 1
            row_is_valid = False
        elif (
            snapshot_time > created_at
            or snapshot_time >= match_start
            or created_at >= match_start
        ):
            timing_violations += 1
            row_is_valid = False

        if any(
            row.get(field) is not None
            for field in OUTCOME_COLUMNS
        ):
            outcome_mutation_rows += 1
            row_is_valid = False

        if (
            row.get("valid_for_policy_evaluation") is not True
            or row.get("invalid_for_model") is True
        ):
            invalid_policy_rows += 1
            row_is_valid = False

        if (
            row.get("score_fingerprint_sha256")
            != _score_fingerprint(row)
        ):
            fingerprint_mismatches += 1
            row_is_valid = False

        if row_is_valid:
            valid_scores += 1

    invalid_scores = len(model_rows) - valid_scores
    return {
        "model_id": model_id,
        "scores": len(model_rows),
        "valid_scores": valid_scores,
        "invalid_scores": invalid_scores,
        "status": "ok" if invalid_scores == 0 else "warn",
        "timing": {
            "missing": missing_timing,
            "violations": timing_violations,
            "outcome_mutation_rows": outcome_mutation_rows,
        },
        "integrity": {
            "duplicate_score_keys": duplicate_score_keys,
            "fingerprint_mismatches": fingerprint_mismatches,
            "invalid_policy_rows": invalid_policy_rows,
        },
    }


def build_forward_score_docs(
    scores: pd.DataFrame,
    *,
    model_id: str,
    artifact_sha256: str,
    training_end: str,
    feature_columns: Iterable[str],
    created_at: datetime | None = None,
) -> list[dict[str, Any]]:
    timestamp = created_at or datetime.now(tz=UTC)
    timestamp = (
        timestamp
        if timestamp.tzinfo is not None
        else timestamp.replace(tzinfo=UTC)
    ).astimezone(UTC)
    forbidden_with_values = sorted(
        column
        for column in OUTCOME_COLUMNS.intersection(scores.columns)
        if scores[column].notna().any()
    )
    if forbidden_with_values:
        raise ValueError(
            "forward scores cannot contain target outcomes: "
            + ", ".join(forbidden_with_values)
        )
    features = list(feature_columns)
    missing_features = sorted(set(features).difference(scores.columns))
    if missing_features:
        raise ValueError(
            f"forward scores are missing model features: {missing_features}"
        )

    docs: list[dict[str, Any]] = []
    for row in scores.to_dict(orient="records"):
        snapshot_time = pd.to_datetime(
            row.get("odds_snapshot_time"),
            errors="coerce",
            utc=True,
        )
        match_start = pd.to_datetime(
            row.get("match_start_time"),
            errors="coerce",
            utc=True,
        )
        if pd.isna(snapshot_time) or pd.isna(match_start):
            raise ValueError("forward scores require valid timing")
        created_timestamp = pd.Timestamp(timestamp)
        if snapshot_time > created_timestamp:
            raise ValueError(
                "odds snapshot must be available before score"
            )
        if snapshot_time >= match_start:
            raise ValueError(
                "odds snapshot must be strictly before kickoff"
            )
        if created_timestamp >= match_start:
            raise ValueError(
                "forward scores must be created before kickoff"
            )
        snapshot_key = str(row.get("snapshot_key") or "")
        if not snapshot_key:
            raise ValueError("forward scores require snapshot_key")
        direction = str(row["direction"])
        over_market_probability = float(
            row["market_fair_probability_over"]
        )
        market_side_probability = (
            over_market_probability
            if direction == "over"
            else 1.0 - over_market_probability
        )
        feature_values = {
            column: _value(row.get(column))
            for column in features
        }
        score_key = f"{model_id}|{snapshot_key}|{direction}"
        doc: dict[str, Any] = {
            "score_key": score_key,
            "score_type": "ev_shadow_candidate",
            "model_id": model_id,
            "model_status": "shadow_only",
            "artifact_sha256": artifact_sha256,
            "training_end": training_end,
            "match_key": str(
                row.get("match_key")
                or row["exposure_match_id"]
            ),
            "sample_key": str(row["sample_key"]),
            "side_key": str(row["side_key"]),
            "snapshot_key": snapshot_key,
            "offer_key": str(row.get("offer_key") or ""),
            "snapshot_label": _value(row.get("snapshot_label")),
            "snapshot_type": _value(row.get("snapshot_type")),
            "stat_key": str(row["stat_key"]),
            "period": str(row["period"]),
            "scope": str(row["scope"]),
            "line_value": float(row["line_value"]),
            "direction": direction,
            "offered_odds": float(row["offered_odds"]),
            "market_side_probability": market_side_probability,
            "predicted_win_probability": float(
                row["predicted_win_probability"]
            ),
            "expected_roi_units": float(
                row["expected_roi_units"]
            ),
            "odds_snapshot_time": snapshot_time.to_pydatetime(),
            "match_start_time": match_start.to_pydatetime(),
            "score_created_at": timestamp,
            "score_created_before_kickoff": True,
            "valid_for_policy_evaluation": True,
            "invalid_for_model": False,
            "feature_values": feature_values,
            "feature_fingerprint_sha256": _sha256_json(
                feature_values
            ),
        }
        doc["score_fingerprint_sha256"] = _score_fingerprint(doc)
        docs.append(doc)
    return docs


def persist_forward_score_docs(
    collection: Any,
    docs: list[dict[str, Any]],
) -> dict[str, int]:
    metrics = {
        "inserted": 0,
        "existing": 0,
        "conflicts": 0,
        "precision_equivalent_existing": 0,
    }
    for doc in docs:
        expected_fingerprint = _score_fingerprint(doc)
        if doc.get("score_fingerprint_sha256") != expected_fingerprint:
            metrics["conflicts"] += 1
            raise RuntimeError(
                f"immutable score conflict for {doc['score_key']}"
            )
        existing = collection.find_one(
            {"score_key": doc["score_key"]},
            projection={"_id": 0},
        )
        if existing is not None:
            existing_fingerprint = existing.get("score_fingerprint_sha256")
            if existing_fingerprint == expected_fingerprint:
                metrics["existing"] += 1
                continue
            if (
                existing_fingerprint != _score_fingerprint(existing)
                or not _score_documents_equivalent(existing, doc)
            ):
                metrics["conflicts"] += 1
                raise RuntimeError(
                    f"immutable score conflict for {doc['score_key']}"
                )
            metrics["existing"] += 1
            metrics["precision_equivalent_existing"] += 1
            continue
        result = collection.update_one(
            {"score_key": doc["score_key"]},
            {"$setOnInsert": doc},
            upsert=True,
        )
        if result.upserted_id is not None:
            metrics["inserted"] += 1
        else:
            metrics["existing"] += 1
    return metrics
