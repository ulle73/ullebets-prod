from __future__ import annotations

import pandas as pd

from ullebets_v2.ev_model.selection_placebo import (
    random_choice_within_selected_groups,
    stratified_random_selection_placebo,
)


def test_random_choice_preserves_selected_group_exposure() -> None:
    universe = pd.DataFrame(
        [
            {"sample_key": "a", "realized_roi_units": 1.0},
            {"sample_key": "a", "realized_roi_units": -1.0},
            {"sample_key": "b", "realized_roi_units": 1.0},
            {"sample_key": "b", "realized_roi_units": -1.0},
        ]
    )
    selected = universe.iloc[[0, 2]].copy()

    report = random_choice_within_selected_groups(
        universe=universe,
        selected=selected,
        group_column="sample_key",
        iterations=2_000,
        random_seed=9,
    )

    assert report["selected_groups"] == 2
    assert report["observed_roi_pct"] == 100.0
    assert report["null_mean_roi_pct"] < 10.0
    assert report["one_sided_p_value"] < 0.4


def test_stratified_placebo_matches_selection_counts() -> None:
    universe = pd.DataFrame(
        [
            {
                "window": "w1",
                "scope": "away",
                "realized_roi_units": value,
            }
            for value in [1.0, 1.0, -1.0, -1.0]
        ]
    )
    selected = universe.iloc[:2].copy()

    report = stratified_random_selection_placebo(
        universe=universe,
        selected=selected,
        strata_columns=["window", "scope"],
        iterations=2_000,
        random_seed=12,
    )

    assert report["selected_bets"] == 2
    assert report["strata"] == 1
    assert report["observed_roi_pct"] == 100.0
    assert report["null_mean_roi_pct"] < 10.0
