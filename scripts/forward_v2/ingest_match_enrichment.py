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
from ullebets_v2.enrichment.service import run_match_enrichment_window
from ullebets_v2.fixtures.replay import iter_target_dates
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay old teamstats files into V2 match enrichment collections.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--date")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--source-workflow", default="update-teamstats-and-teamprofiles.yml")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def resolve_dates(args: argparse.Namespace) -> list[str] | None:
    if args.date:
        return [args.date]
    if args.start_date and args.end_date:
        return iter_target_dates(args.start_date, args.end_date)
    return None


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()

    support_docs = load_support_documents(
        leagues_path=config.old_repo_root / "data" / "leagues-and-teams.json",
        league_urls_path=config.old_repo_root / "data" / "unibetLeagueUrls.json",
    )
    database = None if args.dry_run else get_database(config)
    summary = run_match_enrichment_window(
        source_dir=config.old_repo_root / "data" / "teamstats",
        support_docs=support_docs,
        source_workflow=args.source_workflow,
        dates=resolve_dates(args),
        database=database,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
