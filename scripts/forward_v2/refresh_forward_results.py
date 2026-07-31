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
from ullebets_v2.forward_results.service import run_forward_result_refresh
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh V2 forward result-loop rows from forward bets, CLV, and settlement.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--forward-bets-path", type=Path)
    parser.add_argument("--clv-tracking-path", type=Path)
    parser.add_argument("--closing-lines-path", type=Path)
    parser.add_argument("--settled-bets-path", type=Path)
    parser.add_argument("--match-stats-path", type=Path)
    parser.add_argument("--match-results-path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _load_json_rows(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def _needs_database(args: argparse.Namespace) -> bool:
    return not all(
        [
            args.forward_bets_path,
            (args.clv_tracking_path or args.closing_lines_path),
            (args.settled_bets_path or (args.match_stats_path and args.match_results_path)),
        ]
    )


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()
    database = get_database(config) if _needs_database(args) or not args.dry_run else None
    summary = run_forward_result_refresh(
        forward_bet_docs=_load_json_rows(args.forward_bets_path) if args.forward_bets_path else None,
        clv_tracking_docs=_load_json_rows(args.clv_tracking_path) if args.clv_tracking_path else None,
        closing_line_docs=_load_json_rows(args.closing_lines_path) if args.closing_lines_path else None,
        settled_bet_docs=_load_json_rows(args.settled_bets_path) if args.settled_bets_path else None,
        match_stats_canonical=_load_json_rows(args.match_stats_path) if args.match_stats_path else None,
        match_results_canonical=_load_json_rows(args.match_results_path) if args.match_results_path else None,
        database=database,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
