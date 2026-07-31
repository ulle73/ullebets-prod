from __future__ import annotations

import numpy as np
import pandas as pd


JOIN_KEYS = (
    "side_key",
    "test_start",
    "test_end",
)


def merge_reference_count_predictions(
    reference: pd.DataFrame,
    count: pd.DataFrame,
) -> pd.DataFrame:
    for name, frame in (("reference", reference), ("count", count)):
        missing = sorted(set(JOIN_KEYS).difference(frame.columns))
        if missing:
            raise ValueError(f"{name} predictions are missing keys: {missing}")
        if frame.duplicated(list(JOIN_KEYS)).any():
            raise ValueError(f"{name} predictions contain duplicate join keys")
    count_columns = list(JOIN_KEYS) + [
        "predicted_win_probability",
        "predicted_push_probability",
        "expected_roi_units",
    ]
    missing_count = sorted(set(count_columns).difference(count.columns))
    if missing_count:
        raise ValueError(
            f"count predictions are missing values: {missing_count}"
        )
    renamed = count[count_columns].rename(
        columns={
            "predicted_win_probability": (
                "count_predicted_win_probability"
            ),
            "predicted_push_probability": (
                "count_predicted_push_probability"
            ),
            "expected_roi_units": "count_expected_roi_units",
        }
    )
    merged = reference.merge(
        renamed,
        on=list(JOIN_KEYS),
        how="inner",
        validate="one_to_one",
    )
    if len(merged) != len(reference) or len(merged) != len(count):
        raise ValueError(
            "reference and count prediction universes do not match: "
            f"reference={len(reference)}, count={len(count)}, "
            f"common={len(merged)}"
        )
    return merged


def blend_reference_with_count(
    merged: pd.DataFrame,
    *,
    count_weight: float,
    model_name: str,
) -> pd.DataFrame:
    if not 0.0 <= count_weight <= 1.0:
        raise ValueError("count_weight must be between zero and one")
    result = merged.copy()
    result["model_name"] = model_name
    result["predicted_win_probability"] = (
        (1.0 - count_weight)
        * pd.to_numeric(
            result["predicted_win_probability"],
            errors="coerce",
        )
        + count_weight
        * pd.to_numeric(
            result["count_predicted_win_probability"],
            errors="coerce",
        )
    ).clip(lower=1e-6, upper=1.0 - 1e-6)
    result["predicted_push_probability"] = (
        count_weight
        * pd.to_numeric(
            result["count_predicted_push_probability"],
            errors="coerce",
        ).fillna(0.0)
    ).clip(lower=0.0, upper=1.0)
    probability_total = (
        result["predicted_win_probability"]
        + result["predicted_push_probability"]
    )
    if probability_total.gt(1.0 + 1e-12).any():
        raise ValueError("blended win and push probabilities exceed one")
    loss_probability = (1.0 - probability_total).clip(lower=0.0)
    offered_odds = pd.to_numeric(
        result["offered_odds"],
        errors="coerce",
    )
    result["expected_roi_units"] = (
        result["predicted_win_probability"] * (offered_odds - 1.0)
        - loss_probability
    )
    result["predicted_over_probability"] = np.where(
        result["direction"].eq("over"),
        result["predicted_win_probability"],
        loss_probability,
    )
    return result


def gate_reference_by_count_agreement(
    reference_selections: pd.DataFrame,
    count_predictions: pd.DataFrame,
    *,
    minimum_count_ev: float,
    model_name: str,
) -> pd.DataFrame:
    required = {
        "sample_key",
        "direction",
        "expected_roi_units",
    }
    for name, frame in (
        ("reference", reference_selections),
        ("count", count_predictions),
    ):
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(f"{name} frame is missing columns: {missing}")
    count_preference = (
        count_predictions.sort_values(
            ["sample_key", "expected_roi_units"],
            ascending=[True, False],
            kind="stable",
        )
        .drop_duplicates("sample_key", keep="first")
        [["sample_key", "direction", "expected_roi_units"]]
        .rename(
            columns={
                "direction": "count_preferred_direction",
                "expected_roi_units": "count_preferred_ev",
            }
        )
    )
    gated = reference_selections.merge(
        count_preference,
        on="sample_key",
        how="left",
        validate="many_to_one",
    )
    gated = gated[
        gated["direction"].eq(gated["count_preferred_direction"])
        & gated["count_preferred_ev"].gt(minimum_count_ev)
    ].copy()
    gated["model_name"] = model_name
    return gated.drop(
        columns=["count_preferred_direction", "count_preferred_ev"]
    ).reset_index(drop=True)
