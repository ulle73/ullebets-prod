from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json

from ullebets_v1.registry.stats import get_stat_definition
from ullebets_v2.fixtures.replay import build_support_lookup, canonical_json_hash, parse_iso_datetime


STAT_KEY_ALIASES = {
    "totalShotsOnGoal": "totalShots",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def infer_source_role(filename: str) -> str | None:
    lowered = filename.lower()
    if lowered.endswith("_home_match_stats.json"):
        return "home"
    if lowered.endswith("_away_match_stats.json"):
        return "away"
    return None


def build_teamstats_source_rows(source_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(source_dir.glob("*.json")):
        payload = load_json(path)
        full = payload.get("full") if isinstance(payload.get("full"), list) else payload.get("matches")
        if not isinstance(full, list):
            continue
        rows.append(
            {
                "source_file": path.name,
                "source_path": str(path),
                "source_role": infer_source_role(path.name),
                "matches": full,
            }
        )
    return rows


def normalize_stat_key(stat_key: str | None) -> str | None:
    if not stat_key:
        return None
    return STAT_KEY_ALIASES.get(stat_key, stat_key)


def supports_total_scope(stat_key: str) -> bool:
    definition = get_stat_definition(stat_key)
    return bool(definition and definition.settlement_supported)


def _build_match_key(match: dict[str, Any]) -> tuple[str, str | None]:
    source_match_id = match.get("matchId") or match.get("id") or match.get("eventId")
    if source_match_id is not None:
        return f"sofascore:{source_match_id}", str(source_match_id)
    fallback = "|".join(
        [
            str(match.get("date") or ""),
            str(match.get("homeTeamId") or match.get("homeTeamName") or ""),
            str(match.get("awayTeamId") or match.get("awayTeamName") or ""),
            str(match.get("timestamp") or ""),
        ]
    )
    return f"match:{fallback}", None


def _resolve_match_context(match: dict[str, Any], support_lookup) -> dict[str, Any]:
    home_team = support_lookup.teams_by_id.get(str(match.get("homeTeamId"))) if match.get("homeTeamId") is not None else None
    away_team = support_lookup.teams_by_id.get(str(match.get("awayTeamId"))) if match.get("awayTeamId") is not None else None
    home_team_key = home_team["team_key"] if home_team else f"unknown:{match.get('homeTeamId')}"
    away_team_key = away_team["team_key"] if away_team else f"unknown:{match.get('awayTeamId')}"
    if home_team and away_team and home_team.get("league_key") == away_team.get("league_key"):
        league_key = home_team["league_key"]
        mapping_confidence = "exact_support_ids"
    elif home_team or away_team:
        league_key = (home_team or away_team)["league_key"]
        mapping_confidence = "partial_support_ids"
    else:
        league_key = "unknown-league"
        mapping_confidence = "unmatched"
    return {
        "league_key": league_key,
        "home_team_key": home_team_key,
        "away_team_key": away_team_key,
        "mapping_confidence": mapping_confidence,
    }


def _raw_doc_key(source_file: str, match_key: str, artifact_type: str) -> str:
    return canonical_json_hash(
        {
            "source_file": source_file,
            "match_key": match_key,
            "artifact_type": artifact_type,
        }
    )


def _get_raw_source_meta(match: dict[str, Any], artifact_field: str) -> dict[str, Any]:
    raw_sources = match.get("_rawSources")
    if not isinstance(raw_sources, dict):
        return {}
    artifact_meta = raw_sources.get(artifact_field)
    return artifact_meta if isinstance(artifact_meta, dict) else {}


def _build_raw_artifact_doc(
    *,
    match: dict[str, Any],
    source_file: str,
    source_role: str | None,
    match_key: str,
    source_match_id: str | None,
    source_date: str,
    fetched_at: datetime,
    artifact_field: str,
    artifact_type: str,
    payload: Any,
) -> dict[str, Any]:
    meta = _get_raw_source_meta(match, artifact_field)
    payload_hash = str(meta.get("payload_hash") or canonical_json_hash(payload))
    doc = {
        "raw_key": str(meta.get("raw_key") or _raw_doc_key(source_file, match_key, artifact_type)),
        "match_key": match_key,
        "source_match_id": source_match_id,
        "source_date": source_date,
        "source_file": source_file,
        "source_role": source_role,
        "fetched_at": meta.get("fetched_at") or fetched_at,
        "payload_hash": payload_hash,
        "payload": payload,
    }
    optional_fields = (
        "source_name",
        "source_provider",
        "source_url",
        "source_endpoint",
        "api_key_slot",
        "http_status",
        "source_status",
    )
    for field in optional_fields:
        if field in meta:
            doc[field] = meta[field]
    return doc


def _iter_stat_rows(match: dict[str, Any], match_key: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    statistics = match.get("matchDetails", {}).get("statistics", [])
    if not isinstance(statistics, list):
        return rows

    for period_entry in statistics:
        period = period_entry.get("period")
        groups = period_entry.get("groups", [])
        if not isinstance(groups, list):
            continue
        for group in groups:
            items = group.get("statisticsItems", [])
            if not isinstance(items, list):
                continue
            for item in items:
                canonical_stat_key = normalize_stat_key(item.get("key"))
                if canonical_stat_key is None:
                    continue
                home_value = item.get("homeValue")
                away_value = item.get("awayValue")
                if isinstance(home_value, (int, float)):
                    rows.append(
                        {
                            "match_key": match_key,
                            "source_match_id": context["source_match_id"],
                            "source_date": context["source_date"],
                            "league_key": context["league_key"],
                            "home_team_key": context["home_team_key"],
                            "away_team_key": context["away_team_key"],
                            "stat_key": canonical_stat_key,
                            "period": period,
                            "scope": "home",
                            "actual_value": home_value,
                            "mapping_confidence": context["mapping_confidence"],
                        }
                    )
                if isinstance(away_value, (int, float)):
                    rows.append(
                        {
                            "match_key": match_key,
                            "source_match_id": context["source_match_id"],
                            "source_date": context["source_date"],
                            "league_key": context["league_key"],
                            "home_team_key": context["home_team_key"],
                            "away_team_key": context["away_team_key"],
                            "stat_key": canonical_stat_key,
                            "period": period,
                            "scope": "away",
                            "actual_value": away_value,
                            "mapping_confidence": context["mapping_confidence"],
                        }
                    )
                if (
                    supports_total_scope(canonical_stat_key)
                    and isinstance(home_value, (int, float))
                    and isinstance(away_value, (int, float))
                ):
                    rows.append(
                        {
                            "match_key": match_key,
                            "source_match_id": context["source_match_id"],
                            "source_date": context["source_date"],
                            "league_key": context["league_key"],
                            "home_team_key": context["home_team_key"],
                            "away_team_key": context["away_team_key"],
                            "stat_key": canonical_stat_key,
                            "period": period,
                            "scope": "all",
                            "actual_value": home_value + away_value,
                            "mapping_confidence": context["mapping_confidence"],
                        }
                    )
    return rows


def build_match_enrichment_documents(
    *,
    source_rows: list[dict[str, Any]],
    support_docs: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    support_lookup = build_support_lookup(support_docs)
    raw_match_statistics: list[dict[str, Any]] = []
    raw_incidents: list[dict[str, Any]] = []
    raw_shotmaps: list[dict[str, Any]] = []
    raw_results: list[dict[str, Any]] = []
    match_results_by_key: dict[str, dict[str, Any]] = {}
    match_stats_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    for source_row in source_rows:
        source_file = source_row["source_file"]
        for match in source_row["matches"]:
            match_key, source_match_id = _build_match_key(match)
            source_date = str(match.get("date") or "")
            fetched_at = parse_iso_datetime(match.get("savedAt"))
            context = _resolve_match_context(match, support_lookup)
            result_doc = {
                "match_key": match_key,
                "source_match_id": source_match_id,
                "source_date": source_date,
                "fetched_at": fetched_at,
                "league_key": context["league_key"],
                "home_team_key": context["home_team_key"],
                "away_team_key": context["away_team_key"],
                "home_team_name": match.get("homeTeamName"),
                "away_team_name": match.get("awayTeamName"),
                "home_score": match.get("homeScore"),
                "away_score": match.get("awayScore"),
                "mapping_confidence": context["mapping_confidence"],
                "has_match_details": isinstance(match.get("matchDetails"), dict),
                "has_incidents": match.get("incidents") is not None,
                "has_shotmap": match.get("shotmap") is not None,
            }
            existing_result = match_results_by_key.get(match_key)
            if existing_result is None or fetched_at >= existing_result["fetched_at"]:
                match_results_by_key[match_key] = result_doc

            if isinstance(match.get("matchDetails"), dict):
                raw_match_statistics.append(
                    _build_raw_artifact_doc(
                        match=match,
                        source_file=source_file,
                        source_role=source_row["source_role"],
                        match_key=match_key,
                        source_match_id=source_match_id,
                        source_date=source_date,
                        fetched_at=fetched_at,
                        artifact_field="matchDetails",
                        artifact_type="match_statistics",
                        payload=match["matchDetails"],
                    )
                )
                for stat_row in _iter_stat_rows(
                    match,
                    match_key,
                    {
                        **context,
                        "source_match_id": source_match_id,
                        "source_date": source_date,
                    },
                ):
                    stat_key = (
                        stat_row["match_key"],
                        stat_row["stat_key"],
                        stat_row["period"],
                        stat_row["scope"],
                    )
                    match_stats_by_key[stat_key] = stat_row

            if match.get("incidents") is not None:
                raw_incidents.append(
                    _build_raw_artifact_doc(
                        match=match,
                        source_file=source_file,
                        source_role=source_row["source_role"],
                        match_key=match_key,
                        source_match_id=source_match_id,
                        source_date=source_date,
                        fetched_at=fetched_at,
                        artifact_field="incidents",
                        artifact_type="incidents",
                        payload=match["incidents"],
                    )
                )

            if match.get("shotmap") is not None:
                raw_shotmaps.append(
                    _build_raw_artifact_doc(
                        match=match,
                        source_file=source_file,
                        source_role=source_row["source_role"],
                        match_key=match_key,
                        source_match_id=source_match_id,
                        source_date=source_date,
                        fetched_at=fetched_at,
                        artifact_field="shotmap",
                        artifact_type="shotmap",
                        payload=match["shotmap"],
                    )
                )

            raw_results.append(
                _build_raw_artifact_doc(
                    match=match,
                    source_file=source_file,
                    source_role=source_row["source_role"],
                    match_key=match_key,
                    source_match_id=source_match_id,
                    source_date=source_date,
                    fetched_at=fetched_at,
                    artifact_field="result",
                    artifact_type="result",
                    payload={
                        "homeScore": match.get("homeScore"),
                        "awayScore": match.get("awayScore"),
                    },
                )
            )

    match_results = list(match_results_by_key.values())
    match_results.sort(key=lambda row: (row["source_date"], row["match_key"]))
    match_stats_canonical = list(match_stats_by_key.values())
    match_stats_canonical.sort(
        key=lambda row: (row["match_key"], row["stat_key"], row["period"], row["scope"])
    )

    return {
        "raw_match_statistics": raw_match_statistics,
        "raw_incidents": raw_incidents,
        "raw_shotmaps": raw_shotmaps,
        "raw_results": raw_results,
        "match_results": match_results,
        "match_stats_canonical": match_stats_canonical,
    }
