from __future__ import annotations

import pandas as pd


WALK_FORWARD_CATEGORICAL_COLUMNS = ["league_name_normalized", "period", "scope", "stat_key"]
_WALK_FORWARD_NUMERIC_EXCLUDE = {
    "actual_value",
    "home_opta_rank",
    "home_opta_rating",
    "away_opta_rank",
    "away_opta_rating",
    "opta_rating_diff",
    "opta_rank_diff",
}
_WALK_FORWARD_NUMERIC_PREFIXES_EXCLUDE = (
    "home__match_id",
    "away__match_id",
    "home__match_date",
    "away__match_date",
)
_WALK_FORWARD_NON_FEATURE_COLUMNS = {
    "exposure_match_id",
    "match_id",
    "resolved_teamstats_match_id",
    "match_date",
    "league_name",
    "home_team_name",
    "away_team_name",
    "match_mapping_method",
    "over_result",
    "under_result",
    "over_clv_pct",
    "under_clv_pct",
    "has_both_sides",
    "segment_shape",
    "market_side_policy",
    "is_model_eligible_segment",
    "has_clv",
    "line_side_key",
    "saved_at",
    "source_kind",
    "home_support_team_name",
    "away_support_team_name",
    "home_support_team_slug",
    "away_support_team_slug",
    "support_league_c",
    "home_team_c",
    "away_team_c",
    "odds_timing_status",
    "is_strictly_prematch_odds",
    "odds_snapshot_time_source",
    "odds_snapshot_time",
    "match_start_time_source",
    "match_start_time",
    "over_odds_timing_status",
    "under_odds_timing_status",
    "over_snapshot_time",
    "under_snapshot_time",
    "over_snapshot_time_source",
    "under_snapshot_time_source",
    "over_snapshot_is_required",
    "under_snapshot_is_required",
    "timing_leakage_risk",
}


def select_walk_forward_candidate_rows(
    features: pd.DataFrame,
    *,
    enforce_strict_prematch: bool,
) -> pd.DataFrame:
    frame = features[
        (features["is_model_eligible_segment"] == True)
        & (features["is_canonical_line"] == True)
    ].copy()
    if enforce_strict_prematch:
        frame = frame[frame["is_strictly_prematch_odds"] == True].copy()
    return frame


def build_walk_forward_feature_columns(features: pd.DataFrame) -> tuple[list[str], list[str]]:
    feature_columns: list[str] = []
    for column in features.columns:
        if column in WALK_FORWARD_CATEGORICAL_COLUMNS:
            continue
        if column in _WALK_FORWARD_NON_FEATURE_COLUMNS:
            continue
        if column.startswith(_WALK_FORWARD_NUMERIC_PREFIXES_EXCLUDE):
            continue
        if column in _WALK_FORWARD_NUMERIC_EXCLUDE:
            continue
        if (
            column
            in {
                "over_odds",
                "under_odds",
                "market_no_vig_prob_over",
                "market_no_vig_prob_under",
                "market_overround",
                "baseline_lambda",
                "line_value",
            }
            or "__team_" in column
            or column.startswith("lambda_")
        ):
            feature_columns.append(column)
    return sorted(set(feature_columns)), list(WALK_FORWARD_CATEGORICAL_COLUMNS)
