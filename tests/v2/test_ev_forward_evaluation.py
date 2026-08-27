from __future__ import annotations

from datetime import UTC, datetime

from ullebets_v2.ev_model.forward_evaluation import (
    build_forward_evaluation_report,
)


def test_forward_evaluation_separates_pending_settlement_and_clv() -> None:
    predictions = [
        {
            "prediction_key": "p1",
            "model_id": "model-v3",
            "match_key": "m1",
            "stat_key": "cornerKicks",
            "period": "ALL",
            "scope": "total",
            "line_value": 10.5,
            "direction": "under",
            "odds_snapshot_time": datetime(2026, 1, 1, 10, tzinfo=UTC),
            "prediction_created_at": datetime(2026, 1, 1, 11, tzinfo=UTC),
            "match_start_time": datetime(2026, 1, 1, 14, tzinfo=UTC),
        },
        {
            "prediction_key": "p2",
            "model_id": "model-v3",
            "match_key": "m2",
            "stat_key": "shotsOnGoal",
            "period": "ALL",
            "scope": "home",
            "line_value": 4.5,
            "direction": "over",
            "odds_snapshot_time": datetime(2026, 1, 2, 10, tzinfo=UTC),
            "prediction_created_at": datetime(2026, 1, 2, 11, tzinfo=UTC),
            "match_start_time": datetime(2026, 1, 2, 14, tzinfo=UTC),
        },
    ]
    settled = [
        {
            "prediction_key": "p1",
            "settlement_status": "settled",
            "settlement_result": "win",
            "pnl_units": 0.9,
        }
    ]
    clv = [
        {
            "prediction_key": "p1",
            "clv_pct": 2.0,
            "beat_closing_line": True,
            "closing_snapshot_label": "T_MINUS_10M",
        }
    ]

    report = build_forward_evaluation_report(
        predictions=predictions,
        settled_rows=settled,
        clv_rows=clv,
        model_id="model-v3",
        bootstrap_iterations=100,
    )

    assert report["predictions"] == 2
    assert report["settlement"]["settled"] == 1
    assert report["settlement"]["pending"] == 1
    assert report["performance"]["pnl_units"] == 0.9
    assert report["timing"]["violations"] == 0
    assert report["clv"]["coverage_pct"] == 50.0
    assert report["promotion"]["eligible"] is False


def test_forward_evaluation_excludes_t30_fallback_from_official_clv_gate() -> None:
    prediction = {
        "prediction_key": "p1",
        "model_id": "model-v3",
        "match_key": "m1",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "total",
        "line_value": 10.5,
        "direction": "over",
        "odds_snapshot_time": datetime(2026, 1, 1, 10, tzinfo=UTC),
        "prediction_created_at": datetime(2026, 1, 1, 11, tzinfo=UTC),
        "match_start_time": datetime(2026, 1, 1, 14, tzinfo=UTC),
    }
    report = build_forward_evaluation_report(
        predictions=[prediction],
        settled_rows=[],
        clv_rows=[
            {
                "prediction_key": "p1",
                "clv_pct": 3.0,
                "beat_closing_line": True,
                "closing_snapshot_label": "T_MINUS_30M",
                "official_clv": False,
            }
        ],
        model_id="model-v3",
        bootstrap_iterations=100,
    )

    assert report["clv"]["rows"] == 0
    assert report["clv"]["fallback_t30_rows"] == 1
    assert report["clv"]["coverage_pct"] == 0.0


def test_forward_evaluation_respects_explicit_promotion_clv_eligibility() -> None:
    prediction = {
        "prediction_key": "p1",
        "model_id": "model-v3",
        "match_key": "m1",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "total",
        "line_value": 10.5,
        "direction": "over",
        "odds_snapshot_time": datetime(2026, 1, 1, 10, tzinfo=UTC),
        "prediction_created_at": datetime(2026, 1, 1, 11, tzinfo=UTC),
        "match_start_time": datetime(2026, 1, 1, 14, tzinfo=UTC),
    }
    report = build_forward_evaluation_report(
        predictions=[prediction],
        settled_rows=[],
        clv_rows=[
            {
                "prediction_key": "p1",
                "clv_pct": 3.0,
                "beat_closing_line": True,
                "closing_snapshot_label": "T_MINUS_10M",
                "official_clv": True,
                "eligible_for_promotion_clv": False,
            }
        ],
        model_id="model-v3",
        bootstrap_iterations=100,
    )

    assert report["clv"]["rows"] == 0
    assert report["clv"]["coverage_pct"] == 0.0


def test_forward_evaluation_excludes_snapshot_created_after_prediction() -> None:
    prediction = {
        "prediction_key": "invalid",
        "model_id": "model-v3",
        "match_key": "m1",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "total",
        "line_value": 10.5,
        "direction": "under",
        "odds_snapshot_time": datetime(2026, 1, 1, 12, tzinfo=UTC),
        "prediction_created_at": datetime(2026, 1, 1, 11, tzinfo=UTC),
        "match_start_time": datetime(2026, 1, 1, 14, tzinfo=UTC),
    }
    settlement = {
        "prediction_key": "invalid",
        "settlement_status": "settled",
        "settlement_result": "win",
        "pnl_units": 0.9,
    }

    report = build_forward_evaluation_report(
        predictions=[prediction],
        settled_rows=[settlement],
        clv_rows=[],
        model_id="model-v3",
        bootstrap_iterations=100,
    )

    assert report["valid_predictions"] == 0
    assert report["invalid_predictions"] == 1
    assert report["timing"]["violations"] == 1
    assert report["settlement"]["settled"] == 0
    assert report["performance"]["pnl_units"] == 0
