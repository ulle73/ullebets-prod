from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


CATEGORICAL_FEATURES = (
    "league_name_normalized",
    "period",
    "scope",
    "snapshot_horizon_bucket",
    "stat_key",
)

MARKET_FEATURES = {
    "available_side_balance_gap",
    "baseline_lambda",
    "has_both_sides",
    "latest_snapshot_minutes_before_kickoff",
    "line_value",
    "market_balance_gap",
    "market_no_vig_prob_over",
    "market_no_vig_prob_under",
    "market_overround",
    "over_odds",
    "prematch_snapshot_count",
    "snapshot_horizon_log1p_hours",
    "under_odds",
}

FORBIDDEN_EXACT = {
    "actual_value",
    "over_result",
    "under_result",
    "settlement_result",
    "realized_roi_units",
}

FORBIDDEN_TOKENS = (
    "__team_value",
    "__opponent_value",
    "_clv",
    "closing_",
)


def find_forbidden_feature_columns(columns: Iterable[str]) -> list[str]:
    return sorted(
        column
        for column in columns
        if column in FORBIDDEN_EXACT or any(token in column for token in FORBIDDEN_TOKENS)
    )


def _is_lagged_team_feature(column: str) -> bool:
    return (
        ("__team_for_" in column or "__team_against_" in column)
        and "_avg_" in column
    )


def build_leakage_safe_feature_columns(
    frame: pd.DataFrame,
) -> tuple[list[str], list[str]]:
    numeric = sorted(
        column
        for column in frame.columns
        if (
            column in MARKET_FEATURES
            or column.startswith("lambda_")
            or _is_lagged_team_feature(column)
        )
        and pd.api.types.is_numeric_dtype(frame[column])
    )
    categorical = [
        column
        for column in CATEGORICAL_FEATURES
        if column in frame.columns
    ]
    return numeric, categorical
