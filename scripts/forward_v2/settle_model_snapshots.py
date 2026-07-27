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

from ullebets_v2.config import V2Config
from ullebets_v2.model_snapshots.ephemeral import (
    build_ephemeral_match_enrichment_documents,
    build_ephemeral_model_read_database,
)
from ullebets_v2.model_snapshots.oracle import OriginalJsModelOracle, V2JsModelOracle
from ullebets_v2.model_snapshots.service import run_model_snapshot_build
from ullebets_v2.odds.service import load_legacy_backtest_targets
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.settlement.service import run_model_snapshot_settlement
from ullebets_v2.storage.mongo import get_database, get_legacy_app_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Settle V2 model snapshots against canonical match stats.")
    parser.add_argument("--mode", choices=["paths-or-db", "legacy-backtest"], default="paths-or-db")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-workflow", default="correct-backtests-daily.yml")
    parser.add_argument("--model-snapshots-path", type=Path)
    parser.add_argument("--match-stats-path", type=Path)
    parser.add_argument("--match-results-path", type=Path)
    parser.add_argument("--date", dest="dates", action="append", default=[])
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--teamstats-dir", type=Path)
    parser.add_argument("--leagues-path", type=Path)
    parser.add_argument("--league-urls-path", type=Path)
    parser.add_argument("--snapshot-mode", choices=["backtest", "forward"], default="backtest")
    parser.add_argument("--snapshot-label", default="CURRENT")
    parser.add_argument("--use-original-model-oracle", action="store_true")
    parser.add_argument("--now")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _load_json_rows(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()
    database = None if args.dry_run else get_database(config)
    if args.mode == "legacy-backtest":
        if not args.dates:
            raise RuntimeError("--date is required in legacy-backtest mode.")
        legacy_app_database = get_legacy_app_database(config)
        support_docs = load_support_documents(
            leagues_path=args.leagues_path or config.default_leagues_path(),
            league_urls_path=args.league_urls_path or config.default_league_urls_path(),
        )
        targets = load_legacy_backtest_targets(
            dates=args.dates,
            support_docs=support_docs,
            legacy_backtest_database=legacy_app_database,
            legacy_match_database=legacy_app_database,
            limit=args.limit if args.limit > 0 else None,
        )
        teamstats_dir = args.teamstats_dir or (config.old_repo_root / "data" / "teamstats")
        if not teamstats_dir.exists():
            raise RuntimeError(f"teamstats directory not found: {teamstats_dir}")
        fetched_at = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
        read_database = build_ephemeral_model_read_database(
            teamstats_dir=teamstats_dir,
            support_docs=support_docs,
            targets=targets,
            generated_at=fetched_at,
        )
        enrichment_docs = build_ephemeral_match_enrichment_documents(
            teamstats_dir=teamstats_dir,
            support_docs=support_docs,
            targets=targets,
        )
        model_oracle = (
            OriginalJsModelOracle(config.old_repo_root)
            if args.use_original_model_oracle
            else V2JsModelOracle(read_database, support_docs)
        )
        model_summary = run_model_snapshot_build(
            targets=targets,
            support_docs=support_docs,
            source_workflow="run-unibet-backtests.yml",
            snapshot_mode=args.snapshot_mode,
            snapshot_label=args.snapshot_label,
            database=None,
            dry_run=True,
            model_oracle=model_oracle,
            legacy_backtest_database=legacy_app_database,
            use_legacy_snapshot_lines=False,
            fetched_at=fetched_at,
            return_documents=True,
        )
        model_snapshot_docs = model_summary["documents"]["model_snapshot_docs"]
        match_stats_canonical = enrichment_docs["match_stats_canonical"]
        match_results_canonical = enrichment_docs["match_results"]
    else:
        model_snapshot_docs = _load_json_rows(args.model_snapshots_path) if args.model_snapshots_path else None
        match_stats_canonical = _load_json_rows(args.match_stats_path) if args.match_stats_path else None
        match_results_canonical = _load_json_rows(args.match_results_path) if args.match_results_path else None
    summary = run_model_snapshot_settlement(
        source_workflow=args.source_workflow,
        model_snapshot_docs=model_snapshot_docs,
        match_stats_canonical=match_stats_canonical,
        match_results_canonical=match_results_canonical,
        database=database,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
