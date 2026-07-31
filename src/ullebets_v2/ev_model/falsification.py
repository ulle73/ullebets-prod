from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd


_POLICY_FILTER_COLUMNS = {
    "stat_keys": "stat_key",
    "periods": "period",
    "scopes": "scope",
    "directions": "direction",
    "leagues": "league_name_normalized",
}


def apply_policy_filters_to_frame(
    frame: pd.DataFrame,
    filters: Mapping[str, list[str]],
) -> pd.DataFrame:
    unsupported = sorted(
        set(filters).difference(_POLICY_FILTER_COLUMNS)
    )
    if unsupported:
        raise ValueError(
            f"unsupported policy filters: {unsupported}"
        )
    filtered = frame
    for filter_name, values in filters.items():
        column = _POLICY_FILTER_COLUMNS[filter_name]
        allowed = {str(value) for value in values}
        filtered = filtered[
            filtered[column].astype(str).isin(allowed)
        ]
    return filtered.copy()


def apply_policy_exposure_cap_to_frame(
    frame: pd.DataFrame,
    *,
    maximum_bets_per_match: int | None,
) -> pd.DataFrame:
    if maximum_bets_per_match is None:
        return frame.copy()
    if maximum_bets_per_match <= 0:
        raise ValueError(
            "maximum_bets_per_match must be positive"
        )
    return (
        frame.sort_values(
            "expected_roi_units",
            ascending=False,
            kind="stable",
        )
        .groupby(
            "exposure_match_id",
            sort=False,
            group_keys=False,
        )
        .head(maximum_bets_per_match)
        .copy()
    )


def _performance(
    frame: pd.DataFrame,
    *,
    pnl_column: str = "realized_roi_units",
) -> dict[str, float | int | None]:
    pnl = pd.to_numeric(
        frame.get(pnl_column),
        errors="coerce",
    ).dropna()
    return {
        "bets": int(len(pnl)),
        "matches": int(
            frame.loc[pnl.index, "exposure_match_id"]
            .astype(str)
            .nunique()
        ),
        "pnl_units": float(pnl.sum()),
        "roi_pct": (
            float(pnl.mean() * 100.0)
            if not pnl.empty
            else None
        ),
    }


def apply_absolute_odds_haircut(
    frame: pd.DataFrame,
    *,
    absolute_decimal_points: float,
) -> pd.Series:
    if absolute_decimal_points < 0:
        raise ValueError("absolute_decimal_points must be non-negative")
    result = frame["settlement_result"].astype(str)
    odds = pd.to_numeric(
        frame["offered_odds"],
        errors="coerce",
    )
    adjusted_win_profit = (
        odds - absolute_decimal_points - 1.0
    ).clip(lower=0.0)
    pnl = pd.Series(np.nan, index=frame.index, dtype=float)
    pnl.loc[result.eq("win")] = adjusted_win_profit.loc[
        result.eq("win")
    ]
    pnl.loc[result.eq("loss")] = -1.0
    pnl.loc[result.eq("push")] = 0.0
    return pnl


def _leave_one_group_out(
    frame: pd.DataFrame,
    *,
    column: str,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for group in sorted(
        frame[column].dropna().astype(str).unique()
    ):
        remainder = frame[
            frame[column].astype(str).ne(group)
        ]
        rows.append(
            {
                "excluded_group": group,
                **_performance(remainder),
            }
        )
    valid_roi = [
        float(row["roi_pct"])
        for row in rows
        if row["roi_pct"] is not None
    ]
    return {
        "group_column": column,
        "groups": len(rows),
        "all_positive": bool(
            valid_roi
            and len(valid_roi) == len(rows)
            and all(value > 0.0 for value in valid_roi)
        ),
        "minimum_roi_pct": (
            min(valid_roi) if valid_roi else None
        ),
        "maximum_roi_pct": (
            max(valid_roi) if valid_roi else None
        ),
        "rows": rows,
    }


def _cluster_inference(
    frame: pd.DataFrame,
    *,
    iterations: int,
    random_seed: int,
    experiments_inspected: int,
) -> dict[str, float | int | None]:
    clusters = (
        frame.groupby("exposure_match_id")[
            "realized_roi_units"
        ]
        .agg(["sum", "size"])
        .to_numpy(dtype=float)
    )
    if not len(clusters):
        return {
            "clusters": 0,
            "low_95_pct": None,
            "high_95_pct": None,
            "probability_positive": None,
            "one_sided_null_p_value": None,
            "multiple_comparison_adjusted_p_value": None,
        }
    observed_roi = (
        clusters[:, 0].sum() / clusters[:, 1].sum()
    )
    rng = np.random.default_rng(random_seed)
    sampled = clusters[
        rng.integers(
            0,
            len(clusters),
            size=(iterations, len(clusters)),
        )
    ]
    sampled_roi = (
        sampled[:, :, 0].sum(axis=1)
        / sampled[:, :, 1].sum(axis=1)
    )

    centered = clusters.copy()
    centered[:, 0] -= observed_roi * centered[:, 1]
    sampled_null = centered[
        rng.integers(
            0,
            len(centered),
            size=(iterations, len(centered)),
        )
    ]
    null_roi = (
        sampled_null[:, :, 0].sum(axis=1)
        / sampled_null[:, :, 1].sum(axis=1)
    )
    null_exceedances = int(
        np.count_nonzero(null_roi >= observed_roi)
    )
    p_value = (
        (null_exceedances + 1.0) / (iterations + 1.0)
    )
    return {
        "clusters": int(len(clusters)),
        "low_95_pct": float(
            np.quantile(sampled_roi, 0.025) * 100.0
        ),
        "high_95_pct": float(
            np.quantile(sampled_roi, 0.975) * 100.0
        ),
        "probability_positive": float(
            np.mean(sampled_roi > 0.0)
        ),
        "one_sided_null_p_value": float(p_value),
        "multiple_comparison_adjusted_p_value": float(
            min(1.0, p_value * experiments_inspected)
        ),
    }


def _price_stress(frame: pd.DataFrame) -> dict[str, object]:
    report: dict[str, object] = {
        "recorded_odds": _performance(frame),
    }
    for decimal_points in (0.02, 0.05, 0.10):
        stressed = frame.copy()
        stressed["_stressed_pnl"] = (
            apply_absolute_odds_haircut(
                stressed,
                absolute_decimal_points=decimal_points,
            )
        )
        report[
            f"minus_{decimal_points:.2f}_decimal"
        ] = _performance(
            stressed,
            pnl_column="_stressed_pnl",
        )
    return report


def _calibration(frame: pd.DataFrame) -> dict[str, object]:
    settled = frame[
        frame["settlement_result"].isin(["win", "loss"])
    ].copy()
    if settled.empty:
        return {
            "settled_non_push_rows": 0,
            "observed_win_rate": None,
            "mean_model_probability": None,
            "mean_market_probability": None,
            "model_brier": None,
            "market_brier": None,
            "expected_calibration_error": None,
        }
    target = settled["settlement_result"].eq("win").astype(
        float
    )
    model_probability = pd.to_numeric(
        settled["predicted_win_probability"],
        errors="coerce",
    ).clip(0.0, 1.0)
    market_over = pd.to_numeric(
        settled["market_fair_probability_over"],
        errors="coerce",
    ).clip(0.0, 1.0)
    market_probability = market_over.where(
        settled["direction"].astype(str).eq("over"),
        1.0 - market_over,
    )
    valid = (
        target.notna()
        & model_probability.notna()
        & market_probability.notna()
    )
    target = target[valid]
    model_probability = model_probability[valid]
    market_probability = market_probability[valid]

    bins = pd.cut(
        model_probability,
        bins=np.linspace(0.0, 1.0, 11),
        include_lowest=True,
    )
    calibration_rows = pd.DataFrame(
        {
            "probability": model_probability,
            "target": target,
            "bin": bins,
        }
    )
    grouped = calibration_rows.groupby(
        "bin",
        observed=True,
    ).agg(
        rows=("target", "size"),
        mean_probability=("probability", "mean"),
        observed_rate=("target", "mean"),
    )
    ece = float(
        (
            grouped["rows"]
            / len(calibration_rows)
            * (
                grouped["mean_probability"]
                - grouped["observed_rate"]
            ).abs()
        ).sum()
    )
    return {
        "settled_non_push_rows": int(len(target)),
        "observed_win_rate": float(target.mean()),
        "mean_model_probability": float(
            model_probability.mean()
        ),
        "mean_market_probability": float(
            market_probability.mean()
        ),
        "model_brier": float(
            np.mean((model_probability - target) ** 2)
        ),
        "market_brier": float(
            np.mean((market_probability - target) ** 2)
        ),
        "expected_calibration_error": ece,
    }


def _group_summary(
    frame: pd.DataFrame,
    *,
    columns: list[str],
) -> list[dict[str, object]]:
    rows = (
        frame.groupby(columns, dropna=False)
        .agg(
            bets=("realized_roi_units", "size"),
            matches=("exposure_match_id", "nunique"),
            pnl_units=("realized_roi_units", "sum"),
            roi_pct=("realized_roi_units", "mean"),
        )
        .reset_index()
    )
    rows["roi_pct"] *= 100.0
    rows = rows.sort_values(
        ["bets", "pnl_units"],
        ascending=[False, False],
    )
    return rows.to_dict(orient="records")


def _concentration(frame: pd.DataFrame) -> dict[str, object]:
    league_rows = _group_summary(
        frame,
        columns=["league_name_normalized"],
    )
    if not league_rows:
        return {
            "top_net_pnl_league": None,
            "top_net_pnl_units": None,
            "roi_without_top_net_pnl_league_pct": None,
            "league_bet_hhi": None,
        }
    top = max(
        league_rows,
        key=lambda row: float(row["pnl_units"]),
    )
    top_league = str(top["league_name_normalized"])
    remainder = frame[
        frame["league_name_normalized"]
        .astype(str)
        .ne(top_league)
    ]
    shares = (
        frame["league_name_normalized"]
        .astype(str)
        .value_counts(normalize=True)
    )
    return {
        "top_net_pnl_league": top_league,
        "top_net_pnl_units": float(top["pnl_units"]),
        "top_net_pnl_share_of_total": (
            float(
                float(top["pnl_units"])
                / frame["realized_roi_units"].sum()
            )
            if frame["realized_roi_units"].sum() > 0
            else None
        ),
        "roi_without_top_net_pnl_league_pct": (
            _performance(remainder)["roi_pct"]
        ),
        "league_bet_hhi": float((shares**2).sum()),
    }


def _candidate_report(
    name: str,
    frame: pd.DataFrame,
    *,
    experiments_inspected: int,
    bootstrap_iterations: int,
    random_seed: int,
) -> dict[str, object]:
    required = {
        "exposure_match_id",
        "league_name_normalized",
        "test_start",
        "stat_key",
        "period",
        "scope",
        "direction",
        "offered_odds",
        "predicted_win_probability",
        "market_fair_probability_over",
        "settlement_result",
        "realized_roi_units",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(
            f"{name} is missing required columns: {missing}"
        )
    candidate = frame.copy()
    candidate["realized_roi_units"] = pd.to_numeric(
        candidate["realized_roi_units"],
        errors="coerce",
    )
    candidate = candidate[
        candidate["realized_roi_units"].notna()
    ].copy()

    inference = _cluster_inference(
        candidate,
        iterations=bootstrap_iterations,
        random_seed=random_seed,
        experiments_inspected=experiments_inspected,
    )
    league_jackknife = _leave_one_group_out(
        candidate,
        column="league_name_normalized",
    )
    window_jackknife = _leave_one_group_out(
        candidate,
        column="test_start",
    )
    confirmed = bool(
        inference["low_95_pct"] is not None
        and float(inference["low_95_pct"]) > 0.0
        and float(
            inference[
                "multiple_comparison_adjusted_p_value"
            ]
        )
        < 0.05
        and league_jackknife["all_positive"]
        and window_jackknife["all_positive"]
    )
    return {
        "candidate": name,
        "performance": _performance(candidate),
        "cluster_inference": inference,
        "leave_one_league_out": league_jackknife,
        "leave_one_test_window_out": window_jackknife,
        "concentration": _concentration(candidate),
        "price_stress": _price_stress(candidate),
        "calibration": _calibration(candidate),
        "segments": {
            "stat": _group_summary(
                candidate,
                columns=["stat_key"],
            ),
            "period": _group_summary(
                candidate,
                columns=["period"],
            ),
            "scope": _group_summary(
                candidate,
                columns=["scope"],
            ),
            "stat_period_scope": _group_summary(
                candidate,
                columns=["stat_key", "period", "scope"],
            ),
            "league": _group_summary(
                candidate,
                columns=["league_name_normalized"],
            ),
        },
        "mechanical_gate_status": (
            "passes" if confirmed else "fails"
        ),
        "historical_edge_status": "not_confirmed",
        "evidence_limit": (
            "Passing the mechanical gate does not convert inspected or "
            "hypothesis-generating history into untouched confirmation."
        ),
        "failure_reasons": [
            reason
            for condition, reason in (
                (
                    inference["low_95_pct"] is None
                    or float(inference["low_95_pct"]) <= 0.0,
                    "match-clustered 95% interval crosses zero",
                ),
                (
                    inference[
                        "multiple_comparison_adjusted_p_value"
                    ]
                    is None
                    or float(
                        inference[
                            "multiple_comparison_adjusted_p_value"
                        ]
                    )
                    >= 0.05,
                    "not significant after experiment-count correction",
                ),
                (
                    not league_jackknife["all_positive"],
                    "edge does not survive every leave-one-league-out test",
                ),
                (
                    not window_jackknife["all_positive"],
                    "edge does not survive every leave-one-window-out test",
                ),
            )
            if condition
        ],
    }


def build_candidate_falsification_report(
    candidates: Mapping[str, pd.DataFrame],
    *,
    experiments_inspected: int,
    bootstrap_iterations: int = 50_000,
    random_seed: int = 20260730,
) -> dict[str, Any]:
    if experiments_inspected <= 0:
        raise ValueError("experiments_inspected must be positive")
    if bootstrap_iterations <= 0:
        raise ValueError("bootstrap_iterations must be positive")
    return {
        "methodology": {
            "experiments_inspected": experiments_inspected,
            "bootstrap_iterations": bootstrap_iterations,
            "cluster_unit": "exposure_match_id",
            "odds_stress": (
                "absolute decimal points removed from winning prices"
            ),
            "confirmation_gate": (
                "clustered lower bound > 0, experiment-count adjusted "
                "one-sided p < 0.05, and every leave-one-league/window "
                "ROI > 0"
            ),
        },
        "candidates": [
            _candidate_report(
                name,
                frame,
                experiments_inspected=experiments_inspected,
                bootstrap_iterations=bootstrap_iterations,
                random_seed=random_seed + index,
            )
            for index, (name, frame) in enumerate(
                candidates.items()
            )
        ],
    }
