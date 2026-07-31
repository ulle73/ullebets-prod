from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np
import pandas as pd


JOIN_KEYS = (
    "side_key",
    "test_start",
    "test_end",
)


def build_fixed_prediction_ensemble(
    predictions: Mapping[str, pd.DataFrame],
    *,
    weights: Mapping[str, float],
    model_name: str,
) -> pd.DataFrame:
    if not predictions or set(predictions) != set(weights):
        raise ValueError(
            "predictions and weights require identical non-empty keys"
        )
    normalized_weights = {
        name: float(weight)
        for name, weight in weights.items()
    }
    if (
        any(weight < 0.0 for weight in normalized_weights.values())
        or not math.isclose(
            sum(normalized_weights.values()),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    ):
        raise ValueError(
            "ensemble weights must be non-negative and sum to one"
        )
    names = list(predictions)
    base_name = names[0]
    base = predictions[base_name].copy()
    for name, frame in predictions.items():
        missing = sorted(
            {
                *JOIN_KEYS,
                "predicted_win_probability",
            }.difference(frame.columns)
        )
        if missing:
            raise ValueError(
                f"{name} predictions are missing columns: {missing}"
            )
        if frame.duplicated(list(JOIN_KEYS)).any():
            raise ValueError(
                f"{name} predictions contain duplicate keys"
            )
    base[f"_probability_{base_name}"] = pd.to_numeric(
        base["predicted_win_probability"],
        errors="coerce",
    )
    for name in names[1:]:
        component = predictions[name][
            [*JOIN_KEYS, "predicted_win_probability"]
        ].rename(
            columns={
                "predicted_win_probability": (
                    f"_probability_{name}"
                )
            }
        )
        merged = base.merge(
            component,
            on=list(JOIN_KEYS),
            how="inner",
            validate="one_to_one",
        )
        if (
            len(merged) != len(base)
            or len(merged) != len(predictions[name])
        ):
            raise ValueError(
                "prediction universes do not match: "
                f"{base_name}={len(base)}, "
                f"{name}={len(predictions[name])}, "
                f"common={len(merged)}"
            )
        base = merged

    probability = np.zeros(len(base), dtype=float)
    for name, weight in normalized_weights.items():
        probability += (
            weight
            * pd.to_numeric(
                base[f"_probability_{name}"],
                errors="coerce",
            ).to_numpy(dtype=float)
        )
    result = base.copy()
    result["model_name"] = model_name
    result["predicted_win_probability"] = np.clip(
        probability,
        1e-6,
        1.0 - 1e-6,
    )
    result["predicted_over_probability"] = np.where(
        result["direction"].eq("over"),
        result["predicted_win_probability"],
        1.0 - result["predicted_win_probability"],
    )
    result["expected_roi_units"] = (
        result["predicted_win_probability"]
        * pd.to_numeric(result["offered_odds"], errors="coerce")
        - 1.0
    )
    return result.drop(
        columns=[
            f"_probability_{name}"
            for name in normalized_weights
        ]
    )


def gate_reference_by_multi_model_agreement(
    reference_selections: pd.DataFrame,
    challengers: Mapping[str, pd.DataFrame],
    *,
    minimum_challenger_ev: float,
    model_name: str,
) -> pd.DataFrame:
    if not challengers:
        raise ValueError("at least one challenger is required")
    result = reference_selections.copy()
    added_columns: list[str] = []
    for index, (name, frame) in enumerate(challengers.items()):
        required = {
            "sample_key",
            "direction",
            "expected_roi_units",
        }
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(
                f"{name} challenger is missing columns: {missing}"
            )
        direction_column = f"_challenger_{index}_direction"
        ev_column = f"_challenger_{index}_ev"
        preference = (
            frame.sort_values(
                ["sample_key", "expected_roi_units"],
                ascending=[True, False],
                kind="stable",
            )
            .drop_duplicates("sample_key", keep="first")
            [["sample_key", "direction", "expected_roi_units"]]
            .rename(
                columns={
                    "direction": direction_column,
                    "expected_roi_units": ev_column,
                }
            )
        )
        result = result.merge(
            preference,
            on="sample_key",
            how="left",
            validate="many_to_one",
        )
        result = result[
            result["direction"].eq(result[direction_column])
            & result[ev_column].gt(minimum_challenger_ev)
        ].copy()
        added_columns.extend([direction_column, ev_column])
    result["model_name"] = model_name
    return result.drop(columns=added_columns).reset_index(drop=True)
