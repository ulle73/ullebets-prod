from __future__ import annotations

from typing import Any

from ullebets_v2.read_api import service
from ullebets_v2.storage.collections import (
    FIXTURES_CANONICAL,
    FORWARD_BETS,
    FORWARD_RESULTS,
    MATCH_RESULTS_CANONICAL,
    TEAMPROFILES,
)


def _latest_current_profiles(database: Any, league_key: str) -> list[dict[str, Any]]:
    rows = service._find_rows(database, TEAMPROFILES, {"league_key": league_key})
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        team_key = str(row.get("team_key") or "")
        context = str(row.get("match_type") or "")
        if not team_key or context not in {"home", "away"}:
            continue
        key = (team_key, context)
        current = latest.get(key)
        row_is_current = str(row.get("profile_date") or "") == "current"
        current_is_current = current is not None and str(current.get("profile_date") or "") == "current"
        if current is None or (row_is_current and not current_is_current) or (row_is_current == current_is_current and service._profile_order_key(row) > service._profile_order_key(current)):
            latest[key] = row
    return list(latest.values())


def _league_stat_rows(database: Any, league_key: str, team_names: dict[str, str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for profile in _latest_current_profiles(database, league_key):
        team_key = str(profile.get("team_key") or "")
        context = str(profile.get("match_type") or "")
        statistics = profile.get("statistics") if isinstance(profile.get("statistics"), dict) else {}
        league_average = statistics.get("leagueAverage") if isinstance(statistics.get("leagueAverage"), dict) else {}
        for orientation in ("for", "against"):
            stat_map = statistics.get(orientation) if isinstance(statistics.get(orientation), dict) else {}
            average_map = league_average.get(orientation) if isinstance(league_average.get(orientation), dict) else {}
            for stat_key, periods in stat_map.items():
                if not isinstance(periods, dict):
                    continue
                for period, node in periods.items():
                    if not isinstance(node, dict) or node.get("value") is None:
                        continue
                    average_node = average_map.get(stat_key, {}).get(period, {}) if isinstance(average_map.get(stat_key), dict) else {}
                    output.append({
                        "teamKey": team_key,
                        "teamName": team_names.get(team_key) or profile.get("meta", {}).get("lagnamn") or team_key,
                        "context": context,
                        "orientation": orientation,
                        "statKey": stat_key,
                        "period": period,
                        "value": node.get("value"),
                        "rank": node.get("rank"),
                        "leagueAverage": average_node.get("value") if isinstance(average_node, dict) else None,
                    })
    return output


def read_league(database: Any, league_key: str) -> dict[str, Any] | None:
    payload = service.read_league(database, league_key)
    if payload is None:
        return None
    team_names = {str(row.get("teamKey")): str(row.get("teamName") or row.get("teamKey")) for row in payload["teams"]}
    return {**payload, "statRows": _league_stat_rows(database, league_key, team_names)}


def _fixture_by_source_match_id(database: Any, match_ids: list[Any]) -> dict[str, dict[str, Any]]:
    values = [value for value in match_ids if value is not None]
    if not values:
        return {}
    rows = service._find_rows(database, FIXTURES_CANONICAL, {"source_match_id": {"$in": values}})
    return {str(row.get("source_match_id")): row for row in rows if row.get("source_match_id") is not None}


def _results_by_match_key(database: Any, match_keys: list[str]) -> dict[str, dict[str, Any]]:
    return service._latest_results(database, match_keys)


def _enrich_profile_games(database: Any, team_key: str, context: dict[str, Any] | None) -> dict[str, Any] | None:
    if context is None:
        return None
    games = list(context.get("games") or [])
    fixtures = _fixture_by_source_match_id(database, [game.get("matchId") for game in games])
    result_map = _results_by_match_key(database, [str(row.get("match_key")) for row in fixtures.values() if row.get("match_key")])
    enriched: list[dict[str, Any]] = []
    for game in games:
        fixture = fixtures.get(str(game.get("matchId")))
        if fixture is None:
            enriched.append(game)
            continue
        is_home = str(fixture.get("home_team_key") or "") == team_key
        opponent_key = fixture.get("away_team_key") if is_home else fixture.get("home_team_key")
        opponent_name = fixture.get("away_team_name") if is_home else fixture.get("home_team_name")
        match_key = str(fixture.get("match_key") or "")
        result = result_map.get(match_key)
        enriched.append({
            **game,
            "matchKey": match_key or game.get("matchKey"),
            "opponentTeamKey": opponent_key,
            "opponentName": opponent_name or game.get("opponentName"),
            "homeScore": result.get("home_score") if result else None,
            "awayScore": result.get("away_score") if result else None,
        })
    return {**context, "games": enriched}


def read_team(database: Any, team_key: str) -> dict[str, Any] | None:
    payload = service.read_team(database, team_key)
    if payload is None:
        return None
    return {
        **payload,
        "contexts": {
            "home": _enrich_profile_games(database, team_key, payload["contexts"].get("home")),
            "away": _enrich_profile_games(database, team_key, payload["contexts"].get("away")),
        },
    }


def _selection_row(row: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    selected_odds = row.get("selected_odds") if row.get("selected_odds") is not None else row.get("saved_odds")
    return {
        "selectionKey": row.get("selection_key") or row.get("prediction_key"),
        "predictionKey": row.get("prediction_key"),
        "matchKey": row.get("match_key"),
        "leagueKey": fixture.get("league_key"),
        "leagueName": fixture.get("league_name") or row.get("league_name"),
        "homeTeamKey": fixture.get("home_team_key"),
        "awayTeamKey": fixture.get("away_team_key"),
        "homeTeamName": fixture.get("home_team_name") or row.get("home_team_name"),
        "awayTeamName": fixture.get("away_team_name") or row.get("away_team_name"),
        "statKey": row.get("stat_key"), "period": row.get("period"), "scope": row.get("scope"), "direction": row.get("direction"),
        "lineValue": row.get("line_value"), "selectedOdds": selected_odds,
        "predictedWinProbability": row.get("predicted_win_probability"), "expectedRoiUnits": row.get("expected_roi_units"),
        "modelId": row.get("model_id"), "modelStatus": row.get("model_status"), "policyId": row.get("selection_policy_id"),
        "policyStatus": row.get("selection_policy_status"), "snapshotKey": row.get("snapshot_key"), "offerKey": row.get("offer_key"),
        "oddsSnapshotTime": service._iso(row.get("odds_snapshot_time")), "predictionCreatedAt": service._iso(row.get("prediction_created_at")),
        "matchStartTime": service._iso(row.get("match_start_time")), "validForForwardEvaluation": row.get("valid_for_forward_evaluation"),
        "invalidForModel": bool(row.get("invalid_for_model")),
    }


def read_match_detail(database: Any, match_key: str) -> dict[str, Any] | None:
    payload = service.read_match_detail(database, match_key)
    if payload is None:
        return None
    fixture = database[FIXTURES_CANONICAL].find_one({"match_key": match_key}, projection={"_id": 0}) or {}
    selections = service._find_rows(database, FORWARD_BETS, {"match_key": match_key}, sort=[("prediction_created_at", 1)])
    result_rows = service._find_rows(database, FORWARD_RESULTS, {"match_key": match_key}, sort=[("refreshed_at", 1)])
    return {
        **payload,
        "forwardSelections": [_selection_row(row, fixture) for row in selections],
        "forwardResults": [service._result_read_model(row, fixture) for row in result_rows],
    }
