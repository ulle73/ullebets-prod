from __future__ import annotations

import pandas as pd


def add_categorical_interaction_features(
    frame: pd.DataFrame,
    *,
    category_column: str,
    source_columns: tuple[str, ...],
    deviation_values: tuple[str, ...],
) -> pd.DataFrame:
    if category_column not in frame.columns:
        raise ValueError(
            f"missing category column: {category_column}"
        )
    if not source_columns:
        raise ValueError("source_columns cannot be empty")
    if not deviation_values:
        raise ValueError("deviation_values cannot be empty")
    result = frame.copy()
    category = result[category_column].astype(str)
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
        for deviation_value in deviation_values:
            result[
                "category_interaction__"
                f"{category_column}__{deviation_value}__"
                f"{source_column}"
            ] = result[source_column].where(
                category.eq(deviation_value),
                0.0,
            )
    return result
