from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np
import pandas as pd

from ullebets_v1.audit.odds_timing import annotate_backtest_timing
from ullebets_v2.ev_model.asof_features import (
    build_asof_compact_model_features,
)
from ullebets_v2.ev_model.candidate_audit import audit_candidate
from ullebets_v2.ev_model.dataset import prepare_modeling_frame
from ullebets_v2.ev_model.market_walk_forward import (
    select_market_classifier_bets,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit one frozen EV model candidate."
    )
    parser.add_argument("--offline-v1-dir", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-name", default="logistic_market")
    parser.add_argument("--minimum-ev", type=float, default=0.075)
    parser.add_argument("--maximum-ev", type=float)
    parser.add_argument(
        "--history-availability-buffer-hours",
        type=float,
        default=3.0,
    )
    return parser.parse_args()


def _cluster_bootstrap(
    selections: pd.DataFrame,
    *,
    iterations: int = 50_000,
) -> dict[str, float]:
    clustered = (
        selections.groupby("exposure_match_id")["realized_roi_units"]
        .agg(["sum", "size"])
        .to_numpy(dtype=float)
    )
    rng = np.random.default_rng(20260730)
    rois = np.empty(iterations, dtype=float)
    for iteration in range(iterations):
        sampled = clustered[
            rng.integers(0, len(clustered), len(clustered))
        ]
        rois[iteration] = sampled[:, 0].sum() / sampled[:, 1].sum() * 100.0
    return {
        "low_95_pct": float(np.quantile(rois, 0.025)),
        "median_pct": float(np.quantile(rois, 0.5)),
        "high_95_pct": float(np.quantile(rois, 0.975)),
        "probability_positive": float((rois > 0.0).mean()),
    }


def _markdown(report: dict[str, object]) -> str:
    performance = report["performance"]
    timing = report["timing"]
    duplicates = report["duplicates"]
    settlement = report["settlement"]
    features = report["features"]
    clv = report["clv"]
    bootstrap = report["cluster_bootstrap"]
    return "\n".join(
        [
            "# Frozen EV Candidate Audit",
            "",
            "## Configuration",
            "",
            f"- Model: `{report['configuration']['model_name']}`",
            f"- Minimum EV: `{report['configuration']['minimum_ev']:.1%}`",
            f"- Maximum EV: "
            f"`{report['configuration']['maximum_ev']:.1%}`"
            if report["configuration"]["maximum_ev"] is not None
            else "- Maximum EV: `none`",
            "- Training window: `90 days`",
            "- Recency half-life: `45 days`",
            "- Feature set: `compact snapshot-as-of leakage-safe`",
            f"- History availability buffer: "
            f"`{features['availability_buffer_hours']:.1f} hours`",
            "",
            "## Performance",
            "",
            f"- Bets: `{performance['bets']}`",
            f"- Unique matches: `{performance['unique_matches']}`",
            f"- PnL: `{performance['pnl_units']:.2f}` units",
            f"- ROI: `{performance['roi_pct']:.2f}%`",
            f"- Positive windows: `{performance['positive_windows']}/"
            f"{performance['windows']}`",
            f"- Match-clustered 95% interval: "
            f"`{bootstrap['low_95_pct']:.2f}%` to "
            f"`{bootstrap['high_95_pct']:.2f}%`",
            "",
            "## Integrity",
            "",
            f"- Prematch odds: `{timing['before_match_start']}`",
            f"- At/after kickoff: `{timing['at_or_after_match_start']}`",
            f"- Missing snapshot time: `{timing['missing_snapshot_time']}`",
            f"- Missing match start: `{timing['missing_match_start_time']}`",
            f"- Duplicate market exposures: "
            f"`{duplicates['duplicate_market_exposures']}`",
            f"- Duplicate side exposures: "
            f"`{duplicates['duplicate_side_exposures']}`",
            f"- Settlement mismatches: `{settlement['mismatches']}`",
            f"- Forbidden model features: "
            f"`{features['forbidden_columns']}`",
            f"- Training rows at/after target match: "
            f"`{features['training_rows_at_or_after_match']}`",
            f"- History observations at/after snapshot used: "
            f"`{features['history_observations_at_or_after_snapshot_used']}`",
            f"- History observations excluded by snapshot: "
            f"`{features['history_observations_excluded_by_snapshot']}`",
            "",
            "## CLV",
            "",
            f"- Rows with CLV: `{clv['rows_with_clv']}`",
            f"- CLV coverage: `{clv['coverage_pct']:.2f}%`",
            "",
            "## Decision",
            "",
            "Shadow/forward-test candidate only. The clustered interval includes "
            "zero, CLV coverage is insufficient, May has already been reused by "
            "earlier experiments, and the configuration was selected after "
            "multiple comparisons.",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    predictions = pd.read_parquet(args.predictions)
    model_predictions = predictions[
        predictions["model_name"].eq(args.model_name)
    ]
    selections = select_market_classifier_bets(
        model_predictions,
        minimum_ev=args.minimum_ev,
        maximum_ev=args.maximum_ev,
    )

    features = pd.read_parquet(
        args.offline_v1_dir / "features" / "market_points_primary.parquet"
    )
    lines = pd.read_parquet(
        args.offline_v1_dir / "normalized" / "market_lines.parquet"
    )
    team_stats = pd.read_parquet(
        args.offline_v1_dir / "normalized" / "team_stats_long.parquet"
    )
    modeling_frame, _ = prepare_modeling_frame(
        annotate_backtest_timing(features, lines)
    )
    model_features, asof_audit = build_asof_compact_model_features(
        modeling_frame,
        team_stats,
        availability_buffer_hours=(
            args.history_availability_buffer_hours
        ),
    )
    if asof_audit["history_observations_at_or_after_snapshot_used"]:
        raise RuntimeError(
            "snapshot-relative feature leakage detected in candidate audit"
        )
    report = audit_candidate(
        selections,
        modeling_frame,
        feature_columns=model_features.columns,
    )
    report["features"].update(asof_audit)
    window_roi = (
        selections.groupby(["test_start", "test_end"])
        ["realized_roi_units"]
        .mean()
        .mul(100.0)
    )
    report["configuration"] = {
        "model_name": args.model_name,
        "minimum_ev": args.minimum_ev,
        "maximum_ev": args.maximum_ev,
        "train_window_days": 90,
        "recency_half_life_days": 45,
        "feature_set": "compact_snapshot_asof",
        "history_availability_buffer_hours": (
            args.history_availability_buffer_hours
        ),
    }
    report["performance"] = {
        "bets": int(len(selections)),
        "unique_matches": int(selections["exposure_match_id"].nunique()),
        "pnl_units": float(selections["realized_roi_units"].sum()),
        "roi_pct": float(selections["realized_roi_units"].mean() * 100.0),
        "wins": int(selections["settlement_result"].eq("win").sum()),
        "losses": int(selections["settlement_result"].eq("loss").sum()),
        "pushes": int(selections["settlement_result"].eq("push").sum()),
        "windows": int(len(window_roi)),
        "positive_windows": int((window_roi > 0.0).sum()),
        "window_roi_pct": {
            f"{start}..{end}": float(value)
            for (start, end), value in window_roi.items()
        },
    }
    report["cluster_bootstrap"] = _cluster_bootstrap(selections)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    selections.to_parquet(
        args.output_dir / "frozen_candidate_selections.parquet",
        index=False,
    )
    (args.output_dir / "candidate_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (args.output_dir / "candidate_audit.md").write_text(
        _markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
