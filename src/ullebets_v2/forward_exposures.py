from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from ullebets_v2.forward_timing import evaluate_forward_timing
from ullebets_v2.support.schemas import stable_json_hash


ForwardSelectionFamily = Literal["v6", "legacy"]


def forward_selection_family(row: dict[str, Any]) -> ForwardSelectionFamily:
    prediction_type = str(row.get("prediction_type") or "").lower()
    policy_id = str(row.get("selection_policy_id") or "").lower()
    model_id = str(row.get("model_id") or "").lower()
    is_registered_v6 = (
        prediction_type == "ev_registered_score_policy"
        and policy_id.startswith("v6_")
        and "v6" in model_id
    )
    return "v6" if is_registered_v6 else "legacy"


def is_combo_leg(row: dict[str, Any]) -> bool:
    return (
        str(row.get("prediction_type") or "").lower() == "combo"
        or str(row.get("export_mode") or "").lower() == "combos"
    )


def is_shadow_prediction(row: dict[str, Any]) -> bool:
    return (
        str(row.get("model_status") or "").lower() == "shadow_only"
        or str(row.get("prediction_type") or "").lower() == "ev_shadow_model"
    )


def _normalized_line(value: Any) -> str:
    try:
        return format(float(value), ".12g")
    except (TypeError, ValueError):
        return str(value or "")


def forward_exposure_key(row: dict[str, Any]) -> str:
    explicit = row.get("canonical_exposure_key")
    if isinstance(explicit, str) and explicit.strip():
        return explicit

    family = forward_selection_family(row)
    policy_namespace = (
        str(row.get("selection_policy_id") or row.get("model_id") or "v6")
        if family == "v6"
        else "legacy"
    )
    identity = {
        "family": family,
        "policy_namespace": policy_namespace,
        "match_key": str(row.get("match_key") or ""),
        "stat_key": str(row.get("stat_key") or ""),
        "scope": str(row.get("scope") or "").lower(),
        "period": str(row.get("period") or "").upper(),
        "direction": str(row.get("direction") or "").lower(),
        "line_value": _normalized_line(row.get("line_value")),
    }
    if not all(
        identity[field]
        for field in (
            "match_key",
            "stat_key",
            "scope",
            "period",
            "direction",
            "line_value",
        )
    ):
        fallback = next(
            (
                str(row.get(field) or "")
                for field in ("prediction_key", "selection_key", "tracking_key")
                if str(row.get(field) or "")
            ),
            stable_json_hash(row),
        )
        identity["unresolved_fallback"] = fallback
    return f"forward-exposure:{stable_json_hash(identity)}"


def forward_evaluation_key(row: dict[str, Any]) -> str:
    exposure_key = forward_exposure_key(row)
    if str(row.get("selection_granularity") or "") != (
        "checkpoint_observation"
    ):
        return exposure_key
    snapshot_identity = (
        row.get("snapshot_key")
        or row.get("odds_snapshot_time")
        or row.get("saved_at")
        or row.get("prediction_key")
        or row.get("selection_key")
    )
    return (
        "forward-evaluation:"
        + stable_json_hash(
            {
                "canonical_exposure_key": exposure_key,
                "snapshot_identity": str(snapshot_identity or ""),
            }
        )
    )


def _to_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _selection_rank(row: dict[str, Any]) -> tuple[int, datetime, str]:
    timing = evaluate_forward_timing(row)
    observed_at = next(
        (
            parsed
            for field in (
                "prediction_created_at",
                "odds_snapshot_time",
                "saved_at",
                "created_at",
            )
            if (parsed := _to_datetime(row.get(field))) is not None
        ),
        datetime.max.replace(tzinfo=UTC),
    )
    return (
        0 if timing["valid_for_performance"] else 1,
        observed_at,
        str(row.get("prediction_key") or row.get("selection_key") or ""),
    )


def canonicalize_forward_bet_docs(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    excluded_combo_leg_count = 0
    excluded_shadow_prediction_count = 0
    for source_row in rows:
        if is_combo_leg(source_row):
            excluded_combo_leg_count += 1
            continue
        if is_shadow_prediction(source_row):
            excluded_shadow_prediction_count += 1
            continue
        row = dict(source_row)
        exposure_key = forward_exposure_key(row)
        row["canonical_exposure_key"] = exposure_key
        evaluation_key = forward_evaluation_key(row)
        row["canonical_evaluation_key"] = evaluation_key
        groups.setdefault(evaluation_key, []).append(row)

    canonical = [
        min(group, key=_selection_rank)
        for group in groups.values()
    ]
    eligible_count = (
        len(rows)
        - excluded_combo_leg_count
        - excluded_shadow_prediction_count
    )
    return canonical, {
        "raw_count": len(rows),
        "canonical_count": len(canonical),
        "excluded_combo_leg_count": excluded_combo_leg_count,
        "excluded_shadow_prediction_count": excluded_shadow_prediction_count,
        "collapsed_duplicate_count": eligible_count - len(canonical),
    }
