from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import joblib
import pandas as pd

from ullebets_v2.config import V2Config
from ullebets_v2.ev_model.domain import (
    audit_score_domain,
    extract_categorical_training_domain,
)
from ullebets_v2.ev_model.engineering import TEAM_STATS_KEYS
from ullebets_v2.ev_model.forward_predictions import (
    build_registered_policy_prediction_docs,
    build_forward_prediction_docs,
    exclude_previously_frozen_matches,
    persist_forward_prediction_docs,
    valid_frozen_match_keys,
    validate_model_runtime,
)
from ullebets_v2.ev_model.forward_scores import (
    build_forward_score_docs,
    persist_forward_score_docs,
)
from ullebets_v2.ev_model.market_walk_forward import (
    select_market_classifier_bets,
)
from ullebets_v2.ev_model.policy_registry import load_policy_registry
from ullebets_v2.ev_model.score_evaluation import (
    filter_policy_scores,
    fingerprint_policy_registry,
    select_online_policy,
)
from ullebets_v2.ev_model.shadow_candidate import (
    score_shadow_candidate_sides,
)
from ullebets_v2.ev_model.v2_forward_adapter import (
    build_v2_forward_model_frame,
)
from ullebets_v2.jobs.job_runs import (
    build_job_run_finished_update,
    build_job_run_started_doc,
)
from ullebets_v2.safety import (
    ensure_no_simulated_time_write,
    ensure_v2_database,
)
from ullebets_v2.storage.collections import (
    AUDIT_REPORTS,
    EV_MODEL_SCORES,
    FIXTURES_CANONICAL,
    FORWARD_BETS,
    HEALTH_REPORTS,
    JOB_RUNS,
    MARKET_SNAPSHOTS,
    MATCH_STATS_CANONICAL,
)
from ullebets_v2.storage.mongo import get_database


JOB_NAME = "score_ev_shadow_model"
SOURCE_WORKFLOW = "ev-shadow-forward.yml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze leakage-safe EV shadow predictions before kickoff."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--match-key", action="append", default=[])
    parser.add_argument("--now")
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--selection-policy-registry", type=Path)
    parser.add_argument("--selection-policy-id")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _as_utc(value: str | None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize("UTC")
    return parsed.tz_convert("UTC").to_pydatetime()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_rows(
    database: Any,
    *,
    now: datetime,
    match_keys: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    snapshot_query: dict[str, Any] = {
        "invalid_for_model": {"$ne": True},
        "snapshot_time": {"$lte": now},
        "captured_at": {"$lte": now},
        "match_start_time": {"$gt": now},
        "$expr": {"$lt": ["$snapshot_time", "$match_start_time"]},
    }
    if match_keys:
        snapshot_query["match_key"] = {"$in": match_keys}
    snapshots = list(
        database[MARKET_SNAPSHOTS].find(
            snapshot_query,
            projection={"_id": 0},
        )
    )
    target_keys = sorted(
        {
            str(row["match_key"])
            for row in snapshots
            if row.get("match_key")
        }
    )
    if not target_keys:
        return [], [], []

    fixtures = list(
        database[FIXTURES_CANONICAL].find(
            {},
            projection={
                "_id": 0,
                "match_key": 1,
                "start_time": 1,
                "home_team_key": 1,
                "away_team_key": 1,
                "home_team_name": 1,
                "away_team_name": 1,
                "league_name": 1,
            },
        )
    )
    stats = list(
        database[MATCH_STATS_CANONICAL].find(
            {
                "match_key": {"$nin": target_keys},
                "stat_key": {"$in": sorted(set(TEAM_STATS_KEYS.values()))},
                "period": {"$in": ["ALL", "1ST", "2ND"]},
                "scope": {"$in": ["home", "away", "total"]},
            },
            projection={
                "_id": 0,
                "match_key": 1,
                "stat_key": 1,
                "period": 1,
                "scope": 1,
                "actual_value": 1,
            },
        )
    )
    return snapshots, fixtures, stats


def _write_local_report(
    config: V2Config,
    run_id: str,
    summary: dict[str, Any],
) -> Path:
    path = config.reports_dir / f"ev-shadow-scoring-{run_id}.json"
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return path


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    ensure_no_simulated_time_write(
        time_override=args.now,
        dry_run=args.dry_run,
        job_name=JOB_NAME,
    )
    config.ensure_directories()
    now = _as_utc(args.now)
    artifact = (
        args.artifact
        or config.repo_root
        / "models"
        / "ev"
        / "ev_logistic_recency45_asof_capped_v3"
        / "ev_logistic_recency45_asof_capped_v3.joblib"
    )
    manifest_path = (
        args.manifest or artifact.parent / "model_manifest.json"
    )
    if not artifact.exists() or not manifest_path.exists():
        raise FileNotFoundError(
            f"shadow artifact or manifest is missing: {artifact}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "shadow_only":
        raise RuntimeError("only a shadow_only model may use this job")
    manifest_requires_score_only = (
        manifest.get("forward_mode") == "score_only"
    )
    if manifest_requires_score_only and not args.score_only:
        raise RuntimeError(
            "this challenger manifest requires --score-only"
        )
    if bool(args.selection_policy_registry) != bool(
        args.selection_policy_id
    ):
        raise RuntimeError(
            "selection policy registry and policy id must be provided together"
        )
    selection_policy = None
    selection_registry = None
    selection_registry_fingerprint = None
    if args.selection_policy_registry is not None:
        registry_path = (
            args.selection_policy_registry
            if args.selection_policy_registry.is_absolute()
            else config.repo_root / args.selection_policy_registry
        )
        selection_registry = load_policy_registry(registry_path)
        matching_policies = [
            row
            for row in selection_registry.get("policies", [])
            if str(row.get("policy_id")) == args.selection_policy_id
        ]
        if len(matching_policies) != 1:
            raise RuntimeError(
                "selection policy id must resolve to exactly one policy"
            )
        selection_policy = matching_policies[0]
        if str(selection_policy.get("model_id")) != str(
            manifest.get("model_id")
        ):
            raise RuntimeError(
                "selection policy model does not match scorer manifest"
            )
        selection_registry_fingerprint = fingerprint_policy_registry(
            selection_registry
        )
    validate_model_runtime(dict(manifest.get("runtime_versions") or {}))

    database = get_database(config)
    run_doc = build_job_run_started_doc(
        job_name=JOB_NAME,
        source_workflow=SOURCE_WORKFLOW,
        target_window={
            "created_at": now.isoformat(),
            "requested_match_keys": list(args.match_key),
            "future_matches_only": True,
        },
        job_args={
            "artifact": artifact.name,
            "model_id": manifest["model_id"],
            "score_only": args.score_only,
            "dry_run": args.dry_run,
        },
        now=now,
    )
    if not args.dry_run:
        database[JOB_RUNS].insert_one(run_doc)

    try:
        snapshots, fixtures, stats = _load_rows(
            database,
            now=now,
            match_keys=list(args.match_key),
        )
        candidate_target_keys = sorted(
            {
                str(row["match_key"])
                for row in snapshots
                if row.get("match_key")
            }
        )
        previously_frozen_rows = list(
            database[FORWARD_BETS].find(
                {
                    "prediction_type": "ev_shadow_model",
                    "match_key": {"$in": candidate_target_keys},
                },
                projection={
                    "_id": 0,
                    "match_key": 1,
                    "odds_snapshot_time": 1,
                    "prediction_created_at": 1,
                    "match_start_time": 1,
                    "invalid_for_model": 1,
                },
            )
        )
        previously_frozen_keys = valid_frozen_match_keys(
            previously_frozen_rows
        )
        registered_frozen_rows = (
            list(
                database[FORWARD_BETS].find(
                    {
                        "prediction_type": (
                            "ev_registered_score_policy"
                        ),
                        "selection_policy_id": args.selection_policy_id,
                        "match_key": {"$in": candidate_target_keys},
                    },
                    projection={
                        "_id": 0,
                        "match_key": 1,
                        "odds_snapshot_time": 1,
                        "prediction_created_at": 1,
                        "match_start_time": 1,
                        "invalid_for_model": 1,
                    },
                )
            )
            if selection_policy is not None
            else []
        )
        registered_frozen_keys = valid_frozen_match_keys(
            registered_frozen_rows
        )
        _, excluded_snapshot_rows = (
            exclude_previously_frozen_matches(
                pd.DataFrame(snapshots),
                frozen_match_keys=previously_frozen_keys,
            )
        )
        score_target_keys = candidate_target_keys
        prediction_target_keys = sorted(
            set(candidate_target_keys).difference(
                previously_frozen_keys
            )
        )
        model_frame, feature_audit = build_v2_forward_model_frame(
            snapshots=pd.DataFrame(snapshots),
            fixtures=pd.DataFrame(fixtures),
            match_stats=pd.DataFrame(stats),
            availability_buffer_hours=float(
                manifest["configuration"][
                    "history_availability_buffer_hours"
                ]
            ),
        )
        bundle = joblib.load(artifact)
        artifact_sha256 = _sha256_file(artifact)
        minimum_ev = float(manifest["configuration"]["minimum_ev"])
        maximum_ev_value = manifest["configuration"].get("maximum_ev")
        maximum_ev = (
            float(maximum_ev_value)
            if maximum_ev_value is not None
            else None
        )
        all_side_scores = (
            score_shadow_candidate_sides(
                bundle,
                model_frame,
            )
            if not model_frame.empty
            else pd.DataFrame()
        )
        training_domain = extract_categorical_training_domain(
            bundle
        )
        in_domain_rows, domain_audit = audit_score_domain(
            all_side_scores.to_dict(orient="records"),
            training_domain,
        )
        in_domain_side_scores = pd.DataFrame(
            in_domain_rows,
            columns=all_side_scores.columns,
        )
        score_docs = (
            build_forward_score_docs(
                all_side_scores,
                model_id=str(manifest["model_id"]),
                artifact_sha256=artifact_sha256,
                training_end=str(manifest["training"]["end"]),
                feature_columns=list(manifest["features"]),
                created_at=now,
            )
            if not all_side_scores.empty
            else []
        )
        score_persistence = {
            "inserted": 0,
            "existing": 0,
            "conflicts": 0,
        }
        if not args.dry_run:
            score_persistence = persist_forward_score_docs(
                database[EV_MODEL_SCORES],
                score_docs,
            )

        selections = (
            select_market_classifier_bets(
                in_domain_side_scores,
                minimum_ev=minimum_ev,
                maximum_ev=maximum_ev,
            )
            if not in_domain_side_scores.empty
            else pd.DataFrame()
        )
        selected_before_prediction_dedupe = len(selections)
        if (
            not args.score_only
            and not selections.empty
            and previously_frozen_keys
        ):
            selections = selections[
                ~selections["exposure_match_id"].astype(str).isin(
                    previously_frozen_keys
                )
            ].copy()
        prediction_docs = (
            build_forward_prediction_docs(
                selections,
                model_id=str(manifest["model_id"]),
                artifact_sha256=artifact_sha256,
                training_end=str(manifest["training"]["end"]),
                feature_columns=list(manifest["features"]),
                minimum_ev=minimum_ev,
                maximum_ev=maximum_ev,
                created_at=now,
            )
            if not args.score_only and not selections.empty
            else []
        )
        registered_prediction_docs: list[dict[str, Any]] = []
        registered_selected_before_dedupe = 0
        if selection_policy is not None and not in_domain_side_scores.empty:
            in_domain_score_docs = build_forward_score_docs(
                in_domain_side_scores,
                model_id=str(manifest["model_id"]),
                artifact_sha256=artifact_sha256,
                training_end=str(manifest["training"]["end"]),
                feature_columns=list(manifest["features"]),
                created_at=now,
            )
            if not args.dry_run and in_domain_score_docs:
                persisted_score_docs = list(
                    database[EV_MODEL_SCORES].find(
                        {
                            "score_key": {
                                "$in": [
                                    row["score_key"]
                                    for row in in_domain_score_docs
                                ]
                            }
                        },
                        projection={"_id": 0},
                    )
                )
                if len(persisted_score_docs) != len(
                    in_domain_score_docs
                ):
                    raise RuntimeError(
                        "registered policy selection requires every source "
                        "score to be persisted first"
                    )
                in_domain_score_docs = persisted_score_docs
            filtered_score_docs = filter_policy_scores(
                in_domain_score_docs,
                dict(selection_policy.get("filters") or {}),
            )
            maximum_bets_value = selection_policy.get(
                "maximum_bets_per_match"
            )
            registered_selections = select_online_policy(
                filtered_score_docs,
                minimum_ev=float(selection_policy["minimum_ev"]),
                maximum_ev=(
                    float(selection_policy["maximum_ev"])
                    if selection_policy.get("maximum_ev") is not None
                    else None
                ),
                maximum_bets_per_match=(
                    int(maximum_bets_value)
                    if maximum_bets_value is not None
                    else None
                ),
            )
            registered_selected_before_dedupe = len(
                registered_selections
            )
            registered_selections = [
                row
                for row in registered_selections
                if str(row.get("match_key"))
                not in registered_frozen_keys
            ]
            registered_prediction_docs = (
                build_registered_policy_prediction_docs(
                    registered_selections,
                    policy=selection_policy,
                    registry_id=str(
                        selection_registry.get("registry_id")
                    ),
                    registry_fingerprint=str(
                        selection_registry_fingerprint
                    ),
                    created_at=now,
                )
            )
        persistence = {
            "inserted": 0,
            "existing": 0,
            "conflicts": 0,
        }
        if not args.dry_run:
            persistence = persist_forward_prediction_docs(
                database[FORWARD_BETS],
                prediction_docs,
            )
        registered_persistence = {
            "inserted": 0,
            "existing": 0,
            "conflicts": 0,
        }
        if not args.dry_run:
            registered_persistence = persist_forward_prediction_docs(
                database[FORWARD_BETS],
                registered_prediction_docs,
            )

        summary = {
            "job": JOB_NAME,
            "run_id": run_doc["run_id"],
            "model_id": manifest["model_id"],
            "artifact_sha256": artifact_sha256,
            "created_at": now.isoformat(),
            "future_matches_only": True,
            "score_only": args.score_only,
            "target_match_count": (
                0
                if args.score_only
                else len(prediction_target_keys)
            ),
            "target_match_keys": (
                [] if args.score_only else prediction_target_keys
            ),
            "score_target_match_count": len(score_target_keys),
            "score_target_match_keys": score_target_keys,
            "previously_frozen_match_count": len(
                previously_frozen_keys
            ),
            "previously_frozen_match_keys": sorted(
                previously_frozen_keys
            ),
            "snapshot_rows_excluded_for_prior_prediction": (
                excluded_snapshot_rows
            ),
            "input_snapshot_rows": len(snapshots),
            "canonical_market_rows": len(model_frame),
            "score_rows": len(score_docs),
            "training_domain_audit": domain_audit,
            "score_persistence": score_persistence,
            "eligible_selected_bets_before_prediction_dedupe": (
                selected_before_prediction_dedupe
            ),
            "selected_bets": len(prediction_docs),
            "selection_policy": (
                {
                    "registry_id": selection_registry.get("registry_id"),
                    "registry_fingerprint": (
                        selection_registry_fingerprint
                    ),
                    "policy_id": selection_policy.get("policy_id"),
                    "policy_status": selection_policy.get("status"),
                    "model_id": selection_policy.get("model_id"),
                }
                if selection_policy is not None
                else None
            ),
            "registered_previously_frozen_match_count": len(
                registered_frozen_keys
            ),
            "registered_selected_before_prediction_dedupe": (
                registered_selected_before_dedupe
            ),
            "registered_selected_bets": len(
                registered_prediction_docs
            ),
            "registered_persistence": registered_persistence,
            "target_outcome_rows_read": 0,
            "feature_audit": feature_audit,
            "persistence": persistence,
            "dry_run": args.dry_run,
        }
        report_path = _write_local_report(
            config,
            run_doc["run_id"],
            summary,
        )
        summary["local_report"] = str(report_path)

        if not args.dry_run:
            report_date = now.date().isoformat()
            database[AUDIT_REPORTS].update_one(
                {
                    "audit_type": "ev_shadow_scoring",
                    "scope_key": run_doc["run_id"],
                    "report_date": report_date,
                },
                {
                    "$setOnInsert": {
                        "audit_type": "ev_shadow_scoring",
                        "scope_key": run_doc["run_id"],
                        "report_date": report_date,
                        "status": (
                            "ok"
                            if domain_audit[
                                "scores_out_of_domain"
                            ]
                            == 0
                            else "warn"
                        ),
                        "findings": (
                            []
                            if domain_audit[
                                "scores_out_of_domain"
                            ]
                            == 0
                            else [
                                "Out-of-domain scores were archived "
                                "but excluded from bet selection."
                            ]
                        ),
                        "metrics": summary,
                        "created_at": now,
                    }
                },
                upsert=True,
            )
            database[HEALTH_REPORTS].update_one(
                {
                    "job_name": JOB_NAME,
                    "report_date": report_date,
                },
                {
                    "$set": {
                        "job_name": JOB_NAME,
                        "report_date": report_date,
                        "run_id": run_doc["run_id"],
                        "status": "ok",
                        "summary": (
                            "Prematch challenger scores archived."
                            if args.score_only and score_docs
                            else "Shadow predictions frozen before kickoff."
                            if prediction_docs
                            else "No qualifying shadow predictions or scores."
                        ),
                        "metrics": summary,
                        "created_at": now,
                    }
                },
                upsert=True,
            )
            database[JOB_RUNS].update_one(
                {"run_id": run_doc["run_id"]},
                build_job_run_finished_update(
                    status="succeeded",
                    metrics=summary,
                    now=now,
                ),
            )
        print(json.dumps(summary, indent=2, default=str))
        return 0
    except Exception as exc:
        if not args.dry_run:
            database[JOB_RUNS].update_one(
                {"run_id": run_doc["run_id"]},
                build_job_run_finished_update(
                    status="failed",
                    error={
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                    now=now,
                ),
            )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
