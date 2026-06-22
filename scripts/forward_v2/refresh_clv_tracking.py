from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.clv_tracking.service import run_clv_tracking_refresh
from ullebets_v2.config import V2Config
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh V2 CLV tracking rows from model_snapshots and closing_lines_v2.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--model-snapshots-path", type=Path)
    parser.add_argument("--closing-lines-path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _load_json_rows(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    ensure_v2_database(config)
    config.ensure_directories()
    database = None if args.dry_run else get_database(config)
    model_snapshot_docs = _load_json_rows(args.model_snapshots_path) if args.model_snapshots_path else None
    closing_line_docs = _load_json_rows(args.closing_lines_path) if args.closing_lines_path else None
    summary = run_clv_tracking_refresh(
        model_snapshot_docs=model_snapshot_docs,
        closing_line_docs=closing_line_docs,
        database=database,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
