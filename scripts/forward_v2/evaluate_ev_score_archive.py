from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

import joblib

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.config import V2Config
from ullebets_v2.ev_model.domain import (
    extract_categorical_training_domain,
)
from ullebets_v2.ev_model.policy_registry import (
    load_policy_registry,
)
from ullebets_v2.ev_model.score_evaluation import (
    build_registered_policy_evaluation,
    build_score_policy_evaluation,
    fingerprint_policy_registry,
)
from ullebets_v2.jobs.job_runs import (
    build_job_run_finished_update,
    build_job_run_started_doc,
)
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.collections import (
    AUDIT_REPORTS,
    CLOSING_LINES,
    EV_MODEL_SCORES,
    JOB_RUNS,
    MATCH_RESULTS_CANONICAL,
    MATCH_STATS_CANONICAL,
)
from ullebets_v2.storage.mongo import get_database


DEFAULT_MODEL_IDS = (
    "ev_logistic_recency45_asof_capped_v3",
    "ev_nested_logistic_recency45_asof_capped_v4_shadow",
    "ev_ensemble_v3_75_v4_25_shadow",
    "ev_scope_interaction_recency45_asof_capped_v6_shadow",
)


def _load_training_domains(
    repo_root: Path,
    model_ids: list[str],
) -> dict[str, dict[str, tuple[str, ...]]]:
    domains: dict[str, dict[str, tuple[str, ...]]] = {}
    for model_id in model_ids:
        artifact_path = (
            repo_root
            / "models"
            / "ev"
            / model_id
            / f"{model_id}.joblib"
        )
        if not artifact_path.exists():
            raise RuntimeError(
                f"model artifact missing for domain audit: {artifact_path}"
            )
        domains[model_id] = extract_categorical_training_domain(
            joblib.load(artifact_path)
        )
    return domains


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate immutable score-only model policies against canonical "
            "post-match outcomes without mutating score rows."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--model-id", action="append", default=[])
    parser.add_argument("--minimum-ev", type=float, default=0.075)
    parser.add_argument("--maximum-ev", type=float, default=0.25)
    parser.add_argument(
        "--policy-registry",
        type=Path,
        default=(
            Path("models")
            / "ev"
            / "score_policy_registry_v5.json"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()
    database = get_database(config)
    model_ids = list(args.model_id or DEFAULT_MODEL_IDS)
    training_domain_by_model = _load_training_domains(
        args.repo_root,
        model_ids,
    )
    scores = list(
        database[EV_MODEL_SCORES].find(
            {"model_id": {"$in": model_ids}},
            projection={"_id": 0},
        )
    )
    match_keys = sorted(
        {
            str(row["match_key"])
            for row in scores
            if row.get("match_key")
        }
    )
    match_query = {"match_key": {"$in": match_keys}}
    match_stats = (
        list(
            database[MATCH_STATS_CANONICAL].find(
                match_query,
                projection={"_id": 0},
            )
        )
        if match_keys
        else []
    )
    match_results = (
        list(
            database[MATCH_RESULTS_CANONICAL].find(
                match_query,
                projection={"_id": 0},
            )
        )
        if match_keys
        else []
    )
    offer_keys = sorted(
        {
            str(row["offer_key"])
            for row in scores
            if row.get("offer_key")
        }
    )
    closing_lines = (
        list(
            database[CLOSING_LINES].find(
                {"offer_key": {"$in": offer_keys}},
                projection={"_id": 0},
            )
        )
        if offer_keys
        else []
    )
    report = build_score_policy_evaluation(
        scores=scores,
        match_stats=match_stats,
        match_results=match_results,
        model_ids=model_ids,
        minimum_ev=args.minimum_ev,
        maximum_ev=args.maximum_ev,
        training_domain_by_model=training_domain_by_model,
    )
    registry = load_policy_registry(args.policy_registry)
    policies = registry.get("policies")
    if not isinstance(policies, list) or not policies:
        raise RuntimeError(
            "score policy registry has no policies"
        )
    audit_status_by_model: dict[str, str] = {}
    audit_cursor = database[AUDIT_REPORTS].find(
        {
            "audit_type": "ev_forward_model_performance",
            "scope_key": {"$in": model_ids},
        },
        projection={
            "_id": 0,
            "scope_key": 1,
            "status": 1,
            "generated_at": 1,
        },
    ).sort("generated_at", -1)
    for audit in audit_cursor:
        model_id = str(audit.get("scope_key") or "")
        if model_id and model_id not in audit_status_by_model:
            audit_status_by_model[model_id] = str(
                audit.get("status") or "missing"
            )
    registered_policy_evaluation = (
        build_registered_policy_evaluation(
            scores=scores,
            match_stats=match_stats,
            match_results=match_results,
            policies=policies,
            closing_lines=closing_lines,
            promotion_gate=registry.get("promotion_gate"),
            multiple_comparison_family_size=int(
                registry.get(
                    "multiple_comparison_family_size"
                )
                or len(policies)
            ),
            audit_status_by_model=audit_status_by_model,
            training_domain_by_model=training_domain_by_model,
        )
    )
    registered_policy_evaluation["registry_id"] = registry.get(
        "registry_id"
    )
    registered_policy_evaluation[
        "policy_registry_fingerprint"
    ] = fingerprint_policy_registry(registry)
    registered_policy_evaluation["registered_at"] = (
        registry.get("registered_at")
    )
    registered_policy_evaluation[
        "multiple_comparison_family_size"
    ] = registry.get("multiple_comparison_family_size")
    report["registered_policy_evaluation"] = (
        registered_policy_evaluation
    )
    now = datetime.now(tz=UTC)
    report["generated_at"] = now.isoformat()
    report["dry_run"] = args.dry_run
    report_path = (
        config.reports_dir / "ev-score-policy-evaluation.json"
    )
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report["local_report"] = str(report_path)

    if not args.dry_run:
        run_doc = build_job_run_started_doc(
            job_name="evaluate_ev_score_archive",
            source_workflow="ev-shadow-settlement.yml",
            target_window={
                "model_ids": model_ids,
                "match_count": len(match_keys),
                "policy_registry_id": registry.get(
                    "registry_id"
                ),
            },
            job_args={
                "minimum_ev": args.minimum_ev,
                "maximum_ev": args.maximum_ev,
            },
            now=now,
        )
        database[JOB_RUNS].insert_one(run_doc)
        try:
            invalid_timing = sum(
                int(row["in_domain_scores"])
                - int(row["valid_timing_scores"])
                for row in report["models"]
            )
            out_of_domain_scores = sum(
                int(row["domain"]["scores_out_of_domain"])
                for row in report["models"]
            )
            database[AUDIT_REPORTS].update_one(
                {
                    "audit_type": "ev_score_policy_evaluation",
                    "scope_key": "v3_vs_v4_shadow",
                    "report_date": now.date().isoformat(),
                },
                {
                    "$set": {
                        "audit_type": (
                            "ev_score_policy_evaluation"
                        ),
                        "scope_key": "v3_vs_v4_shadow",
                        "report_date": now.date().isoformat(),
                        "status": (
                            "ok"
                            if (
                                invalid_timing == 0
                                and out_of_domain_scores == 0
                            )
                            else "warn"
                        ),
                        "findings": [
                            finding
                            for finding, present in (
                                (
                                    "Score timing violations detected.",
                                    invalid_timing > 0,
                                ),
                                (
                                    "Out-of-domain scores excluded from "
                                    "policy evidence.",
                                    out_of_domain_scores > 0,
                                ),
                            )
                            if present
                        ],
                        "metrics": report,
                        "generated_at": now,
                    }
                },
                upsert=True,
            )
            database[JOB_RUNS].update_one(
                {"run_id": run_doc["run_id"]},
                build_job_run_finished_update(
                    status="succeeded",
                    metrics=report,
                ),
            )
        except Exception as exc:
            database[JOB_RUNS].update_one(
                {"run_id": run_doc["run_id"]},
                build_job_run_finished_update(
                    status="failed",
                    error={
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                ),
            )
            raise
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
