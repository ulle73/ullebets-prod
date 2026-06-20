from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from ullebets_v1.config import PipelineConfig
from ullebets_v1.logging_utils import configure_logging
from ullebets_v1.reporting.diagnostics import build_model_diagnostics, build_model_diagnostics_markdown


def main() -> None:
    configure_logging()
    config = PipelineConfig.from_env()
    config.ensure_directories()

    feature_frame = pd.read_parquet(config.features_dir / "market_points_primary.parquet")
    selections_path = config.models_dir / "walk_forward_selections.parquet"
    selections = pd.read_parquet(selections_path) if selections_path.exists() else pd.DataFrame()

    diagnostics = build_model_diagnostics(feature_frame, selections)
    markdown = build_model_diagnostics_markdown(diagnostics)

    json_path = config.reports_dir / "model_diagnostics.json"
    md_path = config.reports_dir / "model_diagnostics.md"
    json_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    print(f"wrote_model_diagnostics_json={json_path}")
    print(f"wrote_model_diagnostics_markdown={md_path}")


if __name__ == "__main__":
    main()
