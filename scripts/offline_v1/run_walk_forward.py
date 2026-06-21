from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from ullebets_v1.audit.odds_timing import annotate_backtest_timing
from ullebets_v1.backtest.walk_forward import WalkForwardConfig, run_walk_forward
from ullebets_v1.backtest.pipeline import (
    build_walk_forward_feature_columns,
    select_walk_forward_candidate_rows,
)
from ullebets_v1.config import PipelineConfig
from ullebets_v1.logging_utils import configure_logging
from ullebets_v1.reporting.signal_report import build_signal_report


def main() -> None:
    configure_logging()
    config = PipelineConfig.from_env()
    config.ensure_directories()

    features = pd.read_parquet(config.features_dir / "market_points_primary.parquet")
    market_lines = pd.read_parquet(config.normalized_dir / "market_lines.parquet")
    features = annotate_backtest_timing(features, market_lines)
    features = select_walk_forward_candidate_rows(
        features,
        enforce_strict_prematch=True,
    )
    audit_summary = json.loads((config.reports_dir / "audit_summary.json").read_text(encoding="utf-8"))
    feature_columns, categorical_columns = build_walk_forward_feature_columns(features)

    summary, selections = run_walk_forward(
        features,
        feature_columns=feature_columns,
        categorical_columns=categorical_columns,
        config=WalkForwardConfig(),
    )

    summary_path = config.models_dir / "walk_forward_summary.json"
    selections_path = config.models_dir / "walk_forward_selections.parquet"
    report_path = config.reports_dir / "signal_report.md"
    summary_path.write_text(summary.to_json(orient="records", indent=2), encoding="utf-8")
    if not selections.empty:
        selections.to_parquet(selections_path, index=False)
    report_path.write_text(build_signal_report(audit_summary, summary, selections), encoding="utf-8")
    print(f"wrote_walk_forward_summary={summary_path}")
    print(f"wrote_signal_report={report_path}")
    if not selections.empty:
        print(f"wrote_walk_forward_selections={selections_path}")


if __name__ == "__main__":
    main()
