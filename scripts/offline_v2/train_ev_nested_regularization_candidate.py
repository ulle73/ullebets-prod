from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
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
from ullebets_v2.ev_model.features import (
    find_forbidden_feature_columns,
)
from ullebets_v2.ev_model.market_classifier import (
    build_market_classifier_frame,
    build_market_prediction_frame,
)
from ullebets_v2.ev_model.nested_regularization import (
    NestedRegularizationConfig,
    train_nested_regularization_candidate,
)
from ullebets_v2.ev_model.shadow_candidate import (
    score_shadow_candidate_sides,
)


MODEL_ID = (
    "ev_nested_logistic_recency45_asof_capped_v4_shadow"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train the nested-regularization score-only challenger."
        )
    )
    parser.add_argument("--offline-v1-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cutoff-date")
    parser.add_argument("--candidate-audit", type=Path)
    parser.add_argument("--robustness-audit", type=Path)
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
    return hashlib.sha256(
        hashed.to_numpy().tobytes()
    ).hexdigest()


def _read_optional_json(path: Path | None) -> dict[str, object]:
    if path is None:
        return {"status": "not_attached"}
    return {
        "status": "historical_exploratory_only",
        "path": str(path),
        "report": json.loads(path.read_text(encoding="utf-8")),
    }


def main() -> int:
    args = parse_args()
    features = pd.read_parquet(
        args.offline_v1_dir
        / "features"
        / "market_points_primary.parquet"
    )
    lines = pd.read_parquet(
        args.offline_v1_dir
        / "normalized"
        / "market_lines.parquet"
    )
    team_stats = pd.read_parquet(
        args.offline_v1_dir
        / "normalized"
        / "team_stats_long.parquet"
    )
    modeling_frame, dataset_audit = prepare_modeling_frame(
        annotate_backtest_timing(features, lines)
    )
    model_features, asof_audit = (
        build_asof_compact_model_features(
            modeling_frame,
            team_stats,
            availability_buffer_hours=3.0,
        )
    )
    forbidden = find_forbidden_feature_columns(
        model_features.columns
    )
    if (
        forbidden
        or asof_audit[
            "history_observations_at_or_after_snapshot_used"
        ]
    ):
        raise RuntimeError(
            "challenger training feature integrity failed"
        )
    training_frame = build_market_classifier_frame(
        modeling_frame,
        model_features,
    )
    cutoff = (
        pd.Timestamp(args.cutoff_date).normalize()
        if args.cutoff_date
        else pd.to_datetime(
            modeling_frame["match_date"]
        ).max().normalize()
        + timedelta(days=1)
    )
    config = NestedRegularizationConfig()
    result = train_nested_regularization_candidate(
        training_frame,
        cutoff_date=cutoff.date(),
        config=config,
    )
    bundle = result.bundle

    training_days = pd.to_datetime(
        training_frame["match_date"]
    ).dt.normalize()
    artifact_training_rows = training_frame[
        training_days.ge(pd.Timestamp(bundle.training_start))
        & training_days.le(pd.Timestamp(bundle.training_end))
        & training_frame["is_over_win"].notna()
    ]
    smoke_markets = modeling_frame.tail(10).drop(
        columns=["actual_value"],
        errors="ignore",
    )
    smoke_frame = build_market_prediction_frame(
        smoke_markets,
        model_features.tail(10),
    )
    smoke_frame["odds_snapshot_time"] = pd.to_datetime(
        smoke_frame["odds_snapshot_time"],
        utc=True,
    )
    smoke_frame["match_start_time"] = pd.to_datetime(
        smoke_frame["match_start_time"],
        utc=True,
    )
    smoke_scores = score_shadow_candidate_sides(
        bundle,
        smoke_frame,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = args.output_dir / f"{MODEL_ID}.joblib"
    joblib.dump(bundle, artifact_path)
    restored = joblib.load(artifact_path)
    restored_scores = score_shadow_candidate_sides(
        restored,
        smoke_frame,
    )
    if not restored_scores[
        "predicted_win_probability"
    ].equals(smoke_scores["predicted_win_probability"]):
        raise RuntimeError(
            "serialized challenger changed predictions"
        )

    manifest = {
        "model_id": MODEL_ID,
        "status": "shadow_only",
        "forward_mode": "score_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact": artifact_path.name,
        "configuration": {
            "algorithm": (
                "nested_temporal_regularized_logistic_regression"
            ),
            "train_window_days": config.train_window_days,
            "validation_window_days": (
                config.validation_window_days
            ),
            "recency_half_life_days": (
                config.recency_half_life_days
            ),
            "c_grid": list(config.c_grid),
            "default_logistic_c": config.default_logistic_c,
            "selected_logistic_c": (
                result.selected_logistic_c
            ),
            "regularization_selection_source": (
                result.selection_source
            ),
            "minimum_ev": 0.075,
            "maximum_ev": 0.25,
            "probability_calibration": "none",
            "feature_set": (
                "compact_snapshot_asof_leakage_safe"
            ),
            "history_availability_buffer_hours": 3.0,
        },
        "training": {
            "start": bundle.training_start,
            "end": bundle.training_end,
            "rows": bundle.training_rows,
            "validation_start": result.validation_start,
            "validation_end": result.validation_end,
            "selected_validation_brier": (
                result.selected_validation_brier
            ),
            "candidate_metrics": list(
                result.candidate_metrics
            ),
            "source_fingerprint_sha256": _fingerprint(
                artifact_training_rows
            ),
        },
        "features": list(model_features.columns),
        "forbidden_features": forbidden,
        "dataset_audit": dataset_audit.__dict__,
        "asof_feature_audit": asof_audit,
        "historical_evidence": _read_optional_json(
            args.candidate_audit
        ),
        "robustness_evidence": _read_optional_json(
            args.robustness_audit
        ),
        "promotion_requirements": [
            "new untouched score-level forward outcomes",
            "complete prematch closing-line capture",
            "zero timing, mapping, duplicate, and feature-leakage failures",
            "positive match-clustered lower confidence bound",
        ],
        "runtime_versions": {
            "joblib": joblib.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit-learn": sklearn.__version__,
        },
        "smoke_test": {
            "markets_scored": len(smoke_frame),
            "side_scores": len(restored_scores),
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
