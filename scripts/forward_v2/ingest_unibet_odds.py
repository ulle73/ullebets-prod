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
from ullebets_v2.odds.oracle import OriginalJsOracle
from ullebets_v2.odds.service import (
    build_smoke_targets_for_league,
    load_fixture_targets_from_database,
    load_replay_fixture_targets,
    run_unibet_odds_ingest,
)
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Unibet/Kambi raw odds and normalized market offers into V2.")
    parser.add_argument(
        "--mode",
        choices=["replay-fixtures", "smoke-live", "fixture-db"],
        default="smoke-live",
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-workflow")
    parser.add_argument("--league", help="Required for smoke-live mode.")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--max-days-ahead", type=int, default=7)
    parser.add_argument(
        "--date",
        dest="dates",
        action="append",
        default=[],
        help="Replay fixture date in YYYY-MM-DD format. Repeat the flag for multiple dates.",
    )
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
        leagues_path=args.leagues_path or (config.old_repo_root / "data" / "leagues-and-teams.json"),
        league_urls_path=args.league_urls_path or (config.old_repo_root / "data" / "unibetLeagueUrls.json"),
    )

    read_database = None
    if args.mode == "replay-fixtures":
        if not args.dates:
            raise RuntimeError("--date is required in replay-fixtures mode.")
        source_workflow = args.source_workflow or "run-unibet-backtests.yml"
        targets = load_replay_fixture_targets(
            dates=args.dates,
            support_docs=support_docs,
            old_repo_root=config.old_repo_root,
        )
    elif args.mode == "fixture-db":
        source_workflow = args.source_workflow or "run-unibet-backtests.yml"
        read_database = get_database(config)
        targets = load_fixture_targets_from_database(
            database=read_database,
            dates=args.dates or None,
            max_days_ahead=args.max_days_ahead,
            league_name=args.league,
            limit=args.limit if args.limit > 0 else None,
        )
    else:
        if not args.league:
            raise RuntimeError("--league is required in smoke-live mode.")
        source_workflow = args.source_workflow or "run-unibet-forward.yml"
        targets = build_smoke_targets_for_league(
            league_name=args.league,
            support_docs=support_docs,
            limit=args.limit,
            max_days_ahead=args.max_days_ahead,
        )

    database = None if args.dry_run else (read_database or get_database(config))
    oracle = None if args.disable_oracle else OriginalJsOracle(config.old_repo_root)
    summary = run_unibet_odds_ingest(
        targets=targets,
        support_docs=support_docs,
        source_workflow=source_workflow,
        database=database,
        dry_run=args.dry_run,
        oracle=oracle,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
