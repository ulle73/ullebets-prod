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
from ullebets_v2.matchups.service import run_matchups_score_build


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build V2 matchup score rankings from fixtures and teamprofiles.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--date", required=True)
    parser.add_argument("--source-workflow", default="dump-matchups.yml")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()
    database = get_database(config)
    targets = list(database["fixtures_canonical"].find({"source_date": args.date}, projection={"_id": 0}))
    summary = run_matchups_score_build(
        source_workflow=args.source_workflow,
        target_matches=targets,
        snapshot_date=args.date,
        database=None if args.dry_run else database,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
