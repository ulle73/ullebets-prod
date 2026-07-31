from __future__ import annotations

import pandas as pd


def add_stat_interaction_features(
    frame: pd.DataFrame,
    *,
    source_columns: tuple[str, ...],
    deviation_stat_keys: tuple[str, ...] = (
        "shotsOnGoal",
        "totalShots",
    ),
) -> pd.DataFrame:
    if "stat_key" not in frame.columns:
        raise ValueError("frame requires stat_key")
    if not source_columns:
        raise ValueError("source_columns cannot be empty")
    result = frame.copy()
    stat_values = result["stat_key"].astype(str)
    for source_column in source_columns:
        if source_column not in result.columns:
            raise ValueError(
                f"missing source column: {source_column}"
            )
        if not pd.api.types.is_numeric_dtype(
            result[source_column]
        ):
            raise ValueError(
                f"source column must be numeric: {source_column}"
            )
        for stat_key in deviation_stat_keys:
            result[
                f"stat_interaction__{stat_key}__{source_column}"
            ] = result[source_column].where(
                stat_values.eq(stat_key),
                0.0,
            )
    return result
