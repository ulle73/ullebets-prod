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
from ullebets_v2.fixtures.replay import iter_target_dates, load_fixture_payload
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
    parser.add_argument("--source-workflow", default="import-fixtures-rolling.yml")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def resolve_dates(args: argparse.Namespace) -> list[str]:
    if args.date:
        return [args.date]
    if args.start_date and args.end_date:
        return iter_target_dates(args.start_date, args.end_date)
    raise SystemExit("Provide either --date or both --start-date and --end-date.")


def load_old_payloads_by_date(*, source_dir: Path, dates: list[str]) -> dict[str, dict]:
    payloads: dict[str, dict] = {}
    for date_str in dates:
        source_path = source_dir / f"fixtures-{date_str}.json"
        if source_path.exists():
            payloads[date_str] = load_fixture_payload(source_path)
    return payloads


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()

    support_docs = load_support_documents(
        leagues_path=config.old_repo_root / "data" / "leagues-and-teams.json",
        league_urls_path=config.old_repo_root / "data" / "unibetLeagueUrls.json",
    )
    dates = resolve_dates(args)
    source_dir = config.old_repo_root / "matches-for-date"
    old_payloads_by_date = load_old_payloads_by_date(source_dir=source_dir, dates=dates)
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
