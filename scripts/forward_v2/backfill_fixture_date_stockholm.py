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
from ullebets_v2.fixtures.persistence import backfill_fixture_date_stockholm
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Stockholm-local fixture dates in Ullebets V2.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    summary = backfill_fixture_date_stockholm(
        get_database(config),
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    print(json.dumps({"database": config.mongo_db, "dry_run": args.dry_run, **summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
