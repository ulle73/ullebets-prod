from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.closing.service import build_closing_line_docs
from ullebets_v2.config import V2Config
from ullebets_v2.ev_model.snapshot_integrity import (
    build_missing_closing_clv_update,
    detect_simulated_capture_runs,
    select_simulated_capture_snapshots,
)
from ullebets_v2.jobs.job_runs import (
    build_job_run_finished_update,
    build_job_run_started_doc,
)
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.collections import (
    AUDIT_REPORTS,
    CLV_TRACKING,
    CLOSING_LINES,
    JOB_RUNS,
    MARKET_SNAPSHOTS,
)
from ullebets_v2.storage.mongo import get_database


CAPTURE_JOB_NAMES = (
    "capture_odds_checkpoints",
    "capture_closing_snapshots",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect production writes made with simulated capture times, "
            "invalidate only their derived market snapshots, and rebuild "
            "affected closing lines from valid observations."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--tolerance-minutes", type=float, default=5.0)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    database = get_database(config)
    now = datetime.now(tz=UTC)

    job_runs = list(
        database[JOB_RUNS].find(
            {"job_name": {"$in": list(CAPTURE_JOB_NAMES)}},
            projection={"_id": 0},
        )
    )
    simulated_runs = detect_simulated_capture_runs(
        job_runs,
        tolerance_minutes=args.tolerance_minutes,
    )
    capture_queries = {
        (
            str(row["source_workflow"]),
            row["captured_at"],
        )
        for row in simulated_runs
    }
    snapshot_docs: list[dict] = []
    for source_workflow, captured_at in sorted(
        capture_queries,
        key=lambda row: (row[0], row[1]),
    ):
        snapshot_docs.extend(
            database[MARKET_SNAPSHOTS].find(
                {
                    "source_workflow": source_workflow,
                    "captured_at": captured_at,
                },
                projection={"_id": 0},
            )
        )
    selected = select_simulated_capture_snapshots(
        snapshot_docs=snapshot_docs,
        simulated_runs=simulated_runs,
    )
    pending = [
        row
        for row in selected
        if not (
            row.get("invalid_for_model") is True
            and row.get("invalidation_reason")
            == "simulated_time_override"
        )
    ]
    affected_offer_keys = sorted(
        {
            str(row["offer_key"])
            for row in selected
            if row.get("offer_key")
        }
    )
    affected_match_keys = sorted(
        {
            str(row["match_key"])
            for row in selected
            if row.get("match_key")
        }
    )
    summary = {
        "job": "invalidate_simulated_snapshots",
        "apply": args.apply,
        "tolerance_minutes": args.tolerance_minutes,
        "capture_job_runs_scanned": len(job_runs),
        "simulated_job_runs": len(simulated_runs),
        "unique_simulated_capture_times": len(capture_queries),
        "matched_snapshot_count": len(selected),
        "pending_invalidation_count": len(pending),
        "affected_offer_count": len(affected_offer_keys),
        "affected_match_count": len(affected_match_keys),
        "affected_match_keys": affected_match_keys,
        "simulated_runs": [
            {
                **row,
                "started_at": row["started_at"].isoformat(),
                "captured_at": row["captured_at"].isoformat(),
            }
            for row in simulated_runs
        ],
    }
    if not args.apply:
        print(json.dumps(summary, indent=2, default=str))
        return 0

    run_doc = build_job_run_started_doc(
        job_name="invalidate_simulated_snapshots",
        source_workflow="manual-data-integrity-repair",
        target_window={
            "detected_through": now.isoformat(),
            "tolerance_minutes": args.tolerance_minutes,
        },
        job_args={"apply": True},
        now=now,
    )
    database[JOB_RUNS].insert_one(run_doc)
    try:
        invalidated_count = 0
        for row in pending:
            result = database[MARKET_SNAPSHOTS].update_one(
                {"snapshot_key": row["snapshot_key"]},
                {
                    "$set": {
                        "invalid_for_model": True,
                        "invalidation_reason": "simulated_time_override",
                        "invalidated_at": now,
                        "invalidation_job_run_id": run_doc["run_id"],
                        "invalidation_source_run_ids": row[
                            "invalidation_source_run_ids"
                        ],
                    }
                },
            )
            invalidated_count += int(result.modified_count)

        rebuilt_closing_docs: list[dict] = []
        if affected_offer_keys:
            remaining_snapshots = list(
                database[MARKET_SNAPSHOTS].find(
                    {"offer_key": {"$in": affected_offer_keys}},
                    projection={"_id": 0},
                )
            )
            rebuilt_closing_docs = build_closing_line_docs(
                market_snapshot_docs=remaining_snapshots,
                refreshed_at=now,
            )
        valid_closing_keys = {
            str(row["closing_key"])
            for row in rebuilt_closing_docs
        }
        for row in rebuilt_closing_docs:
            database[CLOSING_LINES].update_one(
                {"closing_key": row["closing_key"]},
                {"$set": row},
                upsert=True,
            )
        stale_closing_keys = [
            key
            for key in affected_offer_keys
            if key not in valid_closing_keys
        ]
        deleted_closing_count = 0
        if stale_closing_keys:
            deleted_closing_count = int(
                database[CLOSING_LINES].delete_many(
                    {"closing_key": {"$in": stale_closing_keys}}
                ).deleted_count
            )
        invalidated_clv_count = 0
        if stale_closing_keys:
            invalidated_clv_count = int(
                database[CLV_TRACKING].update_many(
                    {
                        "offer_key": {"$in": stale_closing_keys},
                        "$or": [
                            {"clv_status": "tracked"},
                            {"clv_status": "tracked_fallback_t30"},
                            {"clv_pct": {"$ne": None}},
                            {
                                "closing_invalidation_reason": {
                                    "$ne": "simulated_time_override"
                                }
                            },
                        ],
                    },
                    build_missing_closing_clv_update(
                        invalidated_at=now
                    ),
                ).modified_count
            )

        summary.update(
            {
                "invalidated_snapshot_count": invalidated_count,
                "rebuilt_closing_line_count": len(
                    rebuilt_closing_docs
                ),
                "deleted_stale_closing_line_count": (
                    deleted_closing_count
                ),
                "invalidated_clv_tracking_count": (
                    invalidated_clv_count
                ),
            }
        )
        report_date = now.date().isoformat()
        database[AUDIT_REPORTS].update_one(
            {
                "audit_type": "simulated_snapshot_integrity",
                "scope_key": "market_snapshots",
                "report_date": report_date,
            },
            {
                "$set": {
                    "audit_type": "simulated_snapshot_integrity",
                    "scope_key": "market_snapshots",
                    "report_date": report_date,
                    "status": (
                        "warn"
                        if selected
                        else "ok"
                    ),
                    "findings": (
                        ["simulated_time_snapshots_invalidated"]
                        if selected
                        else []
                    ),
                    "metrics": summary,
                    "generated_at": now,
                }
            },
            upsert=True,
        )
        database[JOB_RUNS].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics=summary,
            ),
        )
    except Exception as exc:
        database[JOB_RUNS].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="failed",
                metrics=summary,
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            ),
        )
        raise

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
