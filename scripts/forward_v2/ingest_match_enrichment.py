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
from ullebets_v2.enrichment.live import EnrichmentSourceConfig
from ullebets_v2.enrichment.service import run_live_match_enrichment_window, run_match_enrichment_window
from ullebets_v2.fixtures.replay import iter_target_dates
from ullebets_v2.odds.service import load_replay_fixture_targets
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database
from ullebets_v2.support.loaders import load_support_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest V2 match enrichment from replay teamstats files or live fixture targets.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--date")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument("--fixture-source", choices=("replay", "db"), default="replay")
    parser.add_argument("--source-workflow", default="update-teamstats-and-teamprofiles.yml")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def resolve_dates(args: argparse.Namespace) -> list[str] | None:
    if args.date:
        return [args.date]
    if args.start_date and args.end_date:
        return iter_target_dates(args.start_date, args.end_date)
    return None


def load_fixture_targets_from_database(database, dates: list[str] | None) -> list[dict]:
    query = {"source_date": {"$in": dates}} if dates else {}
    return list(database["fixtures_canonical"].find(query, projection={"_id": 0}))


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
    write_database = None if args.dry_run else get_database(config)

    if args.mode == "replay":
        summary = run_match_enrichment_window(
            source_dir=config.old_repo_root / "data" / "teamstats",
            support_docs=support_docs,
            source_workflow=args.source_workflow,
            dates=dates,
            database=write_database,
            dry_run=args.dry_run,
        )
    else:
        dotenv_values = load_dotenv_map(config.env_file)
        merged_env = dict(dotenv_values)
        merged_env.update({key: value for key, value in os.environ.items() if value})
        source_config = EnrichmentSourceConfig.from_env(merged_env)

        if args.fixture_source == "db":
            read_database = write_database or get_database(config)
            targets = load_fixture_targets_from_database(read_database, dates)
        else:
            if not dates:
                raise RuntimeError("--date or --start-date/--end-date is required when --fixture-source=replay.")
            targets = load_replay_fixture_targets(
                dates=dates,
                support_docs=support_docs,
                old_repo_root=config.old_repo_root,
            )

        summary = run_live_match_enrichment_window(
            targets=targets,
            support_docs=support_docs,
            source_workflow=args.source_workflow,
            source_config=source_config,
            database=write_database,
            dry_run=args.dry_run,
        )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
