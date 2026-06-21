from __future__ import annotations

import numpy as np
import pandas as pd

from ullebets_v1.registry.stats import PRIMARY_TARGET_STAT_KEYS


TEAMSTATS_STAT_KEY_BY_MARKET_STAT = {
    "cornerKicks": "cornerKicks",
    "totalShots": "totalShotsOnGoal",
    "shotsOnGoal": "shotsOnGoal",
}


def authoritative_settlement_result(
    actual_value: object,
    line_value: object,
    direction: object,
) -> str | None:
    if actual_value is None or line_value is None or pd.isna(actual_value) or pd.isna(line_value):
        return None
    try:
        actual = float(actual_value)
        line = float(line_value)
    except (TypeError, ValueError):
        return None
    side = str(direction or "").lower()
    if side not in {"over", "under"}:
        return None
    if actual > line:
        return "win" if side == "over" else "loss"
    if actual < line:
        return "loss" if side == "over" else "win"
    return "push"


def _build_teamstats_actual_lookup(team_stats_long: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "teamstats_match_id",
        "teamstats_period",
        "teamstats_stat_key",
        "home_team_value",
        "away_team_value",
        "total_team_value",
    ]
    if team_stats_long.empty:
        return pd.DataFrame(columns=columns)

    relevant = team_stats_long[
        team_stats_long["stat_item_key"].isin(set(TEAMSTATS_STAT_KEY_BY_MARKET_STAT.values()))
    ].copy()
    if relevant.empty:
        return pd.DataFrame(columns=columns)

    relevant = relevant.drop_duplicates(
        subset=["match_id", "period", "stat_item_key", "team_role"],
        keep="first",
    )
    home = relevant[relevant["team_role"] == "home"][
        ["match_id", "period", "stat_item_key", "team_value", "total_value"]
    ].rename(
        columns={
            "match_id": "teamstats_match_id",
            "period": "teamstats_period",
            "stat_item_key": "teamstats_stat_key",
            "team_value": "home_team_value",
            "total_value": "total_team_value",
        }
    )
    away = relevant[relevant["team_role"] == "away"][
        ["match_id", "period", "stat_item_key", "team_value"]
    ].rename(
        columns={
            "match_id": "teamstats_match_id",
            "period": "teamstats_period",
            "stat_item_key": "teamstats_stat_key",
            "team_value": "away_team_value",
        }
    )
    return home.merge(
        away,
        how="outer",
        on=["teamstats_match_id", "teamstats_period", "teamstats_stat_key"],
    )


def annotate_market_line_outcomes(
    market_lines: pd.DataFrame,
    team_stats_long: pd.DataFrame,
) -> pd.DataFrame:
    frame = market_lines.copy()
    if "legacy_actual_value" not in frame.columns:
        frame["legacy_actual_value"] = frame["actual_value"]
    if "legacy_settlement_result" not in frame.columns:
        frame["legacy_settlement_result"] = frame["settlement_result"]

    frame["exposure_match_id"] = frame["resolved_teamstats_match_id"].fillna(frame["match_id"]).astype("string")
    frame["teamstats_stat_key"] = frame["stat_key"].map(TEAMSTATS_STAT_KEY_BY_MARKET_STAT)

    lookup = _build_teamstats_actual_lookup(team_stats_long)
    frame = frame.merge(
        lookup,
        how="left",
        left_on=["resolved_teamstats_match_id", "period", "teamstats_stat_key"],
        right_on=["teamstats_match_id", "teamstats_period", "teamstats_stat_key"],
    )
    frame["teamstats_actual_value"] = np.where(
        frame["scope"].eq("home"),
        frame["home_team_value"],
        np.where(
            frame["scope"].eq("away"),
            frame["away_team_value"],
            frame["total_team_value"],
        ),
    )
    frame["teamstats_actual_value"] = pd.to_numeric(frame["teamstats_actual_value"], errors="coerce")
    frame["verified_settlement_result"] = [
        authoritative_settlement_result(actual, line, direction)
        for actual, line, direction in zip(
            frame["teamstats_actual_value"],
            frame["line_value"],
            frame["direction"],
            strict=False,
        )
    ]

    frame["actual_value"] = pd.to_numeric(frame["legacy_actual_value"], errors="coerce")
    frame["settlement_result"] = frame["legacy_settlement_result"]

    primary_modeled = frame["stat_key"].isin(PRIMARY_TARGET_STAT_KEYS)
    has_teamstats_outcome = primary_modeled & frame["verified_settlement_result"].notna()
    frame.loc[has_teamstats_outcome, "actual_value"] = frame.loc[has_teamstats_outcome, "teamstats_actual_value"]
    frame.loc[has_teamstats_outcome, "settlement_result"] = frame.loc[has_teamstats_outcome, "verified_settlement_result"]

    # Exclude modeled rows from backtest when teamstats cannot prove the settlement.
    missing_teamstats_outcome = primary_modeled & ~has_teamstats_outcome
    frame.loc[missing_teamstats_outcome, "actual_value"] = np.nan
    frame.loc[missing_teamstats_outcome, "settlement_result"] = None

    comparable_actual = has_teamstats_outcome & frame["legacy_actual_value"].notna()
    comparable_result = has_teamstats_outcome & frame["legacy_settlement_result"].notna()
    frame["legacy_actual_matches_teamstats"] = pd.Series(pd.NA, index=frame.index, dtype="boolean")
    frame.loc[comparable_actual, "legacy_actual_matches_teamstats"] = (
        frame.loc[comparable_actual, "legacy_actual_value"] == frame.loc[comparable_actual, "teamstats_actual_value"]
    )
    frame["legacy_settlement_matches_verified"] = pd.Series(pd.NA, index=frame.index, dtype="boolean")
    frame.loc[comparable_result, "legacy_settlement_matches_verified"] = (
        frame.loc[comparable_result, "legacy_settlement_result"]
        == frame.loc[comparable_result, "verified_settlement_result"]
    )

    status = pd.Series("not_primary_target", index=frame.index, dtype="string")
    status.loc[missing_teamstats_outcome] = "missing_teamstats_actual"
    status.loc[has_teamstats_outcome] = "verified_legacy_match"
    status.loc[has_teamstats_outcome & frame["legacy_actual_value"].isna()] = "verified_missing_legacy_actual"
    status.loc[
        has_teamstats_outcome
        & frame["legacy_actual_value"].notna()
        & (frame["legacy_actual_value"] != frame["teamstats_actual_value"])
    ] = "verified_legacy_actual_mismatch"
    status.loc[
        has_teamstats_outcome
        & frame["legacy_settlement_result"].isna()
    ] = "verified_missing_legacy_settlement"
    status.loc[
        has_teamstats_outcome
        & frame["legacy_settlement_result"].notna()
        & (frame["legacy_settlement_result"] != frame["verified_settlement_result"])
    ] = "verified_legacy_settlement_mismatch"
    frame["outcome_verification_status"] = status
    frame["has_authoritative_teamstats_outcome"] = has_teamstats_outcome

    return frame.drop(
        columns=[
            "teamstats_match_id",
            "teamstats_period",
            "home_team_value",
            "away_team_value",
            "total_team_value",
        ],
        errors="ignore",
    )
