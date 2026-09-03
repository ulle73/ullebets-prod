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


def _latest_build_statuses(
    database: Any, *, date_from: str, date_to: str
) -> dict[tuple[str, str], str]:
    rows = database["job_runs"].find(
        {
            "job_name": {"$in": ["build_matchups_score", "build_matchups_league_avg"]},
            "target_window.snapshot_date": {"$gte": date_from, "$lte": date_to},
        },
        projection={
            "_id": 0,
            "job_name": 1,
            "run_id": 1,
            "started_at": 1,
            "status": 1,
            "target_window.snapshot_date": 1,
        },
    )
    latest: dict[tuple[str, str], tuple[tuple[str, str], str]] = {}
    for row in rows:
        job_name = str(row.get("job_name") or "")
        snapshot_date = str((row.get("target_window") or {}).get("snapshot_date") or "")
        if not job_name or not snapshot_date:
            continue
        order_key = (str(row.get("started_at") or ""), str(row.get("run_id") or ""))
        key = (job_name, snapshot_date)
        if key not in latest or order_key > latest[key][0]:
            latest[key] = (order_key, str(row.get("status") or ""))
    return {key: value[1] for key, value in latest.items()}


def repair_matchup_history(
    *,
    database: Any,
    date_from: str,
    date_to: str,
    source_workflow: str,
    dry_run: bool = False,
    rebuild_existing: bool = False,
    max_rebuild_dates: int | None = None,
) -> dict[str, Any]:
    if max_rebuild_dates is not None and max_rebuild_dates < 1:
        raise ValueError("max_rebuild_dates must be positive")
    dates = iter_dates(date_from, date_to)
    build_statuses = _latest_build_statuses(
        database, date_from=date_from, date_to=date_to
    )
    per_date: list[dict[str, Any]] = []
    rebuilt_dates = 0
    for target_date in reversed(dates):
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
        existing_league_rows = list(
            database["matchups_league_avg"].find(
                {"snapshot_date": target_date},
                projection={"_id": 0},
            )
        )
        score_summary = None
        league_summary = None
        score_rows = existing_rows
        league_rows = existing_league_rows
        score_status = build_statuses.get(("build_matchups_score", target_date))
        league_status = build_statuses.get(("build_matchups_league_avg", target_date))
        needs_score = bool(
            fixtures
            and (
                rebuild_existing
                or not existing_rows
                or (score_status is not None and score_status != "succeeded")
            )
        )
        needs_league = bool(
            fixtures
            and (
                rebuild_existing
                or not existing_league_rows
                or (league_status is not None and league_status != "succeeded")
            )
        )
        needs_rebuild = needs_score or needs_league
        deferred = needs_rebuild and max_rebuild_dates is not None and rebuilt_dates >= max_rebuild_dates
        if needs_rebuild and not deferred:
            if needs_score:
                score_summary = run_matchups_score_build(
                    source_workflow=source_workflow,
                    target_matches=fixtures,
                    snapshot_date=target_date,
                    database=database,
                    dry_run=dry_run,
                )
            if needs_league:
                league_summary = run_matchups_league_avg_build(
                    source_workflow=source_workflow,
                    target_matches=fixtures,
                    snapshot_date=target_date,
                    database=database,
                    dry_run=dry_run,
                )
            if dry_run:
                score_rows = score_summary["entry_docs"] if score_summary is not None else score_rows
                league_rows = league_summary["entry_docs"] if league_summary is not None else league_rows
            rebuilt_dates += 1

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
                "ranking_action": "deferred" if deferred else "rebuilt" if needs_rebuild else "reused",
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
        "rebuilt_dates": rebuilt_dates,
        "deferred_dates": sum(row["ranking_action"] == "deferred" for row in per_date),
        "max_rebuild_dates": max_rebuild_dates,
        "resolved_rows": sum(int(row["settlement"].get("resolved_rows") or 0) for row in per_date),
        "per_date": sorted(per_date, key=lambda row: row["date"]),
    }
