from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Iterable

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


def immutable_observation_fingerprint(observation: dict[str, Any]) -> str:
    payload = {field: observation.get(field) for field in _IMMUTABLE_OBSERVATION_FIELDS}
    canonical = json.dumps(payload, default=lambda value: value.isoformat(), sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def persist_observations(database: Any, observations: Iterable[dict[str, Any]]) -> dict[str, int]:
    inserts = replays = 0
    collection = database[MARKET_BIAS_OBSERVATIONS]
    for observation in observations:
        observation_key = str(observation.get("observation_key") or "")
        if not observation_key:
            raise ValueError("observation_key is required.")
        existing = collection.find_one({"observation_key": observation_key}, projection={"_id": 0})
        if existing is None:
            collection.insert_one(dict(observation))
            inserts += 1
            continue
        if immutable_observation_fingerprint(existing) != immutable_observation_fingerprint(observation):
            raise ImmutableMarketBiasConflict(f"immutable_market_bias_observation_conflict:{observation_key}")
        replays += 1
    return {"observation_inserts": inserts, "observation_replays": replays}


def persist_profiles(database: Any, profiles: Iterable[dict[str, Any]]) -> dict[str, int]:
    upserts = 0
    collection = database[MARKET_BIAS_PROFILES]
    for profile in profiles:
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
