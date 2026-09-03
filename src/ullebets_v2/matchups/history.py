from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ullebets_v2.matchups.service import run_matchups_league_avg_build, run_matchups_score_build
from ullebets_v2.matchups_settlement.service import run_matchup_settlement


def iter_dates(date_from: str, date_to: str) -> list[str]:
    start = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    if end < start:
        raise ValueError("date_to must be on or after date_from")
    return [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]


def _compact(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in summary.items()
        if key not in {"entry_docs", "missing_matches", "score_docs", "league_avg_docs"}
    }


def repair_matchup_history(
    *,
    database: Any,
    date_from: str,
    date_to: str,
    source_workflow: str,
    dry_run: bool = False,
    rebuild_existing: bool = False,
) -> dict[str, Any]:
    dates = iter_dates(date_from, date_to)
    per_date: list[dict[str, Any]] = []
    for target_date in dates:
        fixtures = list(
            database["fixtures_canonical"].find(
                {"fixture_date_stockholm": target_date},
                projection={"_id": 0},
            )
        )
        existing_rows = list(
            database["matchups_score"].find(
                {"snapshot_date": target_date},
                projection={"_id": 0},
            )
        )
        score_summary = None
        league_summary = None
        score_rows = existing_rows
        league_rows = None
        if fixtures and (rebuild_existing or not existing_rows):
            score_summary = run_matchups_score_build(
                source_workflow=source_workflow,
                target_matches=fixtures,
                snapshot_date=target_date,
                database=database,
                dry_run=dry_run,
            )
            league_summary = run_matchups_league_avg_build(
                source_workflow=source_workflow,
                target_matches=fixtures,
                snapshot_date=target_date,
                database=database,
                dry_run=dry_run,
            )
            if dry_run:
                score_rows = score_summary["entry_docs"]
                league_rows = league_summary["entry_docs"]

        settlement = run_matchup_settlement(
            source_workflow=source_workflow,
            date_from=target_date,
            date_to=target_date,
            score_rows=score_rows if dry_run else None,
            league_avg_rows=league_rows if dry_run else None,
            database=database,
            dry_run=dry_run,
            unresolved_only=True,
        )
        per_date.append(
            {
                "date": target_date,
                "fixtures": len(fixtures),
                "ranking_action": "rebuilt" if score_summary is not None else "reused",
                "score_build": _compact(score_summary) if score_summary is not None else None,
                "league_build": _compact(league_summary) if league_summary is not None else None,
                "settlement": _compact(settlement),
            }
        )
    return {
        "job": "repair_matchup_history",
        "date_from": date_from,
        "date_to": date_to,
        "dates": len(dates),
        "rebuilt_dates": sum(row["ranking_action"] == "rebuilt" for row in per_date),
        "resolved_rows": sum(int(row["settlement"].get("resolved_rows") or 0) for row in per_date),
        "per_date": per_date,
    }
