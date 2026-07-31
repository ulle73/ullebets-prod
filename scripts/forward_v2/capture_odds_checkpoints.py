from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.checkpoints.service import run_checkpoint_capture
from ullebets_v2.config import V2Config
from ullebets_v2.date_windows import resolve_target_limit
from ullebets_v2.odds.oracle import OriginalJsOracle
from ullebets_v2.odds.service import (
    build_smoke_targets_for_league,
    inspect_fixture_target_window_from_database,
    load_fixture_targets_from_database,
    load_legacy_backtest_targets,
    load_replay_fixture_targets,
)
from ullebets_v2.safety import (
    ensure_no_simulated_time_write,
    ensure_v2_database,
)
from ullebets_v2.storage.mongo import get_database, get_legacy_app_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture V2 odds checkpoints into market_snapshots with strict prematch timing metadata.")
    parser.add_argument("--mode", choices=["smoke-live", "replay-fixtures", "legacy-backtest", "fixture-db"], default="smoke-live")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-workflow", default="run-unibet-odds-checkpoints.yml")
    parser.add_argument("--league")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-days-ahead", type=int, default=7)
    parser.add_argument("--checkpoint")
    parser.add_argument(
        "--exclude-checkpoint",
        action="append",
        default=[],
        help="Checkpoint key to leave to another capture job. May be repeated.",
    )
    parser.add_argument("--date", dest="dates", action="append", default=[])
    parser.add_argument("--now")
    parser.add_argument("--leagues-path", type=Path)
    parser.add_argument("--league-urls-path", type=Path)
    oracle_group = parser.add_mutually_exclusive_group()
    oracle_group.add_argument(
        "--use-original-oracle",
        action="store_true",
        help="Enable the original JS odds oracle for live parity cross-checks.",
    )
    oracle_group.add_argument("--disable-oracle", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    ensure_no_simulated_time_write(
        time_override=args.now,
        dry_run=args.dry_run,
        job_name="capture_odds_checkpoints",
    )
    config.ensure_directories()
    support_docs = load_support_documents(
        leagues_path=args.leagues_path or config.default_leagues_path(),
        league_urls_path=args.league_urls_path or config.default_league_urls_path(),
    )
    if args.now:
        from datetime import datetime

        now = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
    else:
        now = None

    read_database = None
    target_window = None
    if args.mode == "replay-fixtures":
        if not args.dates:
            raise RuntimeError("--date is required in replay-fixtures mode.")
        targets = load_replay_fixture_targets(
            dates=args.dates,
            support_docs=support_docs,
            old_repo_root=config.old_repo_root,
            legacy_match_database=get_legacy_app_database(config),
        )
    elif args.mode == "legacy-backtest":
        if not args.dates:
            raise RuntimeError("--date is required in legacy-backtest mode.")
        targets = load_legacy_backtest_targets(
            dates=args.dates,
            support_docs=support_docs,
            legacy_backtest_database=get_legacy_app_database(config),
            legacy_match_database=get_legacy_app_database(config),
            limit=resolve_target_limit(args.limit),
        )
    elif args.mode == "fixture-db":
        read_database = get_database(config)
        target_window = inspect_fixture_target_window_from_database(
            database=read_database,
            dates=args.dates or None,
            max_days_ahead=args.max_days_ahead,
            reference_time=now,
            league_name=args.league,
            forward_only=True,
        )
        targets = load_fixture_targets_from_database(
            database=read_database,
            dates=args.dates or None,
            max_days_ahead=args.max_days_ahead,
            reference_time=now,
            league_name=args.league,
            forward_only=True,
            limit=resolve_target_limit(args.limit),
        )
    else:
        if not args.league:
            raise RuntimeError("--league is required in smoke-live mode.")
        targets = build_smoke_targets_for_league(
            league_name=args.league,
            support_docs=support_docs,
            limit=resolve_target_limit(args.limit, default_when_unspecified=1),
            max_days_ahead=args.max_days_ahead,
            reference_time=now,
        )

    database = None if args.dry_run else (read_database if read_database is not None else get_database(config))
    oracle = OriginalJsOracle(config.old_repo_root) if args.use_original_oracle else None
    legacy_backtest_database = get_legacy_app_database(config) if args.mode in {"replay-fixtures", "legacy-backtest"} else None
    summary = run_checkpoint_capture(
        targets=targets,
        support_docs=support_docs,
        source_workflow=args.source_workflow,
        database=database,
        dry_run=args.dry_run,
        checkpoint_filter=args.checkpoint,
        excluded_checkpoint_keys=set(args.exclude_checkpoint),
        oracle=oracle,
        legacy_backtest_database=legacy_backtest_database,
        now=now,
    )
    if target_window is not None:
        target_window["selected_target_match_count"] = len(targets)
        summary["target_window"] = target_window
        if not targets:
            summary["empty_reason"] = target_window.get("empty_reason")
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
