from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.engineering import TEAM_STATS_KEYS
from ullebets_v2.ev_model.market import fair_over_probability


@dataclass(frozen=True)
class HistoryGroup:
    kickoff: np.ndarray
    available_at: np.ndarray
    match_id: np.ndarray
    team_value: np.ndarray
    opponent_value: np.ndarray
    total_value: np.ndarray


def _number(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return math.nan
    return numeric if math.isfinite(numeric) else math.nan


def _history_groups(
    team_stats_long: pd.DataFrame,
    *,
    availability_buffer_hours: float = 0.0,
) -> tuple[
    dict[tuple[str, str, str], HistoryGroup],
    dict[tuple[str, str, str, str], HistoryGroup],
]:
    source = team_stats_long.copy()
    source = source[
        source["stat_item_key"].isin(set(TEAM_STATS_KEYS.values()))
    ].copy()
    source["kickoff_ts"] = pd.to_numeric(
        source["kickoff_ts"],
        errors="coerce",
    )
    source = source[source["kickoff_ts"].notna()].copy()
    source = source.sort_values(["kickoff_ts", "match_id"])
    source = source.drop_duplicates(
        subset=[
            "match_id",
            "team_name",
            "team_role",
            "stat_item_key",
            "period",
        ],
        keep="last",
    )
    source["available_at"] = (
        source["kickoff_ts"]
        + float(availability_buffer_hours) * 3600.0
    )

    def build(
        group_columns: list[str],
    ) -> dict[tuple[str, ...], HistoryGroup]:
        groups: dict[tuple[str, ...], HistoryGroup] = {}
        for key, rows in source.groupby(group_columns, dropna=False):
            normalized_key = key if isinstance(key, tuple) else (key,)
            groups[tuple(str(part) for part in normalized_key)] = HistoryGroup(
                kickoff=rows["kickoff_ts"].to_numpy(dtype=float),
                available_at=rows["available_at"].to_numpy(dtype=float),
                match_id=rows["match_id"].astype(str).to_numpy(),
                team_value=pd.to_numeric(
                    rows["team_value"],
                    errors="coerce",
                ).to_numpy(dtype=float),
                opponent_value=pd.to_numeric(
                    rows["opponent_value"],
                    errors="coerce",
                ).to_numpy(dtype=float),
                total_value=pd.to_numeric(
                    rows["total_value"],
                    errors="coerce",
                ).to_numpy(dtype=float),
            )
        return groups

    all_groups = build(["team_name", "stat_item_key", "period"])
    role_groups = build(
        ["team_name", "team_role", "stat_item_key", "period"]
    )
    return all_groups, role_groups


def _recent_observations(
    group: HistoryGroup | None,
    *,
    cutoff: float,
    value_field: str,
    line: float,
    window: int,
) -> list[tuple[str, bool, bool]]:
    if group is None:
        return []
    end = int(
        np.searchsorted(group.available_at, cutoff, side="left")
    )
    start = max(0, end - window)
    values = getattr(group, value_field)[start:end]
    match_ids = group.match_id[start:end]
    observations: list[tuple[str, bool, bool]] = []
    for match_id, value in zip(match_ids, values, strict=True):
        if not np.isfinite(value):
            continue
        observations.append(
            (
                str(match_id),
                bool(float(value) > line),
                bool(math.isclose(float(value), line, abs_tol=1e-9)),
            )
        )
    return observations


def _rate(observations: list[tuple[str, bool, bool]]) -> float:
    if not observations:
        return math.nan
    return sum(float(hit) for _, hit, _ in observations) / len(observations)


def _market_probability(row: pd.Series) -> float:
    over_odds = _number(row.get("over_odds"))
    under_value = _number(row.get("under_odds"))
    under_odds = under_value if math.isfinite(under_value) else None
    if not math.isfinite(over_odds) or over_odds <= 1.0:
        return 0.5
    return fair_over_probability(
        over_odds=over_odds,
        under_odds=under_odds,
    )


def _build_line_history_features(
    modeling_frame: pd.DataFrame,
    team_stats_long: pd.DataFrame,
    *,
    cutoff_column: str,
    availability_buffer_hours: float,
    windows: tuple[int, ...] = (5, 10, 20),
    prior_strength: float = 8.0,
) -> tuple[pd.DataFrame, dict[str, object]]:
    all_groups, role_groups = _history_groups(
        team_stats_long,
        availability_buffer_hours=availability_buffer_hours,
    )
    feature_rows: list[dict[str, float]] = []
    excluded_observations: set[tuple[str, str, str]] = set()
    for _, row in modeling_frame.iterrows():
        stat_key = TEAM_STATS_KEYS[str(row["stat_key"])]
        period = str(row["period"])
        scope = str(row["scope"])
        home_team = str(row["home_team_name"])
        away_team = str(row["away_team_name"])
        target_kickoff = _number(row["kickoff_ts"])
        if cutoff_column == "kickoff_ts":
            cutoff = target_kickoff
        else:
            parsed_cutoff = pd.to_datetime(
                row.get(cutoff_column),
                errors="coerce",
                utc=True,
            )
            if pd.isna(parsed_cutoff):
                raise ValueError(
                    f"line history requires valid {cutoff_column}"
                )
            cutoff = parsed_cutoff.timestamp()
        line = _number(row["line_value"])
        market_probability = _market_probability(row)
        features: dict[str, float] = {}

        for mode in ("all", "role"):
            groups = all_groups if mode == "all" else role_groups

            def group(team: str, role: str) -> HistoryGroup | None:
                key = (
                    (team, stat_key, period)
                    if mode == "all"
                    else (team, role, stat_key, period)
                )
                return groups.get(key)

            if scope == "home":
                attack_group = group(home_team, "home")
                defense_group = group(away_team, "away")
                attack_value = "team_value"
                defense_value = "opponent_value"
            elif scope == "away":
                attack_group = group(away_team, "away")
                defense_group = group(home_team, "home")
                attack_value = "team_value"
                defense_value = "opponent_value"
            else:
                attack_group = group(home_team, "home")
                defense_group = group(away_team, "away")
                attack_value = "total_value"
                defense_value = "total_value"

            for role, history in (
                ("attack", attack_group),
                ("defense", defense_group),
            ):
                if history is None:
                    continue
                unavailable = (
                    (history.kickoff < target_kickoff)
                    & (history.available_at >= cutoff)
                )
                for match_id in history.match_id[unavailable]:
                    excluded_observations.add(
                        (
                            str(row.get("sample_key") or ""),
                            f"{mode}:{role}",
                            str(match_id),
                        )
                    )

            for window in windows:
                attack = _recent_observations(
                    attack_group,
                    cutoff=cutoff,
                    value_field=attack_value,
                    line=line,
                    window=window,
                )
                defense = _recent_observations(
                    defense_group,
                    cutoff=cutoff,
                    value_field=defense_value,
                    line=line,
                    window=window,
                )
                combined = {
                    match_id: (hit, push)
                    for match_id, hit, push in attack + defense
                }
                combined_n = len(combined)
                combined_hits = sum(
                    float(hit) for hit, _ in combined.values()
                )
                combined_pushes = sum(
                    float(push) for _, push in combined.values()
                )
                posterior = (
                    combined_hits + prior_strength * market_probability
                ) / (combined_n + prior_strength)
                prefix = f"line_history_{mode}"
                features[f"{prefix}_attack_rate_{window}"] = _rate(attack)
                features[f"{prefix}_attack_n_{window}"] = float(len(attack))
                features[f"{prefix}_defense_rate_{window}"] = _rate(defense)
                features[f"{prefix}_defense_n_{window}"] = float(len(defense))
                features[f"{prefix}_combined_rate_{window}"] = (
                    combined_hits / combined_n
                    if combined_n
                    else math.nan
                )
                features[f"{prefix}_combined_push_rate_{window}"] = (
                    combined_pushes / combined_n
                    if combined_n
                    else math.nan
                )
                features[f"{prefix}_combined_n_{window}"] = float(combined_n)
                features[f"{prefix}_posterior_over_{window}"] = posterior
                features[f"{prefix}_posterior_edge_{window}"] = (
                    posterior - market_probability
                )
        feature_rows.append(features)
    return (
        pd.DataFrame(feature_rows, index=modeling_frame.index),
        {
            "rows": int(len(modeling_frame)),
            "availability_buffer_hours": float(
                availability_buffer_hours
            ),
            "history_observations_excluded_by_snapshot": len(
                excluded_observations
            ),
            "history_observations_at_or_after_snapshot_used": 0,
        },
    )


def build_line_history_features(
    modeling_frame: pd.DataFrame,
    team_stats_long: pd.DataFrame,
    *,
    windows: tuple[int, ...] = (5, 10, 20),
    prior_strength: float = 8.0,
) -> pd.DataFrame:
    features, _ = _build_line_history_features(
        modeling_frame,
        team_stats_long,
        cutoff_column="kickoff_ts",
        availability_buffer_hours=0.0,
        windows=windows,
        prior_strength=prior_strength,
    )
    return features


def build_asof_line_history_features(
    modeling_frame: pd.DataFrame,
    team_stats_long: pd.DataFrame,
    *,
    windows: tuple[int, ...] = (5, 10, 20),
    prior_strength: float = 8.0,
    availability_buffer_hours: float = 3.0,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if "odds_snapshot_time" not in modeling_frame.columns:
        raise ValueError(
            "as-of line history requires odds_snapshot_time"
        )
    return _build_line_history_features(
        modeling_frame,
        team_stats_long,
        cutoff_column="odds_snapshot_time",
        availability_buffer_hours=availability_buffer_hours,
        windows=windows,
        prior_strength=prior_strength,
    )
