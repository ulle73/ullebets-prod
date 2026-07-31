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
from ullebets_v2.date_windows import resolve_requested_dates, resolve_target_limit
from ullebets_v2.model_snapshots.ephemeral import resolve_historical_model_read_database
from ullebets_v2.model_snapshots.oracle import OriginalJsModelOracle, V2JsModelOracle
from ullebets_v2.odds.oracle import OriginalJsOracle
from ullebets_v2.odds.service import (
    build_smoke_targets_for_league,
    inspect_fixture_target_window_from_database,
    load_historical_replay_targets,
    load_fixture_targets_from_database,
    load_replay_fixture_targets,
)
from ullebets_v2.safety import (
    ensure_no_simulated_time_write,
    ensure_v2_database,
)
from ullebets_v2.storage.mongo import get_database, get_legacy_app_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V2 auto-analysis using canonical model snapshots and the legacy JS ranking policy.")
    parser.add_argument("--mode", choices=["smoke-live", "replay-fixtures", "legacy-backtest", "fixture-db"], default="smoke-live")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-workflow", default="run-auto-analysis-checkpoints.yml")
    parser.add_argument("--league")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-days-ahead", type=int, default=7)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
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


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    ensure_no_simulated_time_write(
        time_override=args.now,
        dry_run=args.dry_run,
        job_name="run_auto_analysis",
    )
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
        targets = load_replay_fixture_targets(
            dates=requested_dates,
            support_docs=support_docs,
            old_repo_root=config.old_repo_root,
            legacy_match_database=get_legacy_app_database(config),
        )
        run_date = args.run_date or requested_dates[0]
    elif args.mode == "legacy-backtest":
        if not requested_dates:
            raise RuntimeError("--date or --start-date/--end-date is required in legacy-backtest mode.")
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
        run_date = args.run_date or requested_dates[0]
    elif args.mode == "fixture-db":
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
        run_date = args.run_date or (requested_dates[0] if requested_dates else None)
    else:
        if not args.league:
            raise RuntimeError("--league is required in smoke-live mode.")
        targets = build_smoke_targets_for_league(
            league_name=args.league,
            support_docs=support_docs,
            limit=resolve_target_limit(args.limit, default_when_unspecified=1),
            max_days_ahead=args.max_days_ahead,
        )
        run_date = args.run_date

    fetched_at = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    snapshot_read_database = read_database if read_database is not None else (
        get_database(config) if args.snapshot_source == "db" else None
    )
    database = None if args.dry_run else (read_database if read_database is not None else get_database(config))
    legacy_backtest_database = get_legacy_app_database(config) if args.mode in {"replay-fixtures", "legacy-backtest"} else None
    odds_oracle = OriginalJsOracle(config.old_repo_root) if args.use_original_odds_oracle else None
    teamstats_dir = args.teamstats_dir or (config.old_repo_root / "data" / "teamstats")
    model_read_database = snapshot_read_database
    model_read_source = "v2_database"
    if (
        not args.use_original_model_oracle
        and args.mode == "legacy-backtest"
    ):
        model_read_database, model_read_source = resolve_historical_model_read_database(
            read_database=model_read_database,
            teamstats_dir=teamstats_dir,
            support_docs=support_docs,
            targets=targets,
            generated_at=fetched_at,
            legacy_teamstats_database=legacy_backtest_database,
        )
    if args.disable_model_oracle:
        model_oracle = None
    elif args.use_original_model_oracle or args.mode == "replay-fixtures":
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
        use_legacy_snapshot_lines=args.mode != "legacy-backtest",
        fetched_at=fetched_at,
        snapshot_source=args.snapshot_source,
        snapshot_read_database=snapshot_read_database,
    )
    if target_window is not None:
        target_window["selected_target_match_count"] = len(targets)
        summary["target_window"] = target_window
        if not targets:
            summary["empty_reason"] = target_window.get("empty_reason")
    summary["model_read_source"] = model_read_source
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
