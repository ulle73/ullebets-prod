from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from ullebets_v1.audit.data_audit import build_audit_markdown, build_audit_summary
from ullebets_v1.config import PipelineConfig
from ullebets_v1.logging_utils import configure_logging


def _load_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def main() -> None:
    configure_logging()
    config = PipelineConfig.from_env()
    config.ensure_directories()

    market_lines = _load_parquet(config.normalized_dir / "market_lines.parquet")
    coverage = _load_parquet(config.normalized_dir / "source_coverage.parquet")
    team_stats_long = _load_parquet(config.normalized_dir / "team_stats_long.parquet")

    summary = build_audit_summary(
        market_lines=market_lines,
        coverage=coverage,
        team_stats_long=team_stats_long,
    )
    markdown = build_audit_markdown(summary)

    json_path = config.reports_dir / "audit_summary.json"
    md_path = config.reports_dir / "audit_summary.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    print(f"wrote_audit_json={json_path}")
    print(f"wrote_audit_markdown={md_path}")


if __name__ == "__main__":
    main()
