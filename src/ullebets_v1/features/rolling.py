from __future__ import annotations

import pandas as pd


def last_n_average(rows: list[dict], cutoff_ts: int, n: int, value_key: str) -> float | None:
    eligible = [row[value_key] for row in rows if row.get("kickoff_ts") is not None and row["kickoff_ts"] < cutoff_ts]
    if not eligible:
        return None
    selected = eligible[-n:]
    return sum(selected) / len(selected)


def add_shifted_rolling_mean(
    frame: pd.DataFrame,
    *,
    group_cols: list[str],
    value_col: str,
    windows: tuple[int, ...],
    prefix: str,
) -> pd.DataFrame:
    enriched = frame.copy()
    grouped = enriched.groupby(group_cols, dropna=False)[value_col]
    shifted = grouped.shift(1)
    for window in windows:
        enriched[f"{prefix}_{window}"] = shifted.groupby(
            [enriched[col] for col in group_cols], dropna=False
        ).transform(lambda series: series.rolling(window, min_periods=1).mean())
    return enriched
