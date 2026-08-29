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
from ullebets_v2.matchup_evaluation.legacy import build_legacy_matchup_evaluation_docs
from ullebets_v2.matchup_evaluation.observations import persist_matchup_observations
from ullebets_v2.matchup_evaluation.results import persist_matchup_results
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.collections import MATCHUP_OBSERVATIONS, MATCHUP_RESULTS, MATCHUPS_SCORE
from ullebets_v2.storage.indexes import bootstrap_indexes, build_core_index_plan
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill bounded legacy descriptive matchup evidence.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if date.fromisoformat(args.date_to) < date.fromisoformat(args.date_from):
        raise SystemExit("date range is reversed")
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    database = get_database(config)
    if not args.dry_run:
        wanted = {MATCHUP_OBSERVATIONS, MATCHUP_RESULTS}
        bootstrap_indexes(database, [row for row in build_core_index_plan() if row["collection"] in wanted])
    score_rows = list(database[MATCHUPS_SCORE].find({"snapshot_date": {"$gte": args.date_from, "$lte": args.date_to}}, projection={"_id": 0}))
    observations, results = build_legacy_matchup_evaluation_docs(score_rows=score_rows, generated_at=datetime.now(tz=UTC))
    persistence = {"observations": {"inserted": 0, "existing": 0, "conflicts": 0}, "results": {"inserted": 0, "updated": 0, "unchanged": 0, "conflicts": 0}}
    if not args.dry_run:
        persistence["observations"] = persist_matchup_observations(database[MATCHUP_OBSERVATIONS], observations)
        persistence["results"] = persist_matchup_results(database[MATCHUP_RESULTS], results)
    print(json.dumps({"score_rows": len(score_rows), "observations": len(observations), "results": len(results), "persistence": persistence}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
