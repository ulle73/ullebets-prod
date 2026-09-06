"""Resume downstream work from persisted snapshots, independently of new inserts.

Completion is recorded only after all three consumers succeed. A killed runner
leaves no completion marker, so the next run repeats idempotently. Started
matches are never reconstructed as new forward evidence.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from ullebets_v2.config import V2Config
from ullebets_v2.storage.mongo import get_database
from ullebets_v2.storage.retry import retry_idempotent


def pending_scopes(database: Any, *, now: datetime, version: str) -> list[dict[str, Any]]:
    rows = retry_idempotent(lambda: list(database["market_snapshots"].find(
        {"match_start_time": {"$gt": now, "$lte": now + timedelta(days=8)}, "invalid_for_model": {"$ne": True}},
        projection={"_id": 0, "match_key": 1, "snapshot_key": 1, "match_start_time": 1, "snapshot_label": 1},
    )))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["match_key"], []).append(row)
    scopes = []
    for key, snapshots in grouped.items():
        keys = sorted({row["snapshot_key"] for row in snapshots})
        digest = hashlib.sha256(json.dumps([version, key, keys]).encode()).hexdigest()
        scopes.append({"_id": f"checkpoint-processing:{digest}", "match_key": key,
                       "match_start_time": min(row["match_start_time"] for row in snapshots), "snapshot_count": len(keys),
                       "has_t1d": any(row.get("snapshot_label") == "T_MINUS_1D" for row in snapshots)})
    completed = set()
    for offset in range(0, len(scopes), 50):
        ids = [row["_id"] for row in scopes[offset:offset + 50]]
        completed.update(row["_id"] for row in retry_idempotent(lambda: list(database["job_runs"].find(
            {"_id": {"$in": ids}, "status": "succeeded"}, projection={"_id": 1}))))
    return sorted((row for row in scopes if row["_id"] not in completed), key=lambda row: (row["match_start_time"], row["match_key"]))


def process_scope(database: Any, scope: dict[str, Any], *, repo_root: Path, runner: Any = subprocess.run) -> None:
    deadline = time.monotonic() + 1500
    consumers = {}
    for script in ("materialize_matchup_observations.py", "score_registered_shadow_models.py", "materialize_formula_journal.py"):
        if script == "materialize_matchup_observations.py":
            hours = (scope["match_start_time"] - datetime.now(UTC)).total_seconds() / 3600
            if not scope["has_t1d"] or not 18 <= hours < 36:
                continue
        if datetime.now(UTC) >= scope["match_start_time"]:
            raise RuntimeError(f"Forward processing deadline passed for {scope['match_key']}; missing evidence must remain unproven")
        print(json.dumps({"stage": script, "match_key": scope["match_key"]}), flush=True)
        remaining = min(900, deadline - time.monotonic())
        if remaining <= 0:
            raise RuntimeError(f"Processing time budget exhausted for {scope['match_key']}")
        result = runner([sys.executable, str(repo_root / "scripts/forward_v2" / script),
                "--repo-root", str(repo_root), "--match-key", scope["match_key"]], check=True, timeout=remaining, capture_output=True, text=True)
        print(result.stdout, flush=True)
        if result.stderr:
            print(result.stderr, file=sys.stderr, flush=True)
        summary = json.loads(result.stdout)
        if summary.get("oracle_error_count", 0):
            raise RuntimeError(f"Incomplete oracle results for {scope['match_key']}")
        if summary.get("skipped_missing_fixture", 0):
            raise RuntimeError(f"Missing fixture for {scope['match_key']}")
        consumers[script] = {key: summary[key] for key in ("snapshot_rows", "observations", "persistence", "model_count", "score_rows") if key in summary}
    marker = {**scope, "run_id": scope["_id"], "job_name": "checkpoint_processing", "status": "succeeded", "finished_at": datetime.now(UTC), "consumers": consumers}
    retry_idempotent(lambda: database["job_runs"].update_one({"_id": scope["_id"]}, {"$setOnInsert": marker}, upsert=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = V2Config.from_env(args.repo_root)
    database = get_database(config)
    try:
        if not args.dry_run:
            retry_idempotent(lambda: database["market_snapshots"].create_index([("match_start_time", 1)], name="snapshot_match_start_time"))
        version = hashlib.sha256((args.repo_root / "models/ev/shadow_formula_registry_v1.json").read_bytes()).hexdigest()
        scopes = pending_scopes(database, now=datetime.now(UTC), version=f"v1:{version}")
        print(json.dumps({"pending_matches": len(scopes), "pending_snapshots": sum(row["snapshot_count"] for row in scopes), "scopes": scopes}, default=str), flush=True)
        if args.dry_run:
            return 0
        started = time.monotonic()
        failures = []
        completed = 0
        for scope in scopes:
            # Leave time for a bounded match and graceful reporting before the
            # hosted runner's 60-minute hard stop. Pending scopes remain durable.
            if time.monotonic() - started > 1800:
                break
            try:
                process_scope(database, scope, repo_root=args.repo_root)
                completed += 1
            except (subprocess.SubprocessError, RuntimeError) as exc:
                if getattr(exc, "stderr", None):
                    print(exc.stderr, file=sys.stderr, flush=True)
                failures.append({"match_key": scope["match_key"], "error": str(exc)})
        print(json.dumps({"completed_matches": completed, "pending_matches": len(scopes) - completed, "failures": failures}), flush=True)
        return 1 if failures or completed < len(scopes) else 0
    finally:
        database.client.close()


if __name__ == "__main__":
    raise SystemExit(main())
