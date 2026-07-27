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
from ullebets_v2.config import V2Config
from ullebets_v2.model_snapshots.ephemeral import build_ephemeral_model_read_database
from ullebets_v2.model_snapshots.oracle import OriginalJsModelOracle, V2JsModelOracle
from ullebets_v2.odds.oracle import OriginalJsOracle
from ullebets_v2.odds.service import (
    build_smoke_targets_for_league,
    inspect_fixture_target_window_from_database,
    load_fixture_targets_from_database,
    load_legacy_backtest_targets,
    load_replay_fixture_targets,
)
from ullebets_v2.prediction_exports.service import run_prediction_export_pipeline
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database, get_legacy_app_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build V2 AI bet exports and immutable forward bet rows from canonical analysis outputs.")
    parser.add_argument("--mode", choices=["daily", "combos", "user-daily", "user-closing"], default="daily")
    parser.add_argument("--target-mode", choices=["smoke-live", "replay-fixtures", "legacy-backtest", "fixture-db"], default="smoke-live")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-workflow")
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
    parser.add_argument("--snapshot-source", choices=["build", "db"], default="build")
    parser.add_argument("--now", help="Optional ISO timestamp override for deterministic replay.")
    parser.add_argument("--leagues-path", type=Path)
    parser.add_argument("--league-urls-path", type=Path)
    parser.add_argument("--teamstats-dir", type=Path)
    odds_oracle_group = parser.add_mutually_exclusive_group()
    odds_oracle_group.add_argument(
        "--use-original-odds-oracle",
        action="store_true",
        help="Enable the original JS odds oracle for live parity cross-checks before model snapshots are built.",
    )
    odds_oracle_group.add_argument("--disable-odds-oracle", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--disable-model-oracle", action="store_true")
    parser.add_argument("--use-original-model-oracle", action="store_true")
    parser.add_argument("--disable-analysis-oracle", action="store_true")
    parser.add_argument("--use-original-analysis-oracle", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def default_source_workflow(mode: str) -> str:
    return {
        "daily": "ai-bets-daily.yml",
        "combos": "ai-user-combos.yml",
        "user-daily": "ai-user-daily.yml",
        "user-closing": "ai-user-closing.yml",
    }[mode]


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
    legacy_backtest_database = None
    if args.target_mode == "replay-fixtures":
        if not args.dates:
            raise RuntimeError("--date is required in replay-fixtures target mode.")
        targets = load_replay_fixture_targets(
            dates=args.dates,
            support_docs=support_docs,
            old_repo_root=config.old_repo_root,
            legacy_match_database=get_legacy_app_database(config),
        )
        legacy_backtest_database = get_legacy_app_database(config)
        run_date = args.run_date or args.dates[0]
    elif args.target_mode == "legacy-backtest":
        if not args.dates:
            raise RuntimeError("--date is required in legacy-backtest target mode.")
        targets = load_legacy_backtest_targets(
            dates=args.dates,
            support_docs=support_docs,
            legacy_backtest_database=get_legacy_app_database(config),
            legacy_match_database=get_legacy_app_database(config),
            limit=args.limit if args.limit > 0 else None,
        )
        legacy_backtest_database = get_legacy_app_database(config)
        run_date = args.run_date or args.dates[0]
    elif args.target_mode == "fixture-db":
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
            raise RuntimeError("--league is required in smoke-live target mode.")
        targets = build_smoke_targets_for_league(
            league_name=args.league,
            support_docs=support_docs,
            limit=args.limit,
            max_days_ahead=args.max_days_ahead,
        )
        run_date = args.run_date

    fetched_at = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    snapshot_read_database = read_database or (get_database(config) if args.snapshot_source == "db" else None)
    database = None if args.dry_run else (read_database or get_database(config))
    odds_oracle = OriginalJsOracle(config.old_repo_root) if args.use_original_odds_oracle else None
    teamstats_dir = args.teamstats_dir or (config.old_repo_root / "data" / "teamstats")
    model_read_database = snapshot_read_database
    if (
        not args.use_original_model_oracle
        and args.target_mode == "legacy-backtest"
        and teamstats_dir.exists()
    ):
        model_read_database = build_ephemeral_model_read_database(
            teamstats_dir=teamstats_dir,
            support_docs=support_docs,
            targets=targets,
            generated_at=fetched_at,
        )
    if args.disable_model_oracle:
        model_oracle = None
    elif args.use_original_model_oracle or args.target_mode == "replay-fixtures":
        model_oracle = OriginalJsModelOracle(config.old_repo_root)
    elif model_read_database is not None:
        model_oracle = V2JsModelOracle(model_read_database, support_docs)
    else:
        model_oracle = None
    if args.disable_analysis_oracle:
        analysis_oracle = False
    elif args.use_original_analysis_oracle:
        analysis_oracle = OriginalJsAutoAnalysisOracle(config.old_repo_root)
    else:
        analysis_oracle = InternalAnalysisOracle()
    summary = run_prediction_export_pipeline(
        export_mode=args.mode,
        source_workflow=args.source_workflow or default_source_workflow(args.mode),
        targets=targets,
        support_docs=support_docs,
        database=database,
        dry_run=args.dry_run,
        strategy_id=args.strategy,
        run_date=run_date,
        checkpoint_key=args.checkpoint_key,
        checkpoint_label=args.checkpoint_label,
        checkpoint_target_days=args.checkpoint_target_days,
        snapshot_mode=args.snapshot_mode,
        snapshot_label=args.snapshot_label,
        analysis_oracle=analysis_oracle,
        odds_oracle=odds_oracle,
        model_oracle=model_oracle,
        legacy_backtest_database=legacy_backtest_database,
        use_legacy_snapshot_lines=args.target_mode != "legacy-backtest",
        fetched_at=fetched_at,
        snapshot_source=args.snapshot_source,
        snapshot_read_database=snapshot_read_database,
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
