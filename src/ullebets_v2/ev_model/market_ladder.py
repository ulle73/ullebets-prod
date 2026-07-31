from __future__ import annotations

from functools import lru_cache
import math

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.market import infer_poisson_mean
from ullebets_v2.ev_model.market_movement import (
    build_snapshot_line_points,
)


LADDER_FEATURE_COLUMNS = (
    "ladder_line_count",
    "ladder_line_span",
    "ladder_other_anchor_median",
    "ladder_other_anchor_iqr",
    "ladder_other_anchor_mad",
    "ladder_current_anchor_minus_other_median",
    "ladder_current_probability_minus_neighbor_consensus",
    "ladder_monotonic_violation_rate",
    "ladder_current_line_percentile",
    "ladder_overround_median",
)

LADDER_MODEL_FEATURE_COLUMNS = (
    "ladder_line_count_log1p",
    "ladder_line_span_log1p",
    "ladder_other_anchor_median",
    "ladder_other_anchor_iqr_log1p",
    "ladder_other_anchor_mad_log1p",
    "ladder_current_anchor_minus_other_median_signed_log1p",
    "ladder_current_probability_minus_neighbor_consensus_signed_log1p",
    "ladder_monotonic_violation_rate",
    "ladder_current_line_percentile",
    "ladder_overround_median",
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
        columns=LADDER_FEATURE_COLUMNS,
    )
    result["ladder_line_count"] = 0.0
    return result


def _target_snapshot_times(frame: pd.DataFrame) -> pd.Series:
    required = {"odds_snapshot_time", "match_start_time"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"ladder frame is missing timing: {missing}")
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
        raise ValueError("ladder frame contains missing timing")
    if snapshot.ge(kickoff).any():
        raise ValueError(
            "every model odds snapshot must be strictly before kickoff"
        )
    return snapshot


def _line_anchors(ladder: pd.DataFrame) -> np.ndarray:
    pairs = [
        (
            round(float(line), 6),
            round(float(probability), 8),
        )
        for line, probability in zip(
            ladder["line_value"],
            ladder["_fair_over"],
            strict=True,
        )
    ]
    return np.asarray([_anchor(*pair) for pair in pairs])


def build_snapshot_ladder_features(
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
    }
    missing = sorted(required.difference(market_frame.columns))
    if missing:
        raise ValueError(f"ladder frame is missing columns: {missing}")
    cutoff_times = _target_snapshot_times(market_frame)
    features = _empty_features(market_frame.index)
    if market_snapshots.empty:
        return features, {
            "input_rows": int(len(market_frame)),
            "input_snapshot_rows": 0,
            "snapshot_line_points": 0,
            "rows_with_snapshot_ladder": 0,
            "current_line_price_alignment_rows": 0,
            "rows_with_usable_leave_current_out_ladder": 0,
            "future_snapshot_ladders_excluded": 0,
            "future_snapshot_ladders_used": 0,
        }

    points, source_audit = build_snapshot_line_points(
        market_snapshots
    )
    grouped = {
        tuple(str(part) for part in key): rows.reset_index(
            drop=True
        )
        for key, rows in points.groupby(
            list(_MARKET_KEYS),
            sort=False,
        )
    }
    rows_with_ladder = 0
    aligned_rows = 0
    usable_rows = 0
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
        market_points = grouped.get(key)
        if market_points is None or market_points.empty:
            continue
        cutoff = cutoff_times.iloc[position]
        eligible_times = market_points.loc[
            market_points["_snapshot_at"].le(cutoff),
            "_snapshot_at",
        ]
        future_excluded += int(
            market_points.loc[
                market_points["_snapshot_at"].gt(cutoff),
                "_snapshot_at",
            ].nunique()
        )
        if eligible_times.empty:
            continue
        latest_time = eligible_times.max()
        ladder = (
            market_points[
                market_points["_snapshot_at"].eq(latest_time)
            ]
            .sort_values("line_value")
            .reset_index(drop=True)
        )
        rows_with_ladder += 1
        features.iloc[
            position,
            features.columns.get_loc("ladder_line_count"),
        ] = float(len(ladder))
        current_line = float(row.line_value)
        current_point = ladder[
            np.isclose(
                ladder["line_value"],
                current_line,
                rtol=0.0,
                atol=1e-9,
            )
        ]
        if len(current_point) != 1:
            continue
        current_point = current_point.iloc[0]
        aligned_over = math.isclose(
            float(current_point["over_odds"]),
            float(row.over_odds),
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        row_under = getattr(row, "under_odds", math.nan)
        aligned_under = (
            pd.isna(row_under)
            or (
                pd.notna(current_point["under_odds"])
                and math.isclose(
                    float(current_point["under_odds"]),
                    float(row_under),
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            )
        )
        if not (aligned_over and aligned_under):
            continue
        aligned_rows += 1
        other = ladder[
            ~np.isclose(
                ladder["line_value"],
                current_line,
                rtol=0.0,
                atol=1e-9,
            )
        ].copy()
        if len(other) < 2:
            continue
        usable_rows += 1
        other_anchors = _line_anchors(other)
        median_anchor = float(np.median(other_anchors))
        anchor_q25, anchor_q75 = np.quantile(
            other_anchors,
            [0.25, 0.75],
        )
        anchor_mad = float(
            np.median(np.abs(other_anchors - median_anchor))
        )
        neighbor_probability = float(
            np.interp(
                current_line,
                other["line_value"].to_numpy(dtype=float),
                other["_fair_over"].to_numpy(dtype=float),
            )
        )
        fair_probabilities = ladder[
            "_fair_over"
        ].to_numpy(dtype=float)
        violation_rate = float(
            np.mean(np.diff(fair_probabilities) > 1e-9)
        )
        current_rank = int(
            np.searchsorted(
                ladder["line_value"].to_numpy(dtype=float),
                current_line,
                side="left",
            )
        )
        line_percentile = (
            current_rank / (len(ladder) - 1)
            if len(ladder) > 1
            else 0.5
        )
        overround = pd.to_numeric(
            ladder["_overround"],
            errors="coerce",
        ).dropna()
        features.iloc[position] = [
            float(len(ladder)),
            float(
                ladder["line_value"].max()
                - ladder["line_value"].min()
            ),
            median_anchor,
            float(anchor_q75 - anchor_q25),
            anchor_mad,
            float(row.market_anchor_lambda) - median_anchor,
            (
                float(row.market_fair_probability_over)
                - neighbor_probability
            ),
            violation_rate,
            float(line_percentile),
            (
                float(overround.median())
                if not overround.empty
                else math.nan
            ),
        ]

    return features, {
        "input_rows": int(len(market_frame)),
        **source_audit,
        "rows_with_snapshot_ladder": rows_with_ladder,
        "current_line_price_alignment_rows": aligned_rows,
        "rows_with_usable_leave_current_out_ladder": usable_rows,
        "rows_without_snapshot_ladder": int(
            len(market_frame) - rows_with_ladder
        ),
        "future_snapshot_ladders_excluded": future_excluded,
        "future_snapshot_ladders_used": 0,
    }


def transform_ladder_features_for_model(
    raw_features: pd.DataFrame,
) -> pd.DataFrame:
    missing = sorted(
        set(LADDER_FEATURE_COLUMNS).difference(
            raw_features.columns
        )
    )
    if missing:
        raise ValueError(
            f"raw ladder features are missing columns: {missing}"
        )

    def signed_log1p(series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce")
        return np.sign(numeric) * np.log1p(np.abs(numeric))

    result = pd.DataFrame(index=raw_features.index)
    result["ladder_line_count_log1p"] = np.log1p(
        pd.to_numeric(
            raw_features["ladder_line_count"],
            errors="coerce",
        ).clip(lower=0.0)
    )
    result["ladder_line_span_log1p"] = np.log1p(
        pd.to_numeric(
            raw_features["ladder_line_span"],
            errors="coerce",
        ).clip(lower=0.0)
    )
    result["ladder_other_anchor_median"] = pd.to_numeric(
        raw_features["ladder_other_anchor_median"],
        errors="coerce",
    )
    for source in (
        "ladder_other_anchor_iqr",
        "ladder_other_anchor_mad",
    ):
        result[f"{source}_log1p"] = np.log1p(
            pd.to_numeric(
                raw_features[source],
                errors="coerce",
            ).clip(lower=0.0)
        )
    for source in (
        "ladder_current_anchor_minus_other_median",
        "ladder_current_probability_minus_neighbor_consensus",
    ):
        result[f"{source}_signed_log1p"] = signed_log1p(
            raw_features[source]
        )
    for source in (
        "ladder_monotonic_violation_rate",
        "ladder_current_line_percentile",
        "ladder_overround_median",
    ):
        result[source] = pd.to_numeric(
            raw_features[source],
            errors="coerce",
        )
    return result.loc[:, LADDER_MODEL_FEATURE_COLUMNS]
