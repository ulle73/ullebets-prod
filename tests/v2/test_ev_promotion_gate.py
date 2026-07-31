from __future__ import annotations

from ullebets_v2.ev_model.promotion import (
    evaluate_forward_promotion_gate,
)


GATE = {
    "minimum_settled_bets": 300,
    "minimum_match_clusters": 150,
    "minimum_clv_coverage_pct": 80,
    "require_positive_clustered_95pct_lower_bound": True,
    "require_positive_mean_clv": True,
    "require_multiple_comparison_adjusted_p_below": 0.05,
    "require_zero_timing_outcome_duplicate_feature_audit_errors": True,
}


def test_forward_promotion_gate_requires_all_evidence() -> None:
    result = evaluate_forward_promotion_gate(
        promotion_gate=GATE,
        settled_bets=320,
        match_clusters=180,
        clustered_low_95_pct=1.2,
        bootstrap_probability_positive=0.999,
        multiple_comparison_family_size=10,
        clv_coverage_pct=90.0,
        mean_clv_pct=2.1,
        audit_error_count=0,
        audit_evidence_complete=True,
    )

    assert result["eligible_for_promotion"] is True
    assert result["blocking_reasons"] == []
    assert result["multiple_comparison_adjusted_p"] == 0.01


def test_forward_promotion_gate_reports_missing_sample_and_clv() -> None:
    result = evaluate_forward_promotion_gate(
        promotion_gate=GATE,
        settled_bets=12,
        match_clusters=8,
        clustered_low_95_pct=None,
        bootstrap_probability_positive=None,
        multiple_comparison_family_size=10,
        clv_coverage_pct=0.0,
        mean_clv_pct=None,
        audit_error_count=1,
        audit_evidence_complete=True,
    )

    assert result["eligible_for_promotion"] is False
    assert set(result["blocking_reasons"]) == {
        "insufficient settled bets: 12 < 300",
        "insufficient match clusters: 8 < 150",
        "clustered 95% lower bound is not positive",
        "multiple-comparison adjusted p-value is unavailable",
        "insufficient CLV coverage: 0.00% < 80.00%",
        "mean CLV is not positive",
        "audit errors present: 1",
    }
