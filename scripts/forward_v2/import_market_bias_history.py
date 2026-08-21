from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ullebets_v2.config import V2Config
from ullebets_v2.market_bias.bootstrap import build_bootstrap_candidates
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
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _compact_report(summary: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in summary.items() if key not in PRIVATE_REPORT_FIELDS}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if args.write and args.dry_run:
        raise RuntimeError("--write and --dry-run are mutually exclusive")

    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    database = get_database(config)
    support_docs = {
        "teams": list(database["support_teams"].find({})),
        "leagues": list(database["support_leagues"].find({})),
    }
    as_of = _as_of(args.as_of)
    candidates, adapter_audit = build_bootstrap_candidates(
        args.repo_root / "data" / "derived" / "offline_v1" / "normalized",
        support_docs=support_docs,
        as_of=as_of,
        run_id="bootstrap",
    )
    summary = run_market_bias_refresh(
        source_workflow="import_market_bias_history.py",
        source_kind="offline_v1_bootstrap",
        candidates=candidates,
        as_of=as_of,
        profile_date=args.as_of[:10],
        database=database if args.write else None,
        dry_run=not args.write,
    )
    summary["bootstrap_audit"] = adapter_audit
    report = _compact_report(summary)

    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(report, default=str, indent=2), encoding="utf-8")
    print(json.dumps(report, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
