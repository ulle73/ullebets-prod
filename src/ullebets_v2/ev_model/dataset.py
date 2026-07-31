from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


PRIMARY_TARGETS = frozenset({"cornerKicks", "shotsOnGoal", "totalShots"})
SAMPLE_KEY_COLUMNS = (
    "exposure_match_id",
    "stat_key",
    "period",
    "scope",
)
REQUIRED_COLUMNS = frozenset(
    {
        *SAMPLE_KEY_COLUMNS,
        "actual_value",
        "is_canonical_line",
        "is_model_eligible_segment",
        "is_strictly_prematch_odds",
        "line_value",
        "match_date",
        "over_odds",
    }
)


@dataclass(frozen=True)
class DatasetAudit:
    input_rows: int
    eligible_rows: int
    duplicate_rows_removed: int
    output_rows: int


def _sample_keys(frame: pd.DataFrame) -> pd.Series:
    return frame[list(SAMPLE_KEY_COLUMNS)].astype(str).agg("|".join, axis=1)


def prepare_modeling_frame(
    feature_frame: pd.DataFrame,
) -> tuple[pd.DataFrame, DatasetAudit]:
    missing = sorted(REQUIRED_COLUMNS.difference(feature_frame.columns))
    if missing:
        raise ValueError(f"modeling frame is missing required columns: {', '.join(missing)}")

    frame = feature_frame[
        feature_frame["stat_key"].isin(PRIMARY_TARGETS)
        & feature_frame["is_model_eligible_segment"].eq(True)
        & feature_frame["is_canonical_line"].eq(True)
        & feature_frame["is_strictly_prematch_odds"].eq(True)
        & feature_frame["actual_value"].notna()
        & feature_frame["over_odds"].notna()
    ].copy()
    if "under_odds" in frame.columns:
        frame = frame[
            frame["stat_key"].ne("cornerKicks")
            | frame["under_odds"].notna()
        ].copy()

    frame["sample_key"] = _sample_keys(frame)
    eligible_rows = len(frame)
    sort_columns = ["sample_key"]
    ascending = [True]
    if "latest_snapshot_minutes_before_kickoff" in frame.columns:
        sort_columns.append("latest_snapshot_minutes_before_kickoff")
        ascending.append(True)
    frame = frame.sort_values(sort_columns, ascending=ascending, na_position="last")
    frame = frame.drop_duplicates(subset=["sample_key"], keep="first")
    frame = frame.sort_values(["match_date", "sample_key"]).reset_index(drop=True)

    return frame, DatasetAudit(
        input_rows=len(feature_frame),
        eligible_rows=eligible_rows,
        duplicate_rows_removed=eligible_rows - len(frame),
        output_rows=len(frame),
    )
