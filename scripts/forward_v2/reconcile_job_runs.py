from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.config import V2Config
from ullebets_v2.jobs.job_runs import inspect_job_run_health, reconcile_stale_job_runs
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect or reconcile stale running V2 job_runs records.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--stale-hours", type=int, default=6)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    database = get_database(config)
    collection = database["job_runs"]

    before_rows = list(collection.find({}, projection={"_id": 0}))
    before = inspect_job_run_health(
        job_runs=before_rows,
        stale_hours=args.stale_hours,
    )

    reconcile_summary = None
    if args.apply:
        reconcile_summary = reconcile_stale_job_runs(
            collection,
            stale_hours=args.stale_hours,
        )

    after_rows = list(collection.find({}, projection={"_id": 0}))
    after = inspect_job_run_health(
        job_runs=after_rows,
        stale_hours=args.stale_hours,
    )

    payload = {
        "job": "reconcile_job_runs",
        "stale_hours": args.stale_hours,
        "apply": args.apply,
        "before": {
            "status": before["status"],
            "findings": before["findings"],
            "metrics": before["metrics"],
            "stale_run_ids": [str(row.get("run_id") or "") for row in before["stale_rows"]],
        },
        "after": {
            "status": after["status"],
            "findings": after["findings"],
            "metrics": after["metrics"],
            "stale_run_ids": [str(row.get("run_id") or "") for row in after["stale_rows"]],
        },
        "reconcile": reconcile_summary,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
