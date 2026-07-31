from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss


JOIN_KEYS = (
    "side_key",
    "test_start",
    "test_end",
)


def _merge_predictions(
    reference: pd.DataFrame,
    challenger: pd.DataFrame,
) -> pd.DataFrame:
    for name, frame in (
        ("reference", reference),
        ("challenger", challenger),
    ):
        required = {
            *JOIN_KEYS,
            "direction",
            "predicted_win_probability",
            "is_over_win",
        }
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(
                f"{name} predictions are missing columns: {missing}"
            )
        if frame.duplicated(list(JOIN_KEYS)).any():
            raise ValueError(
                f"{name} predictions contain duplicate keys"
            )
    challenger_values = challenger[
        [
            *JOIN_KEYS,
            "predicted_win_probability",
        ]
    ].rename(
        columns={
            "predicted_win_probability": (
                "challenger_predicted_win_probability"
            )
        }
    )
    merged = reference.merge(
        challenger_values,
        on=list(JOIN_KEYS),
        how="inner",
        validate="one_to_one",
    )
    if len(merged) != len(reference) or len(merged) != len(challenger):
        raise ValueError(
            "reference and challenger universes do not match"
        )
    return merged


def build_prequential_blend_predictions(
    reference: pd.DataFrame,
    challenger: pd.DataFrame,
    *,
    challenger_weights: tuple[float, ...],
    cold_start_weight: float,
    model_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    weights = tuple(sorted(set(float(value) for value in challenger_weights)))
    if (
        not weights
        or any(value < 0.0 or value > 1.0 for value in weights)
        or cold_start_weight not in weights
    ):
        raise ValueError(
            "weights must be non-empty, unique values between zero "
            "and one and include cold_start_weight"
        )
    merged = _merge_predictions(reference, challenger)
    merged["_test_start_at"] = pd.to_datetime(
        merged["test_start"],
        errors="raise",
    )
    merged["_test_end_at"] = pd.to_datetime(
        merged["test_end"],
        errors="raise",
    )
    prediction_parts: list[pd.DataFrame] = []
    decision_rows: list[dict[str, object]] = []
    test_windows = (
        merged[["test_start", "_test_start_at"]]
        .drop_duplicates()
        .sort_values("_test_start_at")
        .rename(columns={"_test_start_at": "test_start_at"})
    )
    for window in test_windows.itertuples(index=False):
        history = merged[
            merged["_test_end_at"].lt(window.test_start_at)
            & merged["direction"].eq("over")
            & merged["is_over_win"].notna()
        ].copy()
        candidate_metrics: list[dict[str, float]] = []
        if history.empty:
            selected_weight = float(cold_start_weight)
            selection_source = "cold_start"
            latest_history_test_end = None
        else:
            outcome = history["is_over_win"].to_numpy(dtype=float)
            reference_probability = history[
                "predicted_win_probability"
            ].to_numpy(dtype=float)
            challenger_probability = history[
                "challenger_predicted_win_probability"
            ].to_numpy(dtype=float)
            for weight in weights:
                probability = (
                    (1.0 - weight) * reference_probability
                    + weight * challenger_probability
                )
                candidate_metrics.append(
                    {
                        "challenger_weight": float(weight),
                        "prior_brier": float(
                            brier_score_loss(
                                outcome,
                                probability,
                            )
                        ),
                    }
                )
            selected = min(
                candidate_metrics,
                key=lambda row: (
                    row["prior_brier"],
                    row["challenger_weight"],
                ),
            )
            selected_weight = float(
                selected["challenger_weight"]
            )
            selection_source = "prior_outer_brier"
            latest_history_test_end = str(
                history["_test_end_at"].max().date()
            )

        current = merged[
            merged["test_start"].eq(window.test_start)
        ].copy()
        probability = (
            (1.0 - selected_weight)
            * current["predicted_win_probability"]
            + selected_weight
            * current["challenger_predicted_win_probability"]
        )
        current["model_name"] = model_name
        current["predicted_win_probability"] = probability.clip(
            lower=1e-6,
            upper=1.0 - 1e-6,
        )
        current["predicted_over_probability"] = np.where(
            current["direction"].eq("over"),
            current["predicted_win_probability"],
            1.0 - current["predicted_win_probability"],
        )
        current["expected_roi_units"] = (
            current["predicted_win_probability"]
            * current["offered_odds"]
            - 1.0
        )
        current["selected_challenger_weight"] = (
            selected_weight
        )
        prediction_parts.append(
            current.drop(
                columns=["_test_start_at", "_test_end_at"]
            )
        )
        decision_rows.append(
            {
                "test_start": str(window.test_start),
                "selected_challenger_weight": selected_weight,
                "selection_source": selection_source,
                "prior_market_rows": int(len(history)),
                "latest_history_test_end": (
                    latest_history_test_end
                ),
                "candidate_metrics": candidate_metrics,
            }
        )
    return (
        pd.concat(prediction_parts, ignore_index=True),
        pd.DataFrame(decision_rows),
    )
