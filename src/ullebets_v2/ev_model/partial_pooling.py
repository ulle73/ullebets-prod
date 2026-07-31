from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss


REQUIRED_COLUMNS = {
    "sample_key",
    "stat_key",
    "test_start",
    "is_over_win",
    "predicted_over_probability",
}


def _market_rows(frame: pd.DataFrame, *, name: str) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(
            f"{name} predictions missing columns: {sorted(missing)}"
        )
    return frame.drop_duplicates("sample_key", keep="first").copy()


def build_prequential_partial_pooling_predictions(
    global_predictions: pd.DataFrame,
    local_predictions: pd.DataFrame,
    *,
    candidate_local_weights: tuple[float, ...] = (
        0.0,
        0.10,
        0.25,
        0.50,
        0.75,
        1.0,
    ),
    min_prior_markets: int = 250,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not candidate_local_weights:
        raise ValueError("candidate_local_weights cannot be empty")
    if any(
        weight < 0.0 or weight > 1.0
        for weight in candidate_local_weights
    ):
        raise ValueError(
            "candidate_local_weights must be between zero and one"
        )
    if min_prior_markets < 1:
        raise ValueError("min_prior_markets must be positive")

    global_markets = _market_rows(
        global_predictions,
        name="global",
    )
    local_markets = _market_rows(
        local_predictions,
        name="local",
    )
    local_probability = local_markets[
        ["sample_key", "predicted_over_probability"]
    ].rename(
        columns={
            "predicted_over_probability": (
                "local_predicted_over_probability"
            )
        }
    )
    combined = global_markets.rename(
        columns={
            "predicted_over_probability": (
                "global_predicted_over_probability"
            )
        }
    ).merge(
        local_probability,
        on="sample_key",
        how="left",
        validate="one_to_one",
    )
    combined["predicted_over_probability"] = combined[
        "global_predicted_over_probability"
    ]
    combined["local_weight"] = 0.0
    combined["partial_pooling_source"] = (
        "missing_local_fallback"
    )
    combined["_test_start"] = pd.to_datetime(
        combined["test_start"],
        errors="raise",
    )

    audit_rows: list[dict[str, object]] = []
    for stat_key in sorted(combined["stat_key"].astype(str).unique()):
        stat_mask = combined["stat_key"].astype(str).eq(stat_key)
        stat_windows = sorted(
            combined.loc[stat_mask, "_test_start"].unique()
        )
        for test_start in stat_windows:
            window_mask = stat_mask & combined["_test_start"].eq(
                test_start
            )
            local_available = combined[
                "local_predicted_over_probability"
            ].notna()
            available_mask = window_mask & local_available
            prior_mask = (
                stat_mask
                & combined["_test_start"].lt(test_start)
                & local_available
                & combined["is_over_win"].notna()
            )
            prior = combined.loc[prior_mask]
            candidate_metrics: list[dict[str, float]] = []
            if len(prior) >= min_prior_markets:
                for local_weight in candidate_local_weights:
                    probability = (
                        (1.0 - local_weight)
                        * prior[
                            "global_predicted_over_probability"
                        ]
                        + local_weight
                        * prior[
                            "local_predicted_over_probability"
                        ]
                    )
                    candidate_metrics.append(
                        {
                            "local_weight": float(local_weight),
                            "prior_brier": float(
                                brier_score_loss(
                                    prior["is_over_win"],
                                    probability,
                                )
                            ),
                        }
                    )
                selected = min(
                    candidate_metrics,
                    key=lambda row: (
                        row["prior_brier"],
                        row["local_weight"],
                    ),
                )
                local_weight = float(selected["local_weight"])
                source = "prequential_prior_brier"
            else:
                local_weight = 0.0
                source = "cold_start_global"

            if available_mask.any():
                combined.loc[
                    available_mask,
                    "predicted_over_probability",
                ] = np.clip(
                    (
                        (1.0 - local_weight)
                        * combined.loc[
                            available_mask,
                            "global_predicted_over_probability",
                        ]
                        + local_weight
                        * combined.loc[
                            available_mask,
                            "local_predicted_over_probability",
                        ]
                    ),
                    1e-6,
                    1.0 - 1e-6,
                )
                combined.loc[
                    available_mask,
                    "local_weight",
                ] = local_weight
                combined.loc[
                    available_mask,
                    "partial_pooling_source",
                ] = source

            audit_rows.append(
                {
                    "stat_key": stat_key,
                    "test_start": pd.Timestamp(
                        test_start
                    ).date().isoformat(),
                    "markets": int(window_mask.sum()),
                    "missing_local_markets": int(
                        (window_mask & ~local_available).sum()
                    ),
                    "prior_markets": int(len(prior)),
                    "local_weight": local_weight,
                    "selection_source": source,
                    "candidate_metrics": candidate_metrics,
                }
            )

    return (
        combined.drop(columns=["_test_start"]),
        pd.DataFrame(audit_rows),
    )
