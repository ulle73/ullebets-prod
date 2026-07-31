from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.closing.watch import load_closing_watch_plan
from ullebets_v2.config import V2Config
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decide whether the GitHub Actions T-10 closing watcher should be enabled."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--lookahead-hours", type=float, default=2.0)
    parser.add_argument("--github-output", type=Path)
    return parser.parse_args()


def _write_github_output(path: Path, plan: dict) -> None:
    values = {
        "action": plan["action"],
        "should_enable": str(plan["should_enable"]).lower(),
        "reason": plan["reason"],
        "pending_fixture_count": plan["pending_fixture_count"],
        "next_pending_match_key": plan.get("next_pending_match_key") or "",
        "next_pending_start_time": plan.get("next_pending_start_time") or "",
    }
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    database = get_database(config)
    plan = load_closing_watch_plan(
        database=database,
        now=datetime.now(tz=UTC),
        lookahead_hours=args.lookahead_hours,
    )
    output_path = args.github_output
    if output_path is None and os.getenv("GITHUB_OUTPUT"):
        output_path = Path(str(os.environ["GITHUB_OUTPUT"]))
    if output_path is not None:
        _write_github_output(output_path, plan)
    print(json.dumps(plan, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
