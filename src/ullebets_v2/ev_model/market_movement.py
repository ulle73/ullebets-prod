from __future__ import annotations

from functools import lru_cache
import math

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.market import infer_poisson_mean


MOVEMENT_FEATURE_COLUMNS = (
    "movement_snapshot_observations",
    "movement_snapshot_span_hours",
    "movement_line_delta_from_open",
    "movement_line_delta_from_previous",
    "movement_fair_probability_delta_from_open",
    "movement_fair_probability_delta_from_previous",
    "movement_anchor_delta_from_open",
    "movement_anchor_delta_from_previous",
    "movement_overround_delta_from_open",
    "movement_line_changed_from_open",
)

MOVEMENT_MODEL_FEATURE_COLUMNS = (
    "movement_snapshot_observations_log1p",
    "movement_snapshot_span_hours_log1p",
    "movement_line_delta_from_open_signed_log1p",
    "movement_line_delta_from_previous_signed_log1p",
    "movement_fair_probability_delta_from_open_signed_log1p",
    "movement_fair_probability_delta_from_previous_signed_log1p",
    "movement_anchor_delta_from_open_signed_log1p",
    "movement_anchor_delta_from_previous_signed_log1p",
    "movement_overround_delta_from_open_signed_log1p",
    "movement_line_changed_from_open",
)

_MARKET_KEYS = (
    "match_id",
    "stat_key",
    "period",
    "scope",
)


@lru_cache(maxsize=65_536)
def _anchor(line: float, fair_probability_over: float) -> float:
    return infer_poisson_mean(
        line=line,
        win_probability=fair_probability_over,
        direction="over",
    )


def _empty_features(index: pd.Index) -> pd.DataFrame:
    result = pd.DataFrame(
        np.nan,
        index=index,
        columns=MOVEMENT_FEATURE_COLUMNS,
    )
    result["movement_snapshot_observations"] = 0.0
    return result


def _validate_model_timing(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    required = {"odds_snapshot_time", "match_start_time"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"movement frame is missing timing: {missing}")
    snapshot = pd.to_datetime(
        frame["odds_snapshot_time"],
        errors="coerce",
        utc=True,
    )
    kickoff = pd.to_datetime(
        frame["match_start_time"],
        errors="coerce",
        utc=True,
    )
    if snapshot.isna().any() or kickoff.isna().any():
        raise ValueError("movement frame contains missing timing")
    if snapshot.ge(kickoff).any():
        raise ValueError(
            "every model odds snapshot must be strictly before kickoff"
        )
    return snapshot, kickoff


def build_snapshot_line_points(
    market_snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    required = {
        *_MARKET_KEYS,
        "snapshot_fetched_at",
        "line_value",
        "direction",
        "odds_decimal",
    }
    missing = sorted(required.difference(market_snapshots.columns))
    if missing:
        raise ValueError(f"market snapshots are missing columns: {missing}")
    snapshots = market_snapshots.copy()
    if "is_primary_modeled_stat" in snapshots.columns:
        snapshots = snapshots[
            snapshots["is_primary_modeled_stat"].fillna(False)
        ].copy()
    snapshots["_snapshot_at"] = pd.to_datetime(
        snapshots["snapshot_fetched_at"],
        errors="coerce",
        utc=True,
    )
    snapshots["line_value"] = pd.to_numeric(
        snapshots["line_value"],
        errors="coerce",
    )
    snapshots["odds_decimal"] = pd.to_numeric(
        snapshots["odds_decimal"],
        errors="coerce",
    )
    snapshots["direction"] = (
        snapshots["direction"].astype(str).str.lower()
    )
    valid = snapshots[
        snapshots["_snapshot_at"].notna()
        & snapshots["line_value"].notna()
        & snapshots["direction"].isin(["over", "under"])
        & snapshots["odds_decimal"].gt(1.0)
    ].copy()
    line_keys = [
        *_MARKET_KEYS,
        "_snapshot_at",
        "line_value",
        "direction",
    ]
    price_counts = (
        valid.groupby(line_keys, dropna=False)["odds_decimal"]
        .nunique()
        .rename("_price_count")
        .reset_index()
    )
    conflicts = price_counts["_price_count"].gt(1)
    valid = valid.merge(
        price_counts,
        on=line_keys,
        how="left",
        validate="many_to_one",
    )
    valid = valid[valid["_price_count"].eq(1)].copy()
    deduplicated = (
        valid.sort_values(line_keys + ["snapshot_fetched_at"])
        .drop_duplicates(line_keys, keep="last")
        .copy()
    )
    points = (
        deduplicated.pivot(
            index=[
                *_MARKET_KEYS,
                "_snapshot_at",
                "line_value",
            ],
            columns="direction",
            values="odds_decimal",
        )
        .reset_index()
        .rename_axis(columns=None)
        .rename(
            columns={
                "over": "over_odds",
                "under": "under_odds",
            }
        )
    )
    if "over_odds" not in points.columns:
        points["over_odds"] = np.nan
    if "under_odds" not in points.columns:
        points["under_odds"] = np.nan
    points = points[points["over_odds"].gt(1.0)].copy()
    is_corner = points["stat_key"].astype(str).eq("cornerKicks")
    points = points[
        ~is_corner | points["under_odds"].gt(1.0)
    ].copy()

    implied_over = 1.0 / points["over_odds"]
    implied_under = 1.0 / points["under_odds"]
    both_sides = points["under_odds"].gt(1.0)
    points["_fair_over"] = implied_over
    points.loc[both_sides, "_fair_over"] = (
        implied_over[both_sides]
        / (
            implied_over[both_sides]
            + implied_under[both_sides]
        )
    )
    points["_overround"] = np.nan
    points.loc[both_sides, "_overround"] = (
        implied_over[both_sides]
        + implied_under[both_sides]
        - 1.0
    )
    points["_balance_gap"] = (
        points["_fair_over"] - 0.5
    ).abs()
    return points, {
        "input_snapshot_rows": int(len(market_snapshots)),
        "valid_snapshot_rows": int(len(valid)),
        "duplicate_line_snapshot_price_conflicts": int(
            conflicts.sum()
        ),
        "snapshot_line_points": int(len(points)),
    }


def _canonical_market_observations(
    market_snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    points, source_audit = build_snapshot_line_points(
        market_snapshots
    )
    observation_keys = [*_MARKET_KEYS, "_snapshot_at"]
    canonical = (
        points.sort_values(
            observation_keys
            + ["_balance_gap", "_overround", "line_value"],
            ascending=True,
            na_position="last",
            kind="stable",
        )
        .drop_duplicates(observation_keys, keep="first")
        .sort_values([*_MARKET_KEYS, "_snapshot_at"])
        .reset_index(drop=True)
    )
    pairs = [
        (
            round(float(line), 6),
            round(float(probability), 8),
        )
        for line, probability in zip(
            canonical["line_value"],
            canonical["_fair_over"],
            strict=True,
        )
    ]
    unique_pairs = set(pairs)
    anchor_lookup = {
        pair: _anchor(*pair)
        for pair in unique_pairs
    }
    canonical["_anchor_lambda"] = [
        anchor_lookup[pair] for pair in pairs
    ]
    return canonical, {
        **source_audit,
        "canonical_market_observations": int(len(canonical)),
    }


def build_snapshot_movement_features(
    market_frame: pd.DataFrame,
    market_snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    required = {
        "exposure_match_id",
        "stat_key",
        "period",
        "scope",
        "line_value",
        "over_odds",
        "market_fair_probability_over",
        "market_anchor_lambda",
        "market_overround",
    }
    missing = sorted(required.difference(market_frame.columns))
    if missing:
        raise ValueError(f"movement frame is missing columns: {missing}")
    target_snapshot, _ = _validate_model_timing(market_frame)
    features = _empty_features(market_frame.index)
    if market_snapshots.empty:
        return features, {
            "input_rows": int(len(market_frame)),
            "input_snapshot_rows": 0,
            "valid_snapshot_rows": 0,
            "canonical_market_observations": 0,
            "duplicate_line_snapshot_price_conflicts": 0,
            "rows_with_observations": 0,
            "rows_with_two_or_more_observations": 0,
            "rows_with_usable_movement": 0,
            "rows_without_observations": int(len(market_frame)),
            "current_canonical_line_alignment_rows": 0,
            "current_canonical_odds_alignment_rows": 0,
            "future_market_observations_excluded": 0,
            "future_market_observations_used": 0,
        }

    canonical, source_audit = _canonical_market_observations(
        market_snapshots
    )
    grouped = {
        tuple(str(part) for part in key): rows.reset_index(
            drop=True
        )
        for key, rows in canonical.groupby(
            list(_MARKET_KEYS),
            sort=False,
        )
    }
    rows_with_observations = 0
    rows_with_two_observations = 0
    rows_with_usable_movement = 0
    line_alignment = 0
    odds_alignment = 0
    future_excluded = 0

    for position, row in enumerate(
        market_frame.itertuples(index=False)
    ):
        key = (
            str(row.exposure_match_id),
            str(row.stat_key),
            str(row.period),
            str(row.scope),
        )
        observations = grouped.get(key)
        if observations is None or observations.empty:
            continue
        cutoff = target_snapshot.iloc[position]
        eligible = observations[
            observations["_snapshot_at"].le(cutoff)
        ]
        future_excluded += int(
            observations["_snapshot_at"].gt(cutoff).sum()
        )
        if eligible.empty:
            continue
        rows_with_observations += 1
        latest = eligible.iloc[-1]
        current_line = float(row.line_value)
        current_fair = float(row.market_fair_probability_over)
        current_anchor = float(row.market_anchor_lambda)
        current_overround = (
            float(row.market_overround)
            if pd.notna(row.market_overround)
            else math.nan
        )
        aligned_line = math.isclose(
            float(latest["line_value"]),
            current_line,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        line_alignment += int(aligned_line)
        aligned_over = math.isclose(
            float(latest["over_odds"]),
            float(row.over_odds),
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        row_under = getattr(row, "under_odds", math.nan)
        aligned_under = (
            pd.isna(row_under)
            or (
                pd.notna(latest["under_odds"])
                and math.isclose(
                    float(latest["under_odds"]),
                    float(row_under),
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            )
        )
        odds_alignment += int(
            aligned_line and aligned_over and aligned_under
        )

        count = len(eligible)
        features.iloc[
            position,
            features.columns.get_loc(
                "movement_snapshot_observations"
            ),
        ] = float(count)
        if count < 2:
            continue
        rows_with_two_observations += 1
        if not (aligned_line and aligned_over and aligned_under):
            continue
        rows_with_usable_movement += 1
        opening = eligible.iloc[0]
        previous = eligible.iloc[-2]
        span_hours = (
            cutoff - opening["_snapshot_at"]
        ).total_seconds() / 3600.0
        features.iloc[position] = [
            float(count),
            float(span_hours),
            current_line - float(opening["line_value"]),
            current_line - float(previous["line_value"]),
            current_fair - float(opening["_fair_over"]),
            current_fair - float(previous["_fair_over"]),
            current_anchor - float(opening["_anchor_lambda"]),
            current_anchor - float(previous["_anchor_lambda"]),
            (
                current_overround - float(opening["_overround"])
                if math.isfinite(current_overround)
                and pd.notna(opening["_overround"])
                else math.nan
            ),
            float(
                not math.isclose(
                    current_line,
                    float(opening["line_value"]),
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            ),
        ]

    return features, {
        "input_rows": int(len(market_frame)),
        **source_audit,
        "rows_with_observations": rows_with_observations,
        "rows_with_two_or_more_observations": (
            rows_with_two_observations
        ),
        "rows_with_usable_movement": rows_with_usable_movement,
        "rows_without_observations": int(
            len(market_frame) - rows_with_observations
        ),
        "current_canonical_line_alignment_rows": line_alignment,
        "current_canonical_odds_alignment_rows": odds_alignment,
        "future_market_observations_excluded": future_excluded,
        "future_market_observations_used": 0,
    }


def transform_movement_features_for_model(
    raw_features: pd.DataFrame,
) -> pd.DataFrame:
    missing = sorted(
        set(MOVEMENT_FEATURE_COLUMNS).difference(
            raw_features.columns
        )
    )
    if missing:
        raise ValueError(
            f"raw movement features are missing columns: {missing}"
        )

    def signed_log1p(series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce")
        return np.sign(numeric) * np.log1p(np.abs(numeric))

    result = pd.DataFrame(index=raw_features.index)
    result["movement_snapshot_observations_log1p"] = np.log1p(
        pd.to_numeric(
            raw_features["movement_snapshot_observations"],
            errors="coerce",
        ).clip(lower=0.0)
    )
    result["movement_snapshot_span_hours_log1p"] = np.log1p(
        pd.to_numeric(
            raw_features["movement_snapshot_span_hours"],
            errors="coerce",
        ).clip(lower=0.0)
    )
    for source in (
        "movement_line_delta_from_open",
        "movement_line_delta_from_previous",
        "movement_fair_probability_delta_from_open",
        "movement_fair_probability_delta_from_previous",
        "movement_anchor_delta_from_open",
        "movement_anchor_delta_from_previous",
        "movement_overround_delta_from_open",
    ):
        result[f"{source}_signed_log1p"] = signed_log1p(
            raw_features[source]
        )
    result["movement_line_changed_from_open"] = pd.to_numeric(
        raw_features["movement_line_changed_from_open"],
        errors="coerce",
    )
    return result.loc[:, MOVEMENT_MODEL_FEATURE_COLUMNS]
