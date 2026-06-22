from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.support.schemas import build_support_documents
from ullebets_v2.teamprofiles.persistence import persist_teamprofile_records
from ullebets_v2.teamprofiles.reports import (
    build_teamprofile_audit_rows,
    build_teamprofile_health_rows,
    build_teamprofile_parity_rows,
)
from ullebets_v2.teamprofiles.specials import (
    assign_special_ranks,
    build_raw_payload_lookups,
    compute_profile_specials,
    compute_specials_league_average,
)


PERIODS = ("ALL", "1ST", "2ND")


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _safe_timestamp(result_row: dict[str, Any]) -> int | None:
    start_time = result_row.get("start_time")
    if isinstance(start_time, datetime):
        return int(start_time.timestamp())
    parsed = _parse_date(result_row.get("source_date"))
    if parsed is None:
        return None
    return int(datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC).timestamp())


def _include_result_row(result_row: dict[str, Any], profile_date: str | None) -> bool:
    if profile_date is None:
        return True
    row_date = result_row.get("source_date")
    return bool(row_date and row_date < profile_date)


def _ensure_period_node(container: dict[str, Any], section: str, stat_key: str, period: str) -> dict[str, Any]:
    section_node = container.setdefault(section, {})
    stat_node = section_node.setdefault(stat_key, {})
    return stat_node.setdefault(period, {})


def _team_identity(result_row: dict[str, Any], side: str) -> tuple[str, str | None, str | None]:
    return (
        str(result_row.get(f"{side}_team_key") or ""),
        result_row.get(f"{side}_team_name"),
        result_row.get(f"{side}_team_id"),
    )


def build_teamprofile_docs(
    *,
    match_stats_canonical: list[dict[str, Any]],
    match_results_canonical: list[dict[str, Any]],
    raw_incidents: list[dict[str, Any]],
    raw_shotmaps: list[dict[str, Any]],
    support_docs: dict[str, Any],
    profile_date: str | None = None,
    generated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    captured_at = generated_at or utc_now()
    support_teams = {str(team["team_key"]): team for team in support_docs.get("teams", [])}
    support_leagues = {str(league["league_key"]): league for league in support_docs.get("leagues", [])}
    incidents_by_match, shotmaps_by_match = build_raw_payload_lookups(
        raw_incidents=raw_incidents,
        raw_shotmaps=raw_shotmaps,
    )

    filtered_results = [row for row in match_results_canonical if _include_result_row(row, profile_date)]
    if not filtered_results:
        return []

    stats_lookup: dict[tuple[str, str, str, str], float] = {}
    stat_periods_by_match: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in match_stats_canonical:
        match_key = str(row.get("match_key") or "")
        stat_key = str(row.get("stat_key") or "")
        period = str(row.get("period") or "")
        scope = str(row.get("scope") or "")
        if not match_key or not stat_key or scope not in {"home", "away"}:
            continue
        result_row = next((item for item in filtered_results if str(item.get("match_key") or "") == match_key), None)
        if result_row is None:
            continue
        value = row.get("actual_value")
        if not isinstance(value, (int, float)):
            continue
        stats_lookup[(match_key, stat_key, period, scope)] = float(value)
        stat_periods_by_match[match_key].add((stat_key, period))

    profile_states: dict[tuple[str, str], dict[str, Any]] = {}
    for result_row in filtered_results:
        match_key = str(result_row.get("match_key") or "")
        source_match_id = result_row.get("source_match_id")
        league_key = str(result_row.get("league_key") or "unknown-league")
        league_doc = support_leagues.get(league_key, {})
        timestamp = _safe_timestamp(result_row)
        for side, opponent in (("home", "away"), ("away", "home")):
            team_key, result_team_name, result_team_id = _team_identity(result_row, side)
            if not team_key:
                continue
            state = profile_states.setdefault(
                (team_key, side),
                {
                    "team_key": team_key,
                    "match_type": side,
                    "league_key": league_key,
                    "team_name": support_teams.get(team_key, {}).get("team_name") or result_team_name,
                    "team_id": support_teams.get(team_key, {}).get("team_id") or result_team_id,
                    "league_name": league_doc.get("league_name") or result_row.get("league_name"),
                    "league_id": league_doc.get("league_id"),
                    "games": [],
                    "statistics": {"for": {}, "against": {}, "leagueAverage": {"for": {}, "against": {}}},
                    "accumulators": {
                        "for": defaultdict(lambda: defaultdict(list)),
                        "against": defaultdict(lambda: defaultdict(list)),
                    },
                    "history": defaultdict(lambda: defaultdict(list)),
                },
            )
            state["games"].append(
                {
                    "matchId": source_match_id,
                    "match_key": match_key,
                    "date": result_row.get("source_date"),
                    "timestamp": timestamp,
                    "opp": result_row.get(f"{opponent}_team_name"),
                    "opponent_team_key": result_row.get(f"{opponent}_team_key"),
                }
            )
            side_scope = side
            opponent_scope = opponent
            for stat_key, period in sorted(stat_periods_by_match.get(match_key, set())):
                for_value = stats_lookup.get((match_key, stat_key, period, side_scope))
                against_value = stats_lookup.get((match_key, stat_key, period, opponent_scope))
                if isinstance(for_value, (int, float)):
                    state["accumulators"]["for"][stat_key][period].append(float(for_value))
                if isinstance(against_value, (int, float)):
                    state["accumulators"]["against"][stat_key][period].append(float(against_value))
                if isinstance(for_value, (int, float)) and isinstance(against_value, (int, float)):
                    history_item = {
                        "matchId": source_match_id,
                        "date": result_row.get("source_date"),
                        "timestamp": timestamp,
                        "opp": result_row.get(f"{opponent}_team_name"),
                        "val": float(for_value),
                        "oppVal": float(against_value),
                    }
                    state["history"][stat_key][period].append(history_item)

    profile_docs: list[dict[str, Any]] = []
    for (team_key, match_type), state in sorted(profile_states.items()):
        statistics = state["statistics"]
        stat_keys = sorted(
            {
                *state["accumulators"]["for"].keys(),
                *state["accumulators"]["against"].keys(),
            }
        )
        for stat_key in stat_keys:
            for period in PERIODS:
                for_values = state["accumulators"]["for"][stat_key].get(period, [])
                against_values = state["accumulators"]["against"][stat_key].get(period, [])
                if for_values:
                    node = _ensure_period_node(statistics, "for", stat_key, period)
                    node["value"] = sum(for_values) / len(for_values)
                if against_values:
                    node = _ensure_period_node(statistics, "against", stat_key, period)
                    node["value"] = sum(against_values) / len(against_values)
                history_rows = sorted(
                    state["history"][stat_key].get(period, []),
                    key=lambda row: row.get("timestamp") or 0,
                    reverse=True,
                )
                if history_rows:
                    if "value" in _ensure_period_node(statistics, "for", stat_key, period):
                        _ensure_period_node(statistics, "for", stat_key, period)["history"] = history_rows
                    if "value" in _ensure_period_node(statistics, "against", stat_key, period):
                        _ensure_period_node(statistics, "against", stat_key, period)["history"] = history_rows

        games = sorted(state["games"], key=lambda row: row.get("timestamp") or 0, reverse=True)
        latest_saved_at = None
        if games and games[0].get("date"):
            latest_saved_at = games[0]["date"]
        profile_doc = {
            "profile_key": f"{profile_date or 'current'}|{team_key}|{match_type}",
            "team_key": team_key,
            "league_key": state["league_key"],
            "match_type": match_type,
            "profile_date": profile_date or "current",
            "generated_at": captured_at,
            "games": games,
            "statistics": statistics,
            "specials": compute_profile_specials(
                games=games,
                match_type=match_type,
                incidents_by_match=incidents_by_match,
                shotmaps_by_match=shotmaps_by_match,
            ),
            "behaviour": {},
            "meta": {
                "lagnamn": state["team_name"],
                "lagId": state["team_id"],
                "leagueName": state["league_name"],
                "leagueKey": state["league_key"],
                "ligaId": state["league_id"],
                "matchType": match_type,
                "leagueTeamCount": sum(1 for row in support_docs.get("teams", []) if row.get("league_key") == state["league_key"]),
                "savedAt": latest_saved_at,
            },
        }
        profile_docs.append(profile_doc)

    profiles_by_league_and_type: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in profile_docs:
        profiles_by_league_and_type[(str(row.get("league_key")), str(row.get("match_type")))].append(row)

    for _, league_profiles in profiles_by_league_and_type.items():
        stat_group_keys = {"for", "against"}
        stat_keys = sorted(
            {
                stat_key
                for profile in league_profiles
                for group in stat_group_keys
                for stat_key in profile.get("statistics", {}).get(group, {}).keys()
            }
        )
        for stat_group in stat_group_keys:
            for stat_key in stat_keys:
                for period in PERIODS:
                    values: list[tuple[int, float]] = []
                    for index, profile in enumerate(league_profiles):
                        value = (
                            profile.get("statistics", {})
                            .get(stat_group, {})
                            .get(stat_key, {})
                            .get(period, {})
                            .get("value")
                        )
                        if isinstance(value, (int, float)):
                            values.append((index, float(value)))
                    if values:
                        average_value = sum(value for _, value in values) / len(values)
                        for profile in league_profiles:
                            _ensure_period_node(profile["statistics"]["leagueAverage"], stat_group, stat_key, period)["value"] = average_value
                        for rank, (index, _) in enumerate(sorted(values, key=lambda row: row[1], reverse=True), start=1):
                            _ensure_period_node(league_profiles[index]["statistics"], stat_group, stat_key, period)["rank"] = rank
        assign_special_ranks(league_profiles)
        specials_league_average = compute_specials_league_average(league_profiles)
        for profile in league_profiles:
            profile["specials"]["leagueAverage"] = specials_league_average

    return sorted(profile_docs, key=lambda row: (row["league_key"], row["team_key"], row["match_type"]))


def load_canonical_rows(
    database: Any,
    *,
    profile_date: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    results = list(database["match_results_canonical"].find({}, projection={"_id": 0}))
    if profile_date is not None:
        results = [row for row in results if _include_result_row(row, profile_date)]
    match_keys = [str(row.get("match_key")) for row in results if row.get("match_key") is not None]
    if not match_keys:
        return [], [], [], []
    stats = list(
        database["match_stats_canonical"].find(
            {"match_key": {"$in": match_keys}},
            projection={"_id": 0},
        )
    )
    raw_incidents = list(
        database["raw_incidents"].find(
            {"match_key": {"$in": match_keys}},
            projection={"_id": 0},
        )
    )
    raw_shotmaps = list(
        database["raw_shotmaps"].find(
            {"match_key": {"$in": match_keys}},
            projection={"_id": 0},
        )
    )
    return stats, results, raw_incidents, raw_shotmaps


def run_teamprofile_build(
    *,
    source_workflow: str,
    support_docs: dict[str, Any],
    match_stats_canonical: list[dict[str, Any]] | None = None,
    match_results_canonical: list[dict[str, Any]] | None = None,
    raw_incidents: list[dict[str, Any]] | None = None,
    raw_shotmaps: list[dict[str, Any]] | None = None,
    profile_date: str | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    captured_at = generated_at or utc_now()
    stats_rows = match_stats_canonical
    result_rows = match_results_canonical
    incident_rows = raw_incidents
    shotmap_rows = raw_shotmaps
    if stats_rows is None or result_rows is None or incident_rows is None or shotmap_rows is None:
        if database is None:
            stats_rows = stats_rows or []
            result_rows = result_rows or []
            incident_rows = incident_rows or []
            shotmap_rows = shotmap_rows or []
        else:
            loaded_stats, loaded_results, loaded_incidents, loaded_shotmaps = load_canonical_rows(
                database,
                profile_date=profile_date,
            )
            stats_rows = loaded_stats if stats_rows is None else stats_rows
            result_rows = loaded_results if result_rows is None else result_rows
            incident_rows = loaded_incidents if incident_rows is None else incident_rows
            shotmap_rows = loaded_shotmaps if shotmap_rows is None else shotmap_rows

    profile_docs = build_teamprofile_docs(
        match_stats_canonical=stats_rows or [],
        match_results_canonical=result_rows or [],
        raw_incidents=incident_rows or [],
        raw_shotmaps=shotmap_rows or [],
        support_docs=support_docs,
        profile_date=profile_date,
        generated_at=captured_at,
    )
    report_date = profile_date or captured_at.date().isoformat()
    parity_rows = build_teamprofile_parity_rows(
        source_workflow=source_workflow,
        match_results_canonical=result_rows or [],
        profile_docs=profile_docs,
        report_date=report_date,
    )
    audit_rows = build_teamprofile_audit_rows(
        source_workflow=source_workflow,
        match_results_canonical=result_rows or [],
        profile_docs=profile_docs,
        report_date=report_date,
    )
    health_rows = build_teamprofile_health_rows(
        profile_docs=profile_docs,
        report_date=report_date,
    )

    summary: dict[str, Any] = {
        "job": "build_teamprofiles",
        "generated_at": captured_at.isoformat(),
        "profile_date": profile_date,
        "match_results": len(result_rows or []),
        "match_stats": len(stats_rows or []),
        "raw_incidents": len(incident_rows or []),
        "raw_shotmaps": len(shotmap_rows or []),
        "teamprofiles": len(profile_docs),
        "parity_reports": len(parity_rows),
        "audit_reports": len(audit_rows),
        "health_reports": len(health_rows),
        "parity_status_counts": {
            status: sum(1 for row in parity_rows if row["parity_status"] == status)
            for status in sorted({row["parity_status"] for row in parity_rows})
        },
        "audit_status_counts": {
            status: sum(1 for row in audit_rows if row["status"] == status)
            for status in sorted({row["status"] for row in audit_rows})
        },
        "health_status_counts": {
            status: sum(1 for row in health_rows if row["status"] == status)
            for status in sorted({row["status"] for row in health_rows})
        },
        "profile_docs": profile_docs,
    }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="build_teamprofiles",
        source_workflow=source_workflow,
        target_window={
            "profile_date": profile_date,
            "match_result_count": len(result_rows or []),
        },
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {key: value for key, value in summary.items() if key != "profile_docs"}
    try:
        persistence_metrics = persist_teamprofile_records(
            database,
            profile_docs=profile_docs,
            parity_rows=parity_rows,
            audit_rows=audit_rows,
            health_rows=health_rows,
        )
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics={**persistence_metrics, **job_metrics},
            ),
        )
    except Exception as exc:
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="failed",
                metrics=job_metrics,
                error={"type": type(exc).__name__, "message": str(exc)},
            ),
        )
        raise
    return summary
