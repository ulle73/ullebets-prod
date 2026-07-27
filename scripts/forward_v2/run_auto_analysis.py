from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.analysis import InternalAnalysisOracle
from ullebets_v2.analysis.oracle import OriginalJsAutoAnalysisOracle
from ullebets_v2.analysis.service import run_auto_analysis_pipeline
from ullebets_v2.config import V2Config
from ullebets_v2.model_snapshots.oracle import OriginalJsModelOracle
from ullebets_v2.odds.oracle import OriginalJsOracle
from ullebets_v2.odds.service import (
    build_smoke_targets_for_league,
    inspect_fixture_target_window_from_database,
    load_fixture_targets_from_database,
    load_replay_fixture_targets,
)
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database, get_legacy_app_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V2 auto-analysis using canonical model snapshots and the legacy JS ranking policy.")
    parser.add_argument("--mode", choices=["smoke-live", "replay-fixtures", "fixture-db"], default="smoke-live")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-workflow", default="run-auto-analysis-checkpoints.yml")
    parser.add_argument("--league")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--max-days-ahead", type=int, default=7)
    parser.add_argument("--date", dest="dates", action="append", default=[])
    parser.add_argument("--run-date")
    parser.add_argument("--strategy", default="balanced")
    parser.add_argument("--checkpoint-key")
    parser.add_argument("--checkpoint-label")
    parser.add_argument("--checkpoint-target-days", type=int)
    parser.add_argument("--snapshot-mode", choices=["backtest", "forward"], default="forward")
    parser.add_argument("--snapshot-label", default="CURRENT")
    parser.add_argument("--now", help="Optional ISO timestamp override for deterministic replay.")
    parser.add_argument("--leagues-path", type=Path)
    parser.add_argument("--league-urls-path", type=Path)
    odds_oracle_group = parser.add_mutually_exclusive_group()
    odds_oracle_group.add_argument(
        "--use-original-odds-oracle",
        action="store_true",
        help="Enable the original JS odds oracle for live parity cross-checks before model snapshots are built.",
    )
    odds_oracle_group.add_argument("--disable-odds-oracle", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--disable-model-oracle", action="store_true")
    parser.add_argument("--disable-analysis-oracle", action="store_true")
    parser.add_argument("--use-original-analysis-oracle", action="store_true")
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
        run_date = args.run_date or args.dates[0]
    elif args.mode == "fixture-db":
        read_database = get_database(config)
        target_window = inspect_fixture_target_window_from_database(
            database=read_database,
            dates=args.dates or None,
            max_days_ahead=args.max_days_ahead,
            league_name=args.league,
        )
        targets = load_fixture_targets_from_database(
            database=read_database,
            dates=args.dates or None,
            max_days_ahead=args.max_days_ahead,
            league_name=args.league,
            limit=args.limit if args.limit > 0 else None,
        )
        run_date = args.run_date or (args.dates[0] if args.dates else None)
    else:
        if not args.league:
            raise RuntimeError("--league is required in smoke-live mode.")
        targets = build_smoke_targets_for_league(
            league_name=args.league,
            support_docs=support_docs,
            limit=args.limit,
            max_days_ahead=args.max_days_ahead,
        )
        run_date = args.run_date

    fetched_at = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    database = None if args.dry_run else (read_database or get_database(config))
    legacy_backtest_database = get_legacy_app_database(config) if args.mode == "replay-fixtures" else None
    odds_oracle = OriginalJsOracle(config.old_repo_root) if args.use_original_odds_oracle else None
    model_oracle = None if args.disable_model_oracle else OriginalJsModelOracle(config.old_repo_root)
    if args.disable_analysis_oracle:
        analysis_oracle = False
    elif args.use_original_analysis_oracle:
        analysis_oracle = OriginalJsAutoAnalysisOracle(config.old_repo_root)
    else:
        analysis_oracle = InternalAnalysisOracle()
    summary = run_auto_analysis_pipeline(
        targets=targets,
        support_docs=support_docs,
        source_workflow=args.source_workflow,
        strategy_id=args.strategy,
        run_date=run_date,
        checkpoint_key=args.checkpoint_key,
        checkpoint_label=args.checkpoint_label,
        checkpoint_target_days=args.checkpoint_target_days,
        snapshot_mode=args.snapshot_mode,
        snapshot_label=args.snapshot_label,
        analysis_oracle=analysis_oracle,
        database=database,
        dry_run=args.dry_run,
        odds_oracle=odds_oracle,
        model_oracle=model_oracle,
        legacy_backtest_database=legacy_backtest_database,
        fetched_at=fetched_at,
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
