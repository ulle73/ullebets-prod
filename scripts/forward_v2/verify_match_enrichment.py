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
from ullebets_v2.verification.service import run_match_enrichment_verification


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify V2 match enrichment coverage and staleness.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--from-date")
    parser.add_argument("--stale-hours", type=int, default=36)
    parser.add_argument("--source-workflow", default="verify-teamstats-db.yml")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    database = get_database(config)
    summary = run_match_enrichment_verification(
        source_workflow=args.source_workflow,
        from_date=args.from_date,
        stale_hours=args.stale_hours,
        database=database,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

