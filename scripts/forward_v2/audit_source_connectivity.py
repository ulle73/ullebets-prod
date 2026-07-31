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
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.source_connectivity.service import run_source_connectivity_audit
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit configured RapidAPI and SofaScore source connectivity for V2.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--test-date")
    parser.add_argument("--category-id", default="34")
    parser.add_argument("--match-ids", default="15235566,14065562,14083306")
    parser.add_argument("--max-keys", type=int, default=10)
    parser.add_argument("--source-workflow", default="debug-rapidapi-endpoints.yml")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    database = None if args.dry_run else get_database(config)
    dotenv_values = load_dotenv_map(config.env_file)
    merged_env = dict(dotenv_values)
    merged_env.update({key: value for key, value in os.environ.items() if value})
    summary = run_source_connectivity_audit(
        source_workflow=args.source_workflow,
        test_date=args.test_date,
        category_id=args.category_id,
        match_ids=[item.strip() for item in str(args.match_ids).split(",") if item.strip()],
        max_keys=args.max_keys,
        env=merged_env,
        database=database,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
