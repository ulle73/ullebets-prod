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
from ullebets_v2.enrichment.replay import build_match_enrichment_documents, build_teamstats_source_rows
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database
from ullebets_v2.support.loaders import load_support_documents
from ullebets_v2.teamprofiles.service import run_teamprofile_build


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build V2 teamprofiles from canonical enrichment rows.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--profile-date")
    parser.add_argument("--source-workflow", default="update-teamstats-and-teamprofiles.yml")
    parser.add_argument("--teamstats-dir", type=Path)
    parser.add_argument("--leagues-path", type=Path)
    parser.add_argument("--league-urls-path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()
    support_docs = load_support_documents(
        leagues_path=args.leagues_path or (config.old_repo_root / "data" / "leagues-and-teams.json"),
        league_urls_path=args.league_urls_path or (config.old_repo_root / "data" / "unibetLeagueUrls.json"),
    )
    database = None if args.dry_run else get_database(config)
    match_stats_canonical = None
    match_results_canonical = None
    if args.teamstats_dir:
        docs = build_match_enrichment_documents(
            source_rows=build_teamstats_source_rows(args.teamstats_dir),
            support_docs=support_docs,
        )
        match_stats_canonical = docs["match_stats_canonical"]
        match_results_canonical = docs["match_results"]
    summary = run_teamprofile_build(
        source_workflow=args.source_workflow,
        support_docs=support_docs,
        match_stats_canonical=match_stats_canonical,
        match_results_canonical=match_results_canonical,
        profile_date=args.profile_date,
        database=database,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
