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
from ullebets_v2.storage.indexes import bootstrap_indexes, build_core_index_plan
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap MongoDB indexes for Ullebets V2.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    plan = build_core_index_plan()

    if args.dry_run:
        print(json.dumps({"collections": len(plan), "plan": plan}, indent=2, default=str))
        return 0

    database = get_database(config)
    applied = bootstrap_indexes(database, plan)
    print(json.dumps({"database": config.mongo_db, "applied": applied}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
