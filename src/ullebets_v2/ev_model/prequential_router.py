from __future__ import annotations

from dataclasses import dataclass
import itertools
import math

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.falsification import (
    apply_policy_exposure_cap_to_frame,
)


@dataclass(frozen=True)
class PrequentialScopeRouterConfig:
    minimum_prior_bets: int
    minimum_prior_roi: float
    cold_start: str
    maximum_bets_per_match: int | None = None

    def __post_init__(self) -> None:
        if self.minimum_prior_bets <= 0:
            raise ValueError(
                "minimum_prior_bets must be positive"
            )
        if self.cold_start not in {"include", "abstain"}:
            raise ValueError(
                "cold_start must be include or abstain"
            )
        if (
            self.maximum_bets_per_match is not None
            and self.maximum_bets_per_match <= 0
        ):
            raise ValueError(
                "maximum_bets_per_match must be positive"
            )


def run_prequential_scope_router(
    frame: pd.DataFrame,
    config: PrequentialScopeRouterConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {
        "test_start",
        "scope",
        "exposure_match_id",
        "realized_roi_units",
        "expected_roi_units",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(
            f"router frame is missing columns: {missing}"
        )
    source = frame.copy()
    source["_router_window"] = source[
        "test_start"
    ].astype(str)
    windows = sorted(source["_router_window"].unique())
    scopes = sorted(source["scope"].astype(str).unique())
    selection_parts: list[pd.DataFrame] = []
    decision_rows: list[dict[str, object]] = []

    for target_window in windows:
        prior = source[
            source["_router_window"] < target_window
        ]
        current = source[
            source["_router_window"] == target_window
        ]
        allowed_scopes: list[str] = []
        prior_max_window = (
            str(prior["_router_window"].max())
            if not prior.empty
            else None
        )
        for scope in scopes:
            scope_prior = prior[
                prior["scope"].astype(str).eq(scope)
            ]
            prior_bets = int(len(scope_prior))
            prior_pnl = float(
                pd.to_numeric(
                    scope_prior["realized_roi_units"],
                    errors="coerce",
                ).sum()
            )
            prior_roi = (
                prior_pnl / prior_bets
                if prior_bets
                else None
            )
            if prior_bets < config.minimum_prior_bets:
                eligible = config.cold_start == "include"
                reason = (
                    "cold_start_include"
                    if eligible
                    else "insufficient_prior_bets"
                )
            else:
                eligible = bool(
                    prior_roi is not None
                    and prior_roi
                    > config.minimum_prior_roi
                )
                reason = (
                    "prior_roi_above_threshold"
                    if eligible
                    else "prior_roi_not_above_threshold"
                )
            if eligible:
                allowed_scopes.append(scope)
            decision_rows.append(
                {
                    "target_window": target_window,
                    "scope": scope,
                    "prior_bets": prior_bets,
                    "prior_pnl_units": prior_pnl,
                    "prior_roi": prior_roi,
                    "minimum_prior_bets": (
                        config.minimum_prior_bets
                    ),
                    "minimum_prior_roi": (
                        config.minimum_prior_roi
                    ),
                    "cold_start": config.cold_start,
                    "eligible": eligible,
                    "eligibility_reason": reason,
                    "prior_max_window": prior_max_window,
                    "future_rows_used": 0,
                }
            )
        selected = current[
            current["scope"].astype(str).isin(
                allowed_scopes
            )
        ]
        selected = apply_policy_exposure_cap_to_frame(
            selected,
            maximum_bets_per_match=(
                config.maximum_bets_per_match
            ),
        )
        selection_parts.append(selected)

    selections = (
        pd.concat(selection_parts, ignore_index=True)
        if selection_parts
        else source.iloc[0:0].copy()
    )
    return (
        selections.drop(
            columns=["_router_window"],
            errors="ignore",
        ),
        pd.DataFrame(decision_rows),
    )


def run_scope_identity_permutation_test(
    frame: pd.DataFrame,
    config: PrequentialScopeRouterConfig,
    *,
    maximum_exact_permutations: int = 100_000,
) -> dict[str, float | int]:
    if config.maximum_bets_per_match is not None:
        raise ValueError(
            "exact scope permutation does not support an "
            "exposure cap"
        )
    source = frame.copy()
    source["_router_window"] = source[
        "test_start"
    ].astype(str)
    windows = sorted(source["_router_window"].unique())
    scopes = sorted(source["scope"].astype(str).unique())
    if not windows or not scopes:
        raise ValueError(
            "scope permutation requires non-empty data"
        )
    permutations = list(
        itertools.permutations(range(len(scopes)))
    )
    exact_permutations = len(permutations) ** len(windows)
    if exact_permutations > maximum_exact_permutations:
        raise ValueError(
            "exact scope permutation family is too large: "
            f"{exact_permutations}"
        )

    counts = np.zeros(
        (len(windows), len(scopes)),
        dtype=float,
    )
    pnl = np.zeros_like(counts)
    scope_index = {
        scope: index
        for index, scope in enumerate(scopes)
    }
    window_index = {
        window: index
        for index, window in enumerate(windows)
    }
    grouped = (
        source.groupby(["_router_window", "scope"])
        ["realized_roi_units"]
        .agg(["size", "sum"])
    )
    for (window, scope), row in grouped.iterrows():
        row_index = window_index[str(window)]
        column_index = scope_index[str(scope)]
        counts[row_index, column_index] = float(
            row["size"]
        )
        pnl[row_index, column_index] = float(row["sum"])

    def evaluate(
        sequence: tuple[tuple[int, ...], ...],
    ) -> tuple[float, int]:
        prior_counts = np.zeros(len(scopes), dtype=float)
        prior_pnl = np.zeros(len(scopes), dtype=float)
        selected_count = 0.0
        selected_pnl = 0.0
        for row_index, mapping in enumerate(sequence):
            enough_history = (
                prior_counts >= config.minimum_prior_bets
            )
            prior_roi = np.divide(
                prior_pnl,
                prior_counts,
                out=np.zeros_like(prior_pnl),
                where=prior_counts > 0,
            )
            eligible = (
                enough_history
                & (prior_roi > config.minimum_prior_roi)
            )
            if config.cold_start == "include":
                eligible = eligible | ~enough_history

            for original_scope, mapped_scope in enumerate(
                mapping
            ):
                if eligible[mapped_scope]:
                    selected_count += counts[
                        row_index,
                        original_scope,
                    ]
                    selected_pnl += pnl[
                        row_index,
                        original_scope,
                    ]
                prior_counts[mapped_scope] += counts[
                    row_index,
                    original_scope,
                ]
                prior_pnl[mapped_scope] += pnl[
                    row_index,
                    original_scope,
                ]
        roi = (
            selected_pnl / selected_count
            if selected_count
            else 0.0
        )
        return roi, int(selected_count)

    identity = tuple(range(len(scopes)))
    observed_roi, observed_count = evaluate(
        tuple(identity for _ in windows)
    )
    null_roi = np.empty(exact_permutations, dtype=float)
    for index, sequence in enumerate(
        itertools.product(
            permutations,
            repeat=len(windows),
        )
    ):
        null_roi[index] = evaluate(sequence)[0]
    return {
        "windows": len(windows),
        "scopes": len(scopes),
        "scope_permutations_per_window": math.factorial(
            len(scopes)
        ),
        "exact_permutations": exact_permutations,
        "observed_selected_bets": observed_count,
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
            np.mean(null_roi >= observed_roi)
        ),
        "future_rows_used": 0,
    }
