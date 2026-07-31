from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.engineering import (
    CONTEXT_STAT_KEYS,
    TEAM_STATS_KEYS,
    build_compact_model_features,
)


WINDOWS = (3, 5, 10, 20)


@dataclass(frozen=True)
class AsOfHistory:
    kickoff: np.ndarray
    available_at: np.ndarray
    team_value: np.ndarray
    opponent_value: np.ndarray


def _history_groups(
    team_stats_long: pd.DataFrame,
    *,
    availability_buffer_hours: float,
    stat_item_keys: set[str] | frozenset[str],
) -> tuple[
    dict[tuple[str, str, str], AsOfHistory],
    dict[tuple[str, str, str, str], AsOfHistory],
]:
    stats = team_stats_long[
        team_stats_long["stat_item_key"].isin(
            stat_item_keys
        )
    ].copy()
    stats["kickoff_ts"] = pd.to_numeric(
        stats["kickoff_ts"],
        errors="coerce",
    )
    stats["team_value"] = pd.to_numeric(
        stats["team_value"],
        errors="coerce",
    )
    stats["opponent_value"] = pd.to_numeric(
        stats["opponent_value"],
        errors="coerce",
    )
    stats = stats[stats["kickoff_ts"].notna()].copy()
    stats = stats.sort_values(["kickoff_ts", "match_id"])
    stats = stats.drop_duplicates(
        [
            "match_id",
            "team_name",
            "team_role",
            "period",
            "stat_item_key",
        ],
        keep="last",
    )
    stats["available_at"] = (
        stats["kickoff_ts"] + availability_buffer_hours * 3600.0
    )

    def build(
        group_columns: list[str],
    ) -> dict[tuple[str, ...], AsOfHistory]:
        output: dict[tuple[str, ...], AsOfHistory] = {}
        for key, rows in stats.groupby(group_columns, dropna=False):
            normalized = key if isinstance(key, tuple) else (key,)
            output[tuple(str(part) for part in normalized)] = AsOfHistory(
                kickoff=rows["kickoff_ts"].to_numpy(dtype=float),
                available_at=rows["available_at"].to_numpy(dtype=float),
                team_value=rows["team_value"].to_numpy(dtype=float),
                opponent_value=rows["opponent_value"].to_numpy(dtype=float),
            )
        return output

    return (
        build(["team_name", "period", "stat_item_key"]),
        build(["team_name", "team_role", "period", "stat_item_key"]),
    )


def _recent_mean(
    history: AsOfHistory | None,
    *,
    snapshot_time: float,
    value_name: str,
    window: int,
) -> float:
    if history is None:
        return math.nan
    eligible = np.flatnonzero(history.available_at < snapshot_time)
    if not len(eligible):
        return math.nan
    selected = eligible[-window:]
    values = getattr(history, value_name)[selected]
    values = values[np.isfinite(values)]
    return float(values.mean()) if len(values) else math.nan


def _expected(
    row: dict[str, float],
    *,
    source_stat: str,
    scope: str,
    mode: str,
    window: int,
) -> float:
    home_for = row[
        f"home__{source_stat}__team_for_{mode}_avg_{window}"
    ]
    away_for = row[
        f"away__{source_stat}__team_for_{mode}_avg_{window}"
    ]
    home_against = row[
        f"home__{source_stat}__team_against_{mode}_avg_{window}"
    ]
    away_against = row[
        f"away__{source_stat}__team_against_{mode}_avg_{window}"
    ]
    home_expected = (home_for + away_against) / 2.0
    away_expected = (away_for + home_against) / 2.0
    if scope == "home":
        return home_expected
    if scope == "away":
        return away_expected
    return home_expected + away_expected


def build_asof_compact_model_features(
    modeling_frame: pd.DataFrame,
    team_stats_long: pd.DataFrame,
    *,
    availability_buffer_hours: float = 3.0,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if "odds_snapshot_time" not in modeling_frame.columns:
        raise ValueError("modeling frame requires odds_snapshot_time")
    all_groups, role_groups = _history_groups(
        team_stats_long,
        availability_buffer_hours=availability_buffer_hours,
        stat_item_keys=set(TEAM_STATS_KEYS.values()),
    )
    history_rows: list[dict[str, float]] = []
    excluded_observations = 0
    rows_without_history = 0

    for source_row in modeling_frame.itertuples(index=False):
        snapshot_time = pd.Timestamp(
            source_row.odds_snapshot_time
        ).timestamp()
        target_kickoff = float(source_row.kickoff_ts)
        source_stat = TEAM_STATS_KEYS[str(source_row.stat_key)]
        period = str(source_row.period)
        scope = str(source_row.scope)
        row: dict[str, float] = {}
        for mode, groups in (("all", all_groups), ("role", role_groups)):
            for team_role in ("home", "away"):
                team_name = str(
                    getattr(source_row, f"{team_role}_team_name")
                )
                key = (
                    (team_name, period, source_stat)
                    if mode == "all"
                    else (team_name, team_role, period, source_stat)
                )
                history = groups.get(key)
                if history is not None:
                    naive = (
                        (history.kickoff < target_kickoff)
                        & (history.available_at >= snapshot_time)
                    )
                    excluded_observations += int(naive.sum())
                for window in WINDOWS:
                    row[
                        f"{team_role}__{source_stat}__team_for_"
                        f"{mode}_avg_{window}"
                    ] = _recent_mean(
                        history,
                        snapshot_time=snapshot_time,
                        value_name="team_value",
                        window=window,
                    )
                    row[
                        f"{team_role}__{source_stat}__team_against_"
                        f"{mode}_avg_{window}"
                    ] = _recent_mean(
                        history,
                        snapshot_time=snapshot_time,
                        value_name="opponent_value",
                        window=window,
                    )

        baselines = [
            _expected(
                row,
                source_stat=source_stat,
                scope=scope,
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
        if not math.isfinite(row["baseline_lambda"]):
            rows_without_history += 1
        history_rows.append(row)

    enriched = modeling_frame.reset_index(drop=True).copy()
    history_frame = pd.DataFrame(history_rows)
    for column in history_frame.columns:
        enriched[column] = history_frame[column]
    features = build_compact_model_features(enriched)
    return features, {
        "rows": int(len(features)),
        "availability_buffer_hours": float(availability_buffer_hours),
        "history_observations_excluded_by_snapshot": int(
            excluded_observations
        ),
        "history_observations_at_or_after_snapshot_used": 0,
        "rows_without_baseline_history": int(rows_without_history),
    }


def build_asof_context_model_features(
    modeling_frame: pd.DataFrame,
    team_stats_long: pd.DataFrame,
    *,
    availability_buffer_hours: float = 3.0,
    windows: tuple[int, ...] = (5, 10),
) -> tuple[pd.DataFrame, dict[str, object]]:
    if "odds_snapshot_time" not in modeling_frame.columns:
        raise ValueError("modeling frame requires odds_snapshot_time")
    all_groups, role_groups = _history_groups(
        team_stats_long,
        availability_buffer_hours=availability_buffer_hours,
        stat_item_keys=set(CONTEXT_STAT_KEYS),
    )
    context_rows: list[dict[str, float]] = []
    excluded_observations = 0
    rows_without_context = 0

    for source_row in modeling_frame.itertuples(index=False):
        snapshot_time = pd.Timestamp(
            source_row.odds_snapshot_time
        ).timestamp()
        target_kickoff = float(source_row.kickoff_ts)
        period = str(source_row.period)
        row: dict[str, float] = {}
        finite_values = 0
        for stat_item_key in CONTEXT_STAT_KEYS:
            for mode, groups in (
                ("all", all_groups),
                ("role", role_groups),
            ):
                for team_role in ("home", "away"):
                    team_name = str(
                        getattr(
                            source_row,
                            f"{team_role}_team_name",
                        )
                    )
                    key = (
                        (team_name, period, stat_item_key)
                        if mode == "all"
                        else (
                            team_name,
                            team_role,
                            period,
                            stat_item_key,
                        )
                    )
                    history = groups.get(key)
                    if history is not None:
                        naive = (
                            (history.kickoff < target_kickoff)
                            & (
                                history.available_at
                                >= snapshot_time
                            )
                        )
                        excluded_observations += int(
                            naive.sum()
                        )
                    for orientation, value_name in (
                        ("for", "team_value"),
                        ("against", "opponent_value"),
                    ):
                        for window in windows:
                            value = _recent_mean(
                                history,
                                snapshot_time=snapshot_time,
                                value_name=value_name,
                                window=window,
                            )
                            row[
                                f"context_{stat_item_key}_{mode}_"
                                f"{team_role}_{orientation}_{window}"
                            ] = value
                            finite_values += int(
                                math.isfinite(value)
                            )
        rows_without_context += int(finite_values == 0)
        context_rows.append(row)

    return pd.DataFrame(
        context_rows,
        index=modeling_frame.index,
    ), {
        "rows": int(len(modeling_frame)),
        "availability_buffer_hours": float(
            availability_buffer_hours
        ),
        "history_observations_excluded_by_snapshot": int(
            excluded_observations
        ),
        "history_observations_at_or_after_snapshot_used": 0,
        "rows_without_any_context_history": int(
            rows_without_context
        ),
        "context_stat_keys": list(CONTEXT_STAT_KEYS),
        "windows": list(windows),
    }
