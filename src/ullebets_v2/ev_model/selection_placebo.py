from __future__ import annotations

from collections.abc import Hashable

import numpy as np
import pandas as pd


def _summarize_null(
    *,
    observed_roi: float,
    null_roi: np.ndarray,
) -> dict[str, float]:
    exceedances = int(
        np.count_nonzero(null_roi >= observed_roi)
    )
    return {
        "observed_roi_pct": float(observed_roi * 100.0),
        "null_mean_roi_pct": float(
            np.mean(null_roi) * 100.0
        ),
        "null_low_95_pct": float(
            np.quantile(null_roi, 0.025) * 100.0
        ),
        "null_high_95_pct": float(
            np.quantile(null_roi, 0.975) * 100.0
        ),
        "one_sided_p_value": float(
            (exceedances + 1.0) / (len(null_roi) + 1.0)
        ),
    }


def _simulate_group_counts(
    *,
    universe_groups: dict[Hashable, np.ndarray],
    selected_counts: dict[Hashable, int],
    selected_pnl: pd.Series,
    iterations: int,
    random_seed: int,
) -> dict[str, float | int]:
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    selected_bets = int(sum(selected_counts.values()))
    if selected_bets <= 0:
        raise ValueError("selected frame must not be empty")
    rng = np.random.default_rng(random_seed)
    null_pnl = np.zeros(iterations, dtype=float)
    for group, count in selected_counts.items():
        values = universe_groups.get(group)
        if values is None:
            raise ValueError(
                f"selected group missing from universe: {group}"
            )
        if count > len(values):
            raise ValueError(
                f"selected count exceeds universe for group {group}"
            )
        if count == len(values):
            null_pnl += values.sum()
            continue
        chunk_size = 1_000
        for start in range(0, iterations, chunk_size):
            stop = min(iterations, start + chunk_size)
            random_order = rng.random(
                (stop - start, len(values))
            )
            selected_indices = np.argpartition(
                random_order,
                count - 1,
                axis=1,
            )[:, :count]
            null_pnl[start:stop] += values[
                selected_indices
            ].sum(axis=1)
    observed_roi = float(
        pd.to_numeric(
            selected_pnl,
            errors="coerce",
        ).sum()
        / selected_bets
    )
    null_roi = null_pnl / selected_bets
    return {
        "selected_bets": selected_bets,
        "groups": len(selected_counts),
        "iterations": iterations,
        **_summarize_null(
            observed_roi=observed_roi,
            null_roi=null_roi,
        ),
    }


def random_choice_within_selected_groups(
    *,
    universe: pd.DataFrame,
    selected: pd.DataFrame,
    group_column: str,
    iterations: int = 100_000,
    random_seed: int = 20260730,
) -> dict[str, float | int]:
    universe_groups = {
        group: pd.to_numeric(
            rows["realized_roi_units"],
            errors="coerce",
        )
        .dropna()
        .to_numpy(dtype=float)
        for group, rows in universe.groupby(
            group_column,
            dropna=False,
        )
    }
    selected_counts = {
        group: int(count)
        for group, count in selected[
            group_column
        ].value_counts(dropna=False).items()
    }
    report = _simulate_group_counts(
        universe_groups=universe_groups,
        selected_counts=selected_counts,
        selected_pnl=selected["realized_roi_units"],
        iterations=iterations,
        random_seed=random_seed,
    )
    report["selected_groups"] = report.pop("groups")
    report["group_column"] = group_column
    return report


def stratified_random_selection_placebo(
    *,
    universe: pd.DataFrame,
    selected: pd.DataFrame,
    strata_columns: list[str],
    iterations: int = 50_000,
    random_seed: int = 20260730,
) -> dict[str, float | int | list[str]]:
    if not strata_columns:
        raise ValueError("strata_columns must not be empty")
    universe_groups = {
        group: pd.to_numeric(
            rows["realized_roi_units"],
            errors="coerce",
        )
        .dropna()
        .to_numpy(dtype=float)
        for group, rows in universe.groupby(
            strata_columns,
            dropna=False,
        )
    }
    selected_counts = {
        group: int(count)
        for group, count in selected.groupby(
            strata_columns,
            dropna=False,
        ).size().items()
    }
    report = _simulate_group_counts(
        universe_groups=universe_groups,
        selected_counts=selected_counts,
        selected_pnl=selected["realized_roi_units"],
        iterations=iterations,
        random_seed=random_seed,
    )
    report["strata"] = report.pop("groups")
    report["strata_columns"] = strata_columns
    return report
