from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Iterable

from pymongo import InsertOne, UpdateOne

from ullebets_v2.storage.collections import MARKET_BIAS_OBSERVATIONS, MARKET_BIAS_PROFILES


class ImmutableMarketBiasConflict(RuntimeError):
    """Raised when an existing observation key has different immutable evidence."""


_IMMUTABLE_OBSERVATION_FIELDS = (
    "observation_key",
    "match_key",
    "source_match_id",
    "league_key",
    "team_key",
    "venue_context",
    "market_scope",
    "stat_key",
    "period",
    "line_value",
    "over_odds",
    "under_odds",
    "actual_value",
    "residual_value",
    "line_result",
    "snapshot_key",
    "snapshot_time",
    "match_start_time",
    "outcome_available_at",
    "source_kind",
    "source_record_key",
    "source_payload_hash",
    "line_selection_method",
    "method_version",
)
MARKET_BIAS_BULK_WRITE_BATCH_SIZE = 100
# Keep Cosmos query payloads comfortably below practical $in limits.
MARKET_BIAS_EXISTING_LOOKUP_BATCH_SIZE = 100


def immutable_observation_fingerprint(observation: dict[str, Any]) -> str:
    payload = {field: observation.get(field) for field in _IMMUTABLE_OBSERVATION_FIELDS}
    canonical = json.dumps(payload, default=lambda value: value.isoformat(), sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _batches(rows: list[Any], size: int | None = None) -> Iterable[list[Any]]:
    effective_size = size or MARKET_BIAS_BULK_WRITE_BATCH_SIZE
    for start in range(0, len(rows), effective_size):
        yield rows[start : start + effective_size]


def _load_existing_observations(
    collection: Any,
    observation_keys: list[str],
) -> dict[str, dict[str, Any]]:
    existing_by_key: dict[str, dict[str, Any]] = {}
    for key_batch in _batches(observation_keys, MARKET_BIAS_EXISTING_LOOKUP_BATCH_SIZE):
        existing_documents = collection.find(
            {"observation_key": {"$in": key_batch}},
            projection={"_id": 0},
        )
        for existing in existing_documents:
            observation_key = str(existing.get("observation_key") or "")
            if observation_key:
                existing_by_key[observation_key] = dict(existing)
    return existing_by_key


def persist_observations(database: Any, observations: Iterable[dict[str, Any]]) -> dict[str, int]:
    collection = database[MARKET_BIAS_OBSERVATIONS]
    incoming_by_key: dict[str, dict[str, Any]] = {}
    for observation in observations:
        observation_key = str(observation.get("observation_key") or "")
        if not observation_key:
            raise ValueError("observation_key is required.")
        incoming = dict(observation)
        duplicate = incoming_by_key.get(observation_key)
        if duplicate is not None and (
            immutable_observation_fingerprint(duplicate)
            != immutable_observation_fingerprint(incoming)
        ):
            raise ImmutableMarketBiasConflict(f"immutable_market_bias_observation_conflict:{observation_key}")
        incoming_by_key[observation_key] = incoming

    existing_by_key = _load_existing_observations(collection, list(incoming_by_key))
    replays = 0
    insert_docs: list[dict[str, Any]] = []
    for observation_key, observation in incoming_by_key.items():
        existing = existing_by_key.get(observation_key)
        if existing is None:
            insert_docs.append(observation)
            continue
        if immutable_observation_fingerprint(existing) != immutable_observation_fingerprint(observation):
            raise ImmutableMarketBiasConflict(f"immutable_market_bias_observation_conflict:{observation_key}")
        replays += 1

    if callable(getattr(collection, "bulk_write", None)):
        for batch in _batches([InsertOne(doc) for doc in insert_docs]):
            collection.bulk_write(batch, ordered=False)
    else:
        for doc in insert_docs:
            collection.insert_one(doc)
    return {"observation_inserts": len(insert_docs), "observation_replays": replays}


def persist_profiles(database: Any, profiles: Iterable[dict[str, Any]]) -> dict[str, int]:
    upserts = 0
    collection = database[MARKET_BIAS_PROFILES]
    profile_docs = list(profiles)
    if callable(getattr(collection, "bulk_write", None)):
        operations = []
        for profile in profile_docs:
            profile_key = str(profile.get("profile_key") or "")
            if not profile_key:
                raise ValueError("profile_key is required.")
            operations.append(UpdateOne({"profile_key": profile_key}, {"$set": dict(profile)}, upsert=True))
        for batch in _batches(operations):
            result = collection.bulk_write(batch, ordered=False)
            upserts += int(getattr(result, "upserted_count", 0))
        return {"profile_upserts": upserts}
    for profile in profile_docs:
        profile_key = str(profile.get("profile_key") or "")
        if not profile_key:
            raise ValueError("profile_key is required.")
        result = collection.update_one({"profile_key": profile_key}, {"$set": dict(profile)}, upsert=True)
        upserts += 1 if result.upserted_id is not None else 0
    return {"profile_upserts": upserts}


def persist_market_bias_reports(
    database: Any,
    *,
    audit_rows: Iterable[dict[str, Any]],
    health_rows: Iterable[dict[str, Any]],
) -> dict[str, int]:
    audit_upserts = health_upserts = 0
    for row in audit_rows:
        result = database["audit_reports"].update_one(
            {"audit_type": row["audit_type"], "scope_key": row["scope_key"], "report_date": row["report_date"]},
            {"$set": row},
            upsert=True,
        )
        audit_upserts += 1 if result.upserted_id is not None else 0
    for row in health_rows:
        result = database["health_reports"].update_one(
            {"job_name": row["job_name"], "report_date": row["report_date"]},
            {"$set": row},
            upsert=True,
        )
        health_upserts += 1 if result.upserted_id is not None else 0
    return {"audit_upserts": audit_upserts, "health_upserts": health_upserts}
