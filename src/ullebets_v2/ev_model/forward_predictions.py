from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from typing import Any, Iterable

import numpy as np
import pandas as pd


OUTCOME_COLUMNS = {
    "actual_value",
    "settlement_result",
    "realized_roi_units",
    "over_settlement_result",
    "under_settlement_result",
    "over_realized_roi_units",
    "under_realized_roi_units",
}

FINGERPRINT_EXCLUDED_COLUMNS = {
    "prediction_created_at",
    "prediction_fingerprint_sha256",
}


def valid_frozen_match_keys(
    predictions: list[dict[str, Any]],
) -> set[str]:
    valid: set[str] = set()
    for row in predictions:
        if row.get("invalid_for_model") is True:
            continue
        snapshot_time = pd.to_datetime(
            row.get("odds_snapshot_time"),
            errors="coerce",
            utc=True,
        )
        created_at = pd.to_datetime(
            row.get("prediction_created_at"),
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
            or snapshot_time > created_at
            or snapshot_time >= match_start
            or created_at >= match_start
        ):
            continue
        match_key = row.get("match_key")
        if match_key:
            valid.add(str(match_key))
    return valid


def exclude_previously_frozen_matches(
    snapshots: pd.DataFrame,
    *,
    frozen_match_keys: set[str],
) -> tuple[pd.DataFrame, int]:
    if snapshots.empty or not frozen_match_keys:
        return snapshots.copy(), 0
    frozen_mask = snapshots["match_key"].astype(str).isin(
        frozen_match_keys
    )
    return snapshots.loc[~frozen_mask].copy(), int(frozen_mask.sum())


def validate_model_runtime(expected_versions: dict[str, str]) -> None:
    mismatches: list[str] = []
    for package_name, expected in sorted(expected_versions.items()):
        try:
            installed = version(package_name)
        except PackageNotFoundError:
            installed = "missing"
        if installed != str(expected):
            mismatches.append(
                f"{package_name}: expected {expected}, installed {installed}"
            )
    if mismatches:
        raise RuntimeError(
            "model runtime version mismatch: " + "; ".join(mismatches)
        )


def _native(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).isoformat()
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return value


def _sha256_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _prediction_fingerprint(doc: dict[str, Any]) -> str:
    return _sha256_json(
        {
            key: _native(value)
            for key, value in doc.items()
            if key not in FINGERPRINT_EXCLUDED_COLUMNS
        }
    )


def build_forward_prediction_docs(
    selections: pd.DataFrame,
    *,
    model_id: str,
    artifact_sha256: str,
    training_end: str,
    feature_columns: Iterable[str],
    minimum_ev: float,
    maximum_ev: float | None,
    created_at: datetime | None = None,
) -> list[dict[str, Any]]:
    timestamp = created_at or datetime.now(tz=UTC)
    timestamp = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)
    forbidden_with_values = sorted(
        column
        for column in OUTCOME_COLUMNS.intersection(selections.columns)
        if selections[column].notna().any()
    )
    if forbidden_with_values:
        raise ValueError(
            "forward predictions cannot contain target outcomes: "
            + ", ".join(forbidden_with_values)
        )

    features = list(feature_columns)
    missing_features = sorted(set(features).difference(selections.columns))
    if missing_features:
        raise ValueError(
            f"forward predictions are missing model features: {missing_features}"
        )

    docs: list[dict[str, Any]] = []
    for row in selections.to_dict(orient="records"):
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
            raise ValueError("forward predictions require valid timing")
        if snapshot_time >= match_start:
            raise ValueError("odds snapshot must be strictly before kickoff")
        created_timestamp = pd.Timestamp(timestamp)
        if snapshot_time > created_timestamp:
            raise ValueError(
                "odds snapshot must be available before prediction"
            )
        if created_timestamp >= match_start:
            raise ValueError("forward predictions must be created before kickoff")

        snapshot_key = str(row.get("snapshot_key") or "")
        if not snapshot_key:
            raise ValueError("forward predictions require snapshot_key")
        direction = str(row["direction"])
        prediction_key = f"{model_id}|{snapshot_key}|{direction}"
        feature_payload = {
            column: _native(row.get(column))
            for column in features
        }
        doc: dict[str, Any] = {
            "prediction_key": prediction_key,
            "selection_key": prediction_key,
            "prediction_type": "ev_shadow_model",
            "model_id": model_id,
            "model_status": "shadow_only",
            "artifact_sha256": artifact_sha256,
            "model_training_end": training_end,
            "match_key": str(
                row.get("match_key") or row["exposure_match_id"]
            ),
            "sample_key": str(row["sample_key"]),
            "side_key": str(row["side_key"]),
            "snapshot_key": snapshot_key,
            "offer_key": str(row.get("offer_key") or ""),
            "stat_key": str(row["stat_key"]),
            "period": str(row["period"]),
            "scope": str(row["scope"]),
            "direction": direction,
            "line_value": float(row["line_value"]),
            "selected_odds": float(row["offered_odds"]),
            "saved_odds": float(row["offered_odds"]),
            "predicted_win_probability": float(
                row["predicted_win_probability"]
            ),
            "expected_roi_units": float(row["expected_roi_units"]),
            "minimum_ev": float(minimum_ev),
            "maximum_ev": (
                float(maximum_ev) if maximum_ev is not None else None
            ),
            "stake_units": 1.0,
            "odds_snapshot_time": snapshot_time.to_pydatetime(),
            "match_start_time": match_start.to_pydatetime(),
            "prediction_created_at": timestamp.astimezone(UTC),
            "prediction_created_before_kickoff": True,
            "valid_for_forward_evaluation": True,
            "invalid_for_model": False,
            "feature_fingerprint_sha256": _sha256_json(feature_payload),
        }
        doc["prediction_fingerprint_sha256"] = _prediction_fingerprint(doc)
        docs.append(doc)
    return docs


def persist_forward_prediction_docs(
    collection: Any,
    docs: list[dict[str, Any]],
) -> dict[str, int]:
    metrics = {"inserted": 0, "existing": 0, "conflicts": 0}
    for doc in docs:
        expected_fingerprint = _prediction_fingerprint(doc)
        if doc.get("prediction_fingerprint_sha256") != expected_fingerprint:
            metrics["conflicts"] += 1
            raise RuntimeError(
                f"immutable prediction conflict for {doc['prediction_key']}"
            )
        existing = collection.find_one(
            {"prediction_key": doc["prediction_key"]},
            projection={
                "_id": 0,
                "prediction_key": 1,
                "prediction_fingerprint_sha256": 1,
            },
        )
        if existing is not None:
            if (
                existing.get("prediction_fingerprint_sha256")
                != expected_fingerprint
            ):
                metrics["conflicts"] += 1
                raise RuntimeError(
                    f"immutable prediction conflict for {doc['prediction_key']}"
                )
            metrics["existing"] += 1
            continue
        result = collection.update_one(
            {"prediction_key": doc["prediction_key"]},
            {"$setOnInsert": doc},
            upsert=True,
        )
        if result.upserted_id is not None:
            metrics["inserted"] += 1
        else:
            metrics["existing"] += 1
    return metrics
