from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ullebets_v2.matchups.service import build_matchups_score_docs
from ullebets_v2.storage.collections import (
    AUDIT_REPORTS,
    EV_MODEL_SCORES,
    FIXTURES_CANONICAL,
    FORWARD_BETS,
    FORWARD_RESULTS,
    HEALTH_REPORTS,
    JOB_RUNS,
    MARKET_SNAPSHOTS,
    MATCHUPS_LEAGUE_AVG,
    MATCHUPS_SCORE,
    TEAMPROFILES,
)


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _iso(item) for key, item in value.items() if key != "_id"}
    if isinstance(value, (list, tuple)):
        return [_iso(item) for item in value]
    return value


def _find_rows(database: Any, collection_name: str, query: dict[str, Any], *, sort: list[tuple[str, int]] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    cursor = database[collection_name].find(query, projection={"_id": 0})
    if sort:
        cursor = cursor.sort(sort)
    if limit is not None:
        cursor = cursor.limit(limit)
    return list(cursor)


def _latest_source_date(database: Any) -> str | None:
    row = database[FIXTURES_CANONICAL].find_one({}, projection={"_id": 0, "source_date": 1}, sort=[("source_date", -1)])
    if not row or not row.get("source_date"):
        return None
    return str(row["source_date"])


def _match_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "matchKey": str(row.get("match_key") or ""),
        "sourceMatchId": row.get("source_match_id"),
        "sourceDate": row.get("source_date"),
        "startTime": _iso(row.get("start_time")),
        "leagueKey": row.get("league_key"),
        "leagueName": row.get("league_name"),
        "homeTeamKey": row.get("home_team_key"),
        "awayTeamKey": row.get("away_team_key"),
        "homeTeamName": row.get("home_team_name"),
        "awayTeamName": row.get("away_team_name"),
        "statusType": row.get("status_type"),
    }


def _matchup_summary(row: dict[str, Any]) -> dict[str, Any]:
    forecast = row.get("forecast") if isinstance(row.get("forecast"), dict) else {}
    condition = str(row.get("condition") or "").upper()
    return {
        "entryKey": str(row.get("entry_key") or ""),
        "snapshotDate": row.get("snapshot_date"),
        "matchKey": str(row.get("match_key") or ""),
        "leagueKey": row.get("league_key"),
        "leagueName": row.get("league_name"),
        "homeTeamName": row.get("home_team_name"),
        "awayTeamName": row.get("away_team_name"),
        "statKey": row.get("stat_key"),
        "statLabel": row.get("stat_label"),
        "period": row.get("period"),
        "periodLabel": row.get("period_label"),
        "scope": row.get("scope"),
        "condition": condition,
        "score": row.get("score"),
        "rankPosition": row.get("rank_position"),
        "isTop50": bool(row.get("is_top_50")),
        "marketBias": _iso(row.get("market_bias")),
        "leagueBaseline": forecast.get("leagueBaseline"),
    }


def _load_matchups(database: Any, fixtures: list[dict[str, Any]], source_date: str) -> list[dict[str, Any]]:
    match_keys = [str(row.get("match_key")) for row in fixtures if row.get("match_key")]
    if not match_keys:
        return []
    rows = _find_rows(
        database,
        MATCHUPS_SCORE,
        {"snapshot_date": source_date, "match_key": {"$in": match_keys}},
    )
    if rows:
        return rows

    team_keys = {
        str(row.get("home_team_key"))
        for row in fixtures
        if row.get("home_team_key")
    } | {
        str(row.get("away_team_key"))
        for row in fixtures
        if row.get("away_team_key")
    }
    profiles = _find_rows(database, TEAMPROFILES, {"team_key": {"$in": sorted(team_keys)}}) if team_keys else []
    computed, _ = build_matchups_score_docs(
        target_matches=fixtures,
        teamprofile_docs=profiles,
        snapshot_date=source_date,
    )
    return computed


def read_dashboard(database: Any, *, source_date: str | None = None, limit_per_condition: int = 20) -> dict[str, Any]:
    selected_date = source_date or _latest_source_date(database)
    if selected_date is None:
        return {"selectedDate": None, "matches": [], "matchups": []}

    fixtures = _find_rows(database, FIXTURES_CANONICAL, {"source_date": selected_date}, sort=[("start_time", 1)])
    matchup_rows = _load_matchups(database, fixtures, selected_date)
    matchup_rows.sort(
        key=lambda row: (
            str(row.get("condition") or ""),
            int(row.get("rank_position") or 10**9),
            -float(row.get("score") or 0),
        )
    )
    selected_matchups: list[dict[str, Any]] = []
    for condition in ("over", "under"):
        condition_rows = [row for row in matchup_rows if str(row.get("condition") or "").lower() == condition]
        selected_matchups.extend(condition_rows[:limit_per_condition])

    return {
        "selectedDate": selected_date,
        "matches": [_match_summary(row) for row in fixtures],
        "matchups": [_matchup_summary(row) for row in selected_matchups],
    }


def _latest_profile(database: Any, team_key: str, match_type: str) -> dict[str, Any] | None:
    return database[TEAMPROFILES].find_one(
        {"team_key": team_key, "match_type": match_type},
        projection={"_id": 0},
        sort=[("profile_date", -1), ("generated_at", -1)],
    )


def _stat_rows(home_profile: dict[str, Any] | None, away_profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not home_profile or not away_profile:
        return []
    home_stats = home_profile.get("statistics", {}).get("for", {})
    away_stats = away_profile.get("statistics", {}).get("for", {})
    stat_keys = sorted(set(home_stats) | set(away_stats))
    rows: list[dict[str, Any]] = []
    for stat_key in stat_keys:
        for period in ("ALL", "1ST", "2ND"):
            home_node = home_stats.get(stat_key, {}).get(period, {})
            away_node = away_stats.get(stat_key, {}).get(period, {})
            home_league = home_profile.get("statistics", {}).get("leagueAverage", {}).get("for", {}).get(stat_key, {}).get(period, {})
            away_league = away_profile.get("statistics", {}).get("leagueAverage", {}).get("for", {}).get(stat_key, {}).get(period, {})
            if not any(node.get("value") is not None for node in (home_node, away_node, home_league, away_league)):
                continue
            rows.append(
                {
                    "statKey": stat_key,
                    "period": period,
                    "homeValue": home_node.get("value"),
                    "awayValue": away_node.get("value"),
                    "homeRank": home_node.get("rank"),
                    "awayRank": away_node.get("rank"),
                    "homeLeagueAverage": home_league.get("value"),
                    "awayLeagueAverage": away_league.get("value"),
                }
            )
    return rows


def read_match_detail(database: Any, match_key: str) -> dict[str, Any] | None:
    fixture = database[FIXTURES_CANONICAL].find_one({"match_key": match_key}, projection={"_id": 0})
    if fixture is None:
        return None
    source_date = str(fixture.get("source_date") or "")
    matchup_rows = _load_matchups(database, [fixture], source_date) if source_date else []
    league_avg_rows = _find_rows(database, MATCHUPS_LEAGUE_AVG, {"match_key": match_key, "snapshot_date": source_date}) if source_date else []
    snapshot_rows = _find_rows(database, MARKET_SNAPSHOTS, {"match_key": match_key}, sort=[("snapshot_time", 1)])
    checkpoints: dict[str, dict[str, Any]] = {}
    for row in snapshot_rows:
        label = str(row.get("snapshot_label") or "")
        if not label:
            continue
        checkpoints[label] = {
            "label": label,
            "snapshotType": row.get("snapshot_type"),
            "capturedAt": _iso(row.get("snapshot_time") or row.get("captured_at")),
            "minutesToKickoff": row.get("minutes_to_kickoff"),
            "invalidForModel": bool(row.get("invalid_for_model")),
        }

    home_key = str(fixture.get("home_team_key") or "")
    away_key = str(fixture.get("away_team_key") or "")
    home_profile = _latest_profile(database, home_key, "home") if home_key else None
    away_profile = _latest_profile(database, away_key, "away") if away_key else None
    return {
        "match": _match_summary(fixture),
        "matchups": [_matchup_summary(row) for row in sorted(matchup_rows, key=lambda item: int(item.get("rank_position") or 10**9))],
        "leagueAverageMatchups": [_iso(row) for row in league_avg_rows],
        "checkpoints": list(checkpoints.values()),
        "teamStats": _stat_rows(home_profile, away_profile),
    }


def _fixture_lookup(database: Any, match_keys: list[str]) -> dict[str, dict[str, Any]]:
    if not match_keys:
        return {}
    rows = _find_rows(database, FIXTURES_CANONICAL, {"match_key": {"$in": sorted(set(match_keys))}})
    return {str(row.get("match_key")): row for row in rows if row.get("match_key")}


def read_auto(database: Any, *, limit: int = 200) -> dict[str, Any]:
    rows = _find_rows(database, FORWARD_BETS, {}, sort=[("match_start_time", -1)], limit=limit)
    fixtures = _fixture_lookup(database, [str(row.get("match_key")) for row in rows if row.get("match_key")])
    selections = []
    for row in rows:
        fixture = fixtures.get(str(row.get("match_key") or ""), {})
        selections.append(
            {
                "selectionKey": row.get("selection_key") or row.get("prediction_key"),
                "matchKey": row.get("match_key"),
                "homeTeamName": fixture.get("home_team_name"),
                "awayTeamName": fixture.get("away_team_name"),
                "leagueName": fixture.get("league_name"),
                "statKey": row.get("stat_key"),
                "period": row.get("period"),
                "scope": row.get("scope"),
                "direction": row.get("direction"),
                "lineValue": row.get("line_value"),
                "selectedOdds": row.get("selected_odds") or row.get("saved_odds"),
                "predictedWinProbability": row.get("predicted_win_probability"),
                "expectedRoiUnits": row.get("expected_roi_units"),
                "modelId": row.get("model_id"),
                "modelStatus": row.get("model_status"),
                "policyId": row.get("selection_policy_id"),
                "matchStartTime": _iso(row.get("match_start_time")),
                "validForForwardEvaluation": row.get("valid_for_forward_evaluation"),
                "invalidForModel": bool(row.get("invalid_for_model")),
            }
        )
    return {"count": len(selections), "selections": selections}


def read_results(database: Any, *, limit: int = 250) -> dict[str, Any]:
    rows = _find_rows(database, FORWARD_RESULTS, {}, sort=[("match_start_time", -1)], limit=limit)
    total = len(rows)
    settled_rows = [row for row in rows if str(row.get("settlement_status") or "").lower() == "settled"]
    valid_rows = [row for row in settled_rows if row.get("valid_for_performance") is True]
    return {
        "summary": {
            "rows": total,
            "settled": len(valid_rows),
            "wins": sum(1 for row in valid_rows if row.get("win") is True),
            "losses": sum(1 for row in valid_rows if row.get("win") is False),
            "excluded": sum(1 for row in rows if row.get("valid_for_performance") is False),
        },
        "rows": [_iso(row) for row in rows],
    }


def read_team(database: Any, team_key: str) -> dict[str, Any]:
    rows = _find_rows(database, TEAMPROFILES, {"team_key": team_key}, sort=[("profile_date", -1), ("generated_at", -1)])
    return {"teamKey": team_key, "profiles": [_iso(row) for row in rows]}


def read_model(database: Any) -> dict[str, Any]:
    scores = database[EV_MODEL_SCORES]
    forward = database[FORWARD_BETS]
    results = database[FORWARD_RESULTS]
    model_ids = sorted(str(value) for value in scores.distinct("model_id") if value)
    policy_ids = sorted(str(value) for value in forward.distinct("selection_policy_id") if value)
    return {
        "modelIds": model_ids,
        "policyIds": policy_ids,
        "scoreCount": scores.count_documents({}),
        "forwardSelectionCount": forward.count_documents({}),
        "settledForwardCount": results.count_documents({"settlement_status": "settled", "valid_for_performance": True}),
        "officialClvCount": results.count_documents({"clv_status": "available", "closing_quality": "t10"}),
    }


def read_system_status(database: Any, *, limit: int = 30) -> dict[str, Any]:
    return {
        "jobs": [_iso(row) for row in _find_rows(database, JOB_RUNS, {}, sort=[("started_at", -1)], limit=limit)],
        "health": [_iso(row) for row in _find_rows(database, HEALTH_REPORTS, {}, sort=[("generated_at", -1)], limit=limit)],
        "audits": [_iso(row) for row in _find_rows(database, AUDIT_REPORTS, {}, sort=[("generated_at", -1)], limit=limit)],
    }
