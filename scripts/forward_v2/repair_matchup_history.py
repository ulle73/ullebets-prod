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
from ullebets_v2.matchups.history import repair_matchup_history
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build missing matchup rankings and settle a bounded historical date range.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--source-workflow", default="enrich-matchups-results.yml")
    parser.add_argument("--rebuild-existing", action="store_true")
    parser.add_argument("--max-rebuild-dates", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    database = get_database(config)
    summary = repair_matchup_history(
        database=database,
        date_from=args.start_date,
        date_to=args.end_date,
        source_workflow=args.source_workflow,
        dry_run=args.dry_run,
        rebuild_existing=args.rebuild_existing,
        max_rebuild_dates=args.max_rebuild_dates,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
