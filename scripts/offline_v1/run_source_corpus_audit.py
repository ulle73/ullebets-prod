from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from ullebets_v1.audit.source_corpus import build_source_corpus_markdown, build_source_corpus_summary
from ullebets_v1.config import PipelineConfig
from ullebets_v1.logging_utils import configure_logging


def _load_parquet_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def main() -> None:
    configure_logging()
    config = PipelineConfig.from_env()
    config.ensure_directories()

    source_frames = {
        "unibet_backtest_lines": _load_parquet_if_exists(config.raw_dir / "mongo_unibet_backtest_lines.parquet"),
        "unibet_snapshot_lines": _load_parquet_if_exists(config.raw_dir / "mongo_unibet_snapshot_lines.parquet"),
        "ai_generated_bet_lines": _load_parquet_if_exists(config.raw_dir / "mongo_ai_generated_bet_lines.parquet"),
        "ai_generated_bet_snapshots": _load_parquet_if_exists(config.raw_dir / "mongo_ai_generated_bet_snapshots.parquet"),
        "auto_analysis_bets": _load_parquet_if_exists(config.raw_dir / "mongo_auto_analysis_bets.parquet"),
        "analysis_snapshot_shortlist": _load_parquet_if_exists(config.raw_dir / "mongo_analysis_snapshot_shortlist.parquet"),
        "result_loop_bets": _load_parquet_if_exists(config.raw_dir / "mongo_result_loop_bets.parquet"),
        "closing_line_tracking": _load_parquet_if_exists(config.raw_dir / "mongo_closing_line_tracking.parquet"),
    }

    summary = build_source_corpus_summary(source_frames)
    markdown = build_source_corpus_markdown(summary)

    json_path = config.reports_dir / "source_corpus_summary.json"
    md_path = config.reports_dir / "source_corpus_summary.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    print(f"wrote_source_corpus_json={json_path}")
    print(f"wrote_source_corpus_markdown={md_path}")


if __name__ == "__main__":
    main()
