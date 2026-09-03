from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import joblib

from ullebets_v2.config import V2Config
from ullebets_v2.ev_model.domain import extract_categorical_training_domain
from ullebets_v2.formula_journal.materialize import (
    fingerprint_js_runtime,
    materialize_formula_observations,
)
from ullebets_v2.formula_journal.registry import (
    DEFAULT_REGISTRY_PATH,
    load_formula_registry,
)
from ullebets_v2.jobs.job_runs import (
    build_job_run_finished_update,
    build_job_run_started_doc,
)
from ullebets_v2.model_snapshots.oracle import V2JsModelOracle
from ullebets_v2.safety import ensure_no_simulated_time_write, ensure_v2_database
from ullebets_v2.storage.collections import (
    AUDIT_REPORTS,
    HEALTH_REPORTS,
    JOB_RUNS,
)
from ullebets_v2.storage.mongo import get_database
from ullebets_v2.storage.indexes import (
    bootstrap_indexes,
    build_formula_journal_index_plan,
)
from ullebets_v2.support.loaders import load_support_documents


JOB_NAME = "materialize_formula_journal"
SOURCE_WORKFLOW = "formula-journal"


def _as_utc(value: str | None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _load_training_domains(
    registry: dict[str, Any],
    *,
    repo_root: Path,
) -> dict[str, dict[str, tuple[str, ...]]]:
    domains: dict[str, dict[str, tuple[str, ...]]] = {}
    for row in registry.get("frozen_models", []):
        model_id = str(row["model_id"])
        artifact_path = repo_root / str(row["artifact"])
        manifest_path = repo_root / str(row["manifest"])
        if not artifact_path.exists() or not manifest_path.exists():
            raise FileNotFoundError(
                f"registered model files are missing for {model_id}"
            )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if str(manifest.get("model_id")) != model_id:
            raise RuntimeError(f"registered model id disagrees with manifest: {model_id}")
        if manifest.get("status") != "shadow_only":
            raise RuntimeError(f"registered model is not shadow_only: {model_id}")
        domains[model_id] = extract_categorical_training_domain(joblib.load(artifact_path))
    return domains


def _write_report(config: V2Config, run_id: str, summary: dict[str, Any]) -> Path:
    path = config.reports_dir / f"formula-journal-{run_id}.json"
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize immutable JS and frozen-ML formula observations."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--match-key", action="append", default=[])
    parser.add_argument("--now")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


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
    registry_path = (
        args.registry
        if args.registry.is_absolute()
        else config.repo_root / args.registry
    )
    registry = load_formula_registry(registry_path)
    runtime_root = (
        config.repo_root
        / "src"
        / "ullebets_v2"
        / "model_snapshots"
        / "js_runtime"
    )
    runtime_sha256 = fingerprint_js_runtime(runtime_root)
    training_domains = _load_training_domains(
        registry,
        repo_root=config.repo_root,
    )
    support_docs = load_support_documents(
        leagues_path=config.default_leagues_path(),
        league_urls_path=config.default_league_urls_path(),
    )
    database = get_database(config)
    index_summary: list[dict[str, Any]] = []
    if not args.dry_run:
        index_summary = bootstrap_indexes(
            database,
            plan=build_formula_journal_index_plan(),
        )
    run_doc = build_job_run_started_doc(
        job_name=JOB_NAME,
        source_workflow=SOURCE_WORKFLOW,
        target_window={
            "created_at": now.isoformat(),
            "requested_match_keys": list(args.match_key),
        },
        job_args={
            "registry_id": registry["registry_id"],
            "runtime_sha256": runtime_sha256,
            "dry_run": args.dry_run,
        },
        now=now,
    )
    if not args.dry_run:
        database[JOB_RUNS].insert_one(run_doc)
    try:
        with database.client.start_session(causal_consistency=False) as session:
            oracle = V2JsModelOracle(
                database,
                support_docs,
                runtime_root=runtime_root,
                session=session,
            )
            summary = materialize_formula_observations(
                database=database,
                oracle=oracle,
                registry=registry,
                runtime_sha256=runtime_sha256,
                now=now,
                match_keys=list(args.match_key),
                training_domains_by_model=training_domains,
                dry_run=args.dry_run,
                session=session,
            )
        summary.update(
            {
                "job": JOB_NAME,
                "run_id": run_doc["run_id"],
                "registry_id": registry["registry_id"],
                "registry_fingerprint_sha256": registry[
                    "registry_fingerprint_sha256"
                ],
                "runtime_sha256": runtime_sha256,
                "created_at": now.isoformat(),
                "index_bootstrap": index_summary,
            }
        )
        report_path = _write_report(config, run_doc["run_id"], summary)
        summary["local_report"] = str(report_path)
        if not args.dry_run:
            report_date = now.date().isoformat()
            status = "ok" if summary["oracle_error_count"] == 0 else "warn"
            database[AUDIT_REPORTS].update_one(
                {
                    "audit_type": "formula_journal_materialization",
                    "scope_key": run_doc["run_id"],
                    "report_date": report_date,
                },
                {
                    "$setOnInsert": {
                        "audit_type": "formula_journal_materialization",
                        "scope_key": run_doc["run_id"],
                        "report_date": report_date,
                        "status": status,
                        "findings": (
                            []
                            if status == "ok"
                            else ["One or more JS oracle lines could not be materialized."]
                        ),
                        "metrics": summary,
                        "created_at": now,
                    }
                },
                upsert=True,
            )
            database[HEALTH_REPORTS].update_one(
                {"job_name": JOB_NAME, "report_date": report_date},
                {
                    "$set": {
                        "job_name": JOB_NAME,
                        "report_date": report_date,
                        "run_id": run_doc["run_id"],
                        "status": status,
                        "summary": "All-model formula observations materialized.",
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
                    error={"type": type(exc).__name__, "message": str(exc)},
                    now=now,
                ),
            )
        raise
    finally:
        database.client.close()


if __name__ == "__main__":
    raise SystemExit(main())
