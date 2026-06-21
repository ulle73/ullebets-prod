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
from ullebets_v2.parity.reports import materialize_parity_rows
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed workflow parity rows for Ullebets V2.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    rows = materialize_parity_rows()

    if args.dry_run:
        print(json.dumps({"rows": rows, "count": len(rows)}, indent=2, default=str))
        return 0

    database = get_database(config)
    collection = database["parity_reports"]
    upserted = 0
    for row in rows:
        result = collection.update_one(
            {
                "old_workflow": row["old_workflow"],
                "report_date": row["report_date"],
            },
            {"$set": row},
            upsert=True,
        )
        if result.upserted_id is not None:
            upserted += 1

    print(
        json.dumps(
            {
                "database": config.mongo_db,
                "workflow_count": len(rows),
                "upserted": upserted,
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
