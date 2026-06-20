from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from ullebets_v1.backtest.walk_forward import WalkForwardConfig, run_walk_forward
from ullebets_v1.config import PipelineConfig
from ullebets_v1.logging_utils import configure_logging
from ullebets_v1.reporting.signal_report import build_signal_report


def main() -> None:
    configure_logging()
    config = PipelineConfig.from_env()
    config.ensure_directories()

    features = pd.read_parquet(config.features_dir / "market_points_primary.parquet")
    features = features[
        (features["is_model_eligible_segment"] == True)
        & (features["is_canonical_line"] == True)
    ].copy()
    audit_summary = json.loads((config.reports_dir / "audit_summary.json").read_text(encoding="utf-8"))

    numeric_exclude = {
        "actual_value",
        "home_opta_rank",
        "home_opta_rating",
        "away_opta_rank",
        "away_opta_rating",
        "opta_rating_diff",
        "opta_rank_diff",
    }
    categorical_columns = ["league_name_normalized", "period", "scope", "stat_key"]
    numeric_prefixes_exclude = (
        "home__match_id",
        "away__match_id",
        "home__match_date",
        "away__match_date",
    )
    feature_columns = []
    for column in features.columns:
        if column in categorical_columns:
            continue
        if column in {
            "match_id",
            "resolved_teamstats_match_id",
            "match_date",
            "league_name",
            "home_team_name",
            "away_team_name",
            "match_mapping_method",
            "over_result",
            "under_result",
            "over_clv_pct",
            "under_clv_pct",
            "has_both_sides",
            "segment_shape",
            "market_side_policy",
            "is_model_eligible_segment",
            "has_clv",
            "line_side_key",
            "saved_at",
            "source_kind",
            "home_support_team_name",
            "away_support_team_name",
            "home_support_team_slug",
            "away_support_team_slug",
            "support_league_c",
            "home_team_c",
            "away_team_c",
        }:
            continue
        if column.startswith(numeric_prefixes_exclude):
            continue
        if column in numeric_exclude:
            continue
        if column in {"over_odds", "under_odds", "market_no_vig_prob_over", "market_no_vig_prob_under", "market_overround", "baseline_lambda", "line_value"} or "__team_" in column or column.startswith("lambda_"):
            feature_columns.append(column)

    summary, selections = run_walk_forward(
        features,
        feature_columns=sorted(set(feature_columns)),
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
