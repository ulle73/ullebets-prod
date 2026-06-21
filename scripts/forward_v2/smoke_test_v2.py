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
from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row, materialize_parity_rows
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.indexes import build_core_index_plan
from ullebets_v2.storage.mongo import ping_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a no-side-effect smoke test for the Ullebets V2 foundation.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--ping-db", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()

    payload = {
        "mongo_db": config.mongo_db,
        "data_dir": str(config.data_dir),
        "reports_dir": str(config.reports_dir),
        "index_collection_count": len(build_core_index_plan()),
        "workflow_parity_count": len(materialize_parity_rows()),
        "health_contract": build_health_report_row(
            job_name="smoke_test_v2",
            status="ok",
            summary="Foundation contract loaded.",
        ),
        "audit_contract": build_audit_report_row(
            audit_type="database_safety",
            scope_key="foundation",
            status="ok",
            findings=["MONGODB_DB guard passed."],
        ),
    }

    if args.ping_db:
        payload["ping"] = ping_database(config)

    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
