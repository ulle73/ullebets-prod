from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from ullebets_v2.forward_exposures import (
    canonicalize_forward_bet_docs,
    forward_selection_family,
)
from ullebets_v2.matchups.service import build_matchups_score_docs
from ullebets_v2.storage.collections import (
    AUDIT_REPORTS,
    EV_MODEL_SCORES,
    FIXTURES_CANONICAL,
    FORWARD_BETS,
    FORWARD_RESULTS,
    HEALTH_REPORTS,
    JOB_RUNS,
    MARKET_OFFERS,
    MARKET_SNAPSHOTS,
    MATCH_RESULTS_CANONICAL,
    MATCH_STATS_CANONICAL,
    MATCHUPS_LEAGUE_AVG,
    MATCHUPS_SCORE,
    SUPPORT_LEAGUES,
    SUPPORT_RANKINGS,
    SUPPORT_TEAMS,
    TEAMPROFILES,
)

PRODUCT_TIMEZONE = "Europe/Stockholm"
PRODUCT_TZ = ZoneInfo(PRODUCT_TIMEZONE)
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 100

SENSITIVE_KEY_PARTS = (
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "connection_string",
    "mongodb_uri",
)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _iso(item)
            for key, item in value.items()
            if key != "_id" and not _is_sensitive_key(str(key))
        }
    if isinstance(value, (list, tuple)):
        return [_iso(item) for item in value]
    return value


def _find_rows(
    database: Any,
    collection_name: str,
    query: dict[str, Any],
    *,
    projection: dict[str, int] | None = None,
    sort: list[tuple[str, int]] | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    cursor = database[collection_name].find(query, projection=projection or {"_id": 0})
    if sort:
        cursor = cursor.sort(sort)
    if offset:
        cursor = cursor.skip(offset)
    if limit is not None:
        cursor = cursor.limit(limit)
    return list(cursor)


def _page_values(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(int(limit), MAX_PAGE_LIMIT)), max(0, int(offset))


def _product_date(now: datetime | None = None) -> str:
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(PRODUCT_TZ).date().isoformat()


def _as_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_upcoming_fixture(row: dict[str, Any], now: datetime) -> bool:
    start_time = _as_utc(row.get("start_time"))
    return start_time is not None and start_time > now


def _normalize_match_state(status: Any, result: dict[str, Any] | None) -> str:
    normalized = str(status or "").strip().lower().replace("_", "").replace("-", "")
    if normalized in {"notstarted", "scheduled", "prematch"}:
        return "upcoming"
    if normalized in {"live", "inprogress", "started", "firsthalf", "secondhalf", "halftime"}:
        return "live"
    if normalized in {"postponed", "delayed"}:
        return "postponed"
    if normalized in {"cancelled", "canceled", "abandoned"}:
        return "cancelled"
    if normalized in {"finished", "ended", "closed", "fulltime"}:
        return "finished"
    if result and result.get("home_score") is not None and result.get("away_score") is not None:
        return "finished"
    return "unknown"


def _latest_results(database: Any, match_keys: list[str]) -> dict[str, dict[str, Any]]:
    if not match_keys:
        return {}
    rows = _find_rows(
        database,
        MATCH_RESULTS_CANONICAL,
        {"match_key": {"$in": sorted(set(match_keys))}},
        sort=[("fetched_at", 1)],
    )
    return {str(row.get("match_key")): row for row in rows if row.get("match_key")}


def _match_summary(row: dict[str, Any], result: dict[str, Any] | None = None) -> dict[str, Any]:
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
        "state": _normalize_match_state(row.get("status_type"), result),
        "homeScore": result.get("home_score") if result else None,
        "awayScore": result.get("away_score") if result else None,
        "resultFetchedAt": _iso(result.get("fetched_at")) if result else None,
    }


def _fixture_lookup(database: Any, match_keys: list[str]) -> dict[str, dict[str, Any]]:
    if not match_keys:
        return {}
    rows = _find_rows(
        database,
        FIXTURES_CANONICAL,
        {"match_key": {"$in": sorted(set(match_keys))}},
    )
    return {str(row.get("match_key")): row for row in rows if row.get("match_key")}


def read_matches(database: Any, *, match_keys: list[str]) -> dict[str, Any]:
    requested = list(dict.fromkeys(str(value) for value in match_keys if str(value).strip()))
    fixtures = _fixture_lookup(database, requested)
    results = _latest_results(database, requested)
    matches = [
        _match_summary(fixtures[key], results.get(key))
        for key in requested
        if key in fixtures
    ]
    return {"matches": matches}


def _matchup_summary(row: dict[str, Any], fixture: dict[str, Any] | None = None) -> dict[str, Any]:
    forecast = row.get("forecast") if isinstance(row.get("forecast"), dict) else {}
    return {
        "entryKey": str(row.get("entry_key") or ""),
        "snapshotDate": row.get("snapshot_date"),
        "matchKey": str(row.get("match_key") or ""),
        "leagueKey": row.get("league_key") or (fixture or {}).get("league_key"),
        "leagueName": row.get("league_name") or (fixture or {}).get("league_name"),
        "homeTeamKey": (fixture or {}).get("home_team_key"),
        "awayTeamKey": (fixture or {}).get("away_team_key"),
        "homeTeamName": row.get("home_team_name") or (fixture or {}).get("home_team_name"),
        "awayTeamName": row.get("away_team_name") or (fixture or {}).get("away_team_name"),
        "statKey": row.get("stat_key"),
        "statLabel": row.get("stat_label"),
        "period": row.get("period"),
        "periodLabel": row.get("period_label"),
        "scope": row.get("scope"),
        "condition": str(row.get("condition") or "").upper(),
        "score": row.get("score"),
        "rankPosition": row.get("rank_position"),
        "isTop50": bool(row.get("is_top_50")),
        "marketBias": _iso(row.get("market_bias")),
        "leagueBaseline": forecast.get("leagueBaseline"),
    }


def _profile_order_key(row: dict[str, Any]) -> tuple[str, str]:
    generated = _iso(row.get("generated_at"))
    return str(row.get("profile_date") or ""), str(generated or "")


def _current_profile_for_team(
    database: Any,
    *,
    team_key: str,
    match_type: str,
    now: datetime,
) -> dict[str, Any] | None:
    rows = _find_rows(database, TEAMPROFILES, {"team_key": team_key, "match_type": match_type})
    if not rows:
        return None
    current_rows = [row for row in rows if str(row.get("profile_date") or "") == "current"]
    if current_rows:
        return max(current_rows, key=_profile_order_key)
    today = now.astimezone(UTC).date().isoformat() if now.tzinfo else now.date().isoformat()
    dated_rows = [
        row
        for row in rows
        if str(row.get("profile_date") or "") != "current"
        and str(row.get("profile_date") or "") <= today
    ]
    return max(dated_rows, key=_profile_order_key) if dated_rows else None


def _profiles_for_upcoming_matchups(
    database: Any,
    fixtures: list[dict[str, Any]],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    requested: set[tuple[str, str]] = set()
    for fixture in fixtures:
        home_key = str(fixture.get("home_team_key") or "")
        away_key = str(fixture.get("away_team_key") or "")
        if home_key:
            requested.add((home_key, "home"))
        if away_key:
            requested.add((away_key, "away"))
    profiles: list[dict[str, Any]] = []
    for team_key, match_type in sorted(requested):
        profile = _current_profile_for_team(database, team_key=team_key, match_type=match_type, now=now)
        if profile is not None:
            profiles.append(profile)
    return profiles


def _load_matchups(
    database: Any,
    fixtures: list[dict[str, Any]],
    source_date: str,
    *,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], str]:
    match_keys = [str(row.get("match_key")) for row in fixtures if row.get("match_key")]
    if not match_keys:
        return [], "missing"
    persisted = _find_rows(
        database,
        MATCHUPS_SCORE,
        {"snapshot_date": source_date, "match_key": {"$in": match_keys}},
    )
    if persisted:
        return persisted, "persisted"
    captured_at = now or utc_now()
    upcoming_fixtures = [row for row in fixtures if _is_upcoming_fixture(row, captured_at)]
    if not upcoming_fixtures:
        return [], "missing"
    profiles = _profiles_for_upcoming_matchups(database, upcoming_fixtures, now=captured_at)
    if not profiles:
        return [], "missing"
    computed, _ = build_matchups_score_docs(
        target_matches=upcoming_fixtures,
        teamprofile_docs=profiles,
        snapshot_date=source_date,
    )
    return computed, "computed_read_only" if computed else "missing"


def _ranked_matchups(matchup_rows: list[dict[str, Any]], *, limit_per_condition: int) -> list[dict[str, Any]]:
    rows = list(matchup_rows)
    rows.sort(
        key=lambda row: (
            str(row.get("condition") or ""),
            int(row.get("rank_position") or 10**9),
            -float(row.get("score") or 0),
        )
    )
    selected: list[dict[str, Any]] = []
    for condition in ("over", "under"):
        selected.extend(
            [row for row in rows if str(row.get("condition") or "").lower() == condition][
                :limit_per_condition
            ]
        )
    return selected


def read_dashboard(
    database: Any,
    *,
    source_date: str | None = None,
    limit_per_condition: int = 20,
    now: datetime | None = None,
) -> dict[str, Any]:
    captured_at = now or utc_now()
    selected_date = source_date or _product_date(captured_at)
    fixtures = _find_rows(
        database,
        FIXTURES_CANONICAL,
        {"source_date": selected_date},
        sort=[("start_time", 1)],
    )
    match_keys = [str(row.get("match_key")) for row in fixtures if row.get("match_key")]
    results = _latest_results(database, match_keys)
    matchup_rows, matchup_source = _load_matchups(database, fixtures, selected_date, now=captured_at)
    selected_matchups = _ranked_matchups(matchup_rows, limit_per_condition=limit_per_condition)
    fixture_by_key = {str(row.get("match_key")): row for row in fixtures if row.get("match_key")}
    return {
        "selectedDate": selected_date,
        "timezone": PRODUCT_TIMEZONE,
        "generatedAt": _iso(captured_at),
        "matches": [_match_summary(row, results.get(str(row.get("match_key")))) for row in fixtures],
        "matchups": [
            _matchup_summary(row, fixture_by_key.get(str(row.get("match_key"))))
            for row in selected_matchups
        ],
        "matchupSource": matchup_source,
    }


def _profile_as_of(
    database: Any,
    team_key: str,
    match_type: str,
    source_date: str | None,
) -> dict[str, Any] | None:
    rows = _find_rows(database, TEAMPROFILES, {"team_key": team_key, "match_type": match_type})
    if not rows:
        return None
    if source_date:
        dated_rows = [
            row
            for row in rows
            if str(row.get("profile_date") or "") != "current"
            and str(row.get("profile_date") or "") <= source_date
        ]
        return max(dated_rows, key=_profile_order_key) if dated_rows else None
    current_rows = [row for row in rows if str(row.get("profile_date") or "") == "current"]
    if current_rows:
        return max(current_rows, key=_profile_order_key)
    return max(rows, key=_profile_order_key)


def _stat_rows(home_profile: dict[str, Any] | None, away_profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not home_profile or not away_profile:
        return []
    home_statistics = home_profile.get("statistics", {})
    away_statistics = away_profile.get("statistics", {})
    home_for = home_statistics.get("for", {})
    home_against = home_statistics.get("against", {})
    away_for = away_statistics.get("for", {})
    away_against = away_statistics.get("against", {})
    stat_keys = sorted(set(home_for) | set(home_against) | set(away_for) | set(away_against))
    rows: list[dict[str, Any]] = []
    for stat_key in stat_keys:
        for period in ("ALL", "1ST", "2ND"):
            home_for_node = home_for.get(stat_key, {}).get(period, {})
            home_against_node = home_against.get(stat_key, {}).get(period, {})
            away_for_node = away_for.get(stat_key, {}).get(period, {})
            away_against_node = away_against.get(stat_key, {}).get(period, {})
            home_league_for = home_statistics.get("leagueAverage", {}).get("for", {}).get(stat_key, {}).get(period, {})
            home_league_against = home_statistics.get("leagueAverage", {}).get("against", {}).get(stat_key, {}).get(period, {})
            away_league_for = away_statistics.get("leagueAverage", {}).get("for", {}).get(stat_key, {}).get(period, {})
            away_league_against = away_statistics.get("leagueAverage", {}).get("against", {}).get(stat_key, {}).get(period, {})
            if not any(
                node.get("value") is not None
                for node in (
                    home_for_node,
                    home_against_node,
                    away_for_node,
                    away_against_node,
                    home_league_for,
                    home_league_against,
                    away_league_for,
                    away_league_against,
                )
            ):
                continue
            rows.append(
                {
                    "statKey": stat_key,
                    "period": period,
                    "homeValue": home_for_node.get("value"),
                    "awayValue": away_for_node.get("value"),
                    "homeRank": home_for_node.get("rank"),
                    "awayRank": away_for_node.get("rank"),
                    "homeLeagueAverage": home_league_for.get("value"),
                    "awayLeagueAverage": away_league_for.get("value"),
                    "homeForValue": home_for_node.get("value"),
                    "homeAgainstValue": home_against_node.get("value"),
                    "awayForValue": away_for_node.get("value"),
                    "awayAgainstValue": away_against_node.get("value"),
                    "homeForRank": home_for_node.get("rank"),
                    "homeAgainstRank": home_against_node.get("rank"),
                    "awayForRank": away_for_node.get("rank"),
                    "awayAgainstRank": away_against_node.get("rank"),
                    "homeForLeagueAverage": home_league_for.get("value"),
                    "homeAgainstLeagueAverage": home_league_against.get("value"),
                    "awayForLeagueAverage": away_league_for.get("value"),
                    "awayAgainstLeagueAverage": away_league_against.get("value"),
                }
            )
    return rows


def _result_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "homeScore": row.get("home_score"),
        "awayScore": row.get("away_score"),
        "fetchedAt": _iso(row.get("fetched_at")),
        "mappingConfidence": row.get("mapping_confidence"),
        "hasMatchDetails": row.get("has_match_details"),
        "hasIncidents": row.get("has_incidents"),
        "hasShotmap": row.get("has_shotmap"),
    }


def _actual_stat_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "statKey": row.get("stat_key"),
        "period": row.get("period"),
        "scope": row.get("scope"),
        "actualValue": row.get("actual_value"),
        "mappingConfidence": row.get("mapping_confidence"),
    }


def _market_offer_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "offerKey": row.get("offer_key"),
        "eventId": row.get("event_id"),
        "statKey": row.get("stat_key"),
        "scope": row.get("scope"),
        "period": row.get("period"),
        "line": row.get("line"),
        "overOdds": row.get("over_odds"),
        "underOdds": row.get("under_odds"),
        "sourceProvider": row.get("source_provider"),
        "payloadKind": row.get("payload_kind"),
        "updatedAt": _iso(row.get("updated_at")),
    }


def read_match_detail(database: Any, match_key: str) -> dict[str, Any] | None:
    fixture = database[FIXTURES_CANONICAL].find_one({"match_key": match_key}, projection={"_id": 0})
    if fixture is None:
        return None
    source_date = str(fixture.get("source_date") or "")
    date_fixtures = (
        _find_rows(database, FIXTURES_CANONICAL, {"source_date": source_date}, sort=[("start_time", 1)])
        if source_date
        else [fixture]
    )
    date_matchups, matchup_source = _load_matchups(database, date_fixtures, source_date) if source_date else ([], "missing")
    matchup_rows = [row for row in date_matchups if str(row.get("match_key") or "") == match_key]
    league_avg_rows = (
        _find_rows(database, MATCHUPS_LEAGUE_AVG, {"match_key": match_key, "snapshot_date": source_date})
        if source_date
        else []
    )
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

    result_rows = _find_rows(database, MATCH_RESULTS_CANONICAL, {"match_key": match_key}, sort=[("fetched_at", -1)], limit=1)
    result = result_rows[0] if result_rows else None
    actual_rows = _find_rows(
        database,
        MATCH_STATS_CANONICAL,
        {"match_key": match_key},
        sort=[("stat_key", 1), ("period", 1), ("scope", 1)],
    )
    market_rows = _find_rows(
        database,
        MARKET_OFFERS,
        {"match_key": match_key},
        sort=[("updated_at", -1), ("stat_key", 1), ("period", 1), ("scope", 1), ("line", 1)],
    )

    now = utc_now()
    is_upcoming = _is_upcoming_fixture(fixture, now)
    home_key = str(fixture.get("home_team_key") or "")
    away_key = str(fixture.get("away_team_key") or "")
    if is_upcoming:
        home_profile = _current_profile_for_team(database, team_key=home_key, match_type="home", now=now) if home_key else None
        away_profile = _current_profile_for_team(database, team_key=away_key, match_type="away", now=now) if away_key else None
    else:
        home_profile = _profile_as_of(database, home_key, "home", source_date) if home_key else None
        away_profile = _profile_as_of(database, away_key, "away", source_date) if away_key else None

    team_rows = _find_rows(
        database,
        SUPPORT_TEAMS,
        {"team_key": {"$in": [key for key in (home_key, away_key) if key]}},
        projection={"_id": 0, "team_key": 1, "team_image_url": 1},
    )
    team_images = {
        str(row.get("team_key")): row.get("team_image_url")
        for row in team_rows
        if row.get("team_key")
    }
    match = _match_summary(fixture, result)
    match["homeTeamImageUrl"] = team_images.get(home_key)
    match["awayTeamImageUrl"] = team_images.get(away_key)

    return {
        "match": match,
        "matchups": [
            _matchup_summary(row, fixture)
            for row in sorted(matchup_rows, key=lambda item: int(item.get("rank_position") or 10**9))
        ],
        "matchupSource": matchup_source,
        "leagueAverageMatchups": [_iso(row) for row in league_avg_rows],
        "checkpoints": list(checkpoints.values()),
        "teamStats": _stat_rows(home_profile, away_profile),
        "result": _result_summary(result),
        "actualStats": [_actual_stat_summary(row) for row in actual_rows],
        "marketOffers": [_market_offer_summary(row) for row in market_rows],
        "teamProfiles": {
            "home": _profile_summary(home_profile),
            "away": _profile_summary(away_profile),
        },
    }


def _league_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "leagueKey": row.get("league_key"),
        "leagueName": row.get("league_name"),
        "leagueId": row.get("league_id"),
        "country": row.get("country"),
        "seasonId": row.get("season_id"),
        "categoryId": row.get("category_id"),
        "groupId": row.get("group_id"),
        "capturedAt": _iso(row.get("captured_at")),
    }


def _team_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "teamKey": row.get("team_key"),
        "leagueKey": row.get("league_key"),
        "teamId": row.get("team_id"),
        "teamName": row.get("team_name"),
        "teamImageUrl": row.get("team_image_url"),
        "optaId": row.get("opta_id"),
        "optaRank": row.get("opta_rank"),
        "optaRating": row.get("opta_rating"),
        "capturedAt": _iso(row.get("captured_at")),
    }


def _ranking_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "rankingType": row.get("ranking_type"),
        "leagueAverageOptaRating": row.get("league_avg_opta_rating"),
        "data": _iso(row.get("ranking")),
        "capturedAt": _iso(row.get("captured_at")),
    }


def read_league(database: Any, league_key: str, *, match_limit: int = 100) -> dict[str, Any] | None:
    league = database[SUPPORT_LEAGUES].find_one({"league_key": league_key}, projection={"_id": 0})
    if league is None:
        return None
    teams = _find_rows(database, SUPPORT_TEAMS, {"league_key": league_key}, sort=[("team_name", 1)])
    ranking_rows = _find_rows(database, SUPPORT_RANKINGS, {"league_key": league_key}, sort=[("captured_at", -1)], limit=1)
    fixtures = _find_rows(database, FIXTURES_CANONICAL, {"league_key": league_key}, sort=[("start_time", -1)], limit=match_limit)
    match_keys = [str(row.get("match_key")) for row in fixtures if row.get("match_key")]
    results = _latest_results(database, match_keys)
    return {
        "league": _league_summary(league),
        "teams": [_team_summary(row) for row in teams],
        "ranking": _ranking_summary(ranking_rows[0] if ranking_rows else None),
        "matches": [_match_summary(row, results.get(str(row.get("match_key")))) for row in fixtures],
    }


def _profile_game_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "matchId": row.get("matchId"),
        "matchKey": row.get("match_key"),
        "date": row.get("date"),
        "timestamp": row.get("timestamp"),
        "opponentName": row.get("opp"),
        "opponentTeamKey": row.get("opponent_team_key"),
    }


def _profile_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    games = row.get("games") if isinstance(row.get("games"), list) else []
    return {
        "profileKey": row.get("profile_key"),
        "profileDate": row.get("profile_date"),
        "generatedAt": _iso(row.get("generated_at")),
        "matchType": row.get("match_type"),
        "leagueTeamCount": meta.get("leagueTeamCount"),
        "savedAt": _iso(meta.get("savedAt")),
        "games": [_profile_game_summary(game) for game in games if isinstance(game, dict)],
        "sampleSize": len(games),
        "statistics": _iso(row.get("statistics") or {}),
        "specials": _iso(row.get("specials") or {}),
        "behaviour": _iso(row.get("behaviour")),
    }


def read_team(database: Any, team_key: str, *, match_limit: int = 40) -> dict[str, Any] | None:
    team = database[SUPPORT_TEAMS].find_one({"team_key": team_key}, projection={"_id": 0})
    profile_rows = _find_rows(database, TEAMPROFILES, {"team_key": team_key})
    if team is None and not profile_rows:
        return None

    current_by_type: dict[str, dict[str, Any]] = {}
    for match_type in ("home", "away"):
        candidates = [row for row in profile_rows if str(row.get("match_type") or "") == match_type]
        current = [row for row in candidates if str(row.get("profile_date") or "") == "current"]
        if current:
            current_by_type[match_type] = max(current, key=_profile_order_key)
        elif candidates:
            current_by_type[match_type] = max(candidates, key=_profile_order_key)

    fallback_profile = current_by_type.get("home") or current_by_type.get("away") or (profile_rows[0] if profile_rows else {})
    meta = fallback_profile.get("meta") if isinstance(fallback_profile.get("meta"), dict) else {}
    league_key = str((team or {}).get("league_key") or fallback_profile.get("league_key") or meta.get("leagueKey") or "")
    league = database[SUPPORT_LEAGUES].find_one({"league_key": league_key}, projection={"_id": 0}) if league_key else None

    if team is None:
        team = {
            "team_key": team_key,
            "league_key": league_key or None,
            "team_name": meta.get("lagnamn"),
            "team_id": meta.get("lagId"),
        }

    fixtures = _find_rows(
        database,
        FIXTURES_CANONICAL,
        {"$or": [{"home_team_key": team_key}, {"away_team_key": team_key}]},
        sort=[("start_time", -1)],
        limit=match_limit,
    )
    match_keys = [str(row.get("match_key")) for row in fixtures if row.get("match_key")]
    results = _latest_results(database, match_keys)
    return {
        "team": _team_summary(team),
        "league": _league_summary(league) if league else None,
        "contexts": {
            "home": _profile_summary(current_by_type.get("home")),
            "away": _profile_summary(current_by_type.get("away")),
        },
        "matches": [_match_summary(row, results.get(str(row.get("match_key")))) for row in fixtures],
    }


def _filter_query(
    *,
    stat_key: str | None = None,
    period: str | None = None,
    scope: str | None = None,
    direction: str | None = None,
    model_id: str | None = None,
    policy_id: str | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    for field, value in (
        ("stat_key", stat_key),
        ("period", period),
        ("scope", scope),
        ("direction", direction),
        ("model_id", model_id),
        ("selection_policy_id", policy_id),
    ):
        if value:
            query[field] = value
    return query


def _league_match_keys(database: Any, league_key: str) -> list[str]:
    rows = _find_rows(database, FIXTURES_CANONICAL, {"league_key": league_key})
    return [str(row.get("match_key")) for row in rows if row.get("match_key")]


def _with_league_filter(database: Any, query: dict[str, Any], league_key: str | None) -> dict[str, Any]:
    if not league_key:
        return query
    keys = _league_match_keys(database, league_key)
    return {**query, "match_key": {"$in": keys}}


def _forward_selection_key(row: dict[str, Any]) -> str | None:
    for field_name in ("prediction_key", "selection_key", "tracking_key"):
        value = row.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _forward_result_lookup(database: Any, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    keys = sorted({key for row in rows if (key := _forward_selection_key(row)) is not None})
    if not keys:
        return {}
    result_rows = _find_rows(database, FORWARD_RESULTS, {"result_loop_key": {"$in": keys}})
    lookup: dict[str, dict[str, Any]] = {}
    for result in result_rows:
        for field_name in ("result_loop_key", "prediction_key", "selection_key", "tracking_key"):
            value = result.get(field_name)
            if isinstance(value, str) and value.strip():
                lookup[value] = result
    return lookup


def read_auto(
    database: Any,
    *,
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = 0,
    stat_key: str | None = None,
    period: str | None = None,
    scope: str | None = None,
    direction: str | None = None,
    model_id: str | None = None,
    policy_id: str | None = None,
    league_key: str | None = None,
) -> dict[str, Any]:
    page_limit, page_offset = _page_values(limit, offset)
    query = _with_league_filter(
        database,
        _filter_query(
            stat_key=stat_key,
            period=period,
            scope=scope,
            direction=direction,
            model_id=model_id,
            policy_id=policy_id,
        ),
        league_key,
    )
    raw_rows = _find_rows(database, FORWARD_BETS, query)
    canonical_rows, exposure_audit = canonicalize_forward_bet_docs(raw_rows)
    canonical_rows.sort(
        key=lambda row: (
            str(_iso(row.get("match_start_time")) or ""),
            forward_selection_family(row) == "v6",
            str(row.get("prediction_key") or ""),
        ),
        reverse=True,
    )
    summary = {
        "total": len(canonical_rows),
        "valid": sum(
            row.get("valid_for_forward_evaluation") is True and not row.get("invalid_for_model")
            for row in canonical_rows
        ),
        "excluded": 0,
    }
    summary["excluded"] = summary["total"] - summary["valid"]
    rows = canonical_rows[page_offset:page_offset + page_limit]
    fixtures = _fixture_lookup(database, [str(row.get("match_key")) for row in rows if row.get("match_key")])
    results = _forward_result_lookup(database, rows)
    selections = []
    for row in rows:
        fixture = fixtures.get(str(row.get("match_key") or ""), {})
        selection_key = _forward_selection_key(row)
        result = results.get(selection_key or "", {})
        selected_odds = row.get("selected_odds") if row.get("selected_odds") is not None else row.get("saved_odds")
        selections.append(
            {
                "selectionKey": selection_key,
                "predictionKey": row.get("prediction_key"),
                "matchKey": row.get("match_key"),
                "leagueKey": fixture.get("league_key"),
                "leagueName": fixture.get("league_name") or row.get("league_name"),
                "homeTeamKey": fixture.get("home_team_key"),
                "awayTeamKey": fixture.get("away_team_key"),
                "homeTeamName": fixture.get("home_team_name") or row.get("home_team_name"),
                "awayTeamName": fixture.get("away_team_name") or row.get("away_team_name"),
                "statKey": row.get("stat_key"),
                "period": row.get("period"),
                "scope": row.get("scope"),
                "direction": row.get("direction"),
                "lineValue": row.get("line_value"),
                "selectedOdds": selected_odds,
                "predictedWinProbability": row.get("predicted_win_probability"),
                "expectedRoiUnits": row.get("expected_roi_units"),
                "modelId": row.get("model_id"),
                "modelStatus": row.get("model_status"),
                "policyId": row.get("selection_policy_id"),
                "policyStatus": row.get("selection_policy_status"),
                "snapshotKey": row.get("snapshot_key"),
                "offerKey": row.get("offer_key"),
                "oddsSnapshotTime": _iso(row.get("odds_snapshot_time")),
                "predictionCreatedAt": _iso(row.get("prediction_created_at")),
                "matchStartTime": _iso(row.get("match_start_time")),
                "validForForwardEvaluation": row.get("valid_for_forward_evaluation"),
                "invalidForModel": bool(row.get("invalid_for_model")),
                "selectionFamily": forward_selection_family(row),
                "resultStatus": result.get("result_loop_status"),
                "settlementStatus": result.get("settlement_status"),
                "settlementResult": result.get("settlement_result"),
                "actualValue": result.get("actual_value"),
                "pnlUnits": result.get("pnl_units"),
                "stakeUnits": result.get("stake_units"),
                "validForPerformance": result.get("valid_for_performance"),
            }
        )
    return {
        "count": exposure_audit["canonical_count"],
        "rawCount": exposure_audit["raw_count"],
        "excludedComboLegCount": exposure_audit["excluded_combo_leg_count"],
        "excludedShadowPredictionCount": exposure_audit["excluded_shadow_prediction_count"],
        "collapsedDuplicateCount": exposure_audit["collapsed_duplicate_count"],
        "summary": summary,
        "page": {
            "limit": page_limit,
            "offset": page_offset,
            "hasMore": page_offset + len(rows) < summary["total"],
        },
        "selections": selections,
    }


def _result_read_model(row: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "resultLoopKey": row.get("result_loop_key"),
        "predictionKey": row.get("prediction_key"),
        "selectionKey": row.get("selection_key"),
        "trackingKey": row.get("tracking_key"),
        "matchKey": row.get("match_key"),
        "leagueKey": fixture.get("league_key"),
        "leagueName": fixture.get("league_name") or row.get("league_name"),
        "homeTeamKey": fixture.get("home_team_key"),
        "awayTeamKey": fixture.get("away_team_key"),
        "homeTeamName": fixture.get("home_team_name") or row.get("home_team_name"),
        "awayTeamName": fixture.get("away_team_name") or row.get("away_team_name"),
        "statKey": row.get("stat_key"),
        "period": row.get("period"),
        "scope": row.get("scope"),
        "direction": row.get("direction"),
        "lineValue": row.get("line_value"),
        "savedOdds": row.get("saved_odds"),
        "savedAt": _iso(row.get("saved_at")),
        "oddsSnapshotTime": _iso(row.get("odds_snapshot_time")),
        "predictionCreatedAt": _iso(row.get("prediction_created_at")),
        "matchStartTime": _iso(row.get("match_start_time")),
        "settlementStatus": row.get("settlement_status"),
        "settlementResult": row.get("settlement_result"),
        "actualValue": row.get("actual_value"),
        "homeValue": row.get("home_value"),
        "awayValue": row.get("away_value"),
        "win": row.get("win"),
        "roiUnits": row.get("roi_units"),
        "pnlUnits": row.get("pnl_units"),
        "stakeUnits": row.get("stake_units"),
        "actualSource": row.get("actual_source"),
        "actualSourceStatus": row.get("actual_source_status"),
        "settledAt": _iso(row.get("settled_at")),
        "validForPerformance": row.get("valid_for_performance"),
        "invalidForModel": bool(row.get("invalid_for_model")),
        "resultLoopStatus": row.get("result_loop_status"),
        "statusReason": row.get("status_reason"),
        "openingOdds": row.get("opening_odds"),
        "latestObservedOdds": row.get("latest_observed_odds"),
        "closingOdds": row.get("closing_odds"),
        "closingQuality": row.get("closing_quality"),
        "closingSnapshotLabel": row.get("closing_snapshot_label"),
        "closingSnapshotTime": _iso(row.get("closing_snapshot_time")),
        "officialClv": bool(row.get("official_clv")),
        "clvBasis": row.get("clv_basis"),
        "clvStatus": row.get("clv_status"),
        "clvPct": row.get("clv_pct"),
        "beatClosingLine": row.get("beat_closing_line"),
        "prematchObservationCount": row.get("prematch_observation_count"),
        "refreshedAt": _iso(row.get("refreshed_at")),
    }


def read_results(
    database: Any,
    *,
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = 0,
    status: str | None = None,
    stat_key: str | None = None,
    period: str | None = None,
    scope: str | None = None,
    direction: str | None = None,
    league_key: str | None = None,
) -> dict[str, Any]:
    page_limit, page_offset = _page_values(limit, offset)
    query = _filter_query(stat_key=stat_key, period=period, scope=scope, direction=direction)
    if status:
        query["result_loop_status"] = status
    query = _with_league_filter(database, query, league_key)
    raw_rows = _find_rows(database, FORWARD_RESULTS, query)
    canonical_rows, exposure_audit = canonicalize_forward_bet_docs(raw_rows)
    canonical_rows.sort(key=lambda row: str(_iso(row.get("match_start_time")) or ""), reverse=True)
    valid_settled = [
        row
        for row in canonical_rows
        if row.get("settlement_status") == "settled" and row.get("valid_for_performance") is True
    ]
    rows = canonical_rows[page_offset:page_offset + page_limit]
    fixtures = _fixture_lookup(database, [str(row.get("match_key")) for row in rows if row.get("match_key")])
    return {
        "summary": {
            "rows": len(canonical_rows),
            "settled": len(valid_settled),
            "wins": sum(1 for row in valid_settled if row.get("settlement_result") == "win"),
            "losses": sum(1 for row in valid_settled if row.get("settlement_result") == "loss"),
            "pushes": sum(1 for row in valid_settled if row.get("settlement_result") == "push"),
            "excluded": sum(1 for row in canonical_rows if row.get("valid_for_performance") is False),
        },
        "rawCount": exposure_audit["raw_count"],
        "excludedComboLegCount": exposure_audit["excluded_combo_leg_count"],
        "excludedShadowPredictionCount": exposure_audit["excluded_shadow_prediction_count"],
        "collapsedDuplicateCount": exposure_audit["collapsed_duplicate_count"],
        "page": {
            "limit": page_limit,
            "offset": page_offset,
            "hasMore": page_offset + len(rows) < len(canonical_rows),
        },
        "rows": [_result_read_model(row, fixtures.get(str(row.get("match_key") or ""), {})) for row in rows],
    }


def read_model(database: Any) -> dict[str, Any]:
    scores = database[EV_MODEL_SCORES]
    forward = database[FORWARD_BETS]
    model_ids = sorted(str(value) for value in scores.distinct("model_id") if value)
    policy_ids = sorted(str(value) for value in forward.distinct("selection_policy_id") if value)
    canonical_forward, _ = canonicalize_forward_bet_docs(_find_rows(database, FORWARD_BETS, {}))
    canonical_results, _ = canonicalize_forward_bet_docs(_find_rows(database, FORWARD_RESULTS, {}))
    return {
        "modelIds": model_ids,
        "policyIds": policy_ids,
        "scoreCount": scores.count_documents({}),
        "forwardSelectionCount": len(canonical_forward),
        "settledForwardCount": sum(
            1
            for row in canonical_results
            if row.get("settlement_status") == "settled" and row.get("valid_for_performance") is True
        ),
        "officialClvCount": sum(
            1
            for row in canonical_results
            if row.get("clv_status") == "tracked" and row.get("official_clv") is True
        ),
    }


def read_system_status(database: Any, *, limit: int = 30) -> dict[str, Any]:
    return {
        "jobs": [_iso(row) for row in _find_rows(database, JOB_RUNS, {}, sort=[("started_at", -1)], limit=limit)],
        "health": [_iso(row) for row in _find_rows(database, HEALTH_REPORTS, {}, sort=[("generated_at", -1)], limit=limit)],
        "audits": [_iso(row) for row in _find_rows(database, AUDIT_REPORTS, {}, sort=[("generated_at", -1)], limit=limit)],
    }
