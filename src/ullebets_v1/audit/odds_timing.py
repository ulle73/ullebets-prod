from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ullebets_v1.features.targets import get_modeled_directions


SEGMENT_KEY_COLUMNS = [
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
PRE_MATCH_STATUS = "pre_match"
AT_OR_AFTER_START_STATUS = "at_or_after_start"
MISSING_SNAPSHOT_STATUS = "missing_snapshot_time"
MISSING_MATCH_START_STATUS = "missing_match_start_time"
MISSING_REQUIRED_SIDE_STATUS = "missing_required_side_row"


@dataclass(frozen=True)
class SideTimingSpec:
    direction: str
    snapshot_time_column: str
    snapshot_time_source_column: str
    timing_status_column: str
    snapshot_required_column: str


SIDE_SPECS = {
    "over": SideTimingSpec(
        direction="over",
        snapshot_time_column="over_snapshot_time",
        snapshot_time_source_column="over_snapshot_time_source",
        timing_status_column="over_odds_timing_status",
        snapshot_required_column="over_snapshot_is_required",
    ),
    "under": SideTimingSpec(
        direction="under",
        snapshot_time_column="under_snapshot_time",
        snapshot_time_source_column="under_snapshot_time_source",
        timing_status_column="under_odds_timing_status",
        snapshot_required_column="under_snapshot_is_required",
    ),
}


def _parse_snapshot_time(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    latest_snapshot_time = pd.to_datetime(
        enriched.get("latest_snapshot_fetched_at"),
        errors="coerce",
        utc=True,
    )
    updated_time = pd.to_datetime(
        enriched.get("updated_at"),
        errors="coerce",
        utc=True,
    )
    generated_time = pd.to_datetime(
        enriched.get("generated_at"),
        errors="coerce",
        utc=True,
    )
    match_start_time = pd.to_datetime(
        enriched.get("kickoff_ts"),
        unit="s",
        errors="coerce",
        utc=True,
    )

    snapshot_time = pd.Series(pd.NaT, index=enriched.index, dtype="datetime64[ns, UTC]")
    snapshot_source = pd.Series(pd.NA, index=enriched.index, dtype="string")

    use_latest = latest_snapshot_time.notna()
    snapshot_time.loc[use_latest] = latest_snapshot_time.loc[use_latest]
    snapshot_source.loc[use_latest] = "unibet-backtest snapshots.snapshot_fetched_at"

    use_updated = snapshot_time.isna() & updated_time.notna()
    snapshot_time.loc[use_updated] = updated_time.loc[use_updated]
    snapshot_source.loc[use_updated] = "unibet-backtest lines.updated_at"

    use_generated = snapshot_time.isna() & generated_time.notna()
    snapshot_time.loc[use_generated] = generated_time.loc[use_generated]
    snapshot_source.loc[use_generated] = "unibet-backtest lines.generated_at"

    match_start_source = pd.Series(pd.NA, index=enriched.index, dtype="string")
    match_start_source.loc[match_start_time.notna()] = "teamstats.kickoff_ts"

    status = pd.Series(PRE_MATCH_STATUS, index=enriched.index, dtype="string")
    status.loc[snapshot_time.isna()] = MISSING_SNAPSHOT_STATUS
    status.loc[snapshot_time.notna() & match_start_time.isna()] = MISSING_MATCH_START_STATUS
    status.loc[
        snapshot_time.notna()
        & match_start_time.notna()
        & (snapshot_time >= match_start_time)
    ] = AT_OR_AFTER_START_STATUS

    enriched["raw_odds_snapshot_time"] = snapshot_time
    enriched["raw_odds_snapshot_time_source"] = snapshot_source
    enriched["raw_match_start_time"] = match_start_time
    enriched["raw_match_start_time_source"] = match_start_source
    enriched["raw_odds_timing_status"] = status
    enriched["raw_snapshot_at_match_start"] = (
        snapshot_time.notna()
        & match_start_time.notna()
        & (snapshot_time == match_start_time)
    )
    return enriched


def _first_row_per_side(market_lines: pd.DataFrame) -> pd.DataFrame:
    ordered = market_lines.reset_index(drop=False).rename(columns={"index": "_row_order"})
    ordered = _parse_snapshot_time(ordered)
    ordered = ordered.sort_values("_row_order")
    side_rows = ordered.drop_duplicates(
        subset=SEGMENT_KEY_COLUMNS + ["direction"],
        keep="first",
    ).copy()
    return side_rows


def annotate_backtest_timing(
    features: pd.DataFrame,
    market_lines: pd.DataFrame,
) -> pd.DataFrame:
    audited = features.copy()
    side_rows = _first_row_per_side(market_lines)

    for direction, spec in SIDE_SPECS.items():
        side = side_rows[side_rows["direction"] == direction][
            SEGMENT_KEY_COLUMNS
            + [
                "raw_odds_snapshot_time",
                "raw_odds_snapshot_time_source",
                "raw_match_start_time",
                "raw_match_start_time_source",
                "raw_odds_timing_status",
                "raw_snapshot_at_match_start",
            ]
        ].rename(
            columns={
                "raw_odds_snapshot_time": spec.snapshot_time_column,
                "raw_odds_snapshot_time_source": spec.snapshot_time_source_column,
                "raw_match_start_time": f"{direction}_match_start_time",
                "raw_match_start_time_source": f"{direction}_match_start_time_source",
                "raw_odds_timing_status": spec.timing_status_column,
                "raw_snapshot_at_match_start": f"{direction}_snapshot_at_match_start",
            }
        )
        audited = audited.merge(side, how="left", on=SEGMENT_KEY_COLUMNS)

    audited["over_snapshot_is_required"] = audited["stat_key"].map(
        lambda stat_key: "over" in get_modeled_directions(str(stat_key))
    )
    audited["under_snapshot_is_required"] = audited["stat_key"].map(
        lambda stat_key: "under" in get_modeled_directions(str(stat_key))
    )
    audited["match_start_time"] = audited["over_match_start_time"].fillna(
        audited["under_match_start_time"]
    )
    audited["match_start_time_source"] = audited["over_match_start_time_source"].fillna(
        audited["under_match_start_time_source"]
    )

    for direction, spec in SIDE_SPECS.items():
        required = audited[spec.snapshot_required_column] == True
        missing_required_side = required & audited[spec.snapshot_time_column].isna() & audited[spec.timing_status_column].isna()
        audited.loc[missing_required_side, spec.timing_status_column] = MISSING_REQUIRED_SIDE_STATUS

    audited["odds_snapshot_time"] = audited["over_snapshot_time"].where(
        audited["over_snapshot_is_required"],
        audited["under_snapshot_time"],
    )
    audited["odds_snapshot_time_source"] = audited["over_snapshot_time_source"].where(
        audited["over_snapshot_is_required"],
        audited["under_snapshot_time_source"],
    )

    audited["odds_timing_status"] = PRE_MATCH_STATUS
    audited["timing_leakage_risk"] = False
    for direction, spec in SIDE_SPECS.items():
        required = audited[spec.snapshot_required_column] == True
        status = audited[spec.timing_status_column]
        audited.loc[required & (status == MISSING_REQUIRED_SIDE_STATUS), "odds_timing_status"] = MISSING_REQUIRED_SIDE_STATUS
        audited.loc[required & (status == MISSING_SNAPSHOT_STATUS), "odds_timing_status"] = MISSING_SNAPSHOT_STATUS
        audited.loc[required & (status == MISSING_MATCH_START_STATUS), "odds_timing_status"] = MISSING_MATCH_START_STATUS
        audited.loc[required & (status == AT_OR_AFTER_START_STATUS), "odds_timing_status"] = AT_OR_AFTER_START_STATUS
        audited.loc[required & (status == AT_OR_AFTER_START_STATUS), "timing_leakage_risk"] = True

    audited["is_strictly_prematch_odds"] = audited["odds_timing_status"] == PRE_MATCH_STATUS
    return audited


def required_odds_rows(audited_features: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for direction, spec in SIDE_SPECS.items():
        required = audited_features[audited_features[spec.snapshot_required_column] == True].copy()
        if required.empty:
            continue
        subset = required[
            SEGMENT_KEY_COLUMNS
            + [
                "market_side_policy",
                spec.snapshot_time_column,
                spec.snapshot_time_source_column,
                spec.timing_status_column,
                "match_start_time",
                "match_start_time_source",
                f"{direction}_snapshot_at_match_start",
            ]
        ].rename(
            columns={
                spec.snapshot_time_column: "snapshot_time",
                spec.snapshot_time_source_column: "snapshot_time_source",
                spec.timing_status_column: "timing_status",
                f"{direction}_snapshot_at_match_start": "snapshot_at_match_start",
            }
        )
        subset["direction"] = direction
        rows.append(subset)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def build_backtest_timing_summary(audited_features: pd.DataFrame) -> dict:
    odds_rows = required_odds_rows(audited_features)
    if odds_rows.empty:
        return {
            "total_tested_odds_rows": 0,
            "rows_before_matchstart": 0,
            "rows_at_or_after_matchstart": 0,
            "rows_exactly_at_matchstart": 0,
            "rows_without_snapshot_time": 0,
            "rows_without_matchstart": 0,
            "snapshot_time_source_counts": {},
            "match_start_time_source_counts": {},
        }

    return {
        "total_tested_odds_rows": int(len(odds_rows)),
        "rows_before_matchstart": int((odds_rows["timing_status"] == PRE_MATCH_STATUS).sum()),
        "rows_at_or_after_matchstart": int((odds_rows["timing_status"] == AT_OR_AFTER_START_STATUS).sum()),
        "rows_exactly_at_matchstart": int(
            odds_rows["snapshot_at_match_start"].astype("boolean").fillna(False).sum()
        ),
        "rows_without_snapshot_time": int(odds_rows["snapshot_time"].isna().sum()),
        "rows_without_matchstart": int(odds_rows["match_start_time"].isna().sum()),
        "rows_missing_required_side": int((odds_rows["timing_status"] == MISSING_REQUIRED_SIDE_STATUS).sum()),
        "snapshot_time_source_counts": odds_rows["snapshot_time_source"].fillna("missing").value_counts().to_dict(),
        "match_start_time_source_counts": odds_rows["match_start_time_source"].fillna("missing").value_counts().to_dict(),
    }
