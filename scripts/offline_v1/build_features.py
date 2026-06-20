from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from ullebets_v1.config import PipelineConfig
from ullebets_v1.features.builder import build_feature_dataset
from ullebets_v1.logging_utils import configure_logging


def _load_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def main() -> None:
    configure_logging()
    config = PipelineConfig.from_env()
    config.ensure_directories()

    market_lines = _load_parquet(config.normalized_dir / "market_lines.parquet")
    matches = _load_parquet(config.normalized_dir / "matches.parquet")
    team_stats_long = _load_parquet(config.normalized_dir / "team_stats_long.parquet")
    line_clv = _load_parquet(config.normalized_dir / "line_clv.parquet")

    feature_frame = build_feature_dataset(
        market_lines=market_lines,
        matches=matches,
        team_stats_long=team_stats_long,
        line_clv=line_clv,
        support_path=config.support_dir / "leagues-and-teams.json",
    )
    out_path = config.features_dir / "market_points_primary.parquet"
    feature_frame.to_parquet(out_path, index=False)
    print(f"wrote_features={out_path} rows={len(feature_frame)}")


if __name__ == "__main__":
    main()
