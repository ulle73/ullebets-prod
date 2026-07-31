from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.parity.reports import build_audit_report_row, build_health_report_row


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _date_in_range(value: str, start_date: str | None, end_date: str | None) -> bool:
    if not value:
        return False
    if start_date and value < start_date:
        return False
    if end_date and value > end_date:
        return False
    return True


def _iter_legacy_fixture_entries(legacy_app_database: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    projection = {"_id": 0, "full": 1, "date": 1, "savedAt": 1, "matches": 1}
    for document in legacy_app_database["match-for-date"].find({}, projection=projection):
        full = document.get("full")
        if isinstance(full, list):
            entries.extend(entry for entry in full if isinstance(entry, dict))
        elif isinstance(document.get("matches"), list):
            entries.append(document)
    return entries


def _legacy_fixture_count_map(
    legacy_app_database: Any,
    *,
    start_date: str | None,
    end_date: str | None,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in _iter_legacy_fixture_entries(legacy_app_database):
        date_str = str(entry.get("date") or "").strip()
        if not _date_in_range(date_str, start_date, end_date):
            continue
        counts[date_str] = max(counts.get(date_str, 0), len(entry.get("matches") or []))
    return counts


def _collection_date_count_map(
    collection: Any,
    *,
    field_name: str,
    start_date: str | None,
    end_date: str | None,
    query: dict[str, Any] | None = None,
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    projection = {"_id": 0, field_name: 1}
    for row in collection.find(query or {}, projection=projection):
        date_str = str(row.get(field_name) or "").strip()
        if not _date_in_range(date_str, start_date, end_date):
            continue
        counts[date_str] += 1
    return dict(counts)


def _legacy_unibet_snapshot_date(row: dict[str, Any]) -> str | None:
    payload = row.get("payload")
    if isinstance(payload, dict):
        events = payload.get("events")
        if isinstance(events, list) and events:
            start_value = str((events[0] or {}).get("start") or "").strip()
            if len(start_value) >= 10:
                return start_value[:10]
    match_id = str(row.get("match_id") or "").strip()
    parts = match_id.split("|")
    if len(parts) >= 2 and len(parts[1]) == 10:
        return parts[1]
    return None


def _legacy_unibet_snapshot_count_map(
    legacy_unibet_database: Any,
    *,
    start_date: str | None,
    end_date: str | None,
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    projection = {"_id": 0, "payload": 1, "match_id": 1}
    for row in legacy_unibet_database["raw_odds_snapshots"].find({}, projection=projection):
        date_str = _legacy_unibet_snapshot_date(row)
        if not _date_in_range(str(date_str or ""), start_date, end_date):
            continue
        counts[str(date_str)] += 1
    return dict(counts)


def _resolve_profile_date(database: Any, requested_profile_date: str | None) -> str | None:
    if requested_profile_date:
        return requested_profile_date
    latest: str | None = None
    projection = {"_id": 0, "profile_date": 1}
    for row in database["teamprofiles"].find({}, projection=projection):
        profile_date = str(row.get("profile_date") or "").strip()
        if not profile_date:
            continue
        if latest is None or profile_date > latest:
            latest = profile_date
    return latest


def _teamprofile_summary(database: Any, profile_date: str | None) -> dict[str, Any]:
    if not profile_date:
        return {
            "profile_date": None,
            "profile_doc_count": 0,
            "team_count": 0,
            "teams_with_home": 0,
            "teams_with_away": 0,
            "teams_with_both": 0,
            "teams_missing_home_sample": [],
            "teams_missing_away_sample": [],
        }

    team_roles: dict[str, set[str]] = defaultdict(set)
    rows = list(
        database["teamprofiles"].find(
            {"profile_date": profile_date},
            projection={"_id": 0, "team_key": 1, "match_type": 1},
        )
    )
    for row in rows:
        team_key = str(row.get("team_key") or "").strip()
        match_type = str(row.get("match_type") or "").strip()
        if not team_key or not match_type:
            continue
        team_roles[team_key].add(match_type)

    missing_home = sorted(team_key for team_key, roles in team_roles.items() if "home" not in roles)
    missing_away = sorted(team_key for team_key, roles in team_roles.items() if "away" not in roles)
    return {
        "profile_date": profile_date,
        "profile_doc_count": len(rows),
        "team_count": len(team_roles),
        "teams_with_home": sum(1 for roles in team_roles.values() if "home" in roles),
        "teams_with_away": sum(1 for roles in team_roles.values() if "away" in roles),
        "teams_with_both": sum(1 for roles in team_roles.values() if {"home", "away"}.issubset(roles)),
        "teams_missing_home_sample": missing_home[:25],
        "teams_missing_away_sample": missing_away[:25],
    }


def build_historical_coverage_report(
    *,
    database: Any,
    legacy_app_database: Any,
    legacy_unibet_database: Any,
    start_date: str | None = None,
    end_date: str | None = None,
    profile_date: str | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    legacy_fixture_counts = _legacy_fixture_count_map(
        legacy_app_database,
        start_date=start_date,
        end_date=end_date,
    )
    legacy_backtest_counts = _collection_date_count_map(
        legacy_app_database["unibet-backtest"],
        field_name="matchDate",
        start_date=start_date,
        end_date=end_date,
    )
    legacy_raw_snapshot_counts = _legacy_unibet_snapshot_count_map(
        legacy_unibet_database,
        start_date=start_date,
        end_date=end_date,
    )

    v2_fixture_counts = _collection_date_count_map(
        database["fixtures_canonical"],
        field_name="source_date",
        start_date=start_date,
        end_date=end_date,
    )
    v2_result_counts = _collection_date_count_map(
        database["match_results_canonical"],
        field_name="source_date",
        start_date=start_date,
        end_date=end_date,
    )
    v2_stat_counts = _collection_date_count_map(
        database["match_stats_canonical"],
        field_name="source_date",
        start_date=start_date,
        end_date=end_date,
    )
    v2_legacy_raw_odds_counts = _collection_date_count_map(
        database["raw_odds_kambi"],
        field_name="source_date",
        start_date=start_date,
        end_date=end_date,
        query={"source_provider": "legacy_unibet_backtest"},
    )
    v2_legacy_event_link_counts = _collection_date_count_map(
        database["unibet_event_links"],
        field_name="source_date",
        start_date=start_date,
        end_date=end_date,
        query={"source_provider": "legacy_unibet_backtest"},
    )
    v2_legacy_offer_counts = _collection_date_count_map(
        database["market_offers"],
        field_name="source_date",
        start_date=start_date,
        end_date=end_date,
        query={"source_provider": "legacy_unibet_backtest"},
    )

    overlap_dates = sorted(set(legacy_fixture_counts) & set(legacy_backtest_counts))
    rows: list[dict[str, Any]] = []
    missing_v2_fixture_dates: list[str] = []
    missing_v2_result_dates: list[str] = []
    missing_v2_stat_dates: list[str] = []
    missing_v2_odds_dates: list[str] = []

    for date_str in overlap_dates:
        v2_fixture_count = v2_fixture_counts.get(date_str, 0)
        v2_result_count = v2_result_counts.get(date_str, 0)
        v2_stat_count = v2_stat_counts.get(date_str, 0)
        v2_odds_count = v2_legacy_offer_counts.get(date_str, 0)
        if v2_fixture_count == 0:
            missing_v2_fixture_dates.append(date_str)
        if v2_result_count == 0:
            missing_v2_result_dates.append(date_str)
        if v2_stat_count == 0:
            missing_v2_stat_dates.append(date_str)
        if v2_odds_count == 0:
            missing_v2_odds_dates.append(date_str)
        rows.append(
            {
                "date": date_str,
                "legacy_fixture_matches": legacy_fixture_counts.get(date_str, 0),
                "legacy_backtest_docs": legacy_backtest_counts.get(date_str, 0),
                "legacy_raw_snapshot_docs": legacy_raw_snapshot_counts.get(date_str, 0),
                "v2_fixture_matches": v2_fixture_count,
                "v2_result_matches": v2_result_count,
                "v2_stat_rows": v2_stat_count,
                "v2_legacy_raw_odds_docs": v2_legacy_raw_odds_counts.get(date_str, 0),
                "v2_legacy_event_links": v2_legacy_event_link_counts.get(date_str, 0),
                "v2_legacy_offer_rows": v2_odds_count,
                "ready_for_model_replay": bool(v2_fixture_count and v2_result_count and v2_stat_count and v2_odds_count),
            }
        )

    effective_profile_date = _resolve_profile_date(database, profile_date)
    teamprofile_summary = _teamprofile_summary(database, effective_profile_date)
    ready_dates = [row["date"] for row in rows if row["ready_for_model_replay"]]

    report = {
        "generated_at": generated,
        "window": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "source_inventory": {
            "legacy_fixture_dates_total": len(legacy_fixture_counts),
            "legacy_backtest_dates_total": len(legacy_backtest_counts),
            "legacy_raw_snapshot_dates_total": len(legacy_raw_snapshot_counts),
            "v2_fixture_dates_total": len(v2_fixture_counts),
            "v2_result_dates_total": len(v2_result_counts),
            "v2_stat_dates_total": len(v2_stat_counts),
            "v2_legacy_odds_dates_total": len(v2_legacy_offer_counts),
        },
        "coverage_summary": {
            "fixture_backtest_overlap_dates_total": len(overlap_dates),
            "ready_for_model_replay_dates_total": len(ready_dates),
            "missing_v2_fixture_dates_count": len(missing_v2_fixture_dates),
            "missing_v2_result_dates_count": len(missing_v2_result_dates),
            "missing_v2_stat_dates_count": len(missing_v2_stat_dates),
            "missing_v2_odds_dates_count": len(missing_v2_odds_dates),
            "missing_v2_fixture_dates_sample": missing_v2_fixture_dates[:25],
            "missing_v2_result_dates_sample": missing_v2_result_dates[:25],
            "missing_v2_stat_dates_sample": missing_v2_stat_dates[:25],
            "missing_v2_odds_dates_sample": missing_v2_odds_dates[:25],
            "ready_for_model_replay_dates_sample": ready_dates[:25],
        },
        "teamprofile_summary": teamprofile_summary,
        "rows": rows,
    }
    return report


def render_historical_coverage_markdown(report: dict[str, Any]) -> str:
    window = report["window"]
    inventory = report["source_inventory"]
    coverage = report["coverage_summary"]
    teamprofiles = report["teamprofile_summary"]
    lines = [
        "# Historical Coverage Audit",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Window: `{window.get('start_date') or 'min'}` -> `{window.get('end_date') or 'max'}`",
        "",
        "## Source Inventory",
        f"- Legacy fixture dates: `{inventory['legacy_fixture_dates_total']}`",
        f"- Legacy backtest dates: `{inventory['legacy_backtest_dates_total']}`",
        f"- Legacy raw snapshot dates: `{inventory['legacy_raw_snapshot_dates_total']}`",
        f"- V2 fixture dates: `{inventory['v2_fixture_dates_total']}`",
        f"- V2 result dates: `{inventory['v2_result_dates_total']}`",
        f"- V2 stat dates: `{inventory['v2_stat_dates_total']}`",
        f"- V2 legacy odds dates: `{inventory['v2_legacy_odds_dates_total']}`",
        "",
        "## Overlap Summary",
        f"- Fixture/backtest overlap dates: `{coverage['fixture_backtest_overlap_dates_total']}`",
        f"- Ready for model replay: `{coverage['ready_for_model_replay_dates_total']}`",
        f"- Missing V2 fixture dates: `{coverage['missing_v2_fixture_dates_count']}`",
        f"- Missing V2 result dates: `{coverage['missing_v2_result_dates_count']}`",
        f"- Missing V2 stat dates: `{coverage['missing_v2_stat_dates_count']}`",
        f"- Missing V2 odds dates: `{coverage['missing_v2_odds_dates_count']}`",
        "",
        "## Teamprofiles",
        f"- Profile date: `{teamprofiles['profile_date']}`",
        f"- Profile docs: `{teamprofiles['profile_doc_count']}`",
        f"- Teams with both home+away: `{teamprofiles['teams_with_both']}`",
        "",
        "## Sample Gaps",
        f"- Missing fixture dates sample: `{coverage['missing_v2_fixture_dates_sample']}`",
        f"- Missing odds dates sample: `{coverage['missing_v2_odds_dates_sample']}`",
        f"- Teams missing home sample: `{teamprofiles['teams_missing_home_sample']}`",
        f"- Teams missing away sample: `{teamprofiles['teams_missing_away_sample']}`",
        "",
        "## First Rows",
    ]
    for row in report["rows"][:15]:
        lines.append(
            "- "
            + json.dumps(
                {
                    "date": row["date"],
                    "legacy_fixture_matches": row["legacy_fixture_matches"],
                    "legacy_backtest_docs": row["legacy_backtest_docs"],
                    "v2_fixture_matches": row["v2_fixture_matches"],
                    "v2_result_matches": row["v2_result_matches"],
                    "v2_legacy_offer_rows": row["v2_legacy_offer_rows"],
                    "ready_for_model_replay": row["ready_for_model_replay"],
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines) + "\n"


def run_historical_coverage_audit(
    *,
    database: Any,
    legacy_app_database: Any,
    legacy_unibet_database: Any,
    reports_dir: Path,
    source_workflow: str,
    start_date: str | None = None,
    end_date: str | None = None,
    profile_date: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    report = build_historical_coverage_report(
        database=database,
        legacy_app_database=legacy_app_database,
        legacy_unibet_database=legacy_unibet_database,
        start_date=start_date,
        end_date=end_date,
        profile_date=profile_date,
    )
    markdown = render_historical_coverage_markdown(report)
    coverage = report["coverage_summary"]
    window_label = f"{start_date or 'min'}__{end_date or 'max'}"
    metrics = {
        "fixture_backtest_overlap_dates_total": coverage["fixture_backtest_overlap_dates_total"],
        "ready_for_model_replay_dates_total": coverage["ready_for_model_replay_dates_total"],
        "missing_v2_fixture_dates_count": coverage["missing_v2_fixture_dates_count"],
        "missing_v2_result_dates_count": coverage["missing_v2_result_dates_count"],
        "missing_v2_stat_dates_count": coverage["missing_v2_stat_dates_count"],
        "missing_v2_odds_dates_count": coverage["missing_v2_odds_dates_count"],
        "teamprofiles_with_both": report["teamprofile_summary"]["teams_with_both"],
    }
    status = (
        "ok"
        if coverage["missing_v2_fixture_dates_count"] == 0
        and coverage["missing_v2_result_dates_count"] == 0
        and coverage["missing_v2_stat_dates_count"] == 0
        and coverage["missing_v2_odds_dates_count"] == 0
        else "warn"
    )
    findings: list[str] = []
    if coverage["missing_v2_fixture_dates_count"]:
        findings.append("missing_v2_fixture_dates_present")
    if coverage["missing_v2_result_dates_count"]:
        findings.append("missing_v2_result_dates_present")
    if coverage["missing_v2_stat_dates_count"]:
        findings.append("missing_v2_stat_dates_present")
    if coverage["missing_v2_odds_dates_count"]:
        findings.append("missing_v2_odds_dates_present")

    summary: dict[str, Any] = {
        "job": "audit_historical_coverage",
        "status": status,
        "window": report["window"],
        "metrics": metrics,
        "report_files": {
            "json": str(reports_dir / f"historical_coverage_{window_label}.json"),
            "markdown": str(reports_dir / f"historical_coverage_{window_label}.md"),
        },
        "findings": findings,
    }
    if dry_run:
        summary["report"] = report
        summary["markdown"] = markdown
        return summary

    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / f"historical_coverage_{window_label}.json"
    md_path = reports_dir / f"historical_coverage_{window_label}.md"
    latest_json_path = reports_dir / "historical_coverage_latest.json"
    latest_md_path = reports_dir / "historical_coverage_latest.md"

    job_collection = database["job_runs"]
    run_doc = build_job_run_started_doc(
        job_name="audit_historical_coverage",
        source_workflow=source_workflow,
        target_window={"start_date": start_date, "end_date": end_date, "profile_date": profile_date},
        job_args={"dry_run": False},
    )
    job_collection.insert_one(run_doc)
    try:
        json_text = json.dumps(report, indent=2, ensure_ascii=False, default=str)
        json_path.write_text(json_text, encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")
        latest_json_path.write_text(json_text, encoding="utf-8")
        latest_md_path.write_text(markdown, encoding="utf-8")

        audit_row = build_audit_report_row(
            audit_type="historical_coverage",
            scope_key=f"{source_workflow}:{window_label}",
            status=status,
            metrics=metrics,
            findings=findings,
        )
        health_row = build_health_report_row(
            job_name="audit_historical_coverage",
            status=status,
            summary=(
                "Historical coverage audit found full overlap coverage."
                if status == "ok"
                else "Historical coverage audit found missing fixture, enrichment, or odds coverage."
            ),
            metrics=metrics,
        )
        database["audit_reports"].update_one(
            {
                "audit_type": audit_row["audit_type"],
                "scope_key": audit_row["scope_key"],
                "report_date": audit_row["report_date"],
            },
            {"$set": audit_row},
            upsert=True,
        )
        database["health_reports"].update_one(
            {
                "job_name": health_row["job_name"],
                "report_date": health_row["report_date"],
            },
            {"$set": health_row},
            upsert=True,
        )
        job_collection.update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics=metrics,
            ),
        )
    except Exception as exc:
        job_collection.update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="failed",
                metrics=metrics,
                error={"type": type(exc).__name__, "message": str(exc)},
            ),
        )
        raise

    return summary
