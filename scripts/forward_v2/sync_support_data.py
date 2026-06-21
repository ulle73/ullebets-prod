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
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database
from ullebets_v2.support.loaders import DEFAULT_LEAGUE_RANKING_URL, load_support_sync_sources
from ullebets_v2.support.opta import OPTA_RANKINGS_URL
from ullebets_v2.support.service import run_support_sync


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize support data, Opta metadata, and league rankings into V2 collections.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-workflow", default="update-opta.yml")
    parser.add_argument("--leagues-path", type=Path)
    parser.add_argument("--league-urls-path", type=Path)
    parser.add_argument("--opta-path", type=Path)
    parser.add_argument("--opta-url", default=OPTA_RANKINGS_URL)
    parser.add_argument("--league-ranking-path", type=Path)
    parser.add_argument("--league-ranking-url", default=DEFAULT_LEAGUE_RANKING_URL)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()

    sync_sources = load_support_sync_sources(
        leagues_path=args.leagues_path or (config.old_repo_root / "data" / "leagues-and-teams.json"),
        league_urls_path=args.league_urls_path or (config.old_repo_root / "data" / "unibetLeagueUrls.json"),
        opta_path=args.opta_path,
        opta_url=args.opta_url,
        league_ranking_path=args.league_ranking_path,
        league_ranking_url=args.league_ranking_url,
        timeout_seconds=args.timeout_seconds,
    )
    database = None if args.dry_run else get_database(config)
    summary = run_support_sync(
        source_workflow=args.source_workflow,
        leagues_payload=sync_sources["leagues_payload"],
        league_urls_payload=sync_sources["league_urls_payload"],
        source_inputs=sync_sources["source_inputs"],
        opta_payload=sync_sources["opta_payload"],
        league_ranking_payload=sync_sources["league_ranking_payload"],
        database=database,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
