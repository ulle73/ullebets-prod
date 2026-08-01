from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.domain import (
    audit_score_domain,
    score_feature_value,
)
from ullebets_v2.settlement.common import (
    build_result_lookup,
    build_stats_lookup,
    build_stat_scope_lookup,
    resolve_actual_context,
)
from ullebets_v2.settlement.rules import settle_line
from ullebets_v2.ev_model.promotion import (
    evaluate_forward_promotion_gate,
)


def fingerprint_policy_registry(
    registry: dict[str, Any],
) -> str:
    payload = json.dumps(
        registry,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def _valid_timing(row: dict[str, Any]) -> bool:
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
    return bool(
        pd.notna(snapshot_time)
        and pd.notna(created_at)
        and pd.notna(match_start)
        and snapshot_time <= created_at < match_start
    )


def _filter_model_domain(
    scores: list[dict[str, Any]],
    *,
    model_id: str,
    training_domain_by_model: (
        dict[str, dict[str, tuple[str, ...]]] | None
    ),
) -> tuple[list[dict[str, Any]], dict[str, object]]:
    if training_domain_by_model is None:
        return scores, {
            "status": "not_requested",
            "scores_total": len(scores),
            "scores_in_domain": len(scores),
            "scores_out_of_domain": 0,
            "missing_category_counts": {},
            "unknown_category_counts": {},
            "supported_categories": {},
        }
    training_domain = training_domain_by_model.get(model_id)
    if training_domain is None:
        return [], {
            "status": "training_domain_unavailable",
            "scores_total": len(scores),
            "scores_in_domain": 0,
            "scores_out_of_domain": len(scores),
            "missing_category_counts": {},
            "unknown_category_counts": {},
            "supported_categories": {},
        }
    return audit_score_domain(scores, training_domain)


def select_online_policy(
    rows: list[dict[str, Any]],
    *,
    minimum_ev: float,
    maximum_ev: float | None,
    maximum_bets_per_match: int | None = None,
) -> list[dict[str, Any]]:
    if (
        maximum_bets_per_match is not None
        and maximum_bets_per_match <= 0
    ):
        raise ValueError(
            "maximum_bets_per_match must be positive"
        )
    valid = [
        row
        for row in rows
        if row.get("valid_for_policy_evaluation") is True
        and row.get("invalid_for_model") is not True
        and _valid_timing(row)
    ]
    by_match: dict[str, list[dict[str, Any]]] = {}
    for row in valid:
        by_match.setdefault(
            str(row.get("match_key") or ""),
            [],
        ).append(row)

    selected: list[dict[str, Any]] = []
    for match_rows in by_match.values():
        batches: dict[pd.Timestamp, list[dict[str, Any]]] = {}
        for row in match_rows:
            created_at = pd.to_datetime(
                row["score_created_at"],
                utc=True,
            )
            batches.setdefault(created_at, []).append(row)
        for created_at in sorted(batches):
            eligible = [
                row
                for row in batches[created_at]
                if float(row["expected_roi_units"]) > minimum_ev
                and (
                    maximum_ev is None
                    or float(row["expected_roi_units"]) < maximum_ev
                )
            ]
            if not eligible:
                continue
            best_by_sample: dict[str, dict[str, Any]] = {}
            for row in sorted(
                eligible,
                key=lambda item: float(
                    item["expected_roi_units"]
                ),
                reverse=True,
            ):
                best_by_sample.setdefault(
                    str(row["sample_key"]),
                    row,
                )
            batch_selections = sorted(
                best_by_sample.values(),
                key=lambda item: float(
                    item["expected_roi_units"]
                ),
                reverse=True,
            )
            if maximum_bets_per_match is not None:
                batch_selections = batch_selections[
                    :maximum_bets_per_match
                ]
            selected.extend(batch_selections)
            break
    return selected


def _cluster_bootstrap(
    settled: list[dict[str, Any]],
    *,
    iterations: int,
) -> dict[str, float | int | None]:
    if not settled:
        return {
            "clusters": 0,
            "low_95_pct": None,
            "high_95_pct": None,
            "probability_positive": None,
        }
    by_match: dict[str, list[float]] = {}
    for row in settled:
        by_match.setdefault(str(row["match_key"]), []).append(
            float(row["pnl_units"])
        )
    clusters = np.asarray(
        [
            (sum(values), len(values))
            for values in by_match.values()
        ],
        dtype=float,
    )
    rng = np.random.default_rng(20260730)
    sampled = clusters[
        rng.integers(
            0,
            len(clusters),
            size=(iterations, len(clusters)),
        )
    ]
    roi = (
        sampled[:, :, 0].sum(axis=1)
        / sampled[:, :, 1].sum(axis=1)
        * 100.0
    )
    return {
        "clusters": int(len(clusters)),
        "low_95_pct": float(np.quantile(roi, 0.025)),
        "high_95_pct": float(np.quantile(roi, 0.975)),
        "probability_positive": float(np.mean(roi > 0.0)),
    }


def _evaluate_selections(
    selections: list[dict[str, Any]],
    *,
    result_lookup: dict,
    stats_lookup: dict,
    stat_scope_lookup: dict,
    bootstrap_iterations: int,
) -> dict[str, object]:
    settled: list[dict[str, Any]] = []
    pending = 0
    for selection in selections:
        actual = resolve_actual_context(
            row=selection,
            result_lookup=result_lookup,
            stats_lookup=stats_lookup,
            stat_scope_lookup=stat_scope_lookup,
        )
        if actual["actual_resolution_status"] != "resolved":
            pending += 1
            continue
        settlement = settle_line(
            actual_value=actual["actual_value"],
            line_value=selection["line_value"],
            direction=str(selection["direction"]),
            odds_decimal=selection["offered_odds"],
            stake_units=1.0,
        )
        if settlement is None:
            pending += 1
            continue
        settled.append(
            {
                "match_key": selection["match_key"],
                "score_key": selection["score_key"],
                "settlement_result": settlement[
                    "settlement_result"
                ],
                "pnl_units": settlement["pnl_units"],
            }
        )
    pnl_units = sum(
        float(row["pnl_units"]) for row in settled
    )
    result_counts = {
        result: sum(
            row["settlement_result"] == result
            for row in settled
        )
        for result in ("win", "loss", "push")
    }
    return {
        "selected_bets": len(selections),
        "selected_matches": len(
            {
                str(row["match_key"])
                for row in selections
            }
        ),
        "settlement": {
            "settled": len(settled),
            "pending": pending,
            **result_counts,
        },
        "performance": {
            "pnl_units": pnl_units,
            "roi_pct": (
                pnl_units / len(settled) * 100.0
                if settled
                else None
            ),
        },
        "cluster_bootstrap": _cluster_bootstrap(
            settled,
            iterations=bootstrap_iterations,
        ),
    }


def _evaluate_selection_clv(
    selections: list[dict[str, Any]],
    *,
    closing_lines: list[dict[str, Any]],
) -> dict[str, object]:
    closing_by_offer: dict[str, dict[str, Any]] = {}
    for row in closing_lines:
        offer_key = str(row.get("offer_key") or "")
        if not offer_key:
            continue
        candidate_time = pd.to_datetime(
            row.get("closing_snapshot_time"),
            errors="coerce",
            utc=True,
        )
        existing = closing_by_offer.get(offer_key)
        existing_time = pd.to_datetime(
            existing.get("closing_snapshot_time")
            if existing
            else None,
            errors="coerce",
            utc=True,
        )
        if (
            existing is None
            or (
                pd.notna(candidate_time)
                and (
                    pd.isna(existing_time)
                    or candidate_time > existing_time
                )
            )
        ):
            closing_by_offer[offer_key] = row

    clv_values: list[float] = []
    fallback_t30_clv_values: list[float] = []
    beat_close = 0
    fallback_t30_beat_close = 0
    invalid_closing_timing = 0
    for selection in selections:
        closing = closing_by_offer.get(
            str(selection.get("offer_key") or "")
        )
        if closing is None:
            continue
        closing_time = pd.to_datetime(
            closing.get("closing_snapshot_time"),
            errors="coerce",
            utc=True,
        )
        match_start = pd.to_datetime(
            selection.get("match_start_time"),
            errors="coerce",
            utc=True,
        )
        if (
            pd.isna(closing_time)
            or pd.isna(match_start)
            or closing_time >= match_start
        ):
            invalid_closing_timing += 1
            continue
        closing_label = str(
            closing.get("closing_snapshot_label") or ""
        )
        closing_quality = str(
            closing.get("closing_quality") or ""
        )
        official_closing = bool(
            closing.get("closing_is_official") is True
            or closing_label == "T_MINUS_10M"
            or closing_quality == "t10"
        )
        fallback_t30 = bool(
            not official_closing
            and (
                closing_label == "T_MINUS_30M"
                or closing_quality == "t30_fallback"
            )
        )
        if not official_closing and not fallback_t30:
            continue
        direction = str(selection.get("direction"))
        closing_odds = pd.to_numeric(
            closing.get(f"closing_{direction}_odds"),
            errors="coerce",
        )
        saved_odds = pd.to_numeric(
            selection.get("offered_odds"),
            errors="coerce",
        )
        if (
            pd.isna(closing_odds)
            or pd.isna(saved_odds)
            or float(closing_odds) <= 1.0
            or float(saved_odds) <= 1.0
        ):
            continue
        clv_value = (
            float(saved_odds) / float(closing_odds) - 1.0
        ) * 100.0
        if official_closing:
            clv_values.append(clv_value)
            beat_close += int(float(saved_odds) > float(closing_odds))
        else:
            fallback_t30_clv_values.append(clv_value)
            fallback_t30_beat_close += int(
                float(saved_odds) > float(closing_odds)
            )
    return {
        "selected_bets": len(selections),
        "rows_with_clv": len(clv_values),
        "coverage_pct": (
            len(clv_values) / len(selections) * 100.0
            if selections
            else 0.0
        ),
        "mean_clv_pct": (
            float(np.mean(clv_values))
            if clv_values
            else None
        ),
        "beat_close_rate_pct": (
            beat_close / len(clv_values) * 100.0
            if clv_values
            else None
        ),
        "fallback_t30_rows": len(fallback_t30_clv_values),
        "fallback_t30_coverage_pct": (
            len(fallback_t30_clv_values) / len(selections) * 100.0
            if selections
            else 0.0
        ),
        "fallback_t30_mean_clv_pct": (
            float(np.mean(fallback_t30_clv_values))
            if fallback_t30_clv_values
            else None
        ),
        "fallback_t30_beat_close_rate_pct": (
            fallback_t30_beat_close
            / len(fallback_t30_clv_values)
            * 100.0
            if fallback_t30_clv_values
            else None
        ),
        "invalid_closing_timing": (
            invalid_closing_timing
        ),
    }


def build_score_policy_evaluation(
    *,
    scores: list[dict[str, Any]],
    match_stats: list[dict[str, Any]],
    match_results: list[dict[str, Any]],
    model_ids: list[str],
    minimum_ev: float,
    maximum_ev: float | None,
    training_domain_by_model: (
        dict[str, dict[str, tuple[str, ...]]] | None
    ) = None,
    bootstrap_iterations: int = 20_000,
) -> dict[str, object]:
    result_lookup = build_result_lookup(match_results)
    stats_lookup = build_stats_lookup(match_stats)
    stat_scope_lookup = build_stat_scope_lookup(match_stats)
    reports: list[dict[str, object]] = []
    scored_keys_by_model: list[set[tuple[str, str, str]]] = []

    for model_id in model_ids:
        model_scores = [
            row
            for row in scores
            if str(row.get("model_id")) == model_id
        ]
        scored_keys_by_model.append(
            {
                (
                    str(row.get("match_key") or ""),
                    str(row.get("sample_key") or ""),
                    str(row.get("snapshot_key") or ""),
                )
                for row in model_scores
            }
        )
        domain_scores, domain_report = _filter_model_domain(
            model_scores,
            model_id=model_id,
            training_domain_by_model=training_domain_by_model,
        )
        selections = select_online_policy(
            domain_scores,
            minimum_ev=minimum_ev,
            maximum_ev=maximum_ev,
        )
        reports.append(
            {
                "model_id": model_id,
                "scores": len(model_scores),
                "in_domain_scores": len(domain_scores),
                "domain": domain_report,
                "valid_timing_scores": sum(
                    _valid_timing(row)
                    for row in domain_scores
                ),
                **_evaluate_selections(
                    selections,
                    result_lookup=result_lookup,
                    stats_lookup=stats_lookup,
                    stat_scope_lookup=stat_scope_lookup,
                    bootstrap_iterations=bootstrap_iterations,
                ),
            }
        )

    common_keys = (
        set.intersection(*scored_keys_by_model)
        if scored_keys_by_model
        else set()
    )
    return {
        "configuration": {
            "model_ids": model_ids,
            "minimum_ev": minimum_ev,
            "maximum_ev": maximum_ev,
            "policy_freeze": (
                "first score batch with any eligible side per match"
            ),
        },
        "common_scored_markets": len(common_keys),
        "models": reports,
    }


_POLICY_FILTER_COLUMNS = {
    "stat_keys": "stat_key",
    "periods": "period",
    "scopes": "scope",
    "directions": "direction",
    "leagues": "league_name_normalized",
}


def filter_policy_scores(
    scores: list[dict[str, Any]],
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    unsupported = sorted(
        set(filters).difference(_POLICY_FILTER_COLUMNS)
    )
    if unsupported:
        raise ValueError(
            f"unsupported score policy filters: {unsupported}"
        )
    filtered = scores
    for filter_name, values in filters.items():
        allowed = {str(value) for value in values}
        column = _POLICY_FILTER_COLUMNS[filter_name]
        filtered = [
            row
            for row in filtered
            if str(score_feature_value(row, column)) in allowed
        ]
    return filtered


def build_registered_policy_evaluation(
    *,
    scores: list[dict[str, Any]],
    match_stats: list[dict[str, Any]],
    match_results: list[dict[str, Any]],
    policies: list[dict[str, Any]],
    closing_lines: list[dict[str, Any]] | None = None,
    promotion_gate: dict[str, Any] | None = None,
    multiple_comparison_family_size: int = 1,
    audit_status_by_model: dict[str, str] | None = None,
    training_domain_by_model: (
        dict[str, dict[str, tuple[str, ...]]] | None
    ) = None,
    bootstrap_iterations: int = 20_000,
) -> dict[str, object]:
    registry_fingerprint = fingerprint_policy_registry(
        {"policies": policies}
    )
    result_lookup = build_result_lookup(match_results)
    stats_lookup = build_stats_lookup(match_stats)
    stat_scope_lookup = build_stat_scope_lookup(match_stats)
    reports: list[dict[str, object]] = []

    seen_policy_ids: set[str] = set()
    for policy in policies:
        policy_id = str(policy["policy_id"])
        if policy_id in seen_policy_ids:
            raise ValueError(
                f"duplicate score policy id: {policy_id}"
            )
        seen_policy_ids.add(policy_id)
        model_id = str(policy["model_id"])
        model_scores = [
            row
            for row in scores
            if str(row.get("model_id")) == model_id
        ]
        policy_scores = filter_policy_scores(
            model_scores,
            dict(policy.get("filters") or {}),
        )
        domain_scores, domain_report = _filter_model_domain(
            policy_scores,
            model_id=model_id,
            training_domain_by_model=training_domain_by_model,
        )
        minimum_ev = float(policy["minimum_ev"])
        maximum_ev_value = policy.get("maximum_ev")
        maximum_ev = (
            float(maximum_ev_value)
            if maximum_ev_value is not None
            else None
        )
        maximum_bets_value = policy.get(
            "maximum_bets_per_match"
        )
        maximum_bets_per_match = (
            int(maximum_bets_value)
            if maximum_bets_value is not None
            else None
        )
        selections = select_online_policy(
            domain_scores,
            minimum_ev=minimum_ev,
            maximum_ev=maximum_ev,
            maximum_bets_per_match=maximum_bets_per_match,
        )
        evaluation = _evaluate_selections(
            selections,
            result_lookup=result_lookup,
            stats_lookup=stats_lookup,
            stat_scope_lookup=stat_scope_lookup,
            bootstrap_iterations=bootstrap_iterations,
        )
        clv = _evaluate_selection_clv(
            selections,
            closing_lines=closing_lines or [],
        )
        audit_status = (
            (audit_status_by_model or {}).get(model_id)
        )
        promotion = None
        if promotion_gate is not None:
            promotion = evaluate_forward_promotion_gate(
                promotion_gate=promotion_gate,
                settled_bets=int(
                    evaluation["settlement"]["settled"]
                ),
                match_clusters=int(
                    evaluation["cluster_bootstrap"][
                        "clusters"
                    ]
                ),
                clustered_low_95_pct=(
                    evaluation["cluster_bootstrap"][
                        "low_95_pct"
                    ]
                ),
                bootstrap_probability_positive=(
                    evaluation["cluster_bootstrap"][
                        "probability_positive"
                    ]
                ),
                multiple_comparison_family_size=(
                    multiple_comparison_family_size
                ),
                clv_coverage_pct=float(
                    clv["coverage_pct"]
                ),
                mean_clv_pct=clv["mean_clv_pct"],
                audit_error_count=(
                    int(audit_status != "ok")
                    if audit_status is not None
                    else 0
                )
                + int(clv["invalid_closing_timing"]),
                audit_evidence_complete=(
                    audit_status is not None
                ),
            )
        reports.append(
            {
                "policy_id": policy_id,
                "model_id": model_id,
                "status": policy.get("status"),
                "filters": dict(
                    policy.get("filters") or {}
                ),
                "minimum_ev": minimum_ev,
                "maximum_ev": maximum_ev,
                "maximum_bets_per_match": (
                    maximum_bets_per_match
                ),
                "scores": len(policy_scores),
                "in_domain_scores": len(domain_scores),
                "domain": domain_report,
                "valid_timing_scores": sum(
                    _valid_timing(row)
                    for row in domain_scores
                ),
                **evaluation,
                "clv": clv,
                "source_model_audit_status": audit_status,
                "promotion_gate": promotion,
            }
        )
    return {
        "policy_registry_fingerprint": registry_fingerprint,
        "policy_count": len(policies),
        "multiple_comparison_family_size": (
            multiple_comparison_family_size
        ),
        "policy_freeze": (
            "first score batch with any eligible side per match "
            "after immutable policy and training-domain filters"
        ),
        "policies": reports,
    }
