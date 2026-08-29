from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.config import V2Config
from ullebets_v2.matchup_evaluation.results import refresh_matchup_results
from ullebets_v2.safety import ensure_no_simulated_time_write, ensure_v2_database
from ullebets_v2.storage.collections import MATCHUP_OBSERVATIONS, MATCHUP_RESULTS
from ullebets_v2.storage.indexes import bootstrap_indexes, build_core_index_plan
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh matchup predictor and exact-market results.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--date")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--now")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.date and (args.date_from or args.date_to):
        raise SystemExit("Use either --date or --date-from/--date-to.")
    if bool(args.date_from) != bool(args.date_to):
        raise SystemExit("--date-from and --date-to must be provided together.")
    date_from = args.date or args.date_from
    date_to = args.date or args.date_to
    if date_from and date_to and date.fromisoformat(date_to) < date.fromisoformat(date_from):
        raise SystemExit("date range is reversed")
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    ensure_no_simulated_time_write(time_override=args.now, dry_run=args.dry_run, job_name="refresh_matchup_results")
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(tz=UTC)
    database = get_database(config)
    if not args.dry_run:
        wanted = {MATCHUP_OBSERVATIONS, MATCHUP_RESULTS}
        bootstrap_indexes(database, [row for row in build_core_index_plan() if row["collection"] in wanted])
    print(json.dumps(refresh_matchup_results(database=database, refreshed_at=now, date_from=date_from, date_to=date_to, dry_run=args.dry_run), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
