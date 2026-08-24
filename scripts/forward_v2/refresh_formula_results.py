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

from ullebets_v2.config import V2Config
from ullebets_v2.formula_journal.results import refresh_formula_results
from ullebets_v2.jobs.job_runs import (
    build_job_run_finished_update,
    build_job_run_started_doc,
)
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


JOB_NAME = "refresh_formula_results"
SOURCE_WORKFLOW = "ev-shadow-settlement.yml"


def _as_utc(value: str | None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _write_report(config: V2Config, run_id: str, summary: dict[str, Any]) -> Path:
    path = config.reports_dir / f"formula-results-{run_id}.json"
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh rebuildable settlement and CLV results for formula observations."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
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
        target_window={"refreshed_at": now.isoformat()},
        job_args={"dry_run": args.dry_run},
        now=now,
    )
    if not args.dry_run:
        database[JOB_RUNS].insert_one(run_doc)
    try:
        summary = refresh_formula_results(
            database=database,
            refreshed_at=now,
            dry_run=args.dry_run,
        )
        summary.update(
            {
                "job": JOB_NAME,
                "run_id": run_doc["run_id"],
                "refreshed_at": now.isoformat(),
                "index_bootstrap": index_summary,
            }
        )
        report_path = _write_report(config, run_doc["run_id"], summary)
        summary["local_report"] = str(report_path)
        if not args.dry_run:
            report_date = now.date().isoformat()
            unresolved = summary["pending"]
            status = "ok" if unresolved == 0 else "warn"
            database[AUDIT_REPORTS].update_one(
                {
                    "audit_type": "formula_result_refresh",
                    "scope_key": run_doc["run_id"],
                    "report_date": report_date,
                },
                {
                    "$setOnInsert": {
                        "audit_type": "formula_result_refresh",
                        "scope_key": run_doc["run_id"],
                        "report_date": report_date,
                        "status": status,
                        "findings": (
                            []
                            if unresolved == 0
                            else [f"{unresolved} formula results remain unresolved."]
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
                        "summary": "Formula result and CLV refresh completed.",
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


if __name__ == "__main__":
    raise SystemExit(main())
