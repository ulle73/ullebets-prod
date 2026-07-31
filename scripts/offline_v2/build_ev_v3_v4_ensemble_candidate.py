from __future__ import annotations

import argparse
from datetime import UTC, datetime
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

from ullebets_v2.ev_model.domain import (
    extract_categorical_training_domain,
)
from ullebets_v2.ev_model.market_classifier import (
    WeightedEnsembleMarketClassifier,
)
from ullebets_v2.ev_model.shadow_candidate import (
    ShadowCandidateBundle,
    score_shadow_candidate_sides,
)


MODEL_ID = "ev_ensemble_v3_75_v4_25_shadow"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the frozen 75% V3 / 25% V4 score-only ensemble."
        )
    )
    parser.add_argument(
        "--v3-artifact",
        type=Path,
        default=(
            Path("models/ev/ev_logistic_recency45_asof_capped_v3")
            / "ev_logistic_recency45_asof_capped_v3.joblib"
        ),
    )
    parser.add_argument(
        "--v4-artifact",
        type=Path,
        default=(
            Path(
                "models/ev/"
                "ev_nested_logistic_recency45_asof_capped_v4_shadow"
            )
            / (
                "ev_nested_logistic_recency45_asof_capped_"
                "v4_shadow.joblib"
            )
        ),
    )
    parser.add_argument(
        "--smoke-frame",
        type=Path,
        default=(
            Path("data/v2/ev_model/research_cache")
            / "asof_market_frame.parquet"
        ),
    )
    parser.add_argument(
        "--historical-falsification",
        type=Path,
        default=(
            Path("data/v2/ev_model/experiment_050_v3_v4_ensembles")
            / "falsification.json"
        ),
    )
    parser.add_argument(
        "--paired-comparison",
        type=Path,
        default=(
            Path("data/v2/ev_model/experiment_050_v3_v4_ensembles")
            / "paired_vs_v3.json"
        ),
    )
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


def _manifest_path(artifact: Path) -> Path:
    return artifact.parent / "model_manifest.json"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_components(
    v3_manifest: dict[str, object],
    v4_manifest: dict[str, object],
) -> None:
    if (
        v3_manifest.get("status") != "shadow_only"
        or v4_manifest.get("status") != "shadow_only"
    ):
        raise ValueError("ensemble components must be shadow models")
    if v3_manifest.get("features") != v4_manifest.get("features"):
        raise ValueError(
            "ensemble components must have identical feature contracts"
        )
    v3_training = dict(v3_manifest.get("training") or {})
    v4_training = dict(v4_manifest.get("training") or {})
    for field in (
        "start",
        "end",
        "rows",
        "source_fingerprint_sha256",
    ):
        if v3_training.get(field) != v4_training.get(field):
            raise ValueError(
                f"ensemble component training mismatch: {field}"
            )


def main() -> int:
    args = parse_args()
    v3_manifest = _read_json(
        _manifest_path(args.v3_artifact)
    )
    v4_manifest = _read_json(
        _manifest_path(args.v4_artifact)
    )
    _validate_components(v3_manifest, v4_manifest)
    v3_bundle = joblib.load(args.v3_artifact)
    v4_bundle = joblib.load(args.v4_artifact)
    training = dict(v3_manifest["training"])

    ensemble = WeightedEnsembleMarketClassifier(
        name="weighted_v3_75_v4_25",
        models=(v3_bundle.model, v4_bundle.model),
        weights=(0.75, 0.25),
    )
    bundle = ShadowCandidateBundle(
        model=ensemble,
        training_start=str(training["start"]),
        training_end=str(training["end"]),
        training_rows=int(training["rows"]),
        train_window_days=90,
        recency_half_life_days=45.0,
        minimum_ev=0.075,
    )

    smoke_frame = pd.read_parquet(args.smoke_frame).tail(10)
    before = score_shadow_candidate_sides(
        bundle,
        smoke_frame,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = args.output_dir / f"{MODEL_ID}.joblib"
    joblib.dump(bundle, artifact_path)
    restored = joblib.load(artifact_path)
    after = score_shadow_candidate_sides(
        restored,
        smoke_frame,
    )
    if not np.allclose(
        before["predicted_win_probability"],
        after["predicted_win_probability"],
        rtol=0.0,
        atol=1e-12,
    ):
        raise RuntimeError(
            "ensemble serialization changed predicted probabilities"
        )

    historical = _read_json(args.historical_falsification)
    paired = _read_json(args.paired_comparison)
    manifest = {
        "artifact": artifact_path.name,
        "artifact_sha256": _sha256_file(artifact_path),
        "component_models": [
            {
                "model_id": v3_manifest["model_id"],
                "weight": 0.75,
                "artifact_sha256": _sha256_file(
                    args.v3_artifact
                ),
            },
            {
                "model_id": v4_manifest["model_id"],
                "weight": 0.25,
                "artifact_sha256": _sha256_file(
                    args.v4_artifact
                ),
            },
        ],
        "configuration": {
            "algorithm": "fixed_weight_probability_ensemble",
            "feature_set": (
                "compact_snapshot_asof_leakage_safe"
            ),
            "history_availability_buffer_hours": 3.0,
            "minimum_ev": 0.075,
            "maximum_ev": 0.25,
            "probability_calibration": "none",
            "train_window_days": 90,
            "recency_half_life_days": 45.0,
            "weights": {"v3": 0.75, "v4": 0.25},
        },
        "created_at": datetime.now(tz=UTC).isoformat(),
        "features": list(v3_manifest["features"]),
        "forbidden_features": [],
        "forward_mode": "score_only",
        "historical_evidence": {
            "status": "historical_exploratory_only",
            "experiment": "experiment_050_v3_v4_ensembles",
            "falsification": historical,
            "paired_v3_comparison": paired,
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
            "side_scores": int(len(after)),
        },
        "status": "shadow_only",
        "training": training,
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
                "training_domain": manifest["training_domain"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
