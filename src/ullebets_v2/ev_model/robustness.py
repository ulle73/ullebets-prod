from __future__ import annotations

from collections.abc import Iterable
import math

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.market_walk_forward import (
    select_market_classifier_bets,
)


DEFAULT_THRESHOLD_GRID = (0.05, 0.065, 0.075, 0.085, 0.10, 0.125, 0.15)
DEFAULT_ODDS_HAIRCUTS = (0.0, 0.01, 0.02, 0.03, 0.05, 0.075, 0.10)


def _performance(frame: pd.DataFrame) -> dict[str, float | int]:
    if frame.empty:
        return {"bets": 0, "pnl_units": 0.0, "roi_pct": 0.0}
    pnl = pd.to_numeric(frame["realized_roi_units"], errors="coerce").fillna(0.0)
    return {
        "bets": int(len(frame)),
        "pnl_units": float(pnl.sum()),
        "roi_pct": float(pnl.mean() * 100.0),
    }


def _market_probability(frame: pd.DataFrame) -> pd.Series:
    over = pd.to_numeric(
        frame["market_fair_probability_over"],
        errors="coerce",
    )
    return pd.Series(
        np.where(frame["direction"].eq("over"), over, 1.0 - over),
        index=frame.index,
        dtype=float,
    )


def _calibration(frame: pd.DataFrame) -> dict[str, float | int | None]:
    settled = frame[
        frame["settlement_result"].isin({"win", "loss"})
    ].copy()
    if settled.empty:
        return {"settled_bets": 0}
    actual = settled["settlement_result"].eq("win").astype(float)
    model = pd.to_numeric(
        settled["predicted_win_probability"],
        errors="coerce",
    ).clip(1e-6, 1.0 - 1e-6)
    market = _market_probability(settled).clip(1e-6, 1.0 - 1e-6)
    valid = actual.notna() & model.notna() & market.notna()
    actual = actual[valid]
    model = model[valid]
    market = market[valid]
    if actual.empty:
        return {"settled_bets": 0}
    model_log_loss = -(
        actual * np.log(model) + (1.0 - actual) * np.log(1.0 - model)
    ).mean()
    market_log_loss = -(
        actual * np.log(market) + (1.0 - actual) * np.log(1.0 - market)
    ).mean()
    return {
        "settled_bets": int(len(actual)),
        "actual_win_rate": float(actual.mean()),
        "mean_model_probability": float(model.mean()),
        "mean_market_probability": float(market.mean()),
        "model_calibration_bias": float(actual.mean() - model.mean()),
        "market_calibration_bias": float(actual.mean() - market.mean()),
        "model_brier": float(np.mean((model - actual) ** 2)),
        "market_brier": float(np.mean((market - actual) ** 2)),
        "model_log_loss": float(model_log_loss),
        "market_log_loss": float(market_log_loss),
    }


def _ev_bands(frame: pd.DataFrame) -> list[dict[str, float | int | str]]:
    boundaries = [0.075, 0.10, 0.15, 0.25, math.inf]
    labels = ["7.5-10%", "10-15%", "15-25%", "25%+"]
    bucket = pd.cut(
        frame["expected_roi_units"],
        bins=boundaries,
        labels=labels,
        right=False,
    )
    rows: list[dict[str, float | int | str]] = []
    for label in labels:
        segment = frame[bucket.eq(label)]
        performance = _performance(segment)
        rows.append({"band": label, **performance})
    return rows


def _maximum_loss_streak(frame: pd.DataFrame) -> int:
    is_loss = frame["settlement_result"].eq("loss").astype(int)
    if is_loss.empty:
        return 0
    groups = is_loss.eq(0).cumsum()
    return int(is_loss.groupby(groups).sum().max())


def build_robustness_report(
    predictions: pd.DataFrame,
    *,
    minimum_ev: float,
    maximum_ev: float | None,
    threshold_grid: Iterable[float] = DEFAULT_THRESHOLD_GRID,
    odds_haircuts: Iterable[float] = DEFAULT_ODDS_HAIRCUTS,
) -> dict[str, object]:
    uncapped = select_market_classifier_bets(
        predictions,
        minimum_ev=minimum_ev,
    )
    selections = select_market_classifier_bets(
        predictions,
        minimum_ev=minimum_ev,
        maximum_ev=maximum_ev,
    )
    report: dict[str, object] = {
        "policy": {
            "minimum_ev": minimum_ev,
            "maximum_ev": maximum_ev,
            "rejected_above_maximum_ev": int(
                len(uncapped) - len(selections)
            ),
        },
        "performance": _performance(selections),
        "calibration": _calibration(selections),
        "ev_bands": _ev_bands(uncapped),
    }

    threshold_rows: list[dict[str, float | int]] = []
    for threshold in threshold_grid:
        selected = select_market_classifier_bets(
            predictions,
            minimum_ev=float(threshold),
            maximum_ev=maximum_ev,
        )
        threshold_rows.append(
            {
                "minimum_ev": float(threshold),
                **_performance(selected),
            }
        )
    report["threshold_sensitivity"] = threshold_rows

    haircut_rows: list[dict[str, float | int]] = []
    actual_win = selections["settlement_result"].eq("win")
    actual_push = selections["settlement_result"].eq("push")
    offered_odds = pd.to_numeric(
        selections["offered_odds"],
        errors="coerce",
    )
    for haircut in odds_haircuts:
        degraded_odds = np.maximum(1.01, offered_odds * (1.0 - haircut))
        pnl = np.where(
            actual_push,
            0.0,
            np.where(actual_win, degraded_odds - 1.0, -1.0),
        )
        haircut_rows.append(
            {
                "decimal_odds_haircut": float(haircut),
                "bets": int(len(selections)),
                "pnl_units": float(np.nansum(pnl)),
                "roi_pct": (
                    float(np.nanmean(pnl) * 100.0)
                    if len(selections)
                    else 0.0
                ),
            }
        )
    report["odds_haircut_sensitivity"] = haircut_rows

    league_rows: list[dict[str, float | int | str]] = []
    if "league_name_normalized" in selections.columns:
        for league in sorted(
            selections["league_name_normalized"].dropna().astype(str).unique()
        ):
            remaining = selections[
                selections["league_name_normalized"].astype(str).ne(league)
            ]
            league_rows.append(
                {
                    "excluded_league": league,
                    **_performance(remaining),
                }
            )
    report["leave_one_league_out"] = league_rows

    cluster_rows = (
        selections.groupby("exposure_match_id", as_index=False)
        .agg(
            pnl_units=("realized_roi_units", "sum"),
            bets=("realized_roi_units", "size"),
        )
        .sort_values("pnl_units", ascending=False)
    )
    concentration_rows: list[dict[str, float | int]] = []
    for count in (1, 3, 5, 10, 20):
        excluded_keys = set(cluster_rows.head(count)["exposure_match_id"])
        remaining = selections[
            ~selections["exposure_match_id"].isin(excluded_keys)
        ]
        concentration_rows.append(
            {
                "best_match_clusters_removed": count,
                **_performance(remaining),
            }
        )
    report["match_concentration"] = {
        "match_clusters": int(len(cluster_rows)),
        "top_10_match_pnl_units": float(
            cluster_rows.head(10)["pnl_units"].sum()
        ),
        "removal_sensitivity": concentration_rows,
    }

    ordered = selections.copy()
    if "match_start_time" in ordered.columns:
        ordered["_order_time"] = pd.to_datetime(
            ordered["match_start_time"],
            errors="coerce",
            utc=True,
        )
        ordered = ordered.sort_values(
            ["_order_time", "exposure_match_id", "sample_key"]
        )
    cumulative = pd.to_numeric(
        ordered["realized_roi_units"],
        errors="coerce",
    ).fillna(0.0).cumsum()
    drawdown = cumulative - cumulative.cummax()
    report["risk"] = {
        "maximum_drawdown_units": (
            float(drawdown.min()) if not drawdown.empty else 0.0
        ),
        "maximum_loss_streak": _maximum_loss_streak(ordered),
    }
    return report
