from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd


PROMOTION_REQUIREMENTS = {
    "minimum_settled_bets": 500,
    "minimum_unique_matches": 200,
    "minimum_calendar_days": 90,
    "minimum_clv_coverage_pct": 80.0,
}


def _to_datetime(value: Any) -> datetime | None:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        for field in ("prediction_key", "selection_key", "clv_key"):
            value = row.get(field)
            if value:
                output[str(value)] = row
                break
    return output


def _cluster_bootstrap(
    settled: list[dict[str, Any]],
    *,
    iterations: int,
) -> dict[str, float | int | None]:
    if not settled:
        return {
            "clusters": 0,
            "low_95_pct": None,
            "median_pct": None,
            "high_95_pct": None,
            "probability_positive": None,
        }
    by_match: dict[str, list[float]] = {}
    for row in settled:
        by_match.setdefault(str(row["match_key"]), []).append(
            float(row["pnl_units"])
        )
    clusters = [
        (sum(values), len(values))
        for values in by_match.values()
    ]
    values = np.asarray(clusters, dtype=float)
    rng = np.random.default_rng(20260730)
    rois = np.empty(iterations, dtype=float)
    for index in range(iterations):
        sampled = values[
            rng.integers(0, len(values), len(values))
        ]
        rois[index] = sampled[:, 0].sum() / sampled[:, 1].sum() * 100.0
    return {
        "clusters": len(clusters),
        "low_95_pct": float(np.quantile(rois, 0.025)),
        "median_pct": float(np.quantile(rois, 0.5)),
        "high_95_pct": float(np.quantile(rois, 0.975)),
        "probability_positive": float((rois > 0.0).mean()),
    }


def build_forward_evaluation_report(
    *,
    predictions: list[dict[str, Any]],
    settled_rows: list[dict[str, Any]],
    clv_rows: list[dict[str, Any]],
    model_id: str,
    bootstrap_iterations: int = 20_000,
) -> dict[str, object]:
    model_predictions = [
        row for row in predictions if str(row.get("model_id")) == model_id
    ]
    settlement_lookup = _lookup(settled_rows)
    clv_lookup = _lookup(clv_rows)

    timing_violations = 0
    missing_timing = 0
    outcome_mutation_rows = 0
    exposure_keys: list[tuple[str, ...]] = []
    settled: list[dict[str, Any]] = []
    clv_values: list[float] = []
    beat_close_values: list[bool] = []
    fallback_t30_clv_values: list[float] = []
    fallback_t30_beat_close_values: list[bool] = []
    start_times: list[datetime] = []
    valid_prediction_rows: list[dict[str, Any]] = []

    for prediction in model_predictions:
        prediction_is_valid = True
        key = str(prediction.get("prediction_key") or "")
        snapshot_time = _to_datetime(prediction.get("odds_snapshot_time"))
        created_at = _to_datetime(prediction.get("prediction_created_at"))
        match_start = _to_datetime(prediction.get("match_start_time"))
        if (
            snapshot_time is None
            or created_at is None
            or match_start is None
        ):
            missing_timing += 1
            prediction_is_valid = False
        elif (
            snapshot_time > created_at
            or snapshot_time >= match_start
            or created_at >= match_start
        ):
            timing_violations += 1
            prediction_is_valid = False

        if any(
            prediction.get(field) is not None
            for field in (
                "actual_value",
                "settlement_result",
                "pnl_units",
                "roi_units",
            )
        ):
            outcome_mutation_rows += 1
            prediction_is_valid = False

        if prediction_is_valid:
            valid_prediction_rows.append(prediction)
            if match_start is not None:
                start_times.append(match_start)
            exposure_keys.append(
                (
                    str(prediction.get("match_key")),
                    str(prediction.get("stat_key")),
                    str(prediction.get("period")),
                    str(prediction.get("scope")),
                    str(prediction.get("line_value")),
                    str(prediction.get("direction")),
                )
            )
        settlement = settlement_lookup.get(key)
        if (
            prediction_is_valid
            and settlement is not None
            and settlement.get("settlement_status") == "settled"
            and settlement.get("pnl_units") is not None
        ):
            settled.append(
                {
                    **settlement,
                    "match_key": prediction.get("match_key"),
                    "prediction_key": key,
                    "pnl_units": float(settlement["pnl_units"]),
                }
            )
        clv = clv_lookup.get(key)
        closing_label = str(clv.get("closing_snapshot_label") or "") if clv else ""
        closing_quality = str(clv.get("closing_quality") or "") if clv else ""
        official_clv = bool(
            clv
            and (
                clv.get("official_clv") is True
                or closing_label == "T_MINUS_10M"
                or closing_quality == "t10"
            )
        )
        fallback_t30_clv = bool(
            clv
            and not official_clv
            and (
                closing_label == "T_MINUS_30M"
                or closing_quality == "t30_fallback"
            )
        )
        if (
            prediction_is_valid
            and clv is not None
            and clv.get("clv_pct") is not None
            and official_clv
        ):
            clv_values.append(float(clv["clv_pct"]))
        if (
            prediction_is_valid
            and clv is not None
            and isinstance(clv.get("beat_closing_line"), bool)
            and official_clv
        ):
            beat_close_values.append(bool(clv["beat_closing_line"]))
        if (
            prediction_is_valid
            and clv is not None
            and clv.get("clv_pct") is not None
            and fallback_t30_clv
        ):
            fallback_t30_clv_values.append(float(clv["clv_pct"]))
        if (
            prediction_is_valid
            and clv is not None
            and isinstance(clv.get("beat_closing_line"), bool)
            and fallback_t30_clv
        ):
            fallback_t30_beat_close_values.append(bool(clv["beat_closing_line"]))

    pnl_units = sum(float(row["pnl_units"]) for row in settled)
    settled_count = len(settled)
    result_counts = {
        result: sum(
            1 for row in settled if row.get("settlement_result") == result
        )
        for result in ("win", "loss", "push")
    }
    unique_matches = len(
        {
            str(row.get("match_key"))
            for row in valid_prediction_rows
            if row.get("match_key")
        }
    )
    calendar_days = (
        (max(start_times) - min(start_times)).days + 1
        if start_times
        else 0
    )
    clv_coverage = (
        len(clv_values) / len(valid_prediction_rows) * 100.0
        if valid_prediction_rows
        else 0.0
    )
    bootstrap = _cluster_bootstrap(
        settled,
        iterations=bootstrap_iterations,
    )
    duplicate_exposures = len(exposure_keys) - len(set(exposure_keys))
    audit_clean = (
        timing_violations == 0
        and missing_timing == 0
        and outcome_mutation_rows == 0
        and duplicate_exposures == 0
    )
    requirement_status = {
        "settled_bets": (
            settled_count >= PROMOTION_REQUIREMENTS["minimum_settled_bets"]
        ),
        "unique_matches": (
            unique_matches
            >= PROMOTION_REQUIREMENTS["minimum_unique_matches"]
        ),
        "calendar_days": (
            calendar_days
            >= PROMOTION_REQUIREMENTS["minimum_calendar_days"]
        ),
        "clv_coverage": (
            clv_coverage
            >= PROMOTION_REQUIREMENTS["minimum_clv_coverage_pct"]
        ),
        "positive_clv": bool(clv_values)
        and float(np.mean(clv_values)) > 0.0,
        "positive_clustered_lower_bound": (
            bootstrap["low_95_pct"] is not None
            and float(bootstrap["low_95_pct"]) > 0.0
        ),
        "audit_clean": audit_clean,
        "all_predictions_settled": (
            bool(valid_prediction_rows)
            and settled_count == len(valid_prediction_rows)
        ),
    }
    return {
        "model_id": model_id,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "predictions": len(model_predictions),
        "valid_predictions": len(valid_prediction_rows),
        "invalid_predictions": (
            len(model_predictions) - len(valid_prediction_rows)
        ),
        "unique_matches": unique_matches,
        "calendar_days": calendar_days,
        "settlement": {
            "settled": settled_count,
            "pending": len(valid_prediction_rows) - settled_count,
            **result_counts,
        },
        "performance": {
            "pnl_units": pnl_units,
            "roi_pct": (
                pnl_units / settled_count * 100.0
                if settled_count
                else None
            ),
        },
        "timing": {
            "violations": timing_violations,
            "missing": missing_timing,
            "prediction_outcome_mutation_rows": outcome_mutation_rows,
        },
        "duplicates": {
            "duplicate_exposures": duplicate_exposures,
        },
        "clv": {
            "rows": len(clv_values),
            "coverage_pct": clv_coverage,
            "mean_clv_pct": (
                float(np.mean(clv_values)) if clv_values else None
            ),
            "beat_close_pct": (
                sum(beat_close_values) / len(beat_close_values) * 100.0
                if beat_close_values
                else None
            ),
            "fallback_t30_rows": len(fallback_t30_clv_values),
            "fallback_t30_coverage_pct": (
                len(fallback_t30_clv_values) / len(valid_prediction_rows) * 100.0
                if valid_prediction_rows
                else 0.0
            ),
            "fallback_t30_mean_clv_pct": (
                float(np.mean(fallback_t30_clv_values))
                if fallback_t30_clv_values
                else None
            ),
            "fallback_t30_beat_close_pct": (
                sum(fallback_t30_beat_close_values)
                / len(fallback_t30_beat_close_values)
                * 100.0
                if fallback_t30_beat_close_values
                else None
            ),
        },
        "cluster_bootstrap": bootstrap,
        "promotion": {
            "eligible": all(requirement_status.values()),
            "requirements": PROMOTION_REQUIREMENTS,
            "checks": requirement_status,
        },
    }
