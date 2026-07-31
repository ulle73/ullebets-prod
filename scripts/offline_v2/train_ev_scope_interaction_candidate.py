from __future__ import annotations

import argparse
from datetime import UTC, timedelta, datetime
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

from ullebets_v2.ev_model.categorical_interactions import (
    add_categorical_interaction_features,
)
from ullebets_v2.ev_model.domain import (
    extract_categorical_training_domain,
)
from ullebets_v2.ev_model.market_classifier import (
    CategoricalInteractionMarketClassifier,
)
from ullebets_v2.ev_model.nested_regularization import (
    NestedRegularizationConfig,
    train_nested_regularization_candidate,
)
from ullebets_v2.ev_model.shadow_candidate import (
    ShadowCandidateBundle,
    score_shadow_candidate_sides,
)


MODEL_ID = (
    "ev_scope_interaction_recency45_asof_capped_v6_shadow"
)
SOURCE_COLUMNS = (
    "line_value",
    "market_fair_probability_over",
    "market_anchor_lambda",
    "baseline_lambda",
    "history_role_expected_10",
    "history_all_expected_10",
    "history_role_trend_3_10",
    "history_all_trend_3_10",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train the frozen score-only V6 scope-interaction "
            "challenger."
        )
    )
    parser.add_argument(
        "--market-frame",
        type=Path,
        default=Path(
            "data/v2/ev_model/research_cache/"
            "asof_market_frame.parquet"
        ),
    )
    parser.add_argument(
        "--v4-manifest",
        type=Path,
        default=Path(
            "models/ev/"
            "ev_nested_logistic_recency45_asof_capped_v4_shadow/"
            "model_manifest.json"
        ),
    )
    parser.add_argument(
        "--candidate-falsification",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_060_period_scope_interactions/"
            "falsification.json"
        ),
    )
    parser.add_argument(
        "--candidate-audit",
        type=Path,
        default=Path(
            "data/v2/ev_model/"
            "experiment_061_scope_interaction_audit/"
            "scope_interaction_audit.json"
        ),
    )
    parser.add_argument("--cutoff-date")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/ev") / MODEL_ID,
    )
    return parser.parse_args()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    raw_market_frame = pd.read_parquet(args.market_frame)
    snapshot_time = pd.to_datetime(
        raw_market_frame["odds_snapshot_time"],
        utc=True,
        errors="coerce",
    )
    kickoff = pd.to_datetime(
        raw_market_frame["match_start_time"],
        utc=True,
        errors="coerce",
    )
    if (
        snapshot_time.isna().any()
        or kickoff.isna().any()
        or snapshot_time.ge(kickoff).any()
    ):
        raise RuntimeError(
            "V6 training requires strictly prematch market rows"
        )
    engineered = add_categorical_interaction_features(
        raw_market_frame,
        category_column="scope",
        source_columns=SOURCE_COLUMNS,
        deviation_values=("home", "away"),
    )
    cutoff = (
        pd.Timestamp(args.cutoff_date).normalize()
        if args.cutoff_date
        else pd.to_datetime(
            engineered["match_date"]
        ).max().normalize()
        + timedelta(days=1)
    )
    config = NestedRegularizationConfig()
    result = train_nested_regularization_candidate(
        engineered,
        cutoff_date=cutoff.date(),
        config=config,
    )
    base_bundle = result.bundle
    wrapped_model = CategoricalInteractionMarketClassifier(
        name="nested_logistic_scope_deviations",
        model=base_bundle.model,
        category_column="scope",
        source_columns=SOURCE_COLUMNS,
        deviation_values=("home", "away"),
    )
    bundle = ShadowCandidateBundle(
        model=wrapped_model,
        training_start=base_bundle.training_start,
        training_end=base_bundle.training_end,
        training_rows=base_bundle.training_rows,
        train_window_days=base_bundle.train_window_days,
        recency_half_life_days=(
            base_bundle.recency_half_life_days
        ),
        minimum_ev=0.075,
    )
    training_days = pd.to_datetime(
        raw_market_frame["match_date"]
    ).dt.normalize()
    artifact_training_rows = raw_market_frame[
        training_days.ge(pd.Timestamp(bundle.training_start))
        & training_days.le(pd.Timestamp(bundle.training_end))
        & raw_market_frame["is_over_win"].notna()
    ]

    smoke_frame = raw_market_frame.tail(10).copy()
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
    if not np.allclose(
        smoke_scores["predicted_win_probability"],
        restored_scores["predicted_win_probability"],
        rtol=0.0,
        atol=1e-12,
    ):
        raise RuntimeError(
            "serialized V6 changed predicted probabilities"
        )

    v4_manifest = _read_json(args.v4_manifest)
    derived_features = [
        "category_interaction__scope__"
        f"{scope}__{source_column}"
        for source_column in SOURCE_COLUMNS
        for scope in ("home", "away")
    ]
    manifest = {
        "artifact": artifact_path.name,
        "artifact_sha256": _sha256_file(artifact_path),
        "configuration": {
            "algorithm": (
                "nested_temporal_logistic_with_regularized_"
                "scope_slope_deviations"
            ),
            "base_feature_set": (
                "compact_snapshot_asof_leakage_safe"
            ),
            "category_column": "scope",
            "deviation_values": ["home", "away"],
            "interaction_source_columns": list(SOURCE_COLUMNS),
            "train_window_days": config.train_window_days,
            "validation_window_days": (
                config.validation_window_days
            ),
            "recency_half_life_days": (
                config.recency_half_life_days
            ),
            "c_grid": list(config.c_grid),
            "selected_logistic_c": result.selected_logistic_c,
            "regularization_selection_source": (
                result.selection_source
            ),
            "minimum_ev": 0.075,
            "maximum_ev": 0.25,
            "probability_calibration": "none",
            "history_availability_buffer_hours": 3.0,
        },
        "created_at": datetime.now(tz=UTC).isoformat(),
        "derived_runtime_features": derived_features,
        "features": list(v4_manifest["features"]),
        "forbidden_features": [],
        "forward_mode": "score_only",
        "historical_evidence": {
            "status": "historical_exploratory_only",
            "comparison_family_size": 124,
            "falsification": _read_json(
                args.candidate_falsification
            ),
            "scope_interaction_audit": _read_json(
                args.candidate_audit
            ),
        },
        "model_id": MODEL_ID,
        "promotion_requirements": [
            "new untouched in-domain score-level forward outcomes",
            "complete prematch closing-line capture",
            (
                "zero timing, mapping, duplicate, feature-leakage, "
                "and domain failures"
            ),
            "positive match-clustered lower confidence bound",
            "multiple-comparison-adjusted forward evidence",
        ],
        "runtime_versions": {
            "joblib": joblib.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit-learn": sklearn.__version__,
        },
        "smoke_test": {
            "markets_scored": int(len(smoke_frame)),
            "serialization_round_trip": "passed",
            "side_scores": int(len(restored_scores)),
        },
        "status": "shadow_only",
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
        "training_domain": {
            field: list(values)
            for field, values in (
                extract_categorical_training_domain(bundle).items()
            )
        },
    }
    manifest_path = args.output_dir / "model_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "model_id": MODEL_ID,
                "artifact": str(artifact_path),
                "artifact_sha256": manifest["artifact_sha256"],
                "smoke_test": manifest["smoke_test"],
                "training": manifest["training"],
                "training_domain": manifest["training_domain"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
