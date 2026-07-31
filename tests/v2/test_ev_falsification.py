from __future__ import annotations

import pandas as pd
import pytest

from ullebets_v2.ev_model.falsification import (
    apply_absolute_odds_haircut,
    apply_policy_exposure_cap_to_frame,
    apply_policy_filters_to_frame,
    build_candidate_falsification_report,
)


def _row(
    *,
    match_id: str,
    league: str,
    window: str,
    result: str,
    odds: float,
    probability: float,
    stat_key: str = "cornerKicks",
) -> dict[str, object]:
    pnl = odds - 1.0 if result == "win" else -1.0
    if result == "push":
        pnl = 0.0
    return {
        "exposure_match_id": match_id,
        "league_name_normalized": league,
        "test_start": window,
        "stat_key": stat_key,
        "period": "ALL",
        "scope": "total",
        "direction": "over",
        "offered_odds": odds,
        "predicted_win_probability": probability,
        "market_fair_probability_over": 1.0 / odds,
        "settlement_result": result,
        "realized_roi_units": pnl,
        "expected_roi_units": probability * odds - 1.0,
    }


def test_absolute_odds_haircut_only_reprices_wins() -> None:
    frame = pd.DataFrame(
        [
            _row(
                match_id="m1",
                league="A",
                window="w1",
                result="win",
                odds=2.10,
                probability=0.55,
            ),
            _row(
                match_id="m2",
                league="A",
                window="w1",
                result="loss",
                odds=1.90,
                probability=0.55,
            ),
            _row(
                match_id="m3",
                league="A",
                window="w1",
                result="push",
                odds=2.00,
                probability=0.55,
            ),
        ]
    )

    pnl = apply_absolute_odds_haircut(
        frame,
        absolute_decimal_points=0.05,
    )

    assert pnl.tolist() == pytest.approx([1.05, -1.0, 0.0])


def test_falsification_report_exposes_regime_concentration() -> None:
    frame = pd.DataFrame(
        [
            _row(
                match_id="m1",
                league="A",
                window="w1",
                result="win",
                odds=2.00,
                probability=0.60,
            ),
            _row(
                match_id="m2",
                league="A",
                window="w1",
                result="loss",
                odds=2.00,
                probability=0.60,
            ),
            _row(
                match_id="m3",
                league="B",
                window="w2",
                result="win",
                odds=2.00,
                probability=0.60,
            ),
            _row(
                match_id="m4",
                league="B",
                window="w2",
                result="win",
                odds=2.00,
                probability=0.60,
            ),
        ]
    )

    report = build_candidate_falsification_report(
        {"candidate": frame},
        experiments_inspected=20,
        bootstrap_iterations=2_000,
        random_seed=7,
    )
    candidate = report["candidates"][0]

    assert candidate["performance"] == {
        "bets": 4,
        "matches": 4,
        "pnl_units": pytest.approx(2.0),
        "roi_pct": pytest.approx(50.0),
    }
    assert (
        candidate["leave_one_league_out"]["all_positive"]
        is False
    )
    assert (
        candidate["leave_one_league_out"]["minimum_roi_pct"]
        == pytest.approx(0.0)
    )
    assert candidate["concentration"]["top_net_pnl_league"] == "B"
    assert (
        candidate["price_stress"]["minus_0.05_decimal"]["roi_pct"]
        == pytest.approx(46.25)
    )
    assert candidate["calibration"]["settled_non_push_rows"] == 4
    assert candidate["calibration"]["observed_win_rate"] == 0.75
    assert (
        candidate["cluster_inference"][
            "multiple_comparison_adjusted_p_value"
        ]
        >= candidate["cluster_inference"]["one_sided_null_p_value"]
    )
    assert candidate["historical_edge_status"] == "not_confirmed"
    assert candidate["mechanical_gate_status"] == "fails"


def test_market_probability_is_complemented_for_under_rows() -> None:
    over = _row(
        match_id="m1",
        league="A",
        window="w1",
        result="win",
        odds=2.0,
        probability=0.6,
    )
    under = {
        **_row(
            match_id="m2",
            league="B",
            window="w2",
            result="loss",
            odds=2.0,
            probability=0.6,
        ),
        "direction": "under",
        "market_fair_probability_over": 0.70,
    }

    report = build_candidate_falsification_report(
        {"candidate": pd.DataFrame([over, under])},
        experiments_inspected=1,
        bootstrap_iterations=500,
        random_seed=11,
    )

    assert report["candidates"][0]["calibration"][
        "mean_market_probability"
    ] == pytest.approx(0.40)


def test_policy_filters_apply_stat_and_scope_as_intersection() -> None:
    frame = pd.DataFrame(
        [
            {
                "stat_key": "cornerKicks",
                "scope": "away",
            },
            {
                "stat_key": "cornerKicks",
                "scope": "home",
            },
            {
                "stat_key": "shotsOnGoal",
                "scope": "away",
            },
        ]
    )

    filtered = apply_policy_filters_to_frame(
        frame,
        {
            "stat_keys": ["cornerKicks"],
            "scopes": ["away", "total"],
        },
    )

    assert filtered.to_dict(orient="records") == [
        {
            "stat_key": "cornerKicks",
            "scope": "away",
        }
    ]


def test_policy_exposure_cap_keeps_highest_ev_per_match() -> None:
    frame = pd.DataFrame(
        [
            {
                "exposure_match_id": "m1",
                "side_key": "lower",
                "expected_roi_units": 0.10,
            },
            {
                "exposure_match_id": "m1",
                "side_key": "higher",
                "expected_roi_units": 0.20,
            },
            {
                "exposure_match_id": "m2",
                "side_key": "other",
                "expected_roi_units": 0.08,
            },
        ]
    )

    capped = apply_policy_exposure_cap_to_frame(
        frame,
        maximum_bets_per_match=1,
    )

    assert set(capped["side_key"]) == {"higher", "other"}
