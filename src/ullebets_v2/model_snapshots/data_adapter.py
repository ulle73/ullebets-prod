from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.model_compat.teamprofiles import project_teamprofile_to_legacy_shape
from ullebets_v2.odds.naming import normalize_team_name
from ullebets_v2.storage.collections import TEAMPROFILES


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _coerce_target_date(value: Any, *, start_time: datetime | None = None) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(start_time, datetime):
        return start_time.date().isoformat()
    return None


def build_legacy_leagues_data(support_docs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    teams_by_league_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for team in support_docs.get("teams", []):
        league_key = str(team.get("league_key") or "")
        if not league_key:
            continue
        teams_by_league_key[league_key].append(
            {
                "id": team.get("team_id"),
                "name": team.get("team_name"),
                "slug": team.get("team_slug"),
                "imageUrl": team.get("team_image_url"),
                "optaId": team.get("opta_id"),
                "optaRank": team.get("opta_rank"),
                "optaRating": team.get("opta_rating"),
            }
        )

    payload: dict[str, dict[str, Any]] = {}
    for league in support_docs.get("leagues", []):
        league_key = str(league.get("league_key") or "")
        league_name = str(league.get("league_name") or league_key)
        if not league_name:
            continue
        payload[league_name] = {
            "leagueId": league.get("league_id"),
            "categoryId": league.get("category_id"),
            "seasonId": league.get("season_id"),
            "groupId": league.get("group_id"),
            "slug": league.get("league_slug"),
            "country": league.get("country"),
            "teams": teams_by_league_key.get(league_key, []),
        }
    return payload


def build_legacy_league_rankings(support_docs: dict[str, Any]) -> list[dict[str, Any]]:
    rankings: list[dict[str, Any]] = []
    for row in support_docs.get("rankings", []):
        rankings.append(
            {
                "league": {"name": row.get("league_name")} if row.get("league_name") else row.get("league_key"),
                "leagueAvgOptaRating": row.get("league_avg_opta_rating"),
                "ranking": deepcopy(row.get("ranking") or {}),
            }
        )
    return rankings


class V2ModelDataAdapter:
    def __init__(self, read_database: Any, support_docs: dict[str, Any]) -> None:
        self.read_database = read_database
        self.support_docs = support_docs
        self._profiles_cache: dict[str, list[dict[str, Any]]] = {}
        self._result_rows_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._fixtures_cache: dict[str, dict[str, Any]] = {}
        self._raw_stats_cache: dict[str, dict[str, Any]] = {}
        self._team_lookup_by_name = {
            normalize_team_name(row.get("team_name")): row
            for row in support_docs.get("teams", [])
            if row.get("team_name")
        }
        self._leagues_data = build_legacy_leagues_data(support_docs)
        self._league_rankings = build_legacy_league_rankings(support_docs)

    def build_fetched_data(self, match_info: dict[str, Any]) -> dict[str, Any]:
        match_context = self._resolve_match_context(match_info)
        return {
            "homeBundle": self._build_team_bundle(
                team_key=match_context["home_team_key"],
                target_source_date=match_context["target_source_date"],
            ),
            "awayBundle": self._build_team_bundle(
                team_key=match_context["away_team_key"],
                target_source_date=match_context["target_source_date"],
            ),
            "homeMatchesRaw": self._load_team_role_matches(
                team_key=match_context["home_team_key"],
                role="home",
                target_match_key=match_context["match_key"],
                target_start_time=match_context["start_time"],
                target_source_date=match_context["target_source_date"],
            ),
            "awayMatchesRaw": self._load_team_role_matches(
                team_key=match_context["away_team_key"],
                role="away",
                target_match_key=match_context["match_key"],
                target_start_time=match_context["start_time"],
                target_source_date=match_context["target_source_date"],
            ),
            "leaguesData": deepcopy(self._leagues_data),
            "leagueRankings": deepcopy(self._league_rankings),
        }

    def _collection_find(self, collection_name: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            return list(self.read_database[collection_name].find(query or {}, projection={"_id": 0}))
        except KeyError:
            return []

    def _resolve_team_key(self, team_name: Any, explicit_team_key: Any) -> str | None:
        if isinstance(explicit_team_key, str) and explicit_team_key.strip():
            return explicit_team_key
        normalized_name = normalize_team_name(team_name)
        support_team = self._team_lookup_by_name.get(normalized_name)
        if support_team is None:
            return None
        team_key = support_team.get("team_key")
        return str(team_key) if team_key else None

    def _resolve_match_context(self, match_info: dict[str, Any]) -> dict[str, Any]:
        start_time = _parse_datetime(match_info.get("startTime"))
        target_source_date = _coerce_target_date(match_info.get("sourceDate"), start_time=start_time)
        return {
            "match_key": str(match_info.get("matchKey") or ""),
            "start_time": start_time,
            "target_source_date": target_source_date,
            "home_team_key": self._resolve_team_key(match_info.get("homeTeam"), match_info.get("homeTeamKey")),
            "away_team_key": self._resolve_team_key(match_info.get("awayTeam"), match_info.get("awayTeamKey")),
        }

    def _load_profile_docs(self, team_key: str) -> list[dict[str, Any]]:
        if team_key in self._profiles_cache:
            return self._profiles_cache[team_key]
        rows = [
            row
            for row in self._collection_find(TEAMPROFILES, {"team_key": team_key})
            if str(row.get("team_key") or "") == team_key
        ]
        self._profiles_cache[team_key] = rows
        return rows

    def _select_profile_doc(
        self,
        *,
        team_key: str | None,
        match_type: str,
        target_source_date: str | None,
    ) -> dict[str, Any] | None:
        if not team_key:
            return None
        docs = [
            row
            for row in self._load_profile_docs(team_key)
            if str(row.get("match_type") or "") == match_type
        ]
        if not docs:
            return None

        exact_doc: dict[str, Any] | None = None
        historical_docs: list[dict[str, Any]] = []
        current_docs: list[dict[str, Any]] = []
        for row in docs:
            profile_date = str(row.get("profile_date") or "")
            if profile_date == "current":
                current_docs.append(row)
            elif target_source_date and profile_date == target_source_date:
                exact_doc = row
            elif target_source_date and profile_date and profile_date < target_source_date:
                historical_docs.append(row)
            elif not target_source_date:
                historical_docs.append(row)

        if exact_doc is not None:
            return exact_doc
        if historical_docs:
            return sorted(
                historical_docs,
                key=lambda row: (
                    str(row.get("profile_date") or ""),
                    _parse_datetime(row.get("generated_at")) or datetime.min.replace(tzinfo=UTC),
                ),
            )[-1]
        if current_docs:
            return sorted(
                current_docs,
                key=lambda row: _parse_datetime(row.get("generated_at")) or datetime.min.replace(tzinfo=UTC),
            )[-1]
        return None

    def _build_team_bundle(self, *, team_key: str | None, target_source_date: str | None) -> dict[str, Any]:
        home_profile = self._select_profile_doc(
            team_key=team_key,
            match_type="home",
            target_source_date=target_source_date,
        )
        away_profile = self._select_profile_doc(
            team_key=team_key,
            match_type="away",
            target_source_date=target_source_date,
        )
        return {
            "home": project_teamprofile_to_legacy_shape(home_profile) if home_profile is not None else None,
            "away": project_teamprofile_to_legacy_shape(away_profile) if away_profile is not None else None,
        }

    def _load_result_rows(self, *, team_key: str, role: str) -> list[dict[str, Any]]:
        cache_key = (team_key, role)
        if cache_key in self._result_rows_cache:
            return self._result_rows_cache[cache_key]
        role_key = f"{role}_team_key"
        rows = [
            row
            for row in self._collection_find("match_results_canonical", {role_key: team_key})
            if str(row.get(role_key) or "") == team_key
        ]
        self._result_rows_cache[cache_key] = rows
        return rows

    def _load_fixtures(self, match_keys: list[str]) -> dict[str, dict[str, Any]]:
        missing = [key for key in match_keys if key not in self._fixtures_cache]
        if missing:
            rows = self._collection_find("fixtures_canonical", {"match_key": {"$in": missing}})
            for row in rows:
                match_key = str(row.get("match_key") or "")
                if match_key and match_key not in self._fixtures_cache:
                    self._fixtures_cache[match_key] = row
            for match_key in missing:
                self._fixtures_cache.setdefault(match_key, {})
        return {match_key: self._fixtures_cache.get(match_key, {}) for match_key in match_keys}

    def _load_raw_stats_payloads(self, match_keys: list[str]) -> dict[str, dict[str, Any]]:
        missing = [key for key in match_keys if key not in self._raw_stats_cache]
        if missing:
            rows = self._collection_find("raw_match_statistics", {"match_key": {"$in": missing}})
            for row in rows:
                match_key = str(row.get("match_key") or "")
                payload = row.get("payload")
                if match_key and match_key not in self._raw_stats_cache and isinstance(payload, dict):
                    self._raw_stats_cache[match_key] = payload
            for match_key in missing:
                self._raw_stats_cache.setdefault(match_key, {})
        return {
            match_key: payload
            for match_key, payload in (
                (match_key, self._raw_stats_cache.get(match_key, {})) for match_key in match_keys
            )
            if isinstance(payload, dict) and payload
        }

    def _is_historical_match(
        self,
        *,
        match_start_time: datetime | None,
        source_date: str | None,
        target_start_time: datetime | None,
        target_source_date: str | None,
    ) -> bool:
        if target_start_time is not None and match_start_time is not None:
            return match_start_time < target_start_time
        if target_source_date and source_date:
            return source_date < target_source_date
        if target_start_time is not None and source_date:
            return source_date < target_start_time.date().isoformat()
        return True

    def _build_legacy_match_row(
        self,
        *,
        result_row: dict[str, Any],
        fixture_row: dict[str, Any],
        statistics_payload: dict[str, Any],
    ) -> dict[str, Any]:
        start_time = _parse_datetime(fixture_row.get("start_time")) or _parse_datetime(result_row.get("start_time"))
        timestamp = int(start_time.timestamp()) if isinstance(start_time, datetime) else None
        source_match_id = result_row.get("source_match_id")
        source_date = result_row.get("source_date")
        return {
            "matchId": source_match_id,
            "id": source_match_id,
            "date": source_date,
            "matchDate": source_date,
            "timestamp": timestamp,
            "startTimestamp": timestamp,
            "start": start_time.isoformat().replace("+00:00", "Z") if isinstance(start_time, datetime) else None,
            "homeTeamName": result_row.get("home_team_name"),
            "awayTeamName": result_row.get("away_team_name"),
            "homeTeam": result_row.get("home_team_name"),
            "awayTeam": result_row.get("away_team_name"),
            "homeScore": result_row.get("home_score"),
            "awayScore": result_row.get("away_score"),
            "matchDetails": deepcopy(statistics_payload),
            "statistics": deepcopy(statistics_payload.get("statistics", [])),
        }

    def _load_team_role_matches(
        self,
        *,
        team_key: str | None,
        role: str,
        target_match_key: str | None,
        target_start_time: datetime | None,
        target_source_date: str | None,
    ) -> list[dict[str, Any]]:
        if not team_key:
            return []

        result_rows = self._load_result_rows(team_key=team_key, role=role)
        if not result_rows:
            return []

        match_keys = [
            str(row.get("match_key") or "")
            for row in result_rows
            if row.get("match_key") is not None
        ]
        fixtures_by_key = self._load_fixtures(match_keys)
        raw_stats_by_key = self._load_raw_stats_payloads(match_keys)

        matches: list[dict[str, Any]] = []
        for result_row in result_rows:
            match_key = str(result_row.get("match_key") or "")
            if not match_key:
                continue
            if target_match_key and match_key == target_match_key:
                continue
            statistics_payload = raw_stats_by_key.get(match_key)
            if not isinstance(statistics_payload, dict) or not statistics_payload:
                continue
            fixture_row = fixtures_by_key.get(match_key, {})
            match_start_time = _parse_datetime(fixture_row.get("start_time")) or _parse_datetime(result_row.get("start_time"))
            source_date = str(result_row.get("source_date") or "") or None
            if not self._is_historical_match(
                match_start_time=match_start_time,
                source_date=source_date,
                target_start_time=target_start_time,
                target_source_date=target_source_date,
            ):
                continue
            matches.append(
                self._build_legacy_match_row(
                    result_row=result_row,
                    fixture_row=fixture_row,
                    statistics_payload=statistics_payload,
                )
            )

        matches.sort(
            key=lambda row: (
                int(row.get("timestamp") or 0),
                str(row.get("matchId") or ""),
            ),
            reverse=True,
        )
        return matches
