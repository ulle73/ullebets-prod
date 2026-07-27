from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.config import V2Config, load_dotenv_map
from ullebets_v2.fixtures.live import (
    FixtureSourceConfig,
)
from ullebets_v2.fixtures.oracle import resolve_fixture_oracle_context
from ullebets_v2.fixtures.replay import iter_target_dates
from ullebets_v2.fixtures.service import run_fixture_ingest_window
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay original fixture JSON files into Ullebets V2 fixture collections.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--date")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument(
        "--legacy-oracle-dir",
        type=Path,
        help="Optional legacy match-for-date directory used only for replay or explicit parity comparisons.",
    )
    parser.add_argument("--source-workflow", default="import-fixtures-rolling.yml")
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
    source_dir, old_payloads_by_date = resolve_fixture_oracle_context(
        mode=args.mode,
        dates=dates,
        old_repo_root=config.old_repo_root,
        legacy_oracle_dir=args.legacy_oracle_dir,
    )
    dotenv_values = load_dotenv_map(config.env_file)
    merged_env = dict(dotenv_values)
    merged_env.update({key: value for key, value in os.environ.items() if value})
    source_config = FixtureSourceConfig.from_env(merged_env) if args.mode == "live" else None
    database = None if args.dry_run else get_database(config)
    summary = run_fixture_ingest_window(
        mode=args.mode,
        dates=dates,
        support_docs=support_docs,
        source_workflow=args.source_workflow,
        old_payloads_by_date=old_payloads_by_date,
        source_dir=source_dir,
        database=database,
        dry_run=args.dry_run,
        source_config=source_config,
    )

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
