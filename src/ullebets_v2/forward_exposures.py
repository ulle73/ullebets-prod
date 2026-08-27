from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from ullebets_v2.forward_timing import evaluate_forward_timing
from ullebets_v2.support.schemas import stable_json_hash


ForwardSelectionFamily = Literal["v6", "legacy"]

CHECKPOINT_ORDER = {
    "T_MINUS_3D": 0,
    "T_MINUS_2D": 1,
    "T_MINUS_1D": 2,
    "T_MINUS_12H": 3,
    "T_MINUS_2H": 4,
    "T_MINUS_30M": 5,
    "T_MINUS_10M": 6,
}

PRODUCT_ACCEPTED_CLOSING_QUALITIES = {"t10", "t30_fallback"}


def is_accepted_clv(row: dict[str, Any]) -> bool:
    """Return product acceptance without weakening promotion evidence."""
    if row.get("accepted_clv") is True:
        return True
    if row.get("accepted_clv") is False:
        return False
    if row.get("official_clv") is True:
        return True
    return bool(
        str(row.get("closing_quality") or "")
        in PRODUCT_ACCEPTED_CLOSING_QUALITIES
        and _to_float(row.get("clv_pct")) is not None
        and str(row.get("clv_status") or "")
        in {"available", "tracked", "tracked_fallback_t30"}
    )


def accepted_clv_checkpoint(row: dict[str, Any]) -> str | None:
    if not is_accepted_clv(row):
        return None
    checkpoint = str(
        row.get("closing_checkpoint")
        or row.get("closing_snapshot_label")
        or ""
    )
    if checkpoint in {"T_MINUS_10M", "T_MINUS_30M"}:
        return checkpoint
    quality = str(row.get("closing_quality") or "")
    if quality == "t10":
        return "T_MINUS_10M"
    if quality == "t30_fallback":
        return "T_MINUS_30M"
    return None


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


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _observation_key(row: dict[str, Any]) -> str:
    return str(
        row.get("prediction_key")
        or row.get("selection_key")
        or row.get("tracking_key")
        or row.get("result_loop_key")
        or forward_evaluation_key(row)
    )


def _observation_rank(row: dict[str, Any]) -> tuple[int, datetime, str]:
    label = str(row.get("snapshot_label") or "")
    observed_at = next(
        (
            parsed
            for field in (
                "odds_snapshot_time",
                "saved_at",
                "prediction_created_at",
                "created_at",
            )
            if (parsed := _to_datetime(row.get(field))) is not None
        ),
        datetime.max.replace(tzinfo=UTC),
    )
    return (
        CHECKPOINT_ORDER.get(label, len(CHECKPOINT_ORDER)),
        observed_at,
        _observation_key(row),
    )


def _best_ev_rank(row: dict[str, Any]) -> tuple[float, tuple[int, datetime, str]]:
    expected_roi = _to_float(row.get("expected_roi_units"))
    return (
        -(expected_roi if expected_roi is not None else float("-inf")),
        _observation_rank(row),
    )


def group_forward_observation_docs(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group read-only presentation rows without collapsing evaluation units."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for source_row in rows:
        row = dict(source_row)
        exposure_key = forward_exposure_key(row)
        row["canonical_exposure_key"] = exposure_key
        groups.setdefault(exposure_key, []).append(row)

    grouped: list[dict[str, Any]] = []
    for exposure_key, group in groups.items():
        ordered = sorted(group, key=_observation_rank)
        representative = dict(min(ordered, key=_best_ev_rank))
        stakes = [
            value
            for row in ordered
            if (value := _to_float(row.get("stake_units"))) is not None
        ]
        pnl_values = [
            value
            for row in ordered
            if (value := _to_float(row.get("pnl_units"))) is not None
        ]
        official_clv_rows = [
            row for row in ordered if row.get("official_clv") is True
        ]
        official_clv_values = [
            value
            for row in official_clv_rows
            if (value := _to_float(row.get("clv_pct"))) is not None
        ]
        accepted_clv_rows = [row for row in ordered if is_accepted_clv(row)]
        accepted_clv_values = [
            value
            for row in accepted_clv_rows
            if (value := _to_float(row.get("clv_pct"))) is not None
        ]
        total_stake = sum(stakes) if stakes else None
        total_pnl = sum(pnl_values) if pnl_values else None
        observation_keys = [_observation_key(row) for row in ordered]
        snapshot_labels = list(
            dict.fromkeys(
                str(row.get("snapshot_label"))
                for row in ordered
                if row.get("snapshot_label")
            )
        )
        representative.update(
            {
                "canonical_exposure_key": exposure_key,
                "observation_count": len(ordered),
                "observation_keys": observation_keys,
                "snapshot_labels": snapshot_labels,
                "best_snapshot_label": representative.get(
                    "snapshot_label"
                ),
                "settled_observation_count": sum(
                    row.get("settlement_status") == "settled"
                    for row in ordered
                ),
                "official_clv_count": len(official_clv_rows),
                "beat_closing_line_count": sum(
                    row.get("beat_closing_line") is True
                    for row in official_clv_rows
                ),
                "average_clv_pct": (
                    sum(official_clv_values) / len(official_clv_values)
                    if official_clv_values
                    else None
                ),
                "accepted_clv_count": len(accepted_clv_rows),
                "t30_clv_count": sum(
                    accepted_clv_checkpoint(row) == "T_MINUS_30M"
                    for row in accepted_clv_rows
                ),
                "t10_clv_count": sum(
                    accepted_clv_checkpoint(row) == "T_MINUS_10M"
                    for row in accepted_clv_rows
                ),
                "accepted_beat_closing_line_count": sum(
                    row.get("beat_closing_line") is True
                    for row in accepted_clv_rows
                ),
                "average_accepted_clv_pct": (
                    sum(accepted_clv_values) / len(accepted_clv_values)
                    if accepted_clv_values
                    else None
                ),
            }
        )
        if total_stake is not None:
            representative["stake_units"] = total_stake
        if total_pnl is not None:
            representative["pnl_units"] = total_pnl
        if total_stake and total_pnl is not None:
            representative["roi_units"] = total_pnl / total_stake
        representative["clv_beat_rate"] = (
            representative["beat_closing_line_count"]
            / representative["official_clv_count"]
            if representative["official_clv_count"]
            else None
        )
        representative["accepted_clv_beat_rate"] = (
            representative["accepted_beat_closing_line_count"]
            / representative["accepted_clv_count"]
            if representative["accepted_clv_count"]
            else None
        )
        grouped.append(representative)
    return grouped


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
