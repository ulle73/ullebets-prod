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
from ullebets_v2.historical_coverage import run_historical_coverage_audit
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database, get_legacy_app_database, get_legacy_unibet_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit historical overlap coverage between legacy sources and Ullebets V2 collections."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--profile-date")
    parser.add_argument("--source-workflow", default="historical-coverage-audit")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()
    database = get_database(config)
    summary = run_historical_coverage_audit(
        database=database,
        legacy_app_database=get_legacy_app_database(config),
        legacy_unibet_database=get_legacy_unibet_database(config),
        reports_dir=config.reports_dir,
        source_workflow=args.source_workflow,
        start_date=args.start_date,
        end_date=args.end_date,
        profile_date=args.profile_date,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
