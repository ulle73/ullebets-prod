from __future__ import annotations

import re
import unicodedata

import pandas as pd

from ullebets_v1.normalize.market_lines import resolve_filter_reason
from ullebets_v1.registry.stats import PRIMARY_TARGET_STAT_KEYS


def _canon_name(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _composite_market_key(frame: pd.DataFrame) -> pd.Series:
    pieces = [
        frame["match_id"].fillna("").astype(str),
        frame["stat_key"].fillna("").astype(str),
        frame["period"].fillna("").astype(str),
        frame["scope"].fillna("").astype(str),
        frame["direction"].fillna("").astype(str),
        frame["line_value"].fillna("").astype(str),
    ]
    return pieces[0].str.cat(pieces[1:], sep="|")


def _enrich_latest_snapshot_metadata(
    enriched: pd.DataFrame,
    market_snapshots: pd.DataFrame,
) -> pd.DataFrame:
    if market_snapshots.empty:
        enriched["prematch_snapshot_count"] = 0
        enriched["has_latest_prematch_snapshot"] = False
        enriched["latest_snapshot_type"] = None
        enriched["latest_snapshot_fetched_at"] = None
        enriched["latest_snapshot_odds_decimal"] = None
        enriched["latest_snapshot_minutes_before_kickoff"] = None
        enriched["effective_odds_decimal"] = enriched["odds_decimal"]
        enriched["effective_odds_source"] = "root_line"
        enriched["effective_odds_diff_vs_root"] = 0.0
        return enriched

    snapshot_rows = market_snapshots.copy()
    snapshot_rows["market_join_key"] = _composite_market_key(snapshot_rows)
    snapshot_rows["snapshot_fetched_at_ts"] = pd.to_datetime(
        snapshot_rows["snapshot_fetched_at"],
        errors="coerce",
        utc=True,
    )

    line_meta = enriched[["market_join_key", "kickoff_ts"]].drop_duplicates(
        subset=["market_join_key"]
    )
    snapshot_rows = snapshot_rows.merge(
        line_meta,
        how="left",
        on="market_join_key",
    )
    snapshot_rows["kickoff_at_ts"] = pd.to_datetime(
        snapshot_rows["kickoff_ts"],
        unit="s",
        errors="coerce",
        utc=True,
    )

    prematch = snapshot_rows[
        snapshot_rows["snapshot_fetched_at_ts"].notna()
        & (
            snapshot_rows["kickoff_at_ts"].isna()
            | (snapshot_rows["snapshot_fetched_at_ts"] < snapshot_rows["kickoff_at_ts"])
        )
    ].copy()

    counts = (
        prematch.groupby("market_join_key", dropna=False)
        .size()
        .rename("prematch_snapshot_count")
        .reset_index()
    )
    latest = (
        prematch.sort_values(["market_join_key", "snapshot_fetched_at_ts"])
        .drop_duplicates(subset=["market_join_key"], keep="last")
        .copy()
    )
    latest["latest_snapshot_minutes_before_kickoff"] = (
        (latest["kickoff_at_ts"] - latest["snapshot_fetched_at_ts"]).dt.total_seconds()
        / 60.0
    )
    latest = latest[
        [
            "market_join_key",
            "snapshot_type",
            "snapshot_fetched_at",
            "odds_decimal",
            "latest_snapshot_minutes_before_kickoff",
        ]
    ].rename(
        columns={
            "snapshot_type": "latest_snapshot_type",
            "snapshot_fetched_at": "latest_snapshot_fetched_at",
            "odds_decimal": "latest_snapshot_odds_decimal",
        }
    )

    merged = enriched.merge(counts, how="left", on="market_join_key")
    merged = merged.merge(latest, how="left", on="market_join_key")
    merged["prematch_snapshot_count"] = merged["prematch_snapshot_count"].fillna(0).astype(int)
    merged["has_latest_prematch_snapshot"] = merged["latest_snapshot_fetched_at"].notna()
    merged["effective_odds_decimal"] = merged["latest_snapshot_odds_decimal"].fillna(
        merged["odds_decimal"]
    )
    merged["effective_odds_source"] = merged["has_latest_prematch_snapshot"].map(
        lambda value: "latest_snapshot" if value else "root_line"
    )
    merged["effective_odds_diff_vs_root"] = (
        merged["effective_odds_decimal"] - merged["odds_decimal"]
    )
    return merged


def _fill_count_column(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).astype("int64")


def build_market_line_coverage(
    market_lines: pd.DataFrame,
    market_snapshots: pd.DataFrame,
    teamstats_index: pd.DataFrame,
    closing_lines: pd.DataFrame,
    shortlist_rows: pd.DataFrame,
    result_loop_rows: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    enriched = market_lines.copy()
    enriched["match_id"] = enriched["match_id"].astype("string")
    enriched["bet_key"] = enriched["bet_key"].astype("string")
    enriched["home_c"] = enriched["home_team_name"].map(_canon_name)
    enriched["away_c"] = enriched["away_team_name"].map(_canon_name)

    teamstats_pairs = teamstats_index[
        ["match_id", "match_date", "home_team_name", "away_team_name"]
    ].drop_duplicates()
    teamstats_pairs["match_id"] = teamstats_pairs["match_id"].astype("string")
    teamstats_pairs["home_c"] = teamstats_pairs["home_team_name"].map(_canon_name)
    teamstats_pairs["away_c"] = teamstats_pairs["away_team_name"].map(_canon_name)

    exact_match_ids = set(teamstats_pairs["match_id"].dropna().astype(str))
    fallback_candidates = (
        teamstats_pairs.groupby(["match_date", "home_c", "away_c"], dropna=False)["match_id"]
        .agg(lambda values: sorted({str(value) for value in values if value is not None}))
        .reset_index(name="candidate_match_ids")
    )
    fallback_candidates["candidate_count"] = fallback_candidates["candidate_match_ids"].map(len)
    fallback_unique = fallback_candidates[fallback_candidates["candidate_count"] == 1].copy()
    fallback_unique["resolved_match_id"] = fallback_unique["candidate_match_ids"].map(lambda values: values[0])

    enriched["has_exact_match_id"] = enriched["match_id"].fillna("").astype(str).isin(exact_match_ids)
    enriched = enriched.merge(
        fallback_unique[["match_date", "home_c", "away_c", "resolved_match_id", "candidate_count"]],
        how="left",
        on=["match_date", "home_c", "away_c"],
    )
    enriched["resolved_teamstats_match_id"] = enriched["match_id"].where(enriched["has_exact_match_id"], enriched["resolved_match_id"])
    enriched["match_mapping_method"] = "missing"
    enriched.loc[enriched["resolved_teamstats_match_id"].notna(), "match_mapping_method"] = "name_date_fallback"
    enriched.loc[enriched["has_exact_match_id"], "match_mapping_method"] = "exact_match_id"
    enriched["has_teamstats_match"] = enriched["resolved_teamstats_match_id"].notna()
    enriched["teamstats_match_count"] = enriched["has_teamstats_match"].astype(int)

    teamstats_meta = teamstats_index[
        [
            "match_id",
            "kickoff_ts",
            "saved_at",
            "source_kind",
            "home_team_id",
            "away_team_id",
        ]
    ].drop_duplicates(subset=["match_id"])
    teamstats_meta = teamstats_meta.rename(
        columns={
            "match_id": "resolved_teamstats_match_id",
            "saved_at": "teamstats_saved_at",
            "source_kind": "teamstats_source_kind",
        }
    )
    teamstats_meta["resolved_teamstats_match_id"] = teamstats_meta[
        "resolved_teamstats_match_id"
    ].astype("string")
    enriched = enriched.merge(
        teamstats_meta,
        how="left",
        on="resolved_teamstats_match_id",
    )

    def _reference_join(frame: pd.DataFrame, count_column: str) -> pd.DataFrame:
        if frame.empty or "match_id" not in frame.columns:
            return pd.DataFrame(columns=["market_join_key", count_column])
        joined = frame.copy()
        joined["match_id"] = joined["match_id"].astype("string")
        joined["market_join_key"] = _composite_market_key(joined)
        return (
            joined.groupby("market_join_key", dropna=False)
            .size()
            .rename(count_column)
            .reset_index()
        )

    clv_join = _reference_join(closing_lines, "clv_match_count")
    shortlist_join = _reference_join(shortlist_rows, "shortlist_match_count")
    result_join = _reference_join(result_loop_rows, "result_loop_match_count")

    enriched["market_join_key"] = _composite_market_key(enriched)
    enriched = enriched.merge(clv_join, how="left", on="market_join_key")
    enriched = enriched.merge(shortlist_join, how="left", on="market_join_key")
    enriched = enriched.merge(result_join, how="left", on="market_join_key")
    enriched["clv_match_count"] = _fill_count_column(enriched["clv_match_count"])
    enriched["shortlist_match_count"] = _fill_count_column(enriched["shortlist_match_count"])
    enriched["result_loop_match_count"] = _fill_count_column(enriched["result_loop_match_count"])
    enriched["has_clv"] = enriched["clv_match_count"] > 0
    enriched["has_shortlist_reference"] = enriched["shortlist_match_count"] > 0
    enriched["has_result_loop_reference"] = enriched["result_loop_match_count"] > 0
    enriched["is_primary_target"] = enriched["stat_key"].isin(PRIMARY_TARGET_STAT_KEYS)
    enriched = _enrich_latest_snapshot_metadata(enriched, market_snapshots)
    enriched["filter_reason"] = enriched.apply(
        lambda row: resolve_filter_reason(
            stat_key=row.get("stat_key"),
            period=row.get("period"),
            scope=row.get("scope"),
            line_value=row.get("line_value"),
            odds_decimal=row.get("odds_decimal"),
            settlement_result=row.get("settlement_result"),
            has_teamstats_match=bool(row.get("has_teamstats_match")),
        ),
        axis=1,
    )

    coverage = enriched[
        [
            "match_id",
            "bet_key",
            "stat_key",
            "period",
            "scope",
            "has_teamstats_match",
            "teamstats_match_count",
            "resolved_teamstats_match_id",
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
            "filter_reason",
        ]
    ].copy()
    return enriched, coverage
