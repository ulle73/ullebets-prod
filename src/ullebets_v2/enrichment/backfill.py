from __future__ import annotations

from datetime import datetime
from typing import Any

from ullebets_v2.enrichment.replay import iter_stat_rows_from_statistics_payload


def _date_query(dates: list[str] | None) -> dict[str, Any]:
    if not dates:
        return {}
    return {"source_date": {"$in": dates}}


def load_enrichment_backfill_inputs(
    database: Any,
    *,
    dates: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    query = _date_query(dates)
    projection = {"_id": 0}
    return {
        "fixtures": list(database["fixtures_canonical"].find(query, projection=projection)),
        "raw_match_statistics": list(database["raw_match_statistics"].find(query, projection=projection)),
        "raw_incidents": list(database["raw_incidents"].find(query, projection=projection)),
        "raw_shotmaps": list(database["raw_shotmaps"].find(query, projection=projection)),
        "raw_results": list(database["raw_results"].find(query, projection=projection)),
    }


def _fixture_lookup(fixtures: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_match_key: dict[str, dict[str, Any]] = {}
    by_source_match_id: dict[str, dict[str, Any]] = {}
    for fixture in fixtures:
        match_key = str(fixture.get("match_key") or "")
        if match_key:
            by_match_key[match_key] = fixture
        source_match_id = fixture.get("source_match_id")
        if source_match_id is not None:
            by_source_match_id[str(source_match_id)] = fixture
    return by_match_key, by_source_match_id


def _resolve_fixture_context(
    row: dict[str, Any],
    *,
    fixtures_by_match_key: dict[str, dict[str, Any]],
    fixtures_by_source_match_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    match_key = str(row.get("match_key") or "")
    fixture = fixtures_by_match_key.get(match_key)
    if fixture is None and row.get("source_match_id") is not None:
        fixture = fixtures_by_source_match_id.get(str(row["source_match_id"]))
    return fixture or {}


def _resolved_match_context(row: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "league_key": fixture.get("league_key") or "unknown-league",
        "home_team_key": fixture.get("home_team_key") or "unknown:home",
        "away_team_key": fixture.get("away_team_key") or "unknown:away",
        "mapping_confidence": fixture.get("mapping_confidence") or "unmatched",
        "source_match_id": row.get("source_match_id"),
        "source_date": str(row.get("source_date") or fixture.get("source_date") or ""),
    }


def _result_sort_key(row: dict[str, Any]) -> tuple[datetime | str, str, str]:
    return (
        row.get("fetched_at") or "",
        str(row.get("source_file") or ""),
        str(row.get("source_role") or ""),
    )


def build_canonical_match_enrichment_from_raw(
    *,
    fixtures: list[dict[str, Any]],
    raw_match_statistics: list[dict[str, Any]],
    raw_incidents: list[dict[str, Any]],
    raw_shotmaps: list[dict[str, Any]],
    raw_results: list[dict[str, Any]],
) -> dict[str, Any]:
    fixtures_by_match_key, fixtures_by_source_match_id = _fixture_lookup(fixtures)
    has_statistics = {str(row["match_key"]) for row in raw_match_statistics}
    has_incidents = {str(row["match_key"]) for row in raw_incidents}
    has_shotmaps = {str(row["match_key"]) for row in raw_shotmaps}

    match_results_by_key: dict[str, dict[str, Any]] = {}
    raw_result_keys: dict[str, tuple[datetime | str, str, str]] = {}
    missing_fixture_context_match_keys: set[str] = set()

    for row in raw_results:
        match_key = str(row["match_key"])
        fixture = _resolve_fixture_context(
            row,
            fixtures_by_match_key=fixtures_by_match_key,
            fixtures_by_source_match_id=fixtures_by_source_match_id,
        )
        if not fixture:
            missing_fixture_context_match_keys.add(match_key)
        context = _resolved_match_context(row, fixture)
        candidate = {
            "match_key": match_key,
            "source_match_id": row.get("source_match_id"),
            "source_date": context["source_date"],
            "fetched_at": row.get("fetched_at"),
            "league_key": context["league_key"],
            "home_team_key": context["home_team_key"],
            "away_team_key": context["away_team_key"],
            "home_team_name": fixture.get("home_team_name"),
            "away_team_name": fixture.get("away_team_name"),
            "home_score": (row.get("payload") or {}).get("homeScore"),
            "away_score": (row.get("payload") or {}).get("awayScore"),
            "mapping_confidence": context["mapping_confidence"],
            "has_match_details": match_key in has_statistics,
            "has_incidents": match_key in has_incidents,
            "has_shotmap": match_key in has_shotmaps,
        }
        candidate_key = _result_sort_key(row)
        existing_key = raw_result_keys.get(match_key)
        if existing_key is None or candidate_key >= existing_key:
            raw_result_keys[match_key] = candidate_key
            match_results_by_key[match_key] = candidate

    match_stats_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    stat_sort_keys: dict[tuple[str, str, str, str], tuple[datetime | str, str, str]] = {}
    for row in raw_match_statistics:
        match_key = str(row["match_key"])
        fixture = _resolve_fixture_context(
            row,
            fixtures_by_match_key=fixtures_by_match_key,
            fixtures_by_source_match_id=fixtures_by_source_match_id,
        )
        if not fixture:
            missing_fixture_context_match_keys.add(match_key)
        context = _resolved_match_context(row, fixture)
        stat_rows = iter_stat_rows_from_statistics_payload(
            statistics_payload=row.get("payload"),
            match_key=match_key,
            context=context,
        )
        sort_key = _result_sort_key(row)
        for stat_row in stat_rows:
            stat_key = (
                stat_row["match_key"],
                stat_row["stat_key"],
                stat_row["period"],
                stat_row["scope"],
            )
            existing_key = stat_sort_keys.get(stat_key)
            if existing_key is None or sort_key >= existing_key:
                stat_sort_keys[stat_key] = sort_key
                match_stats_by_key[stat_key] = stat_row

    match_results = list(match_results_by_key.values())
    match_results.sort(key=lambda row: (row["source_date"], row["match_key"]))
    match_stats_canonical = list(match_stats_by_key.values())
    match_stats_canonical.sort(
        key=lambda row: (row["match_key"], row["stat_key"], row["period"], row["scope"])
    )
    expected_matches = fixtures if fixtures else match_results

    return {
        "expected_matches": expected_matches,
        "match_results": match_results,
        "match_stats_canonical": match_stats_canonical,
        "missing_fixture_context_matches": sorted(missing_fixture_context_match_keys),
    }
