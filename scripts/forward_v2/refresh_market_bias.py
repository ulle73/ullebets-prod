from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ullebets_v2.config import V2Config
from ullebets_v2.market_bias.forward import load_forward_candidates
from ullebets_v2.market_bias.service import run_market_bias_refresh
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database


PRIVATE_REPORT_FIELDS = {
    "observation_docs",
    "profile_docs",
    "audit_rows",
    "health_rows",
}


def _as_of(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--as-of must include a timezone offset or Z.")
    return parsed.astimezone(UTC)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--source-workflow", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.dry_run and args.write:
        raise RuntimeError("--write and --dry-run are mutually exclusive")

    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    database = get_database(config)
    as_of = _as_of(args.as_of)
    candidates, adapter_audit = load_forward_candidates(
        database,
        from_date=args.from_date,
        to_date=args.to_date,
        as_of=as_of,
        run_id="forward",
    )
    summary = run_market_bias_refresh(
        source_workflow=args.source_workflow,
        source_kind="v2_forward",
        candidates=candidates,
        as_of=as_of,
        profile_date=args.as_of[:10],
        database=database,
        dry_run=not args.write,
    )
    summary["forward_audit"] = adapter_audit
    report = {key: value for key, value in summary.items() if key not in PRIVATE_REPORT_FIELDS}
    print(json.dumps(report, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
