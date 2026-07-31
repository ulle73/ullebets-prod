from __future__ import annotations

import numpy as np
import pandas as pd


def _performance(frame: pd.DataFrame) -> dict[str, float | int]:
    pnl = pd.to_numeric(
        frame["realized_roi_units"],
        errors="coerce",
    ).dropna()
    return {
        "bets": int(len(pnl)),
        "matches": int(
            frame.loc[pnl.index, "exposure_match_id"]
            .astype(str)
            .nunique()
        ),
        "pnl_units": float(pnl.sum()),
        "roi_pct": (
            float(pnl.mean() * 100.0)
            if len(pnl)
            else 0.0
        ),
    }


def _paired_cluster_bootstrap(
    reference: pd.DataFrame,
    challenger: pd.DataFrame,
    *,
    iterations: int,
    random_seed: int,
) -> dict[str, float | int | None]:
    match_ids = sorted(
        set(
            reference["exposure_match_id"].astype(str)
        ).union(
            challenger["exposure_match_id"].astype(str)
        )
    )
    if not match_ids:
        return {
            "match_clusters": 0,
            "observed_roi_difference_pct": None,
            "low_95_pct": None,
            "high_95_pct": None,
            "probability_challenger_superior": None,
            "one_sided_p_value": None,
        }

    def aggregate(frame: pd.DataFrame) -> np.ndarray:
        grouped = (
            frame.assign(
                _match_id=frame[
                    "exposure_match_id"
                ].astype(str)
            )
            .groupby("_match_id")["realized_roi_units"]
            .agg(["sum", "size"])
            .reindex(match_ids, fill_value=0)
        )
        return grouped.to_numpy(dtype=float)

    reference_clusters = aggregate(reference)
    challenger_clusters = aggregate(challenger)
    observed_reference = (
        reference_clusters[:, 0].sum()
        / reference_clusters[:, 1].sum()
    )
    observed_challenger = (
        challenger_clusters[:, 0].sum()
        / challenger_clusters[:, 1].sum()
    )
    rng = np.random.default_rng(random_seed)
    sampled_indices = rng.integers(
        0,
        len(match_ids),
        size=(iterations, len(match_ids)),
    )
    sampled_reference = reference_clusters[
        sampled_indices
    ]
    sampled_challenger = challenger_clusters[
        sampled_indices
    ]
    reference_count = sampled_reference[:, :, 1].sum(
        axis=1
    )
    challenger_count = sampled_challenger[:, :, 1].sum(
        axis=1
    )
    reference_roi = np.divide(
        sampled_reference[:, :, 0].sum(axis=1),
        reference_count,
        out=np.full(iterations, np.nan),
        where=reference_count > 0,
    )
    challenger_roi = np.divide(
        sampled_challenger[:, :, 0].sum(axis=1),
        challenger_count,
        out=np.full(iterations, np.nan),
        where=challenger_count > 0,
    )
    differences = challenger_roi - reference_roi
    differences = differences[np.isfinite(differences)]
    return {
        "match_clusters": len(match_ids),
        "observed_roi_difference_pct": float(
            (observed_challenger - observed_reference)
            * 100.0
        ),
        "valid_bootstrap_iterations": int(
            len(differences)
        ),
        "low_95_pct": float(
            np.quantile(differences, 0.025) * 100.0
        ),
        "high_95_pct": float(
            np.quantile(differences, 0.975) * 100.0
        ),
        "probability_challenger_superior": float(
            np.mean(differences > 0.0)
        ),
        "one_sided_p_value": float(
            np.mean(differences <= 0.0)
        ),
    }


def _prediction_quality(
    reference: pd.DataFrame,
    challenger: pd.DataFrame,
) -> dict[str, float | int | None]:
    columns = [
        "side_key",
        "predicted_win_probability",
        "settlement_result",
    ]
    paired = (
        reference[columns]
        .drop_duplicates("side_key")
        .merge(
            challenger[columns].drop_duplicates(
                "side_key"
            ),
            on="side_key",
            suffixes=("_reference", "_challenger"),
        )
    )
    paired = paired[
        paired["settlement_result_reference"].isin(
            ["win", "loss"]
        )
    ]
    if paired.empty:
        return {
            "paired_rows": 0,
            "settlement_mismatches": 0,
            "reference_brier": None,
            "challenger_brier": None,
            "brier_improvement": None,
        }
    target = (
        paired["settlement_result_reference"]
        .eq("win")
        .astype(float)
    )
    reference_probability = pd.to_numeric(
        paired["predicted_win_probability_reference"],
        errors="coerce",
    )
    challenger_probability = pd.to_numeric(
        paired["predicted_win_probability_challenger"],
        errors="coerce",
    )
    valid = (
        reference_probability.notna()
        & challenger_probability.notna()
    )
    target = target[valid]
    reference_probability = reference_probability[valid]
    challenger_probability = challenger_probability[valid]
    reference_brier = float(
        np.mean((reference_probability - target) ** 2)
    )
    challenger_brier = float(
        np.mean((challenger_probability - target) ** 2)
    )
    return {
        "paired_rows": int(len(target)),
        "settlement_mismatches": int(
            (
                paired["settlement_result_reference"]
                != paired["settlement_result_challenger"]
            ).sum()
        ),
        "reference_brier": reference_brier,
        "challenger_brier": challenger_brier,
        "brier_improvement": (
            reference_brier - challenger_brier
        ),
    }


def build_paired_strategy_comparison(
    *,
    reference_selections: pd.DataFrame,
    challenger_selections: pd.DataFrame,
    reference_predictions: pd.DataFrame,
    challenger_predictions: pd.DataFrame,
    bootstrap_iterations: int = 50_000,
    random_seed: int = 20260730,
) -> dict[str, object]:
    reference_keys = set(
        reference_selections["side_key"].astype(str)
    )
    challenger_keys = set(
        challenger_selections["side_key"].astype(str)
    )
    common_keys = reference_keys.intersection(
        challenger_keys
    )
    reference_only = reference_keys.difference(
        challenger_keys
    )
    challenger_only = challenger_keys.difference(
        reference_keys
    )
    return {
        "reference": _performance(reference_selections),
        "challenger": _performance(
            challenger_selections
        ),
        "selection_overlap": {
            "common": len(common_keys),
            "reference_only": len(reference_only),
            "challenger_only": len(challenger_only),
        },
        "common_selections": _performance(
            reference_selections[
                reference_selections["side_key"]
                .astype(str)
                .isin(common_keys)
            ]
        ),
        "reference_unique": _performance(
            reference_selections[
                reference_selections["side_key"]
                .astype(str)
                .isin(reference_only)
            ]
        ),
        "challenger_unique": _performance(
            challenger_selections[
                challenger_selections["side_key"]
                .astype(str)
                .isin(challenger_only)
            ]
        ),
        "paired_bootstrap": _paired_cluster_bootstrap(
            reference_selections,
            challenger_selections,
            iterations=bootstrap_iterations,
            random_seed=random_seed,
        ),
        "prediction_quality": _prediction_quality(
            reference_predictions,
            challenger_predictions,
        ),
    }
