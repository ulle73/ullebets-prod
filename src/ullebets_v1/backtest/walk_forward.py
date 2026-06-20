from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd

from ullebets_v1.backtest.metrics import expected_roi_for_side, poisson_probabilities_for_line, roi_units
from ullebets_v1.models.baseline import baseline_lambda
from ullebets_v1.models.calibration import train_poisson_model

SELECTION_METADATA_COLUMNS = (
    "effective_odds_source",
    "latest_snapshot_type",
    "latest_snapshot_minutes_before_kickoff",
    "has_latest_prematch_snapshot",
    "prematch_snapshot_count",
)


@dataclass(frozen=True)
class WalkForwardConfig:
    train_window_days: int = 90
    test_window_days: int = 14
    step_days: int = 14
    min_train_rows: int = 500
    min_expected_edge: float = 0.02


def _to_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _selection_from_lambda(frame: pd.DataFrame, lambda_column: str, threshold: float) -> pd.DataFrame:
    rows: list[dict] = []
    for row in frame.itertuples(index=False):
        lam = getattr(row, lambda_column)
        if lam is None or pd.isna(lam):
            continue
        p_over, p_under, p_push = poisson_probabilities_for_line(float(lam), float(row.line_value))
        over_ev = expected_roi_for_side(p_over, p_push, float(row.over_odds)) if pd.notna(row.over_odds) else None
        under_ev = expected_roi_for_side(p_under, p_push, float(row.under_odds)) if pd.notna(row.under_odds) else None

        best_side = None
        best_ev = None
        best_prob = None
        best_odds = None
        best_result = None
        best_clv = None
        if over_ev is not None and (best_ev is None or over_ev > best_ev):
            best_side = "over"
            best_ev = over_ev
            best_prob = p_over
            best_odds = float(row.over_odds)
            best_result = row.over_result
            best_clv = row.over_clv_pct
        if under_ev is not None and (best_ev is None or under_ev > best_ev):
            best_side = "under"
            best_ev = under_ev
            best_prob = p_under
            best_odds = float(row.under_odds)
            best_result = row.under_result
            best_clv = row.under_clv_pct

        if best_side is None or best_ev is None or best_ev <= threshold:
            continue

        payload = {
            "match_id": row.match_id,
            "match_date": row.match_date,
            "league_name": row.league_name,
            "stat_key": row.stat_key,
            "period": row.period,
            "scope": row.scope,
            "line_value": row.line_value,
            "selected_side": best_side,
            "selected_odds": best_odds,
            "expected_roi_units": best_ev,
            "predicted_lambda": lam,
            "predicted_win_prob": best_prob,
            "realized_result": best_result,
            "realized_roi_units": roi_units(best_result, best_odds) if best_result else None,
            "selected_clv_pct": best_clv,
        }
        for column in SELECTION_METADATA_COLUMNS:
            payload[column] = getattr(row, column, None)
        rows.append(payload)
    selections = pd.DataFrame(rows)
    if selections.empty:
        return selections
    selections = selections.sort_values(
        ["match_id", "stat_key", "period", "scope", "expected_roi_units"],
        ascending=[True, True, True, True, False],
    )
    return selections.drop_duplicates(
        subset=["match_id", "stat_key", "period", "scope"],
        keep="first",
    )


def _summarize_selection_rows(name: str, rows: pd.DataFrame) -> dict:
    if rows.empty:
        return {
            "strategy": name,
            "bets": 0,
            "roi_pct": 0.0,
            "avg_clv_pct": None,
        }
    realized = rows["realized_roi_units"].dropna()
    avg_clv = rows["selected_clv_pct"].dropna()
    return {
        "strategy": name,
        "bets": int(len(rows)),
        "roi_pct": float((realized.sum() / len(rows)) * 100.0) if len(rows) else 0.0,
        "pnl_units": float(realized.sum()) if not realized.empty else 0.0,
        "avg_expected_roi_units": float(rows["expected_roi_units"].mean()),
        "avg_clv_pct": float(avg_clv.mean()) if not avg_clv.empty else None,
    }


def run_walk_forward(
    feature_frame: pd.DataFrame,
    *,
    feature_columns: list[str],
    categorical_columns: list[str],
    config: WalkForwardConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = feature_frame.copy()
    frame = frame[frame["actual_value"].notna()].copy()
    frame["match_day"] = frame["match_date"].map(_to_date)
    all_days = sorted(frame["match_day"].dropna().unique())
    if not all_days:
        return pd.DataFrame(), pd.DataFrame()

    start_day = min(all_days) + timedelta(days=config.train_window_days)
    end_day = max(all_days)

    summary_rows: list[dict] = []
    selection_rows: list[pd.DataFrame] = []
    window_start = start_day

    while window_start <= end_day:
        train_start = window_start - timedelta(days=config.train_window_days)
        train_end = window_start - timedelta(days=1)
        test_end = window_start + timedelta(days=config.test_window_days - 1)

        train = frame[(frame["match_day"] >= train_start) & (frame["match_day"] <= train_end)].copy()
        test = frame[(frame["match_day"] >= window_start) & (frame["match_day"] <= test_end)].copy()

        if len(train) < config.min_train_rows or test.empty:
            window_start += timedelta(days=config.step_days)
            continue

        model = train_poisson_model(
            train,
            feature_columns=feature_columns,
            categorical_columns=categorical_columns,
        )
        test = test.copy()
        test["model_lambda"] = model.predict_lambda(test)
        test["baseline_lambda_eval"] = baseline_lambda(test)

        model_rows = _selection_from_lambda(test, "model_lambda", config.min_expected_edge)
        model_rows["window_start"] = window_start.isoformat()
        model_rows["window_end"] = test_end.isoformat()
        model_rows["strategy"] = "poisson_model"

        baseline_rows = _selection_from_lambda(test, "baseline_lambda_eval", config.min_expected_edge)
        baseline_rows["window_start"] = window_start.isoformat()
        baseline_rows["window_end"] = test_end.isoformat()
        baseline_rows["strategy"] = "baseline_lambda"

        summary_rows.append(
            {
                "window_start": window_start.isoformat(),
                "window_end": test_end.isoformat(),
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                **{f"model_{k}": v for k, v in _summarize_selection_rows("poisson_model", model_rows).items() if k != "strategy"},
                **{f"baseline_{k}": v for k, v in _summarize_selection_rows("baseline_lambda", baseline_rows).items() if k != "strategy"},
            }
        )
        if not model_rows.empty:
            selection_rows.append(model_rows)
        if not baseline_rows.empty:
            selection_rows.append(baseline_rows)

        window_start += timedelta(days=config.step_days)

    return pd.DataFrame(summary_rows), pd.concat(selection_rows, ignore_index=True) if selection_rows else pd.DataFrame()
