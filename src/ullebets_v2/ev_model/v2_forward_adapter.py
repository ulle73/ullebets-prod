from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.dataset import PRIMARY_TARGETS
from ullebets_v2.ev_model.engineering import (
    TEAM_STATS_KEYS,
    build_compact_model_features,
)
from ullebets_v2.ev_model.market_classifier import (
    build_market_prediction_frame,
)


WINDOWS = (3, 5, 10, 20)


@dataclass(frozen=True)
class CanonicalHistory:
    start_ns: np.ndarray
    available_ns: np.ndarray
    team_value: np.ndarray
    opponent_value: np.ndarray


def select_canonical_prematch_markets(
    snapshots: pd.DataFrame,
) -> pd.DataFrame:
    frame = snapshots.copy()
    frame["snapshot_time"] = pd.to_datetime(
        frame["snapshot_time"],
        errors="coerce",
        utc=True,
    )
    frame["match_start_time"] = pd.to_datetime(
        frame["match_start_time"],
        errors="coerce",
        utc=True,
    )
    frame["over_odds"] = pd.to_numeric(
        frame["over_odds"],
        errors="coerce",
    )
    if "under_odds" not in frame.columns:
        frame["under_odds"] = np.nan
    frame["under_odds"] = pd.to_numeric(
        frame["under_odds"],
        errors="coerce",
    )
    frame["line"] = pd.to_numeric(frame["line"], errors="coerce")
    frame = frame[
        frame["stat_key"].isin(PRIMARY_TARGETS)
        & frame["snapshot_time"].notna()
        & frame["match_start_time"].notna()
        & frame["snapshot_time"].lt(frame["match_start_time"])
        & ~frame.get(
            "invalid_for_model",
            pd.Series(False, index=frame.index),
        ).fillna(False)
        & frame["line"].notna()
        & frame["over_odds"].gt(1.0)
    ].copy()
    frame = frame[
        frame["stat_key"].ne("cornerKicks")
        | frame["under_odds"].gt(1.0)
    ].copy()
    if frame.empty:
        return frame

    latest_match_snapshot = frame.groupby("match_key")[
        "snapshot_time"
    ].transform("max")
    frame = frame[frame["snapshot_time"].eq(latest_match_snapshot)].copy()
    frame = frame.sort_values(
        ["offer_key", "snapshot_time"],
        ascending=[True, False],
    ).drop_duplicates("offer_key", keep="first")

    both_sides = frame["under_odds"].gt(1.0)
    implied_over = 1.0 / frame["over_odds"]
    implied_under = 1.0 / frame["under_odds"]
    frame["market_overround"] = np.where(
        both_sides,
        implied_over + implied_under - 1.0,
        np.nan,
    )
    fair_over = implied_over / (implied_over + implied_under)
    frame["canonical_balance_gap"] = np.where(
        both_sides,
        (fair_over - 0.5).abs(),
        (implied_over - 0.5).abs(),
    )
    frame["_overround_sort"] = frame["market_overround"].fillna(
        float("inf")
    )
    group_columns = ["match_key", "stat_key", "period", "scope"]
    frame = frame.sort_values(
        [
            *group_columns,
            "canonical_balance_gap",
            "_overround_sort",
            "line",
        ]
    )
    frame = frame.drop_duplicates(group_columns, keep="first")
    return frame.drop(columns=["_overround_sort"]).reset_index(drop=True)


def _build_history_groups(
    fixtures: pd.DataFrame,
    match_stats: pd.DataFrame,
    *,
    availability_buffer_hours: float,
) -> tuple[
    dict[tuple[str, str, str], CanonicalHistory],
    dict[tuple[str, str, str, str], CanonicalHistory],
]:
    fixture_columns = [
        "match_key",
        "start_time",
        "home_team_key",
        "away_team_key",
    ]
    fixture_frame = fixtures[fixture_columns].drop_duplicates("match_key")
    fixture_frame["start_time"] = pd.to_datetime(
        fixture_frame["start_time"],
        errors="coerce",
        utc=True,
    )
    source_stats = set(TEAM_STATS_KEYS.values())
    stats = match_stats[
        match_stats["stat_key"].isin(source_stats)
        & match_stats["scope"].isin({"home", "away", "total"})
    ].copy()
    stats["actual_value"] = pd.to_numeric(
        stats["actual_value"],
        errors="coerce",
    )
    pivot = stats.pivot_table(
        index=["match_key", "stat_key", "period"],
        columns="scope",
        values="actual_value",
        aggfunc="last",
    ).reset_index()
    history = pivot.merge(
        fixture_frame,
        on="match_key",
        how="inner",
        validate="many_to_one",
    )
    history = history[
        history["start_time"].notna()
        & history["home"].notna()
        & history["away"].notna()
    ].copy()
    history["available_at"] = history["start_time"] + pd.to_timedelta(
        availability_buffer_hours,
        unit="h",
    )

    records: list[dict[str, object]] = []
    for row in history.itertuples(index=False):
        for role in ("home", "away"):
            opponent_role = "away" if role == "home" else "home"
            records.append(
                {
                    "start_time": row.start_time,
                    "available_at": row.available_at,
                    "team_key": str(getattr(row, f"{role}_team_key")),
                    "team_role": role,
                    "stat_key": str(row.stat_key),
                    "period": str(row.period),
                    "team_value": float(getattr(row, role)),
                    "opponent_value": float(getattr(row, opponent_role)),
                }
            )
    record_frame = pd.DataFrame(records)
    if record_frame.empty:
        return {}, {}
    record_frame = record_frame.sort_values("available_at")

    def groups(
        columns: list[str],
    ) -> dict[tuple[str, ...], CanonicalHistory]:
        output: dict[tuple[str, ...], CanonicalHistory] = {}
        for key, rows in record_frame.groupby(columns, dropna=False):
            normalized = key if isinstance(key, tuple) else (key,)
            output[tuple(str(part) for part in normalized)] = (
                CanonicalHistory(
                    start_ns=rows["start_time"]
                    .astype("int64")
                    .to_numpy(dtype=np.int64),
                    available_ns=rows["available_at"]
                    .astype("int64")
                    .to_numpy(dtype=np.int64),
                    team_value=rows["team_value"].to_numpy(dtype=float),
                    opponent_value=rows["opponent_value"].to_numpy(
                        dtype=float
                    ),
                )
            )
        return output

    return (
        groups(["team_key", "stat_key", "period"]),
        groups(["team_key", "team_role", "stat_key", "period"]),
    )


def _recent_mean(
    history: CanonicalHistory | None,
    *,
    target_snapshot_ns: int,
    value_name: str,
    window: int,
) -> float:
    if history is None:
        return math.nan
    end = int(
        np.searchsorted(
            history.available_ns,
            target_snapshot_ns,
            side="left",
        )
    )
    values = getattr(history, value_name)[max(0, end - window) : end]
    values = values[np.isfinite(values)]
    return float(values.mean()) if len(values) else math.nan


def _expected_from_raw_history(
    row: dict[str, object],
    *,
    stat_key: str,
    scope: str,
    mode: str,
    window: int,
) -> float:
    home_for = float(
        row.get(
            f"home__{stat_key}__team_for_{mode}_avg_{window}",
            math.nan,
        )
    )
    away_for = float(
        row.get(
            f"away__{stat_key}__team_for_{mode}_avg_{window}",
            math.nan,
        )
    )
    home_against = float(
        row.get(
            f"home__{stat_key}__team_against_{mode}_avg_{window}",
            math.nan,
        )
    )
    away_against = float(
        row.get(
            f"away__{stat_key}__team_against_{mode}_avg_{window}",
            math.nan,
        )
    )
    home_expected = (home_for + away_against) / 2.0
    away_expected = (away_for + home_against) / 2.0
    if scope == "home":
        return home_expected
    if scope == "away":
        return away_expected
    return home_expected + away_expected


def build_v2_forward_model_frame(
    *,
    snapshots: pd.DataFrame,
    fixtures: pd.DataFrame,
    match_stats: pd.DataFrame,
    availability_buffer_hours: float = 3.0,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if snapshots.empty:
        return pd.DataFrame(), {
            "input_snapshots": 0,
            "canonical_markets": 0,
            "availability_buffer_hours": availability_buffer_hours,
            "history_observations_excluded_by_snapshot": 0,
            "history_observations_at_or_after_snapshot_used": 0,
            "rows_with_baseline": 0,
        }
    markets = select_canonical_prematch_markets(snapshots)
    if markets.empty:
        return pd.DataFrame(), {
            "input_snapshots": len(snapshots),
            "canonical_markets": 0,
            "availability_buffer_hours": availability_buffer_hours,
            "history_observations_excluded_by_snapshot": 0,
            "history_observations_at_or_after_snapshot_used": 0,
            "rows_with_baseline": 0,
        }
    fixture_columns = [
        "match_key",
        "start_time",
        "home_team_key",
        "away_team_key",
        "home_team_name",
        "away_team_name",
        "league_name",
    ]
    fixture_frame = fixtures[fixture_columns].drop_duplicates("match_key")
    markets = markets.merge(
        fixture_frame,
        on="match_key",
        how="inner",
        suffixes=("", "_fixture"),
        validate="many_to_one",
    )
    all_groups, role_groups = _build_history_groups(
        fixtures,
        match_stats,
        availability_buffer_hours=availability_buffer_hours,
    )
    source_rows: list[dict[str, object]] = []
    excluded_observations = 0
    for market in markets.itertuples(index=False):
        start_time = pd.Timestamp(market.match_start_time)
        snapshot_time = pd.Timestamp(market.snapshot_time)
        target_start_ns = int(start_time.value)
        target_snapshot_ns = int(snapshot_time.value)
        source_stat = TEAM_STATS_KEYS[str(market.stat_key)]
        row: dict[str, object] = {
            "sample_key": (
                f"{market.match_key}|{market.stat_key}|"
                f"{market.period}|{market.scope}"
            ),
            "exposure_match_id": str(market.match_key),
            "match_date": start_time.date().isoformat(),
            "match_key": str(market.match_key),
            "home_team_name": market.home_team_name,
            "away_team_name": market.away_team_name,
            "home_team_key": str(market.home_team_key),
            "away_team_key": str(market.away_team_key),
            "league_name_normalized": market.league_name,
            "period": str(market.period),
            "scope": str(market.scope),
            "stat_key": str(market.stat_key),
            "line_value": float(market.line),
            "over_odds": float(market.over_odds),
            "under_odds": (
                float(market.under_odds)
                if pd.notna(market.under_odds)
                else math.nan
            ),
            "latest_snapshot_minutes_before_kickoff": (
                start_time - snapshot_time
            ).total_seconds()
            / 60.0,
            "kickoff_ts": start_time.timestamp(),
            "odds_snapshot_time": market.snapshot_time,
            "match_start_time": start_time,
            "snapshot_key": market.snapshot_key,
            "offer_key": market.offer_key,
        }
        for team_role in ("home", "away"):
            team_key = str(getattr(market, f"{team_role}_team_key"))
            history = all_groups.get(
                (team_key, source_stat, str(market.period))
            )
            if history is not None:
                excluded_observations += int(
                    (
                        (history.start_ns < target_start_ns)
                        & (history.available_ns >= target_snapshot_ns)
                    ).sum()
                )
        for mode, groups in (("all", all_groups), ("role", role_groups)):
            for team_role in ("home", "away"):
                team_key = str(getattr(market, f"{team_role}_team_key"))
                key = (
                    (team_key, source_stat, str(market.period))
                    if mode == "all"
                    else (
                        team_key,
                        team_role,
                        source_stat,
                        str(market.period),
                    )
                )
                history = groups.get(key)
                for window in WINDOWS:
                    row[
                        f"{team_role}__{source_stat}__team_for_"
                        f"{mode}_avg_{window}"
                    ] = _recent_mean(
                        history,
                        target_snapshot_ns=target_snapshot_ns,
                        value_name="team_value",
                        window=window,
                    )
                    row[
                        f"{team_role}__{source_stat}__team_against_"
                        f"{mode}_avg_{window}"
                    ] = _recent_mean(
                        history,
                        target_snapshot_ns=target_snapshot_ns,
                        value_name="opponent_value",
                        window=window,
                    )

        baselines = [
            _expected_from_raw_history(
                row,
                stat_key=source_stat,
                scope=str(market.scope),
                mode=mode,
                window=window,
            )
            for mode, window in (
                ("role", 10),
                ("role", 5),
                ("all", 10),
                ("all", 5),
                ("role", 20),
                ("all", 20),
            )
        ]
        row["baseline_lambda"] = next(
            (value for value in baselines if math.isfinite(value)),
            math.nan,
        )
        source_rows.append(row)

    source_frame = pd.DataFrame(source_rows)
    compact_features = build_compact_model_features(source_frame)
    prediction_frame = build_market_prediction_frame(
        source_frame,
        compact_features,
    )
    passthrough_columns = [
        "match_key",
        "snapshot_key",
        "offer_key",
        "home_team_key",
        "away_team_key",
        "home_team_name",
        "away_team_name",
    ]
    for column in passthrough_columns:
        prediction_frame[column] = source_frame[column].to_numpy()
    return prediction_frame, {
        "input_snapshots": int(len(snapshots)),
        "canonical_markets": int(len(prediction_frame)),
        "availability_buffer_hours": availability_buffer_hours,
        "history_observations_excluded_by_snapshot": int(
            excluded_observations
        ),
        "history_observations_at_or_after_snapshot_used": 0,
        "rows_with_baseline": int(
            prediction_frame["baseline_lambda"].notna().sum()
        ),
        "rows_with_complete_role_10": int(
            prediction_frame[
                [
                    "history_role_attack_10",
                    "history_role_defense_10",
                ]
            ]
            .notna()
            .all(axis=1)
            .sum()
        ),
    }
