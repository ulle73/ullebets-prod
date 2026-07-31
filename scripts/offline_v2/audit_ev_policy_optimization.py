from __future__ import annotations

import argparse
from itertools import product
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np
import pandas as pd

from ullebets_v2.ev_model.policy_optimization import (
    apply_market_probability_blend,
    run_nested_brier_blend_policy,
    select_blended_policy_bets,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit market-probability shrinkage and correlated match "
            "exposure using frozen walk-forward predictions."
        )
    )
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-name", default="logistic_market")
    parser.add_argument("--minimum-ev", type=float, default=0.075)
    parser.add_argument("--maximum-ev", type=float, default=0.25)
    parser.add_argument(
        "--maximum-bets-per-match",
        type=int,
        default=3,
    )
    return parser.parse_args()


def _performance(frame: pd.DataFrame) -> dict[str, float | int]:
    pnl = pd.to_numeric(
        frame.get("realized_roi_units"),
        errors="coerce",
    ).fillna(0.0)
    return {
        "bets": int(len(frame)),
        "matches": (
            int(frame["exposure_match_id"].nunique())
            if "exposure_match_id" in frame.columns
            else 0
        ),
        "pnl_units": float(pnl.sum()),
        "roi_pct": float(pnl.mean() * 100.0) if len(frame) else 0.0,
    }


def _cluster_bootstrap(
    frame: pd.DataFrame,
    *,
    iterations: int = 50_000,
) -> dict[str, float | int | None]:
    if frame.empty:
        return {
            "clusters": 0,
            "low_95_pct": None,
            "median_pct": None,
            "high_95_pct": None,
            "probability_positive": None,
        }
    clusters = (
        frame.groupby("exposure_match_id")["realized_roi_units"]
        .agg(["sum", "size"])
        .to_numpy(dtype=float)
    )
    rng = np.random.default_rng(20260730)
    sampled = clusters[
        rng.integers(
            0,
            len(clusters),
            size=(iterations, len(clusters)),
        )
    ]
    rois = (
        sampled[:, :, 0].sum(axis=1)
        / sampled[:, :, 1].sum(axis=1)
        * 100.0
    )
    return {
        "clusters": int(len(clusters)),
        "low_95_pct": float(np.quantile(rois, 0.025)),
        "median_pct": float(np.quantile(rois, 0.5)),
        "high_95_pct": float(np.quantile(rois, 0.975)),
        "probability_positive": float(np.mean(rois > 0.0)),
    }


def _maximum_drawdown(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    ordered = frame.copy()
    ordered["_start"] = pd.to_datetime(
        ordered.get("match_start_time"),
        errors="coerce",
        utc=True,
    )
    ordered = ordered.sort_values(
        ["_start", "exposure_match_id", "sample_key"]
    )
    cumulative = pd.to_numeric(
        ordered["realized_roi_units"],
        errors="coerce",
    ).fillna(0.0).cumsum()
    drawdown = cumulative - cumulative.cummax()
    return float(drawdown.min())


def _segment_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    grouped = (
        frame.groupby(
            ["stat_key", "period", "scope"],
            dropna=False,
        )
        .agg(
            bets=("realized_roi_units", "size"),
            matches=("exposure_match_id", "nunique"),
            pnl_units=("realized_roi_units", "sum"),
        )
        .reset_index()
    )
    grouped["roi_pct"] = (
        grouped["pnl_units"] / grouped["bets"] * 100.0
    )
    return grouped.sort_values(
        ["bets", "stat_key", "period", "scope"],
        ascending=[False, True, True, True],
    ).to_dict("records")


def _canonical_line_audit(
    predictions: pd.DataFrame,
) -> dict[str, int]:
    markets = predictions.drop_duplicates(
        ["sample_key", "line_value"]
    )
    line_counts = markets.groupby("sample_key")["line_value"].nunique()
    return {
        "sample_keys": int(line_counts.size),
        "sample_keys_with_multiple_lines": int(
            line_counts.gt(1).sum()
        ),
        "maximum_lines_per_sample_key": (
            int(line_counts.max()) if len(line_counts) else 0
        ),
    }


def _markdown(report: dict[str, object]) -> str:
    baseline = report["baseline_v3"]
    nested = report["nested_policy"]["performance"]
    bootstrap = report["nested_policy"]["cluster_bootstrap"]
    lines = [
        "# EV Policy Optimization Audit",
        "",
        "## Canonical Exposure",
        "",
        f"- Sample keys: `{report['canonical_line_audit']['sample_keys']}`",
        "- Sample keys with multiple modeled lines: "
        f"`{report['canonical_line_audit']['sample_keys_with_multiple_lines']}`",
        "",
        "## Current V3",
        "",
        f"- Bets: `{baseline['bets']}`",
        f"- Matches: `{baseline['matches']}`",
        f"- PnL: `{baseline['pnl_units']:.2f}` units",
        f"- ROI: `{baseline['roi_pct']:.2f}%`",
        "",
        "## Nested Brier Blend",
        "",
        f"- Bets: `{nested['bets']}`",
        f"- Matches: `{nested['matches']}`",
        f"- PnL: `{nested['pnl_units']:.2f}` units",
        f"- ROI: `{nested['roi_pct']:.2f}%`",
        f"- Positive evaluation windows: "
        f"`{report['nested_policy']['positive_windows']}/"
        f"{report['nested_policy']['evaluation_windows']}`",
        f"- Match-clustered 95% interval: "
        f"`{bootstrap['low_95_pct']:.2f}%` to "
        f"`{bootstrap['high_95_pct']:.2f}%`",
        "",
        "## Decision",
        "",
        str(report["decision"]),
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    all_predictions = pd.read_parquet(args.predictions)
    predictions = all_predictions[
        all_predictions["model_name"].eq(args.model_name)
    ].copy()
    if predictions.empty:
        raise RuntimeError(
            f"No predictions found for model {args.model_name!r}."
        )

    fixed_rows: list[dict[str, object]] = []
    fixed_selections: dict[tuple[float, int | None], pd.DataFrame] = {}
    for alpha, exposure_cap in product(
        (0.25, 0.50, 0.75, 1.0),
        (1, 3, 5, None),
    ):
        blended = apply_market_probability_blend(
            predictions,
            alpha=alpha,
        )
        selections = select_blended_policy_bets(
            blended,
            minimum_ev=args.minimum_ev,
            maximum_ev=args.maximum_ev,
            maximum_bets_per_match=exposure_cap,
        )
        fixed_selections[(alpha, exposure_cap)] = selections
        window_performance = [
            _performance(rows)
            for _, rows in selections.groupby("test_start")
        ]
        fixed_rows.append(
            {
                "alpha": alpha,
                "maximum_bets_per_match": exposure_cap,
                **_performance(selections),
                "positive_windows": sum(
                    row["roi_pct"] > 0.0
                    for row in window_performance
                ),
                "evaluation_windows": len(window_performance),
                "maximum_drawdown_units": _maximum_drawdown(
                    selections
                ),
            }
        )
    fixed_grid = pd.DataFrame(fixed_rows)
    baseline = fixed_selections[(1.0, None)]

    nested, nested_windows = run_nested_brier_blend_policy(
        predictions,
        alpha_grid=(0.0, 0.25, 0.50, 0.75, 1.0),
        minimum_history_windows=2,
        minimum_ev=args.minimum_ev,
        maximum_ev=args.maximum_ev,
        maximum_bets_per_match=args.maximum_bets_per_match,
    )
    nested_performance = _performance(nested)
    bootstrap = _cluster_bootstrap(nested)
    report: dict[str, object] = {
        "configuration": {
            "predictions": str(args.predictions),
            "model_name": args.model_name,
            "minimum_ev": args.minimum_ev,
            "maximum_ev": args.maximum_ev,
            "nested_alpha_grid": [0.0, 0.25, 0.50, 0.75, 1.0],
            "nested_warmup_windows": 2,
            "maximum_bets_per_match": (
                args.maximum_bets_per_match
            ),
        },
        "canonical_line_audit": _canonical_line_audit(
            predictions
        ),
        "baseline_v3": {
            **_performance(baseline),
            "maximum_drawdown_units": _maximum_drawdown(baseline),
            "segments": _segment_rows(baseline),
        },
        "fixed_policy_grid": fixed_rows,
        "nested_policy": {
            "performance": nested_performance,
            "evaluation_windows": int(len(nested_windows)),
            "positive_windows": int(
                nested_windows["roi_pct"].gt(0.0).sum()
            ),
            "maximum_drawdown_units": _maximum_drawdown(nested),
            "cluster_bootstrap": bootstrap,
            "windows": nested_windows.to_dict("records"),
            "segments": _segment_rows(nested),
        },
        "decision": (
            "Retain V3 as the primary shadow policy. Probability shrinkage "
            "selected from prior OOS Brier scores is a valid challenger and "
            "improves the later-window subset, but its clustered interval "
            "still crosses zero and a fixed 0.75 blend is not stable across "
            "all six windows. Do not promote a V4 from this already-inspected "
            "history; freeze all future candidate scores so both policies "
            "can be evaluated on identical untouched matches."
        ),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    fixed_grid.to_csv(
        args.output_dir / "fixed_policy_grid.csv",
        index=False,
    )
    nested.to_parquet(
        args.output_dir / "nested_policy_selections.parquet",
        index=False,
    )
    nested_windows.to_json(
        args.output_dir / "nested_policy_windows.json",
        orient="records",
        indent=2,
    )
    (args.output_dir / "policy_optimization_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (args.output_dir / "policy_optimization_audit.md").write_text(
        _markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
