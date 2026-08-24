from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import math
from typing import Any, Iterable

from ullebets_v2.formula_journal.registry import frozen_model_registry_by_id


FINGERPRINT_EXCLUDED_FIELDS = {
    "_id",
    "journaled_at",
    "observation_fingerprint_sha256",
}


class ImmutableFormulaObservationConflict(RuntimeError):
    """An observation identity already exists with different evidence."""


def _utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
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


def immutable_observation_fingerprint(doc: dict[str, Any]) -> str:
    return _sha256_json(
        {
            key: value
            for key, value in doc.items()
            if key not in FINGERPRINT_EXCLUDED_FIELDS
        }
    )


def probability_from_ev(*, expected_roi_units: float, offered_odds: float) -> float:
    if not math.isfinite(expected_roi_units):
        raise ValueError("expected ROI must be finite")
    if not math.isfinite(offered_odds) or offered_odds <= 1.0:
        raise ValueError("offered odds must be finite and greater than one")
    value = (1.0 + expected_roi_units) / offered_odds
    if not 0.0 <= value <= 1.0:
        raise ValueError("derived probability must be between zero and one")
    return value


def _is_formula_value_key(value: str) -> bool:
    return value.startswith("evPct") or value == "legacyEvPct" or value.startswith("ml_")


def _market_fields(source: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    match_key = str(source.get("match_key") or context.get("match_key") or "")
    snapshot_key = str(source.get("snapshot_key") or context.get("snapshot_key") or "")
    if not match_key or not snapshot_key:
        raise ValueError("formula observations require match_key and snapshot_key")
    return {
        "match_key": match_key,
        "league_key": source.get("league_key") or context.get("league_key"),
        "league_name": source.get("league_name") or context.get("league_name"),
        "home_team_name": source.get("home_team_name") or context.get("home_team_name"),
        "away_team_name": source.get("away_team_name") or context.get("away_team_name"),
        "match_start_time": _utc_datetime(source.get("match_start_time") or context.get("match_start_time")),
        "snapshot_key": snapshot_key,
        "snapshot_label": source.get("snapshot_label") or context.get("snapshot_label"),
        "snapshot_type": source.get("snapshot_type") or context.get("snapshot_type"),
        "odds_snapshot_time": _utc_datetime(source.get("odds_snapshot_time") or context.get("odds_snapshot_time")),
        "stat_key": str(source.get("stat_key") or source.get("statKey") or ""),
        "scope": str(source.get("scope") or ""),
        "period": str(source.get("period") or ""),
        "direction": str(source.get("direction") or "").lower(),
        "line_value": float(source.get("line_value") if source.get("line_value") is not None else source["line"]),
        "offered_odds": float(source.get("offered_odds") if source.get("offered_odds") is not None else source["odds"]),
    }


def _timing_is_valid(fields: dict[str, Any], created_at: datetime | None = None) -> bool:
    snapshot_time = fields.get("odds_snapshot_time")
    match_start = fields.get("match_start_time")
    if not isinstance(snapshot_time, datetime) or not isinstance(match_start, datetime):
        return False
    if snapshot_time >= match_start:
        return False
    return created_at is None or snapshot_time <= created_at < match_start


def _finish_observation(doc: dict[str, Any]) -> dict[str, Any]:
    identity = {
        "formula_id": doc["formula_id"],
        "formula_version": doc["formula_version"],
        "source_score_key": doc["source_score_key"],
    }
    doc["observation_key"] = f"formula-observation:{_sha256_json(identity)}"
    doc["observation_fingerprint_sha256"] = immutable_observation_fingerprint(doc)
    return doc


def build_js_observation_docs(
    *,
    lines: Iterable[dict[str, Any]],
    context: dict[str, Any],
    runtime_sha256: str,
    registry: dict[str, Any],
    journaled_at: datetime | None = None,
) -> list[dict[str, Any]]:
    created_at = _utc_datetime(journaled_at) or datetime.now(tz=UTC)
    formulas = registry.get("js_formulas") or {}
    registry_id = str(registry.get("registry_id") or "")
    registry_fingerprint = registry.get("registry_fingerprint_sha256")
    docs: list[dict[str, Any]] = []
    for line in lines:
        fields = _market_fields(line, context)
        details = line.get("evDetails")
        if not isinstance(details, dict):
            continue
        source_side_key = "|".join(
            [
                "js",
                runtime_sha256,
                fields["snapshot_key"],
                fields["stat_key"],
                fields["scope"],
                fields["period"],
                format(fields["line_value"], ".12g"),
                fields["direction"],
            ]
        )
        for value_key, raw_value in sorted(details.items()):
            if not _is_formula_value_key(str(value_key)):
                continue
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                continue
            expected_ev_pct = float(raw_value)
            if not math.isfinite(expected_ev_pct):
                continue
            expected_roi_units = expected_ev_pct / 100.0
            probability: float | None
            probability_valid = True
            try:
                probability = probability_from_ev(
                    expected_roi_units=expected_roi_units,
                    offered_odds=fields["offered_odds"],
                )
            except ValueError:
                probability = None
                probability_valid = False
            timing_valid = _timing_is_valid(fields)
            valid_for_comparison = timing_valid and probability_valid
            positive = expected_roi_units > 0.0
            exclusion_reason = (
                None
                if valid_for_comparison and positive
                else "invalid_timing"
                if not timing_valid
                else "invalid_probability"
                if not probability_valid
                else "not_positive_ev"
            )
            metadata = formulas.get(value_key) if isinstance(formulas, dict) else None
            metadata = metadata if isinstance(metadata, dict) else {}
            doc = {
                "source_type": "js_formula",
                "formula_id": f"js:{value_key}",
                "formula_label": str(metadata.get("label") or value_key),
                "formula_family": str(metadata.get("family") or "js_formula"),
                "formula_version": runtime_sha256,
                "runtime_sha256": runtime_sha256,
                "model_id": None,
                "artifact_sha256": None,
                "registry_id": registry_id,
                "registry_fingerprint_sha256": registry_fingerprint,
                "source_score_key": f"{source_side_key}|{value_key}",
                **fields,
                "predicted_win_probability": probability,
                "expected_roi_units": expected_roi_units,
                "expected_ev_pct": expected_ev_pct,
                "domain_status": "formula_emitted",
                "valid_for_comparison": valid_for_comparison,
                "is_positive_ev": positive,
                "shadow_stake_units": 1.0 if valid_for_comparison and positive else 0.0,
                "exclusion_reason": exclusion_reason,
                "journaled_at": created_at,
            }
            docs.append(_finish_observation(doc))
    return docs


def build_ml_observation_docs(
    *,
    scores: Iterable[dict[str, Any]],
    registry: dict[str, Any],
    fixtures_by_match: dict[str, dict[str, Any]] | None = None,
    journaled_at: datetime | None = None,
) -> list[dict[str, Any]]:
    created_at = _utc_datetime(journaled_at) or datetime.now(tz=UTC)
    model_registry = frozen_model_registry_by_id(registry)
    fixture_rows = fixtures_by_match or {}
    docs: list[dict[str, Any]] = []
    for score in scores:
        model_id = str(score.get("model_id") or "")
        metadata = model_registry.get(model_id)
        if metadata is None:
            raise ValueError(f"ML score model is not registered: {model_id}")
        match_key = str(score.get("match_key") or "")
        context = fixture_rows.get(match_key, {})
        fields = _market_fields(score, context)
        expected_roi_units = float(score["expected_roi_units"])
        probability = float(score["predicted_win_probability"])
        probability_valid = math.isfinite(probability) and 0.0 <= probability <= 1.0
        score_created_at = _utc_datetime(score.get("score_created_at"))
        timing_valid = _timing_is_valid(fields, score_created_at)
        explicit_domain_status = str(
            score.get("formula_domain_status")
            or score.get("training_domain_status")
            or ""
        )
        domain_valid = (
            explicit_domain_status not in {"out_of_domain", "missing_domain_feature"}
            and score.get("valid_for_policy_evaluation") is True
            and score.get("invalid_for_model") is not True
        )
        domain_status = (
            explicit_domain_status
            if explicit_domain_status
            else "in_domain"
            if domain_valid
            else "out_of_domain"
        )
        valid_for_comparison = domain_valid and timing_valid and probability_valid
        positive = expected_roi_units > 0.0
        exclusion_reason = (
            None
            if valid_for_comparison and positive
            else "out_of_domain"
            if not domain_valid
            else "invalid_timing"
            if not timing_valid
            else "invalid_probability"
            if not probability_valid
            else "not_positive_ev"
        )
        artifact_sha256 = str(score.get("artifact_sha256") or "")
        if not artifact_sha256:
            raise ValueError("ML score requires artifact_sha256")
        doc = {
            "source_type": "frozen_ml_model",
            "formula_id": f"ml:{model_id}",
            "formula_label": str(metadata["label"]),
            "formula_family": str(metadata["family"]),
            "formula_version": artifact_sha256,
            "runtime_sha256": None,
            "model_id": model_id,
            "artifact_sha256": artifact_sha256,
            "registry_id": str(registry.get("registry_id") or ""),
            "registry_fingerprint_sha256": registry.get("registry_fingerprint_sha256"),
            "source_score_key": str(score.get("score_key") or ""),
            **fields,
            "predicted_win_probability": probability if probability_valid else None,
            "expected_roi_units": expected_roi_units,
            "expected_ev_pct": expected_roi_units * 100.0,
            "domain_status": domain_status,
            "valid_for_comparison": valid_for_comparison,
            "is_positive_ev": positive,
            "shadow_stake_units": 1.0 if valid_for_comparison and positive else 0.0,
            "exclusion_reason": exclusion_reason,
            "journaled_at": created_at,
        }
        if not doc["source_score_key"]:
            raise ValueError("ML score requires score_key")
        docs.append(_finish_observation(doc))
    return docs


def persist_formula_observations(
    collection: Any,
    docs: Iterable[dict[str, Any]],
) -> dict[str, int]:
    metrics = {"inserted": 0, "existing": 0, "conflicts": 0}
    incoming_by_key: dict[str, dict[str, Any]] = {}
    for source_doc in docs:
        doc = dict(source_doc)
        key = str(doc.get("observation_key") or "")
        expected = immutable_observation_fingerprint(doc)
        if not key or doc.get("observation_fingerprint_sha256") != expected:
            metrics["conflicts"] += 1
            raise ImmutableFormulaObservationConflict(
                f"invalid immutable formula observation fingerprint: {key}"
            )
        duplicate = incoming_by_key.get(key)
        if duplicate is not None and immutable_observation_fingerprint(duplicate) != expected:
            metrics["conflicts"] += 1
            raise ImmutableFormulaObservationConflict(
                f"duplicate immutable formula observation conflict: {key}"
            )
        incoming_by_key[key] = doc

    for key, doc in incoming_by_key.items():
        existing = collection.find_one({"observation_key": key}, projection={"_id": 0})
        if existing is not None:
            if (
                existing.get("observation_fingerprint_sha256") != immutable_observation_fingerprint(existing)
                or immutable_observation_fingerprint(existing) != immutable_observation_fingerprint(doc)
            ):
                metrics["conflicts"] += 1
                raise ImmutableFormulaObservationConflict(
                    f"immutable formula observation conflict: {key}"
                )
            metrics["existing"] += 1
            continue
        result = collection.update_one(
            {"observation_key": key},
            {"$setOnInsert": doc},
            upsert=True,
        )
        if result.upserted_id is not None:
            metrics["inserted"] += 1
        else:
            metrics["existing"] += 1
    return metrics
