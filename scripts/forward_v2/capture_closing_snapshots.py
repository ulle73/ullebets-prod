from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.closing.service import run_closing_capture
from ullebets_v2.config import V2Config
from ullebets_v2.odds.oracle import OriginalJsOracle
from ullebets_v2.odds.service import build_smoke_targets_for_league, load_fixture_targets_from_database, load_replay_fixture_targets
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture V2 closing snapshots and derive canonical closing_lines_v2 rows.")
    parser.add_argument("--mode", choices=["smoke-live", "replay-fixtures", "fixture-db"], default="smoke-live")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-workflow", default="run-unibet-closing.yml")
    parser.add_argument("--league")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--max-days-ahead", type=int, default=7)
    parser.add_argument("--date", dest="dates", action="append", default=[])
    parser.add_argument("--now")
    parser.add_argument("--leagues-path", type=Path)
    parser.add_argument("--league-urls-path", type=Path)
    parser.add_argument("--disable-oracle", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
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
    if args.mode == "replay-fixtures":
        if not args.dates:
            raise RuntimeError("--date is required in replay-fixtures mode.")
        targets = load_replay_fixture_targets(
            dates=args.dates,
            support_docs=support_docs,
            old_repo_root=config.old_repo_root,
        )
    elif args.mode == "fixture-db":
        read_database = get_database(config)
        targets = load_fixture_targets_from_database(
            database=read_database,
            dates=args.dates or None,
            max_days_ahead=args.max_days_ahead,
            reference_time=now,
            league_name=args.league,
            limit=args.limit if args.limit > 0 else None,
        )
    else:
        if not args.league:
            raise RuntimeError("--league is required in smoke-live mode.")
        targets = build_smoke_targets_for_league(
            league_name=args.league,
            support_docs=support_docs,
            limit=args.limit,
            max_days_ahead=args.max_days_ahead,
            reference_time=now,
        )

    database = None if args.dry_run else (read_database or get_database(config))
    oracle = None if args.disable_oracle else OriginalJsOracle(config.old_repo_root)
    summary = run_closing_capture(
        targets=targets,
        support_docs=support_docs,
        source_workflow=args.source_workflow,
        database=database,
        dry_run=args.dry_run,
        oracle=oracle,
        now=now,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
