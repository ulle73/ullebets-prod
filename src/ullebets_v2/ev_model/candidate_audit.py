from __future__ import annotations

import math
from typing import Iterable

import pandas as pd

from ullebets_v2.ev_model.features import find_forbidden_feature_columns


def _selected_value(
    row: pd.Series,
    suffix: str,
    fallback: str | None = None,
) -> object:
    direction_column = f"{row['direction']}_{suffix}"
    value = row.get(direction_column)
    if (value is None or pd.isna(value)) and fallback is not None:
        return row.get(fallback)
    return value


def _expected_settlement(row: pd.Series) -> str:
    actual = float(row["actual_value"])
    line = float(row["line_value"])
    if math.isclose(actual, line, rel_tol=0.0, abs_tol=1e-9):
        return "push"
    won = actual > line if row["direction"] == "over" else actual < line
    return "win" if won else "loss"


def audit_candidate(
    selections: pd.DataFrame,
    source_rows: pd.DataFrame,
    *,
    feature_columns: Iterable[str],
) -> dict[str, object]:
    source = source_rows.drop_duplicates("sample_key", keep="last")
    source = source[
        ["sample_key"]
        + [
            column
            for column in source.columns
            if column != "sample_key" and column not in selections.columns
        ]
    ]
    frame = selections.merge(
        source,
        on="sample_key",
        how="left",
        validate="many_to_one",
    )
    frame["_snapshot_time"] = frame.apply(
        _selected_value,
        axis=1,
        suffix="snapshot_time",
        fallback="odds_snapshot_time",
    )
    frame["_snapshot_source"] = frame.apply(
        _selected_value,
        axis=1,
        suffix="snapshot_time_source",
        fallback="odds_snapshot_time_source",
    )
    frame["_match_start_time"] = frame.apply(
        _selected_value,
        axis=1,
        suffix="match_start_time",
        fallback="match_start_time",
    )
    frame["_match_start_source"] = frame.apply(
        _selected_value,
        axis=1,
        suffix="match_start_time_source",
        fallback="match_start_time_source",
    )
    snapshot_time = pd.to_datetime(
        frame["_snapshot_time"],
        errors="coerce",
        utc=True,
    )
    match_start = pd.to_datetime(
        frame["_match_start_time"],
        errors="coerce",
        utc=True,
    )
    valid_timing = snapshot_time.notna() & match_start.notna()
    at_or_after = valid_timing & snapshot_time.ge(match_start)

    expected_settlement = frame.apply(_expected_settlement, axis=1)
    settlement_mismatch = expected_settlement.ne(
        frame["settlement_result"].astype(str)
    )
    training_leakage = pd.Series(False, index=frame.index)
    if "train_end" in frame.columns:
        training_leakage = pd.to_datetime(
            frame["train_end"],
            errors="coerce",
        ).ge(pd.to_datetime(frame["match_date"], errors="coerce"))

    clv_values: list[float] = []
    for _, row in frame.iterrows():
        value = _selected_value(row, "clv_pct")
        if value is not None and not pd.isna(value):
            clv_values.append(float(value))

    return {
        "rows": int(len(frame)),
        "unique_matches": int(frame["exposure_match_id"].nunique())
        if "exposure_match_id" in frame.columns
        else None,
        "timing": {
            "before_match_start": int(
                (valid_timing & snapshot_time.lt(match_start)).sum()
            ),
            "at_or_after_match_start": int(at_or_after.sum()),
            "missing_snapshot_time": int(snapshot_time.isna().sum()),
            "missing_match_start_time": int(match_start.isna().sum()),
            "snapshot_time_sources": {
                str(key): int(value)
                for key, value in frame["_snapshot_source"]
                .fillna("missing")
                .value_counts()
                .items()
            },
            "match_start_time_sources": {
                str(key): int(value)
                for key, value in frame["_match_start_source"]
                .fillna("missing")
                .value_counts()
                .items()
            },
        },
        "duplicates": {
            "duplicate_market_exposures": int(
                frame.duplicated("sample_key").sum()
            ),
            "duplicate_side_exposures": int(
                frame.duplicated("side_key").sum()
            )
            if "side_key" in frame.columns
            else None,
        },
        "settlement": {
            "mismatches": int(settlement_mismatch.sum()),
            "wins": int(frame["settlement_result"].eq("win").sum()),
            "losses": int(frame["settlement_result"].eq("loss").sum()),
            "pushes": int(frame["settlement_result"].eq("push").sum()),
        },
        "features": {
            "forbidden_columns": find_forbidden_feature_columns(
                feature_columns
            ),
            "training_rows_at_or_after_match": int(training_leakage.sum()),
        },
        "clv": {
            "rows_with_clv": int(len(clv_values)),
            "coverage_pct": (
                len(clv_values) / len(frame) * 100.0 if len(frame) else 0.0
            ),
            "mean_clv_pct": (
                sum(clv_values) / len(clv_values)
                if clv_values
                else None
            ),
            "beat_close_pct": (
                sum(value > 0.0 for value in clv_values)
                / len(clv_values)
                * 100.0
                if clv_values
                else None
            ),
        },
    }
