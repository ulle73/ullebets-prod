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
from ullebets_v2.matchups_settlement.service import run_matchup_settlement
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Settle V2 matchup outputs against canonical match actuals.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--date", required=True, help="YYYY-MM-DD or YYYY-MM-DD-YYYY-MM-DD")
    parser.add_argument("--source-workflow", default="enrich-matchups-results.yml")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def expand_date_arg(value: str) -> tuple[str, str]:
    if len(value) == 10:
        return value, value
    if len(value) == 21 and value[10] == "-":
        return value[:10], value[11:]
    raise RuntimeError("--date must be YYYY-MM-DD or YYYY-MM-DD-YYYY-MM-DD")


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()
    date_from, date_to = expand_date_arg(args.date)
    database = get_database(config)
    summary = run_matchup_settlement(
        source_workflow=args.source_workflow,
        date_from=date_from,
        date_to=date_to,
        database=database,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
