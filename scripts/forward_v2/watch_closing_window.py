from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.closing.downstream import refresh_closing_dependents
from ullebets_v2.closing.service import run_closing_capture
from ullebets_v2.closing.session import (
    build_watch_session_plan,
    claim_watch_session,
    heartbeat_watch_session,
    release_watch_session,
)
from ullebets_v2.config import V2Config
from ullebets_v2.odds.service import load_fixture_targets_from_database
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.collections import (
    CLOSING_WATCH_SESSIONS,
    FIXTURES_CANONICAL,
    MARKET_SNAPSHOTS,
)
from ullebets_v2.storage.indexes import bootstrap_indexes, build_core_index_plan
from ullebets_v2.storage.mongo import get_database
from ullebets_v2.support.loaders import load_support_documents


Clock = Callable[[], datetime]
Sleeper = Callable[[float], None]
Capture = Callable[[datetime], dict[str, Any]]
PlanLoader = Callable[..., dict[str, Any]]
PostCapture = Callable[[dict[str, Any], datetime], dict[str, Any]]

DEFAULT_SESSION_KEY = "closing-watch:global"


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def load_database_watch_plan(
    *,
    database: Any,
    now: datetime,
    lookahead_hours: float,
) -> dict[str, Any]:
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(hours=lookahead_hours)
    fixture_docs = list(
        database[FIXTURES_CANONICAL].find(
            {"start_time": {"$gte": window_start, "$lte": window_end}},
            projection={"_id": 0},
        )
    )
    match_keys = [
        str(row["match_key"])
        for row in fixture_docs
        if row.get("match_key")
    ]
    snapshot_docs = (
        list(
            database[MARKET_SNAPSHOTS].find(
                {
                    "match_key": {"$in": match_keys},
                    "snapshot_label": {
                        "$in": ["T_MINUS_30M", "T_MINUS_10M"]
                    },
                },
                projection={"_id": 0},
            )
        )
        if match_keys
        else []
    )
    return build_watch_session_plan(
        fixture_docs=fixture_docs,
        snapshot_docs=snapshot_docs,
        now=now,
        lookahead_hours=lookahead_hours,
    )


def _captured_match_keys(capture_summary: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    keys: list[str] = []
    for row in capture_summary.get("due_targets") or []:
        match_key = str(row.get("match_key") or "")
        if match_key and match_key not in seen:
            seen.add(match_key)
            keys.append(match_key)
    return keys


def score_captured_matches(
    *,
    repo_root: Path,
    capture_summary: dict[str, Any],
) -> dict[str, Any]:
    upserts = int(capture_summary.get("market_snapshot_upserts") or 0)
    if upserts <= 0:
        return {"status": "skipped", "reason": "no_new_snapshots"}
    match_keys = _captured_match_keys(capture_summary)
    if not match_keys:
        raise RuntimeError(
            "Closing capture wrote snapshots but exposed no scoped match keys."
        )
    match_args = [
        argument
        for match_key in match_keys
        for argument in ("--match-key", match_key)
    ]
    commands = [
        [
            sys.executable,
            str(
                repo_root
                / "scripts"
                / "forward_v2"
                / "score_registered_shadow_models.py"
            ),
            "--repo-root",
            str(repo_root),
            "--registry",
            str(repo_root / "models" / "ev" / "shadow_formula_registry_v1.json"),
            *match_args,
        ],
        [
            sys.executable,
            str(
                repo_root
                / "scripts"
                / "forward_v2"
                / "materialize_formula_journal.py"
            ),
            "--repo-root",
            str(repo_root),
            "--registry",
            str(repo_root / "models" / "ev" / "shadow_formula_registry_v1.json"),
            *match_args,
        ],
    ]
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = (
                completed.stderr
                or completed.stdout
                or "unknown checkpoint scoring failure"
            ).strip()
            raise RuntimeError(detail)
    return {
        "status": "scored",
        "match_keys": match_keys,
        "command_count": len(commands),
    }


def _finalize_counts(
    summary: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    matches = list(plan.get("matches") or [])
    summary["t30_captured_matches"] = sum(
        1
        for row in matches
        if "T_MINUS_30M" in set(row.get("captured_checkpoints") or [])
    )
    summary["t10_captured_matches"] = sum(
        1
        for row in matches
        if "T_MINUS_10M" in set(row.get("captured_checkpoints") or [])
    )
    summary["closing_missed_matches"] = sum(
        1 for row in matches if row.get("status") == "closing_missed"
    )
    summary["final_plan"] = plan


def run_watch_session(
    *,
    database: Any,
    owner_id: str,
    capture: Capture,
    now: Clock = utc_now,
    sleep: Sleeper = time.sleep,
    load_plan: PlanLoader = load_database_watch_plan,
    post_capture: PostCapture | None = None,
    lookahead_hours: float = 4.0,
    max_session_seconds: int = 19_200,
    poll_seconds: int = 60,
    lease_seconds: int = 180,
    session_key: str = DEFAULT_SESSION_KEY,
    dry_run: bool = False,
    claim_session: Callable[..., dict[str, Any] | None] = claim_watch_session,
    heartbeat_session: Callable[..., bool] = heartbeat_watch_session,
    release_session: Callable[..., bool] = release_watch_session,
) -> dict[str, Any]:
    if max_session_seconds <= 0:
        raise ValueError("max_session_seconds must be positive.")
    if poll_seconds <= 0 or (poll_seconds < 60 and not dry_run):
        raise ValueError("poll_seconds must be at least 60 outside dry-run.")
    started_at = now()
    deadline = started_at + timedelta(seconds=max_session_seconds)
    summary: dict[str, Any] = {
        "session_key": session_key,
        "owner_id": owner_id,
        "started_at": started_at,
        "deadline": deadline,
        "status": "starting",
        "capture_attempts": 0,
        "capture_errors": 0,
        "valid_empty_captures": 0,
        "market_snapshot_upserts": 0,
        "post_capture_runs": 0,
        "post_capture_errors": 0,
        "captured_match_keys": [],
    }
    initial_plan = load_plan(
        database=database,
        now=started_at,
        lookahead_hours=lookahead_hours,
    )
    if dry_run:
        summary["status"] = "dry_run"
        _finalize_counts(summary, initial_plan)
        return summary

    session_collection = (
        database.get(CLOSING_WATCH_SESSIONS)
        if isinstance(database, dict)
        else database[CLOSING_WATCH_SESSIONS]
    )
    claimed = claim_session(
        collection=session_collection,
        session_key=session_key,
        owner_id=owner_id,
        now=started_at,
        lease_seconds=lease_seconds,
    )
    if claimed is None:
        summary["status"] = "lease_unavailable"
        _finalize_counts(summary, initial_plan)
        return summary

    plan = initial_plan
    pending_post_captures: list[tuple[dict[str, Any], datetime]] = []
    captured_keys: set[str] = set()
    while True:
        current_time = now()
        if current_time >= deadline:
            summary["status"] = "bounded_runtime_reached"
            break

        plan = load_plan(
            database=database,
            now=current_time,
            lookahead_hours=lookahead_hours,
        )
        if not heartbeat_session(
            collection=session_collection,
            session_key=session_key,
            owner_id=owner_id,
            now=current_time,
            lease_seconds=lease_seconds,
            state=plan,
        ):
            summary["status"] = "lease_lost"
            _finalize_counts(summary, plan)
            return summary

        if post_capture is not None and pending_post_captures:
            remaining_posts: list[tuple[dict[str, Any], datetime]] = []
            for capture_summary, captured_at in pending_post_captures:
                try:
                    post_capture(capture_summary, captured_at)
                    summary["post_capture_runs"] += 1
                except Exception as exc:  # keep the watcher alive for retries
                    summary["post_capture_errors"] += 1
                    summary["last_post_capture_error"] = str(exc)
                    remaining_posts.append((capture_summary, captured_at))
            pending_post_captures = remaining_posts

        if not plan.get("should_watch"):
            if pending_post_captures:
                sleep(min(poll_seconds, (deadline - current_time).total_seconds()))
                continue
            summary["status"] = "completed"
            break

        next_wake_seconds = int(plan.get("next_wake_seconds") or 0)
        if next_wake_seconds > 0:
            sleep(
                min(
                    poll_seconds,
                    next_wake_seconds,
                    max(0.0, (deadline - current_time).total_seconds()),
                )
            )
            continue

        summary["capture_attempts"] += 1
        try:
            capture_summary = capture(current_time)
        except Exception as exc:  # transient source errors retry inside the window
            summary["capture_errors"] += 1
            summary["last_capture_error"] = str(exc)
        else:
            upserts = int(capture_summary.get("market_snapshot_upserts") or 0)
            summary["market_snapshot_upserts"] += upserts
            for match_key in _captured_match_keys(capture_summary):
                captured_keys.add(match_key)
            if upserts <= 0:
                summary["valid_empty_captures"] += 1
            elif post_capture is not None:
                pending_post_captures.append((capture_summary, current_time))
        summary["captured_match_keys"] = sorted(captured_keys)
        sleep(
            min(
                poll_seconds,
                max(0.0, (deadline - current_time).total_seconds()),
            )
        )

    _finalize_counts(summary, plan)
    summary["lease_released"] = release_session(
        collection=session_collection,
        session_key=session_key,
        owner_id=owner_id,
        now=now(),
        status=summary["status"],
        summary=summary,
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch upcoming fixtures and capture T-30/T-10 on runner time."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-workflow", default="run-unibet-closing.yml")
    parser.add_argument("--lookahead-hours", type=float, default=4.0)
    parser.add_argument("--max-session-minutes", type=int, default=320)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--lease-seconds", type=int, default=180)
    parser.add_argument("--owner-id")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _default_owner_id() -> str:
    run_id = os.getenv("GITHUB_RUN_ID")
    attempt = os.getenv("GITHUB_RUN_ATTEMPT")
    if run_id:
        return f"github:{run_id}:{attempt or '1'}"
    return f"local:{uuid4()}"


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()
    database = get_database(config)
    if not args.dry_run:
        session_plan = [
            row
            for row in build_core_index_plan()
            if row["collection"] == CLOSING_WATCH_SESSIONS
        ]
        bootstrap_indexes(database, plan=session_plan)
    support_docs = load_support_documents(
        leagues_path=config.default_leagues_path(),
        league_urls_path=config.default_league_urls_path(),
    )

    def capture(captured_at: datetime) -> dict[str, Any]:
        targets = load_fixture_targets_from_database(
            database=database,
            max_days_ahead=1,
            reference_time=captured_at,
            forward_only=True,
        )
        capture_summary = run_closing_capture(
            targets=targets,
            support_docs=support_docs,
            source_workflow=args.source_workflow,
            database=database,
            dry_run=False,
            now=captured_at,
        )
        capture_summary["derived_refresh"] = refresh_closing_dependents(
            database=database,
            closing_summary=capture_summary,
            dry_run=False,
        )
        return capture_summary

    summary = run_watch_session(
        database=database,
        owner_id=args.owner_id or _default_owner_id(),
        capture=capture,
        post_capture=(
            None
            if args.dry_run
            else lambda capture_summary, captured_at: score_captured_matches(
                repo_root=config.repo_root,
                capture_summary=capture_summary,
            )
        ),
        lookahead_hours=args.lookahead_hours,
        max_session_seconds=args.max_session_minutes * 60,
        poll_seconds=args.poll_seconds,
        lease_seconds=args.lease_seconds,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0 if summary["status"] != "lease_lost" else 2


if __name__ == "__main__":
    raise SystemExit(main())
