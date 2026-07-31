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

from ullebets_v2.config import V2Config
from ullebets_v2.ev_model.forward_evaluation import (
    build_forward_evaluation_report,
)
from ullebets_v2.ev_model.forward_scores import (
    audit_forward_score_docs,
)
from ullebets_v2.jobs.job_runs import (
    build_job_run_finished_update,
    build_job_run_started_doc,
)
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.collections import (
    AUDIT_REPORTS,
    CLV_TRACKING,
    EV_MODEL_SCORES,
    FORWARD_BETS,
    JOB_RUNS,
    SETTLED_BETS,
)
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit immutable EV forward predictions by model id."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()
    database = get_database(config)
    predictions = list(
        database[FORWARD_BETS].find(
            {"model_id": args.model_id},
            projection={"_id": 0},
        )
    )
    scores = list(
        database[EV_MODEL_SCORES].find(
            {"model_id": args.model_id},
            projection={"_id": 0},
        )
    )
    prediction_keys = [
        str(row["prediction_key"])
        for row in predictions
        if row.get("prediction_key")
    ]
    related_query = {"prediction_key": {"$in": prediction_keys}}
    settled = (
        list(
            database[SETTLED_BETS].find(
                related_query,
                projection={"_id": 0},
            )
        )
        if prediction_keys
        else []
    )
    clv = (
        list(
            database[CLV_TRACKING].find(
                related_query,
                projection={"_id": 0},
            )
        )
        if prediction_keys
        else []
    )
    report = build_forward_evaluation_report(
        predictions=predictions,
        settled_rows=settled,
        clv_rows=clv,
        model_id=args.model_id,
    )
    report["score_archive"] = audit_forward_score_docs(
        scores,
        model_id=args.model_id,
    )
    report["dry_run"] = args.dry_run
    report_path = (
        config.reports_dir
        / f"ev-forward-evaluation-{args.model_id}.json"
    )
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    report["local_report"] = str(report_path)

    if not args.dry_run:
        now = datetime.now(tz=UTC)
        run_doc = build_job_run_started_doc(
            job_name="audit_ev_forward_model",
            source_workflow="ev-shadow-settlement.yml",
            target_window={"model_id": args.model_id},
            job_args={"dry_run": False},
            now=now,
        )
        database[JOB_RUNS].insert_one(run_doc)
        try:
            database[AUDIT_REPORTS].update_one(
                {
                    "audit_type": "ev_forward_model_performance",
                    "scope_key": args.model_id,
                    "report_date": now.date().isoformat(),
                },
                {
                    "$set": {
                        "audit_type": "ev_forward_model_performance",
                        "scope_key": args.model_id,
                        "report_date": now.date().isoformat(),
                        "status": (
                            "ok"
                            if report["timing"]["violations"] == 0
                            and report["duplicates"][
                                "duplicate_exposures"
                            ]
                            == 0
                            and report["score_archive"]["status"]
                            == "ok"
                            else "warn"
                        ),
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
