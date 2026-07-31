from __future__ import annotations

from typing import Any


def evaluate_forward_promotion_gate(
    *,
    promotion_gate: dict[str, Any],
    settled_bets: int,
    match_clusters: int,
    clustered_low_95_pct: float | None,
    bootstrap_probability_positive: float | None,
    multiple_comparison_family_size: int,
    clv_coverage_pct: float,
    mean_clv_pct: float | None,
    audit_error_count: int,
    audit_evidence_complete: bool,
) -> dict[str, object]:
    if multiple_comparison_family_size <= 0:
        raise ValueError(
            "multiple_comparison_family_size must be positive"
        )
    minimum_bets = int(
        promotion_gate["minimum_settled_bets"]
    )
    minimum_clusters = int(
        promotion_gate["minimum_match_clusters"]
    )
    minimum_clv_coverage = float(
        promotion_gate["minimum_clv_coverage_pct"]
    )
    adjusted_p_threshold = float(
        promotion_gate[
            "require_multiple_comparison_adjusted_p_below"
        ]
    )
    adjusted_p = (
        round(
            min(
                1.0,
                (
                    1.0
                    - float(
                        bootstrap_probability_positive
                    )
                )
                * multiple_comparison_family_size,
            ),
            12,
        )
        if bootstrap_probability_positive is not None
        else None
    )

    reasons: list[str] = []
    if settled_bets < minimum_bets:
        reasons.append(
            f"insufficient settled bets: {settled_bets} < "
            f"{minimum_bets}"
        )
    if match_clusters < minimum_clusters:
        reasons.append(
            f"insufficient match clusters: {match_clusters} < "
            f"{minimum_clusters}"
        )
    if (
        promotion_gate.get(
            "require_positive_clustered_95pct_lower_bound"
        )
        and (
            clustered_low_95_pct is None
            or clustered_low_95_pct <= 0.0
        )
    ):
        reasons.append(
            "clustered 95% lower bound is not positive"
        )
    if adjusted_p is None:
        reasons.append(
            "multiple-comparison adjusted p-value is unavailable"
        )
    elif adjusted_p >= adjusted_p_threshold:
        reasons.append(
            "multiple-comparison adjusted p-value is not below "
            f"{adjusted_p_threshold:.4f}: {adjusted_p:.4f}"
        )
    if clv_coverage_pct < minimum_clv_coverage:
        reasons.append(
            f"insufficient CLV coverage: {clv_coverage_pct:.2f}% "
            f"< {minimum_clv_coverage:.2f}%"
        )
    if (
        promotion_gate.get("require_positive_mean_clv")
        and (
            mean_clv_pct is None
            or mean_clv_pct <= 0.0
        )
    ):
        reasons.append("mean CLV is not positive")
    if (
        promotion_gate.get(
            "require_zero_timing_outcome_duplicate_feature_audit_errors"
        )
        and not audit_evidence_complete
    ):
        reasons.append("required audit evidence is incomplete")
    if (
        promotion_gate.get(
            "require_zero_timing_outcome_duplicate_feature_audit_errors"
        )
        and audit_error_count > 0
    ):
        reasons.append(
            f"audit errors present: {audit_error_count}"
        )
    return {
        "eligible_for_promotion": not reasons,
        "status": (
            "eligible" if not reasons else "insufficient_evidence"
        ),
        "multiple_comparison_family_size": (
            multiple_comparison_family_size
        ),
        "multiple_comparison_adjusted_p": adjusted_p,
        "blocking_reasons": reasons,
    }
