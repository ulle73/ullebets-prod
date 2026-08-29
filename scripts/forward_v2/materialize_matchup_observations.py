from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.config import V2Config
from ullebets_v2.matchup_evaluation.materialize import materialize_matchup_observations
from ullebets_v2.safety import ensure_no_simulated_time_write, ensure_v2_database
from ullebets_v2.storage.collections import MATCHUP_OBSERVATIONS, MATCHUP_RESULTS
from ullebets_v2.storage.indexes import bootstrap_indexes, build_core_index_plan
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze immutable T-1D matchup observations.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--match-key", action="append", required=True)
    parser.add_argument("--now")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    ensure_no_simulated_time_write(time_override=args.now, dry_run=args.dry_run, job_name="materialize_matchup_observations")
    captured_at = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(tz=UTC)
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=UTC)
    database = get_database(config)
    if not args.dry_run:
        wanted = {MATCHUP_OBSERVATIONS, MATCHUP_RESULTS}
        bootstrap_indexes(database, [row for row in build_core_index_plan() if row["collection"] in wanted])
    print(json.dumps(materialize_matchup_observations(database=database, match_keys=args.match_key, captured_at=captured_at, dry_run=args.dry_run), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
