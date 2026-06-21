from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

from ullebets_v1.features.targets import (
    CONTEXT_STAT_KEYS,
    CONTEXT_WINDOWS,
    PRIMARY_TARGETS,
    TARGET_WINDOWS,
    get_market_side_policy,
    get_target_spec,
    is_segment_model_ready,
    segment_shape_from_flags,
)


LEAGUE_ALIASES = {
    "LaLiga": "La Liga",
    "Brasileirão Betano": "Brasileirão Série A",
    "A-League": "A-League Men",
}


def canonicalize_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_team_support_rows(support_path: Path) -> pd.DataFrame:
    raw = json.loads(support_path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for league_name, league_payload in raw.items():
        normalized_league = LEAGUE_ALIASES.get(league_name, league_name)
        for team in league_payload.get("teams", []):
            rows.append(
                {
                    "support_league_name": normalized_league,
                    "support_team_name": team.get("name"),
                    "support_league_c": canonicalize_text(normalized_league),
                    "support_team_c": canonicalize_text(team.get("name")),
                    "support_team_id": team.get("id"),
                    "support_team_slug": team.get("slug"),
                    "support_opta_rank": team.get("optaRank"),
                    "support_opta_rating": team.get("optaRating"),
                }
            )
    return pd.DataFrame(rows)


def build_market_points(market_lines: pd.DataFrame, line_clv: pd.DataFrame) -> pd.DataFrame:
    kept = market_lines[(market_lines["is_primary_target"] == True) & (market_lines["filter_reason"].isna())].copy()
    if kept.empty:
        return kept
    if "exposure_match_id" not in kept.columns:
        kept["exposure_match_id"] = kept["resolved_teamstats_match_id"].fillna(kept["match_id"]).astype("string")
    odds_column = "effective_odds_decimal" if "effective_odds_decimal" in kept.columns else "odds_decimal"

    clv_lookup = line_clv[
        ["match_id", "stat_key", "period", "scope", "direction", "line_value", "clv_pct", "closing_odds"]
    ].copy()
    clv_lookup["line_side_key"] = (
        clv_lookup["match_id"].astype(str)
        + "|"
        + clv_lookup["stat_key"].astype(str)
        + "|"
        + clv_lookup["period"].astype(str)
        + "|"
        + clv_lookup["scope"].astype(str)
        + "|"
        + clv_lookup["direction"].astype(str)
        + "|"
        + clv_lookup["line_value"].astype(str)
    )
    clv_lookup = clv_lookup.drop_duplicates(subset=["line_side_key"], keep="first")

    kept["line_side_key"] = (
        kept["match_id"].astype(str)
        + "|"
        + kept["stat_key"].astype(str)
        + "|"
        + kept["period"].astype(str)
        + "|"
        + kept["scope"].astype(str)
        + "|"
        + kept["direction"].astype(str)
        + "|"
        + kept["line_value"].astype(str)
    )
    kept = kept.merge(
        clv_lookup[["line_side_key", "clv_pct", "closing_odds"]],
        how="left",
        on="line_side_key",
    )

    group_cols = [
        "exposure_match_id",
        "match_id",
        "resolved_teamstats_match_id",
        "match_date",
        "league_name",
        "home_team_name",
        "away_team_name",
        "period",
        "scope",
        "stat_key",
        "line_value",
    ]

    def _first_non_null(series: pd.Series):
        non_null = series.dropna()
        return non_null.iloc[0] if not non_null.empty else None

    points = (
        kept.groupby(group_cols, dropna=False)
        .agg(
            actual_value=("actual_value", _first_non_null),
            match_mapping_method=("match_mapping_method", _first_non_null),
            has_clv=("has_clv", "max"),
            over_odds=(odds_column, lambda series: _first_non_null(kept.loc[series.index][kept.loc[series.index, "direction"] == "over"][odds_column])),
            under_odds=(odds_column, lambda series: _first_non_null(kept.loc[series.index][kept.loc[series.index, "direction"] == "under"][odds_column])),
            over_result=("settlement_result", lambda series: _first_non_null(kept.loc[series.index][kept.loc[series.index, "direction"] == "over"]["settlement_result"])),
            under_result=("settlement_result", lambda series: _first_non_null(kept.loc[series.index][kept.loc[series.index, "direction"] == "under"]["settlement_result"])),
            over_clv_pct=("clv_pct", lambda series: _first_non_null(kept.loc[series.index][kept.loc[series.index, "direction"] == "over"]["clv_pct"])),
            under_clv_pct=("clv_pct", lambda series: _first_non_null(kept.loc[series.index][kept.loc[series.index, "direction"] == "under"]["clv_pct"])),
            prematch_snapshot_count=("prematch_snapshot_count", "max") if "prematch_snapshot_count" in kept.columns else ("line_value", lambda _: None),
            has_latest_prematch_snapshot=("has_latest_prematch_snapshot", "max") if "has_latest_prematch_snapshot" in kept.columns else ("line_value", lambda _: None),
            latest_snapshot_type=("latest_snapshot_type", _first_non_null) if "latest_snapshot_type" in kept.columns else ("line_value", lambda _: None),
            latest_snapshot_fetched_at=("latest_snapshot_fetched_at", _first_non_null) if "latest_snapshot_fetched_at" in kept.columns else ("line_value", lambda _: None),
            latest_snapshot_minutes_before_kickoff=("latest_snapshot_minutes_before_kickoff", _first_non_null) if "latest_snapshot_minutes_before_kickoff" in kept.columns else ("line_value", lambda _: None),
            effective_odds_source=("effective_odds_source", _first_non_null) if "effective_odds_source" in kept.columns else ("line_value", lambda _: "root_line"),
        )
        .reset_index()
    )
    points["has_both_sides"] = points["over_odds"].notna() & points["under_odds"].notna()
    points["segment_shape"] = points.apply(
        lambda row: segment_shape_from_flags(
            has_over=pd.notna(row["over_odds"]),
            has_under=pd.notna(row["under_odds"]),
        ),
        axis=1,
    )
    points["market_side_policy"] = points["stat_key"].map(get_market_side_policy)
    points["is_model_eligible_segment"] = points.apply(
        lambda row: is_segment_model_ready(
            str(row["stat_key"]),
            has_over=pd.notna(row["over_odds"]),
            has_under=pd.notna(row["under_odds"]),
        ),
        axis=1,
    )
    points["market_overround"] = (
        (1.0 / points["over_odds"]) + (1.0 / points["under_odds"])
    )
    points.loc[~points["has_both_sides"], "market_overround"] = None
    points["market_no_vig_prob_over"] = (1.0 / points["over_odds"]) / points["market_overround"]
    points["market_no_vig_prob_under"] = (1.0 / points["under_odds"]) / points["market_overround"]
    points.loc[~points["has_both_sides"], ["market_no_vig_prob_over", "market_no_vig_prob_under"]] = None
    points["market_balance_gap"] = None
    points["available_side_balance_gap"] = None
    points["is_canonical_line"] = False
    points["line_rank_in_segment"] = pd.Series([None] * len(points), dtype="Int64")

    balanced = points["has_both_sides"] == True
    if balanced.any():
        points.loc[balanced, "market_balance_gap"] = (
            points.loc[balanced, "market_no_vig_prob_over"] - 0.5
        ).abs()
        ranked = points.loc[balanced].sort_values(
            ["exposure_match_id", "stat_key", "period", "scope", "market_balance_gap", "market_overround", "line_value"],
            ascending=[True, True, True, True, True, True, True],
        )
        ranked_positions = ranked.groupby(["exposure_match_id", "stat_key", "period", "scope"], dropna=False).cumcount() + 1
        points.loc[ranked.index, "line_rank_in_segment"] = ranked_positions.astype("Int64")
        canonical_index = ranked.loc[ranked_positions == 1].index
        points.loc[canonical_index, "is_canonical_line"] = True

    one_sided_modeled = (points["is_model_eligible_segment"] == True) & (points["has_both_sides"] == False)
    if one_sided_modeled.any():
        available_odds = points.loc[one_sided_modeled, "over_odds"].fillna(
            points.loc[one_sided_modeled, "under_odds"]
        )
        points.loc[one_sided_modeled, "available_side_balance_gap"] = (
            (1.0 / available_odds) - 0.5
        ).abs()
        ranked = points.loc[one_sided_modeled].sort_values(
            [
                "exposure_match_id",
                "stat_key",
                "period",
                "scope",
                "available_side_balance_gap",
                "line_value",
            ],
            ascending=[True, True, True, True, True, True],
        )
        ranked_positions = (
            ranked.groupby(["exposure_match_id", "stat_key", "period", "scope"], dropna=False)
            .cumcount()
            + 1
        )
        points.loc[ranked.index, "line_rank_in_segment"] = ranked_positions.astype("Int64")
        canonical_index = ranked.loc[ranked_positions == 1].index
        points.loc[canonical_index, "is_canonical_line"] = True

    points["league_name_normalized"] = points["league_name"].map(lambda value: LEAGUE_ALIASES.get(value, value))
    return points


def _rolling_feature_frame(team_stats_long: pd.DataFrame) -> pd.DataFrame:
    wanted_stats = set(CONTEXT_STAT_KEYS)
    base = team_stats_long[team_stats_long["stat_item_key"].isin(wanted_stats)].copy()
    base = base.sort_values(["team_name", "period", "stat_item_key", "kickoff_ts", "match_id", "team_role"])
    all_group = ["team_name", "period", "stat_item_key"]
    role_group = ["team_name", "team_role", "period", "stat_item_key"]

    feature_specs: list[tuple[str, list[str], str, tuple[int, ...]]] = [
        ("team_for_all_avg", all_group, "team_value", TARGET_WINDOWS),
        ("team_against_all_avg", all_group, "opponent_value", TARGET_WINDOWS),
        ("team_for_role_avg", role_group, "team_value", TARGET_WINDOWS),
        ("team_against_role_avg", role_group, "opponent_value", TARGET_WINDOWS),
    ]

    for prefix, group_cols, value_col, windows in feature_specs:
        shifted = base.groupby(group_cols, dropna=False)[value_col].shift(1)
        grouped_shifted = shifted.groupby([base[col] for col in group_cols], dropna=False)
        for window in windows:
            base[f"{prefix}_{window}"] = grouped_shifted.transform(
                lambda series: series.rolling(window, min_periods=1).mean()
            )

    keep_cols = [
        "match_id",
        "match_date",
        "kickoff_ts",
        "team_name",
        "opponent_name",
        "team_role",
        "period",
        "stat_item_key",
    ] + [
        col
        for col in base.columns
        if col.startswith("team_") and col not in {"team_name", "team_role"}
    ]

    feature_frame = base[keep_cols].copy()
    wide = feature_frame.pivot_table(
        index=["match_id", "match_date", "kickoff_ts", "team_name", "opponent_name", "team_role", "period"],
        columns="stat_item_key",
        values=[col for col in feature_frame.columns if col.startswith("team_")],
        aggfunc="first",
    )
    wide.columns = [f"{stat_key}__{feature_name}" for feature_name, stat_key in wide.columns]
    return wide.reset_index()


def _join_support_metadata(market_points: pd.DataFrame, support_rows: pd.DataFrame) -> pd.DataFrame:
    frame = market_points.copy()
    frame["support_league_c"] = frame["league_name_normalized"].map(canonicalize_text)
    frame["home_team_c"] = frame["home_team_name"].map(canonicalize_text)
    frame["away_team_c"] = frame["away_team_name"].map(canonicalize_text)

    home_support = support_rows.rename(
        columns={
            "support_team_name": "home_support_team_name",
            "support_team_id": "home_support_team_id",
            "support_team_slug": "home_support_team_slug",
            "support_opta_rank": "home_opta_rank",
            "support_opta_rating": "home_opta_rating",
            "support_team_c": "home_team_c",
        }
    )
    away_support = support_rows.rename(
        columns={
            "support_team_name": "away_support_team_name",
            "support_team_id": "away_support_team_id",
            "support_team_slug": "away_support_team_slug",
            "support_opta_rank": "away_opta_rank",
            "support_opta_rating": "away_opta_rating",
            "support_team_c": "away_team_c",
        }
    )

    frame = frame.merge(
        home_support[
            [
                "support_league_c",
                "home_team_c",
                "home_support_team_name",
                "home_support_team_id",
                "home_support_team_slug",
                "home_opta_rank",
                "home_opta_rating",
            ]
        ],
        how="left",
        on=["support_league_c", "home_team_c"],
    )
    frame = frame.merge(
        away_support[
            [
                "support_league_c",
                "away_team_c",
                "away_support_team_name",
                "away_support_team_id",
                "away_support_team_slug",
                "away_opta_rank",
                "away_opta_rating",
            ]
        ],
        how="left",
        on=["support_league_c", "away_team_c"],
    )
    frame["opta_rating_diff"] = frame["home_opta_rating"] - frame["away_opta_rating"]
    frame["opta_rank_diff"] = frame["home_opta_rank"] - frame["away_opta_rank"]
    return frame


def _join_team_features(market_points: pd.DataFrame, team_feature_frame: pd.DataFrame) -> pd.DataFrame:
    frame = market_points.copy()
    home_features = team_feature_frame[team_feature_frame["team_role"] == "home"].copy()
    away_features = team_feature_frame[team_feature_frame["team_role"] == "away"].copy()

    drop_cols = ["team_name", "opponent_name", "team_role"]
    home_features = home_features.drop(columns=drop_cols).add_prefix("home__")
    away_features = away_features.drop(columns=drop_cols).add_prefix("away__")

    frame = frame.merge(
        home_features,
        how="left",
        left_on=["resolved_teamstats_match_id", "period"],
        right_on=["home__match_id", "home__period"],
    )
    frame = frame.merge(
        away_features,
        how="left",
        left_on=["resolved_teamstats_match_id", "period"],
        right_on=["away__match_id", "away__period"],
    )
    return frame


def _derive_target_baselines(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    for window in TARGET_WINDOWS:
        enriched[f"lambda_role_{window}"] = pd.Series(index=enriched.index, dtype="float64")
        enriched[f"lambda_all_{window}"] = pd.Series(index=enriched.index, dtype="float64")

    for stat_key, spec in (("totalShots", get_target_spec("totalShots")), ("shotsOnGoal", get_target_spec("shotsOnGoal")), ("cornerKicks", get_target_spec("cornerKicks"))):
        mask = enriched["stat_key"] == stat_key
        source_key = spec.team_stats_key
        for window in TARGET_WINDOWS:
            home_for_role = f"home__{source_key}__team_for_role_avg_{window}"
            away_for_role = f"away__{source_key}__team_for_role_avg_{window}"
            home_against_role = f"home__{source_key}__team_against_role_avg_{window}"
            away_against_role = f"away__{source_key}__team_against_role_avg_{window}"
            home_for_all = f"home__{source_key}__team_for_all_avg_{window}"
            away_for_all = f"away__{source_key}__team_for_all_avg_{window}"
            home_against_all = f"home__{source_key}__team_against_all_avg_{window}"
            away_against_all = f"away__{source_key}__team_against_all_avg_{window}"

            role_expected = (
                (enriched[home_for_role] + enriched[away_against_role]) / 2.0
            )
            role_expected_away = (
                (enriched[away_for_role] + enriched[home_against_role]) / 2.0
            )
            all_expected = (
                (enriched[home_for_all] + enriched[away_against_all]) / 2.0
            )
            all_expected_away = (
                (enriched[away_for_all] + enriched[home_against_all]) / 2.0
            )

            total_role_lambda = role_expected + role_expected_away
            total_all_lambda = all_expected + all_expected_away

            enriched.loc[mask & (enriched["scope"] == "home"), f"lambda_role_{window}"] = role_expected[mask & (enriched["scope"] == "home")]
            enriched.loc[mask & (enriched["scope"] == "away"), f"lambda_role_{window}"] = role_expected_away[mask & (enriched["scope"] == "away")]
            enriched.loc[mask & (enriched["scope"] == "total"), f"lambda_role_{window}"] = total_role_lambda[mask & (enriched["scope"] == "total")]

            enriched.loc[mask & (enriched["scope"] == "home"), f"lambda_all_{window}"] = all_expected[mask & (enriched["scope"] == "home")]
            enriched.loc[mask & (enriched["scope"] == "away"), f"lambda_all_{window}"] = all_expected_away[mask & (enriched["scope"] == "away")]
            enriched.loc[mask & (enriched["scope"] == "total"), f"lambda_all_{window}"] = total_all_lambda[mask & (enriched["scope"] == "total")]

    enriched["baseline_lambda"] = (
        enriched["lambda_role_10"]
        .fillna(enriched["lambda_role_5"])
        .fillna(enriched["lambda_all_10"])
        .fillna(enriched["lambda_all_5"])
        .fillna(enriched["lambda_role_20"])
        .fillna(enriched["lambda_all_20"])
    )
    return enriched


def build_feature_dataset(
    *,
    market_lines: pd.DataFrame,
    matches: pd.DataFrame,
    team_stats_long: pd.DataFrame,
    line_clv: pd.DataFrame,
    support_path: Path,
) -> pd.DataFrame:
    market_points = build_market_points(market_lines=market_lines, line_clv=line_clv)
    if market_points.empty:
        return market_points

    support_rows = load_team_support_rows(support_path)
    team_feature_frame = _rolling_feature_frame(team_stats_long)
    matches_frame = matches.rename(columns={"match_id": "resolved_teamstats_match_id"})

    frame = market_points.merge(
        matches_frame[
            [
                "resolved_teamstats_match_id",
                "kickoff_ts",
                "saved_at",
                "home_team_id",
                "away_team_id",
                "source_kind",
            ]
        ].drop_duplicates(subset=["resolved_teamstats_match_id"]),
        how="left",
        on="resolved_teamstats_match_id",
    )
    frame = _join_support_metadata(frame, support_rows)
    frame = _join_team_features(frame, team_feature_frame)
    frame = _derive_target_baselines(frame)
    return frame
