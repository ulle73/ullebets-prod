from __future__ import annotations

import argparse
from datetime import timedelta, timezone, datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import joblib
import numpy as np
import pandas as pd
import sklearn

from ullebets_v1.audit.odds_timing import annotate_backtest_timing
from ullebets_v2.ev_model.asof_features import (
    build_asof_compact_model_features,
)
from ullebets_v2.ev_model.dataset import prepare_modeling_frame
from ullebets_v2.ev_model.features import find_forbidden_feature_columns
from ullebets_v2.ev_model.market_classifier import (
    build_market_classifier_frame,
    build_market_prediction_frame,
)
from ullebets_v2.ev_model.shadow_candidate import (
    score_shadow_candidate,
    train_shadow_candidate,
)


MODEL_ID = "ev_logistic_recency45_asof_capped_v3"
MAXIMUM_EV = 0.25


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and serialize the frozen EV shadow candidate."
    )
    parser.add_argument("--offline-v1-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cutoff-date")
    parser.add_argument("--candidate-audit", type=Path)
    parser.add_argument("--robustness-audit", type=Path)
    parser.add_argument(
        "--history-availability-buffer-hours",
        type=float,
        default=3.0,
    )
    return parser.parse_args()


def _fingerprint(frame: pd.DataFrame) -> str:
    columns = [
        "sample_key",
        "match_date",
        "stat_key",
        "period",
        "scope",
        "line_value",
        "actual_value",
    ]
    hashed = pd.util.hash_pandas_object(
        frame[columns].sort_values("sample_key"),
        index=False,
    )
    return hashlib.sha256(hashed.to_numpy().tobytes()).hexdigest()


def _historical_evidence(path: Path | None) -> dict[str, object]:
    if path is None:
        return {"status": "not_attached"}
    report = json.loads(path.read_text(encoding="utf-8"))
    performance = report["performance"]
    bootstrap = report["cluster_bootstrap"]
    clv = report["clv"]
    return {
        "status": "shadow_candidate_only",
        "audit_report": str(path),
        "bets": performance["bets"],
        "unique_matches": performance["unique_matches"],
        "pnl_units": performance["pnl_units"],
        "roi_pct": performance["roi_pct"],
        "positive_windows": performance["positive_windows"],
        "windows": performance["windows"],
        "clustered_95_interval_pct": [
            bootstrap["low_95_pct"],
            bootstrap["high_95_pct"],
        ],
        "bootstrap_probability_positive": (
            bootstrap["probability_positive"]
        ),
        "clv_coverage_pct": clv["coverage_pct"],
    }


def _robustness_evidence(path: Path | None) -> dict[str, object]:
    if path is None:
        return {"status": "not_attached"}
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        "status": "historical_stress_only",
        "audit_report": str(path),
        "calibration": report["calibration"],
        "odds_haircut_sensitivity": report[
            "odds_haircut_sensitivity"
        ],
        "match_concentration": report["match_concentration"],
        "risk": report["risk"],
    }


def main() -> int:
    args = parse_args()
    features = pd.read_parquet(
        args.offline_v1_dir / "features" / "market_points_primary.parquet"
    )
    lines = pd.read_parquet(
        args.offline_v1_dir / "normalized" / "market_lines.parquet"
    )
    team_stats = pd.read_parquet(
        args.offline_v1_dir / "normalized" / "team_stats_long.parquet"
    )
    modeling_frame, dataset_audit = prepare_modeling_frame(
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
            "snapshot-relative feature leakage detected during training"
        )
    forbidden = find_forbidden_feature_columns(model_features.columns)
    if forbidden:
        raise RuntimeError(f"forbidden shadow model features: {forbidden}")
    training_frame = build_market_classifier_frame(
        modeling_frame,
        model_features,
    )
    cutoff = (
        pd.Timestamp(args.cutoff_date).normalize()
        if args.cutoff_date
        else pd.to_datetime(modeling_frame["match_date"]).max().normalize()
        + timedelta(days=1)
    )
    bundle = train_shadow_candidate(
        training_frame,
        cutoff_date=cutoff.date(),
    )

    training_days = pd.to_datetime(training_frame["match_date"]).dt.normalize()
    artifact_training_rows = training_frame[
        training_days.ge(pd.Timestamp(bundle.training_start))
        & training_days.le(pd.Timestamp(bundle.training_end))
        & training_frame["is_over_win"].notna()
    ]
    smoke_markets = modeling_frame.tail(10).drop(
        columns=["actual_value"],
        errors="ignore",
    )
    smoke_features = model_features.tail(10)
    prediction_frame = build_market_prediction_frame(
        smoke_markets,
        smoke_features,
    )
    smoke_selections = score_shadow_candidate(
        bundle,
        prediction_frame,
        minimum_ev=-1.0,
        maximum_ev=float("inf"),
    )
    if len(smoke_selections) != len(prediction_frame):
        raise RuntimeError("shadow candidate smoke scoring lost market rows")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = args.output_dir / f"{MODEL_ID}.joblib"
    joblib.dump(bundle, artifact_path)
    restored = joblib.load(artifact_path)
    restored_smoke = score_shadow_candidate(
        restored,
        prediction_frame,
        minimum_ev=-1.0,
        maximum_ev=float("inf"),
    )
    if not restored_smoke["predicted_win_probability"].equals(
        smoke_selections["predicted_win_probability"]
    ):
        raise RuntimeError("serialized shadow candidate changed predictions")

    manifest = {
        "model_id": MODEL_ID,
        "status": "shadow_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact": artifact_path.name,
        "configuration": {
            "algorithm": "regularized_logistic_regression",
            "train_window_days": bundle.train_window_days,
            "recency_half_life_days": bundle.recency_half_life_days,
            "minimum_ev": bundle.minimum_ev,
            "maximum_ev": MAXIMUM_EV,
            "probability_calibration": "none",
            "feature_set": "compact_snapshot_asof_leakage_safe",
            "history_availability_buffer_hours": (
                args.history_availability_buffer_hours
            ),
        },
        "training": {
            "start": bundle.training_start,
            "end": bundle.training_end,
            "rows": bundle.training_rows,
            "source_fingerprint_sha256": _fingerprint(
                artifact_training_rows
            ),
        },
        "features": list(model_features.columns),
        "forbidden_features": forbidden,
        "dataset_audit": {
            "input_rows": dataset_audit.input_rows,
            "eligible_rows": dataset_audit.eligible_rows,
            "duplicate_rows_removed": dataset_audit.duplicate_rows_removed,
            "output_rows": dataset_audit.output_rows,
        },
        "asof_feature_audit": asof_audit,
        "historical_evidence": _historical_evidence(
            args.candidate_audit
        ),
        "robustness_evidence": _robustness_evidence(
            args.robustness_audit
        ),
        "promotion_requirements": [
            "new untouched forward bets",
            "complete prematch closing-line capture",
            "zero timing, mapping, duplicate, and feature-leakage audit failures",
            "positive match-clustered uncertainty interval",
        ],
        "runtime_versions": {
            "joblib": joblib.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit-learn": sklearn.__version__,
        },
        "smoke_test": {
            "markets_scored": len(prediction_frame),
            "selections_with_disabled_gate": len(restored_smoke),
            "serialization_round_trip": "passed",
        },
    }
    (args.output_dir / "model_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
