from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.config import V2Config, load_dotenv_map
from ullebets_v2.odds.service import inspect_fixture_target_window_from_database
from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, materialize_parity_rows
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.source_connectivity.service import run_source_connectivity_audit
from ullebets_v2.storage.indexes import build_core_index_plan
from ullebets_v2.storage.mongo import get_database, ping_database
from ullebets_v2.verification.automation import inspect_env_example, inspect_workflow_directory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a no-side-effect healthcheck over the Ullebets V2 backend contract.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--ping-db", action="store_true")
    parser.add_argument("--check-fixture-db", action="store_true")
    parser.add_argument("--check-connectivity", action="store_true")
    parser.add_argument("--test-date")
    parser.add_argument("--category-id", default="34")
    parser.add_argument("--match-ids", default="15235566,14065562,14083306")
    parser.add_argument("--max-keys", type=int, default=10)
    parser.add_argument("--max-days-ahead", type=int, default=7)
    return parser.parse_args()


def _merge_env(config: V2Config) -> dict[str, str]:
    merged = dict(load_dotenv_map(config.env_file))
    merged.update({key: value for key, value in os.environ.items() if value})
    return merged


def _build_contract_findings(
    *,
    workflow_report: dict,
    env_report: dict,
    old_repo_exists: bool,
) -> tuple[str, list[str]]:
    findings: list[str] = []
    if workflow_report["missing_parity_files"]:
        findings.append("missing_workflow_replacements")
    if workflow_report["missing_helper_files"]:
        findings.append("missing_workflow_helpers")
    if workflow_report.get("invalid_content_files"):
        findings.append("workflow_content_mismatches")
    if env_report["missing_required_keys"]:
        findings.append("missing_env_example_keys")
    if env_report.get("mongo_db") != "ullebets_v2":
        findings.append("env_example_mongodb_db_not_v2")
    if not old_repo_exists:
        findings.append("legacy_repo_root_missing")
    return ("ok" if not findings else "warn"), findings


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()

    workflow_report = inspect_workflow_directory(config.repo_root / ".github" / "workflows")
    env_report = inspect_env_example(config.repo_root / ".env.example")
    contract_status, contract_findings = _build_contract_findings(
        workflow_report=workflow_report,
        env_report=env_report,
        old_repo_exists=config.old_repo_root.exists(),
    )

    payload: dict[str, object] = {
        "overall_status": contract_status,
        "mongo_db": config.mongo_db,
        "repo_root": str(config.repo_root),
        "env_file": str(config.env_file),
        "old_repo_root": str(config.old_repo_root),
        "old_repo_root_exists": config.old_repo_root.exists(),
        "data_dir": str(config.data_dir),
        "reports_dir": str(config.reports_dir),
        "index_collection_count": len(build_core_index_plan()),
        "workflow_parity_count": len(materialize_parity_rows()),
        "workflow_files": workflow_report,
        "env_example": env_report,
        "health_contract": build_health_report_row(
            job_name="healthcheck_v2",
            status=contract_status,
            summary="V2 automation and safety contract evaluated without writes.",
            metrics={
                "workflow_missing_count": len(workflow_report["missing_parity_files"]) + len(workflow_report["missing_helper_files"]),
                "workflow_invalid_content_count": len(workflow_report.get("invalid_content_files", [])),
                "env_missing_count": len(env_report["missing_required_keys"]),
                "old_repo_root_exists": config.old_repo_root.exists(),
            },
        ),
        "audit_contract": build_audit_report_row(
            audit_type="automation_contract",
            scope_key="v2-healthcheck",
            status=contract_status,
            findings=contract_findings,
            metrics={
                "workflow_missing_count": len(workflow_report["missing_parity_files"]) + len(workflow_report["missing_helper_files"]),
                "workflow_invalid_content_count": len(workflow_report.get("invalid_content_files", [])),
                "env_missing_count": len(env_report["missing_required_keys"]),
                "workflow_existing_count": workflow_report["existing_workflow_count"],
            },
        ),
    }

    database = None
    if args.ping_db or args.check_fixture_db:
        database = get_database(config)

    if args.ping_db:
        payload["ping"] = ping_database(config)

    if args.check_fixture_db and database is not None:
        payload["fixture_window"] = inspect_fixture_target_window_from_database(
            database=database,
            max_days_ahead=args.max_days_ahead,
        )

    if args.check_connectivity:
        summary = run_source_connectivity_audit(
            source_workflow="v2-healthcheck.yml",
            test_date=args.test_date,
            category_id=args.category_id,
            match_ids=[item.strip() for item in str(args.match_ids).split(",") if item.strip()],
            max_keys=args.max_keys,
            env=_merge_env(config),
            dry_run=True,
        )
        payload["source_connectivity"] = {
            "endpoint_count": len(summary["endpoint_results"]),
            "audit_status_counts": summary["audit_status_counts"],
            "health_status_counts": summary["health_status_counts"],
        }
        if summary["audit_status_counts"] != {"ok": 1} and payload["overall_status"] == "ok":
            payload["overall_status"] = "warn"

    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
