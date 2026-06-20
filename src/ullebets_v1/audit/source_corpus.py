from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any

import pandas as pd

from ullebets_v1.features.targets import PRIMARY_TARGETS, get_market_side_policy, is_segment_model_ready



def _parse_date(value: Any) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if "T" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _date_range(frame: pd.DataFrame, column: str | None) -> tuple[str | None, str | None]:
    if not column or column not in frame.columns:
        return None, None
    parsed = frame[column].map(_parse_date).dropna()
    if parsed.empty:
        return None, None
    return parsed.min().isoformat(), parsed.max().isoformat()


def _segment_shape_counts(
    frame: pd.DataFrame,
    *,
    match_col: str,
    stat_col: str,
    period_col: str,
    scope_col: str,
    line_col: str,
    direction_col: str,
) -> dict[str, int]:
    if frame.empty:
        return {"two_sided": 0, "over_only": 0, "under_only": 0, "other": 0}

    grouped = (
        frame.groupby([match_col, stat_col, period_col, scope_col, line_col], dropna=False)[direction_col]
        .agg(lambda series: tuple(sorted({str(value) for value in series.dropna()})))
        .reset_index(name="directions")
    )
    counts = Counter()
    for directions in grouped["directions"]:
        direction_set = set(directions)
        if direction_set == {"over", "under"}:
            counts["two_sided"] += 1
        elif direction_set == {"over"}:
            counts["over_only"] += 1
        elif direction_set == {"under"}:
            counts["under_only"] += 1
        else:
            counts["other"] += 1
    return {
        "two_sided": int(counts.get("two_sided", 0)),
        "over_only": int(counts.get("over_only", 0)),
        "under_only": int(counts.get("under_only", 0)),
        "other": int(counts.get("other", 0)),
    }


def _model_supported_segment_counts(
    frame: pd.DataFrame,
    *,
    match_col: str,
    stat_col: str,
    period_col: str,
    scope_col: str,
    line_col: str,
    direction_col: str,
) -> dict[str, int]:
    if frame.empty:
        return {"total": 0, "model_ready": 0}

    grouped = (
        frame.groupby([match_col, stat_col, period_col, scope_col, line_col], dropna=False)[direction_col]
        .agg(
            has_over=lambda series: bool((series == "over").any()),
            has_under=lambda series: bool((series == "under").any()),
        )
        .reset_index()
    )
    model_ready = grouped.apply(
        lambda row: is_segment_model_ready(
            str(row[stat_col]),
            has_over=bool(row["has_over"]),
            has_under=bool(row["has_under"]),
        ),
        axis=1,
    )
    return {
        "total": int(len(grouped)),
        "model_ready": int(model_ready.sum()),
    }


def summarize_line_source(
    frame: pd.DataFrame,
    *,
    source_name: str,
    match_col: str = "match_id",
    stat_col: str = "stat_key",
    period_col: str = "period",
    scope_col: str = "scope",
    line_col: str = "line_value",
    direction_col: str = "direction",
    date_col: str | None = None,
    settled_col: str | None = None,
) -> dict:
    if frame.empty:
        return {
            "source_name": source_name,
            "rows": 0,
            "unique_matches": 0,
            "date_range": {"min": None, "max": None},
            "primary_target_rows": 0,
            "primary_target_unique_matches": 0,
            "settled_rows": 0,
            "direction_counts": {},
            "stat_counts": {},
            "primary_target_segment_shapes": {},
            "primary_target_stat_shapes": {},
            "primary_target_model_ready_segments": 0,
        }

    rows = frame.copy()
    primary = rows[rows[stat_col].isin(PRIMARY_TARGETS)].copy()
    settled_rows = 0
    if settled_col and settled_col in rows.columns:
        settled_rows = int(rows[settled_col].notna().sum())

    date_min, date_max = _date_range(rows, date_col)
    direction_counts = rows[direction_col].fillna("MISSING").value_counts().to_dict()
    stat_counts = rows[stat_col].fillna("MISSING").value_counts().head(20).to_dict()

    primary_shapes = _segment_shape_counts(
        primary,
        match_col=match_col,
        stat_col=stat_col,
        period_col=period_col,
        scope_col=scope_col,
        line_col=line_col,
        direction_col=direction_col,
    )
    primary_model_ready = _model_supported_segment_counts(
        primary,
        match_col=match_col,
        stat_col=stat_col,
        period_col=period_col,
        scope_col=scope_col,
        line_col=line_col,
        direction_col=direction_col,
    )

    primary_stat_shapes: dict[str, dict[str, Any]] = {}
    for stat_key, stat_rows in primary.groupby(stat_col, dropna=False):
        model_counts = _model_supported_segment_counts(
            stat_rows,
            match_col=match_col,
            stat_col=stat_col,
            period_col=period_col,
            scope_col=scope_col,
            line_col=line_col,
            direction_col=direction_col,
        )
        primary_stat_shapes[str(stat_key)] = {
            "market_side_policy": get_market_side_policy(str(stat_key)),
            "rows": int(len(stat_rows)),
            "unique_matches": int(stat_rows[match_col].nunique(dropna=True)),
            "direction_counts": stat_rows[direction_col].fillna("MISSING").value_counts().to_dict(),
            "model_ready_segments": model_counts["model_ready"],
            **_segment_shape_counts(
                stat_rows,
                match_col=match_col,
                stat_col=stat_col,
                period_col=period_col,
                scope_col=scope_col,
                line_col=line_col,
                direction_col=direction_col,
            ),
        }

    return {
        "source_name": source_name,
        "rows": int(len(rows)),
        "unique_matches": int(rows[match_col].nunique(dropna=True)) if match_col in rows.columns else 0,
        "date_range": {"min": date_min, "max": date_max},
        "primary_target_rows": int(len(primary)),
        "primary_target_unique_matches": int(primary[match_col].nunique(dropna=True)) if match_col in primary.columns else 0,
        "settled_rows": settled_rows,
        "direction_counts": direction_counts,
        "stat_counts": stat_counts,
        "primary_target_segment_shapes": primary_shapes,
        "primary_target_stat_shapes": primary_stat_shapes,
        "primary_target_model_ready_segments": primary_model_ready["model_ready"],
    }


def build_source_corpus_summary(source_frames: dict[str, pd.DataFrame]) -> dict:
    source_specs = [
        ("unibet_backtest_lines", "unibet-backtest lines", "match_date", "settlement_result"),
        ("unibet_snapshot_lines", "unibet-backtest snapshots", "match_date", None),
        ("ai_generated_bet_lines", "ai-generated-bets lines", "match_date", "settlement_result"),
        ("ai_generated_bet_snapshots", "ai-generated-bets snapshots", "match_date", "settlement_result"),
        ("auto_analysis_bets", "auto-analysis-bets", "match_date", "result"),
        ("analysis_snapshot_shortlist", "analysis-snapshots shortlist", "snapshot_date", None),
        ("result_loop_bets", "result-loop-bets", "created_at", None),
        ("closing_line_tracking", "closing-line-tracking", "created_at", None),
    ]

    sources: list[dict] = []
    by_key: dict[str, dict] = {}
    for key, label, date_col, settled_col in source_specs:
        frame = source_frames.get(key, pd.DataFrame())
        summary = summarize_line_source(
            frame,
            source_name=label,
            date_col=date_col,
            settled_col=settled_col,
        )
        summary["source_key"] = key
        sources.append(summary)
        by_key[key] = summary

    candidate_source_keys = {
        "unibet_backtest_lines",
        "ai_generated_bet_lines",
        "auto_analysis_bets",
    }
    candidate_sources = [source for source in sources if source["source_key"] in candidate_source_keys]

    ranked = sorted(
        candidate_sources,
        key=lambda item: (
            item["settled_rows"],
            item["primary_target_rows"],
            item.get("primary_target_model_ready_segments", 0),
            item["unique_matches"],
        ),
        reverse=True,
    )
    chosen = ranked[0] if ranked else None

    chosen_key = chosen["source_key"] if chosen else None
    chosen_name = chosen["source_name"] if chosen else None

    reasons: list[str] = []
    limitations: list[str] = []
    if chosen:
        reasons.append(
            f"{chosen['source_name']} has the strongest settled primary-target coverage ({chosen['settled_rows']} settled rows)"
        )
        reasons.append(
            f"{chosen['source_name']} also has broad primary-target volume ({chosen['primary_target_rows']} rows)"
        )
        reasons.append(
            f"{chosen['source_name']} has {chosen.get('primary_target_model_ready_segments', 0)} model-ready primary segments under the current market-side policy"
        )

    unibet = by_key.get("unibet_backtest_lines") or {}
    unibet_stats = unibet.get("primary_target_stat_shapes") or {}
    chosen_stats = (chosen or {}).get("primary_target_stat_shapes") or {}
    for stat_key in PRIMARY_TARGETS:
        payload = unibet_stats.get(stat_key) or {}
        if payload.get("model_ready_segments", 0) == 0 and payload.get("rows", 0) > 0:
            limitations.append(
                f"{stat_key} exists in unibet-backtest but still has no model-ready segments under policy `{payload.get('market_side_policy')}`"
            )
        elif payload.get("market_side_policy") == "over_only" and payload.get("rows", 0) > 0:
            reasons.append(
                f"{stat_key} is treated as a bookmaker-designed over-only market, not as missing under coverage"
            )
    if (by_key.get("auto_analysis_bets") or {}).get("rows", 0) > 0:
        limitations.append(
            "auto-analysis-bets exists but is too small and recent to replace the main historical corpus"
        )
    if (by_key.get("ai_generated_bet_lines") or {}).get("rows", 0) > 0:
        limitations.append(
            "ai-generated-bets is useful as a supplementary signal archive, but it does not materially extend model-ready totalShots coverage"
        )
    if (by_key.get("unibet_snapshot_lines") or {}).get("rows", 0) > 0:
        limitations.append(
            "unibet-backtest snapshots are preserved as prematch time-series context, but they are not the primary settled training corpus"
        )

    model_ready_stats = [
        stat_key
        for stat_key, payload in chosen_stats.items()
        if payload.get("model_ready_segments", 0) > 0
    ]

    return {
        "chosen_primary_historical_corpus": chosen_name,
        "chosen_primary_historical_corpus_key": chosen_key,
        "recommended_source_stack": {
            "prematch_odds_lines": "unibet-backtest snapshots (latest prematch snapshot joined onto settled lines)",
            "settled_outcomes": "unibet-backtest lines",
            "historical_stats": "local + mongo teamstats",
            "clv": "closing-line-tracking",
        },
        "selection_reasons": reasons,
        "known_limitations": limitations,
        "model_ready_primary_stats_from_chosen_corpus": model_ready_stats,
        "sources": sources,
    }


def build_source_corpus_markdown(summary: dict) -> str:
    lines = ["# Offline V1 Source Corpus Report", ""]
    lines.append(
        f"- Chosen primary historical corpus: `{summary.get('chosen_primary_historical_corpus')}`"
    )
    ready_stats = summary.get("model_ready_primary_stats_from_chosen_corpus") or []
    lines.append(
        f"- Model-ready primary stats in chosen corpus: `{', '.join(ready_stats) if ready_stats else 'none'}`"
    )
    stack = summary.get("recommended_source_stack") or {}
    if stack:
        lines.append(f"- Recommended prematch odds/line source: `{stack.get('prematch_odds_lines')}`")
        lines.append(f"- Recommended settled outcome source: `{stack.get('settled_outcomes')}`")
        lines.append(f"- Recommended historical stats source: `{stack.get('historical_stats')}`")
        lines.append(f"- Recommended CLV source: `{stack.get('clv')}`")
    lines.append("")

    reasons = summary.get("selection_reasons") or []
    if reasons:
        lines.append("## Why This Corpus")
        for reason in reasons:
            lines.append(f"- {reason}")
        lines.append("")

    limitations = summary.get("known_limitations") or []
    if limitations:
        lines.append("## Known Limitations")
        for limitation in limitations:
            lines.append(f"- {limitation}")
        lines.append("")

    lines.append("## Source Coverage")
    for source in summary.get("sources") or []:
        lines.append(
            f"- `{source['source_name']}`: rows `{source['rows']}`, unique matches `{source['unique_matches']}`, "
            f"primary rows `{source['primary_target_rows']}`, settled `{source['settled_rows']}`, "
            f"model-ready primary segments `{source.get('primary_target_model_ready_segments', 0)}`"
        )
        date_range = source.get("date_range") or {}
        if date_range.get("min") or date_range.get("max"):
            lines.append(
                f"  date range `{date_range.get('min')}` -> `{date_range.get('max')}`"
            )
        for stat_key, payload in (source.get("primary_target_stat_shapes") or {}).items():
            lines.append(
                f"  `{stat_key}` policy `{payload['market_side_policy']}`, rows `{payload['rows']}`, model-ready `{payload['model_ready_segments']}`, two-sided `{payload['two_sided']}`, "
                f"over-only `{payload['over_only']}`, under-only `{payload['under_only']}`"
            )
    lines.append("")
    return "\n".join(lines)
