from __future__ import annotations

import pandas as pd

from ullebets_v2.ev_model.prequential_router import (
    PrequentialScopeRouterConfig,
    run_prequential_scope_router,
    run_scope_identity_permutation_test,
)


def _row(
    *,
    window: str,
    scope: str,
    match_id: str,
    pnl: float,
    expected_ev: float = 0.10,
) -> dict[str, object]:
    return {
        "test_start": window,
        "scope": scope,
        "exposure_match_id": match_id,
        "side_key": f"{match_id}|{scope}",
        "realized_roi_units": pnl,
        "expected_roi_units": expected_ev,
    }


def test_router_uses_only_prior_windows_for_scope_decisions() -> None:
    frame = pd.DataFrame(
        [
            _row(
                window="2026-01-01",
                scope="home",
                match_id="m1",
                pnl=-1.0,
            ),
            _row(
                window="2026-01-01",
                scope="away",
                match_id="m2",
                pnl=1.0,
            ),
            _row(
                window="2026-01-01",
                scope="total",
                match_id="m3",
                pnl=1.0,
            ),
            _row(
                window="2026-01-15",
                scope="home",
                match_id="m4",
                pnl=1.0,
            ),
            _row(
                window="2026-01-15",
                scope="away",
                match_id="m5",
                pnl=1.0,
            ),
            _row(
                window="2026-01-15",
                scope="total",
                match_id="m6",
                pnl=-1.0,
            ),
        ]
    )
    config = PrequentialScopeRouterConfig(
        minimum_prior_bets=1,
        minimum_prior_roi=0.0,
        cold_start="abstain",
    )

    selections, decisions = run_prequential_scope_router(
        frame,
        config,
    )

    assert set(selections["exposure_match_id"]) == {"m5", "m6"}
    first_window = decisions[
        decisions["target_window"].eq("2026-01-01")
    ]
    assert first_window["eligible"].sum() == 0
    second_window = decisions[
        decisions["target_window"].eq("2026-01-15")
    ]
    assert set(
        second_window.loc[
            second_window["eligible"],
            "scope",
        ]
    ) == {"away", "total"}
    assert second_window["prior_max_window"].eq(
        "2026-01-01"
    ).all()
    assert decisions["future_rows_used"].sum() == 0


def test_router_exposure_cap_keeps_highest_ev_per_match() -> None:
    frame = pd.DataFrame(
        [
            _row(
                window="2026-01-01",
                scope="away",
                match_id="history",
                pnl=1.0,
            ),
            _row(
                window="2026-01-15",
                scope="away",
                match_id="m1",
                pnl=1.0,
                expected_ev=0.11,
            ),
            _row(
                window="2026-01-15",
                scope="away",
                match_id="m1",
                pnl=-1.0,
                expected_ev=0.20,
            ),
        ]
    )
    config = PrequentialScopeRouterConfig(
        minimum_prior_bets=1,
        minimum_prior_roi=0.0,
        cold_start="abstain",
        maximum_bets_per_match=1,
    )

    selections, _ = run_prequential_scope_router(
        frame,
        config,
    )

    assert len(selections) == 1
    assert selections.iloc[0]["expected_roi_units"] == 0.20


def test_scope_permutation_test_enumerates_exact_null() -> None:
    frame = pd.DataFrame(
        [
            _row(
                window="2026-01-01",
                scope="away",
                match_id="m1",
                pnl=1.0,
            ),
            _row(
                window="2026-01-01",
                scope="home",
                match_id="m2",
                pnl=-1.0,
            ),
            _row(
                window="2026-01-15",
                scope="away",
                match_id="m3",
                pnl=1.0,
            ),
            _row(
                window="2026-01-15",
                scope="home",
                match_id="m4",
                pnl=-1.0,
            ),
        ]
    )
    config = PrequentialScopeRouterConfig(
        minimum_prior_bets=1,
        minimum_prior_roi=0.0,
        cold_start="abstain",
    )

    report = run_scope_identity_permutation_test(
        frame,
        config,
    )
    selections, _ = run_prequential_scope_router(
        frame,
        config,
    )

    assert report["exact_permutations"] == 4
    assert report["observed_roi_pct"] == (
        selections["realized_roi_units"].mean() * 100.0
    )
    assert 0.0 <= report["one_sided_p_value"] <= 1.0
    assert report["future_rows_used"] == 0
