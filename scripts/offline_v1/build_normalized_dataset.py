from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import duckdb
import pandas as pd

from ullebets_v1.config import PipelineConfig
from ullebets_v1.logging_utils import configure_logging
from ullebets_v1.normalize.coverage import build_market_line_coverage
from ullebets_v1.normalize.market_lines import resolve_filter_reason
from ullebets_v1.normalize.outcomes import annotate_market_line_outcomes
from ullebets_v1.registry.stats import PRIMARY_TARGET_STAT_KEYS


def _load_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def _dedupe_teamstats_index(frame: pd.DataFrame) -> pd.DataFrame:
    priority = {"local_file": 0, "mongo": 1}
    deduped = frame.copy()
    deduped["source_priority"] = deduped["source_kind"].map(priority).fillna(99)
    deduped = deduped.sort_values(
        ["source_priority", "match_id", "match_date", "home_team_name", "away_team_name"]
    )
    deduped = deduped.drop_duplicates(
        subset=["match_id", "match_date", "home_team_name", "away_team_name"],
        keep="first",
    )
    return deduped.drop(columns=["source_priority"])


def _dedupe_teamstats_long(frame: pd.DataFrame) -> pd.DataFrame:
    priority = {"local_file": 0, "mongo": 1}
    deduped = frame.copy()
    deduped["source_priority"] = deduped["source_kind"].map(priority).fillna(99)
    deduped = deduped.sort_values(
        ["source_priority", "match_id", "period", "team_role", "stat_item_key"]
    )
    deduped = deduped.drop_duplicates(
        subset=["match_id", "period", "team_role", "stat_item_key"],
        keep="first",
    )
    return deduped.drop(columns=["source_priority"])


def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    frame.to_parquet(path, index=False)


def _resolved_filter_reason(row: pd.Series) -> str | None:
    if row.get("stat_key") in PRIMARY_TARGET_STAT_KEYS and bool(row.get("has_teamstats_match")):
        if bool(row.get("has_authoritative_teamstats_outcome")) is not True:
            return "missing_teamstats_actual"
    return resolve_filter_reason(
        stat_key=row.get("stat_key"),
        period=row.get("period"),
        scope=row.get("scope"),
        line_value=row.get("line_value"),
        odds_decimal=row.get("odds_decimal"),
        settlement_result=row.get("settlement_result"),
        has_teamstats_match=bool(row.get("has_teamstats_match")),
    )


def _build_source_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[
        [
            "match_id",
            "bet_key",
            "stat_key",
            "period",
            "scope",
            "has_teamstats_match",
            "teamstats_match_count",
            "resolved_teamstats_match_id",
            "exposure_match_id",
            "match_mapping_method",
            "has_clv",
            "clv_match_count",
            "has_shortlist_reference",
            "has_result_loop_reference",
            "is_primary_target",
            "prematch_snapshot_count",
            "has_latest_prematch_snapshot",
            "latest_snapshot_type",
            "latest_snapshot_fetched_at",
            "latest_snapshot_minutes_before_kickoff",
            "effective_odds_source",
            "outcome_verification_status",
            "has_authoritative_teamstats_outcome",
            "filter_reason",
        ]
    ].copy()


def _refresh_duckdb_views(config: PipelineConfig) -> None:
    connection = duckdb.connect(str(config.derived_dir / "ullebets_v1.duckdb"))
    for table_name, subdir in (
        ("matches", "normalized"),
        ("market_lines", "normalized"),
        ("market_snapshots", "normalized"),
        ("line_clv", "normalized"),
        ("source_coverage", "normalized"),
        ("team_stats_long", "normalized"),
    ):
        parquet_path = config.derived_dir / subdir / f"{table_name}.parquet"
        connection.execute(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{parquet_path.as_posix()}')")
    connection.close()


def main() -> None:
    configure_logging()
    config = PipelineConfig.from_env()
    config.ensure_directories()

    market_lines = _load_parquet(config.raw_dir / "mongo_unibet_backtest_lines.parquet")
    market_snapshots = _load_parquet(config.raw_dir / "mongo_unibet_snapshot_lines.parquet")
    closing_lines = _load_parquet(config.raw_dir / "mongo_closing_line_tracking.parquet")
    shortlist_rows = _load_parquet(config.raw_dir / "mongo_analysis_snapshot_shortlist.parquet")
    result_loop_rows = _load_parquet(config.raw_dir / "mongo_result_loop_bets.parquet")
    local_teamstats_index = _load_parquet(config.raw_dir / "local_teamstats_match_index.parquet")
    mongo_teamstats_index = _load_parquet(config.raw_dir / "mongo_teamstats_match_index.parquet")
    local_teamstats_long = _load_parquet(config.raw_dir / "local_teamstats_long.parquet")
    mongo_teamstats_long = _load_parquet(config.raw_dir / "mongo_teamstats_long.parquet")

    teamstats_index = _dedupe_teamstats_index(pd.concat([local_teamstats_index, mongo_teamstats_index], ignore_index=True))
    team_stats_long = _dedupe_teamstats_long(pd.concat([local_teamstats_long, mongo_teamstats_long], ignore_index=True))
    enriched_market_lines, coverage = build_market_line_coverage(
        market_lines=market_lines,
        market_snapshots=market_snapshots,
        teamstats_index=teamstats_index,
        closing_lines=closing_lines,
        shortlist_rows=shortlist_rows,
        result_loop_rows=result_loop_rows,
    )
    enriched_market_lines = annotate_market_line_outcomes(enriched_market_lines, team_stats_long)
    enriched_market_lines["filter_reason"] = enriched_market_lines.apply(_resolved_filter_reason, axis=1)
    coverage = _build_source_coverage(enriched_market_lines)

    _write_parquet(teamstats_index, config.normalized_dir / "matches.parquet")
    _write_parquet(enriched_market_lines, config.normalized_dir / "market_lines.parquet")
    _write_parquet(market_snapshots, config.normalized_dir / "market_snapshots.parquet")
    _write_parquet(closing_lines, config.normalized_dir / "line_clv.parquet")
    _write_parquet(coverage, config.normalized_dir / "source_coverage.parquet")
    _write_parquet(team_stats_long, config.normalized_dir / "team_stats_long.parquet")
    _refresh_duckdb_views(config)

    print(f"wrote_normalized_market_lines={len(enriched_market_lines)}")
    print(f"wrote_normalized_market_snapshots={len(market_snapshots)}")
    print(f"wrote_normalized_team_stats_long={len(team_stats_long)}")


if __name__ == "__main__":
    main()
