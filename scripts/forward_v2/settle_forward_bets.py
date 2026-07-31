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
from ullebets_v2.settlement.service import run_forward_bet_settlement
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Settle V2 forward bets against canonical match stats.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-workflow", default="settle-forward-bets.yml")
    parser.add_argument("--forward-bets-path", type=Path)
    parser.add_argument("--match-stats-path", type=Path)
    parser.add_argument("--match-results-path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _load_json_rows(path: Path | None) -> list[dict] | None:
    if path is None:
        return None
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()
    database = None if args.dry_run else get_database(config)
    summary = run_forward_bet_settlement(
        source_workflow=args.source_workflow,
        forward_bet_docs=_load_json_rows(args.forward_bets_path),
        match_stats_canonical=_load_json_rows(args.match_stats_path),
        match_results_canonical=_load_json_rows(args.match_results_path),
        database=database,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
