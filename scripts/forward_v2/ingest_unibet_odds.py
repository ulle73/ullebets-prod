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
from ullebets_v2.date_windows import resolve_requested_dates, resolve_target_limit
from ullebets_v2.odds.oracle import OriginalJsOracle
from ullebets_v2.odds.service import (
    build_smoke_targets_for_league,
    inspect_fixture_target_window_from_database,
    load_historical_replay_targets,
    load_fixture_targets_from_database,
    load_replay_fixture_targets,
    run_unibet_odds_ingest,
)
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database, get_legacy_app_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Unibet/Kambi raw odds and normalized market offers into V2.")
    parser.add_argument(
        "--mode",
        choices=["replay-fixtures", "legacy-backtest", "smoke-live", "fixture-db"],
        default="smoke-live",
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-workflow")
    parser.add_argument("--league", help="Required for smoke-live mode.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-days-ahead", type=int, default=7)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument(
        "--date",
        dest="dates",
        action="append",
        default=[],
        help="Replay fixture date in YYYY-MM-DD format. Repeat the flag for multiple dates.",
    )
    parser.add_argument("--leagues-path", type=Path)
    parser.add_argument("--league-urls-path", type=Path)
    parser.add_argument(
        "--include-match-rows",
        action="store_true",
        help="Print the full per-match diagnostics payload instead of a compact summary.",
    )
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
    config.ensure_directories()

    support_docs = load_support_documents(
        leagues_path=args.leagues_path or config.default_leagues_path(),
        league_urls_path=args.league_urls_path or config.default_league_urls_path(),
    )
    requested_dates = resolve_requested_dates(
        explicit_dates=args.dates,
        start_date=args.start_date,
        end_date=args.end_date,
        allow_empty=True,
    )

    read_database = None
    target_window = None
    if args.mode == "replay-fixtures":
        if not requested_dates:
            raise RuntimeError("--date or --start-date/--end-date is required in replay-fixtures mode.")
        source_workflow = args.source_workflow or "run-unibet-backtests.yml"
        targets = load_replay_fixture_targets(
            dates=requested_dates,
            support_docs=support_docs,
            old_repo_root=config.old_repo_root,
            legacy_match_database=get_legacy_app_database(config),
        )
    elif args.mode == "legacy-backtest":
        if not requested_dates:
            raise RuntimeError("--date or --start-date/--end-date is required in legacy-backtest mode.")
        source_workflow = args.source_workflow or "run-unibet-backtests.yml"
        read_database = get_database(config)
        targets, target_source = load_historical_replay_targets(
            database=read_database,
            dates=requested_dates,
            support_docs=support_docs,
            legacy_backtest_database=get_legacy_app_database(config),
            legacy_match_database=get_legacy_app_database(config),
            limit=resolve_target_limit(args.limit),
        )
        target_window = {
            "target_source": target_source,
            "requested_dates": list(requested_dates),
            "selected_target_match_count": len(targets),
        }
    elif args.mode == "fixture-db":
        source_workflow = args.source_workflow or "run-unibet-backtests.yml"
        read_database = get_database(config)
        target_window = inspect_fixture_target_window_from_database(
            database=read_database,
            dates=requested_dates or None,
            max_days_ahead=args.max_days_ahead,
            league_name=args.league,
            forward_only=True,
        )
        targets = load_fixture_targets_from_database(
            database=read_database,
            dates=requested_dates or None,
            max_days_ahead=args.max_days_ahead,
            league_name=args.league,
            forward_only=True,
            limit=resolve_target_limit(args.limit),
        )
    else:
        if not args.league:
            raise RuntimeError("--league is required in smoke-live mode.")
        source_workflow = args.source_workflow or "run-unibet-forward.yml"
        targets = build_smoke_targets_for_league(
            league_name=args.league,
            support_docs=support_docs,
            limit=resolve_target_limit(args.limit, default_when_unspecified=1),
            max_days_ahead=args.max_days_ahead,
        )

    database = None if args.dry_run else (read_database if read_database is not None else get_database(config))
    legacy_backtest_database = get_legacy_app_database(config) if args.mode in {"replay-fixtures", "legacy-backtest"} else None
    oracle = OriginalJsOracle(config.old_repo_root) if args.use_original_oracle else None
    summary = run_unibet_odds_ingest(
        targets=targets,
        support_docs=support_docs,
        source_workflow=source_workflow,
        database=database,
        dry_run=args.dry_run,
        oracle=oracle,
        legacy_backtest_database=legacy_backtest_database,
    )
    if target_window is not None:
        target_window["selected_target_match_count"] = len(targets)
        summary["target_window"] = target_window
        if not targets:
            summary["empty_reason"] = target_window.get("empty_reason")
    output_summary = dict(summary)
    if not args.include_match_rows and "match_rows" in output_summary:
        output_summary["match_rows_sample"] = output_summary["match_rows"][:3]
        output_summary.pop("match_rows", None)
    print(json.dumps(output_summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
