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
from ullebets_v2.fixtures.oracle import resolve_fixture_oracle_context
from ullebets_v2.fixtures.replay import iter_target_dates
from ullebets_v2.historical_phase_a.service import run_historical_phase_a_backfill
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database, get_legacy_app_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay historical Phase A fixture + teamstats data into Ullebets V2.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--date")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--profile-date")
    parser.add_argument("--verification-from-date")
    parser.add_argument("--stale-hours", type=int, default=36)
    parser.add_argument("--legacy-oracle-dir", type=Path)
    parser.add_argument("--source-workflow", default="historical-phase-a-backfill")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def resolve_dates(args: argparse.Namespace) -> list[str]:
    if args.date:
        return [args.date]
    if args.start_date and args.end_date:
        return iter_target_dates(args.start_date, args.end_date)
    raise SystemExit("Provide either --date or both --start-date and --end-date.")


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()

    support_docs = load_support_documents(
        leagues_path=config.default_leagues_path(),
        league_urls_path=config.default_league_urls_path(),
    )
    dates = resolve_dates(args)
    legacy_app_database = get_legacy_app_database(config)
    source_dir, old_payloads_by_date, source_paths_by_date = resolve_fixture_oracle_context(
        mode="replay",
        dates=dates,
        old_repo_root=config.old_repo_root,
        legacy_oracle_dir=args.legacy_oracle_dir,
        legacy_match_database=legacy_app_database,
    )
    database = None if args.dry_run else get_database(config)
    summary = run_historical_phase_a_backfill(
        dates=dates,
        support_docs=support_docs,
        old_payloads_by_date=old_payloads_by_date,
        fixture_source_dir=source_dir,
        fixture_source_paths_by_date=source_paths_by_date,
        teamstats_source_dir=config.old_repo_root / "data" / "teamstats",
        legacy_teamstats_database=legacy_app_database,
        database=database,
        dry_run=args.dry_run,
        source_workflow=args.source_workflow,
        verification_from_date=args.verification_from_date,
        profile_date=args.profile_date,
        stale_hours=args.stale_hours,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
