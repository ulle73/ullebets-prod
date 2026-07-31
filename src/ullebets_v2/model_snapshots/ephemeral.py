from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ullebets_v2.enrichment.replay import (
    build_match_enrichment_documents,
    build_teamstats_source_rows,
    build_teamstats_source_rows_from_database,
)
from ullebets_v2.odds.naming import normalize_team_name
from ullebets_v2.storage.collections import (
    FIXTURES_CANONICAL,
    MATCH_RESULTS_CANONICAL,
    MATCH_STATS_CANONICAL,
    RAW_INCIDENTS,
    RAW_MATCH_STATISTICS,
    RAW_SHOTMAPS,
    TEAMPROFILES,
)
from ullebets_v2.teamprofiles.service import build_teamprofile_docs


def _target_source_date(target: dict[str, Any]) -> str | None:
    source_date = target.get("source_date")
    if isinstance(source_date, str) and source_date.strip():
        return source_date
    start_time = target.get("start_time")
    if isinstance(start_time, datetime):
        return start_time.astimezone(UTC).date().isoformat()
    if isinstance(start_time, str) and start_time.strip():
        try:
            return datetime.fromisoformat(start_time.replace("Z", "+00:00")).astimezone(UTC).date().isoformat()
        except ValueError:
            return None
    return None


def _source_row_team_name(source_file: str) -> str:
    base_name = source_file
    for suffix in ("_home_match_stats.json", "_away_match_stats.json"):
        if base_name.endswith(suffix):
            base_name = base_name[: -len(suffix)]
            break
    return normalize_team_name(base_name.replace("_", " "))


def _filter_source_rows_for_targets(
    source_rows: list[dict[str, Any]],
    targets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    target_team_names = {
        normalize_team_name(row.get(key))
        for row in targets
        for key in ("home_team_name", "away_team_name")
        if row.get(key)
    }
    if not target_team_names:
        return source_rows
    filtered = [
        row
        for row in source_rows
        if _source_row_team_name(str(row.get("source_file") or "")) in target_team_names
    ]
    return filtered or source_rows


def _candidate_source_files_for_targets(
    teamstats_dir: Path,
    targets: list[dict[str, Any]],
) -> set[str]:
    target_team_names = {
        normalize_team_name(row.get(key))
        for row in targets
        for key in ("home_team_name", "away_team_name")
        if row.get(key)
    }
    if not target_team_names or not teamstats_dir.exists():
        return set()
    matches: set[str] = set()
    for path in teamstats_dir.glob("*.json"):
        if _source_row_team_name(path.name) in target_team_names:
            matches.add(path.name)
    return matches


def _documents_cover_targets(
    documents: dict[str, list[dict[str, Any]]],
    targets: list[dict[str, Any]],
) -> bool:
    target_match_keys = {
        str(row.get("match_key") or "")
        for row in targets
        if row.get("match_key") is not None
    }
    if not target_match_keys:
        return True
    available_match_keys = {
        str(row.get("match_key") or "")
        for row in documents.get("match_results", [])
        if row.get("match_key") is not None
    }
    return target_match_keys.issubset(available_match_keys)


def _read_collection_rows(
    database: Any,
    collection_name: str,
    query: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    try:
        rows = list(database[collection_name].find(query or {}, projection={"_id": 0}))
    except KeyError:
        return []
    return [row for row in rows if isinstance(row, dict)]


def _target_team_keys(targets: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in targets:
        for key in ("home_team_key", "away_team_key"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                keys.add(value.strip())
    return keys


def _target_match_keys(targets: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in targets:
        value = row.get("match_key")
        if isinstance(value, str) and value.strip():
            keys.add(value.strip())
    return keys


def _target_profile_dates(targets: list[dict[str, Any]]) -> list[str]:
    return sorted({date_str for row in targets if (date_str := _target_source_date(row))})


def _dedupe_rows(rows: Iterable[dict[str, Any]], *, key_field: str) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row.get(key_field) or "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _build_v2_historical_profile_docs(
    *,
    match_stats_canonical: list[dict[str, Any]],
    match_results_canonical: list[dict[str, Any]],
    raw_incidents: list[dict[str, Any]],
    raw_shotmaps: list[dict[str, Any]],
    support_docs: dict[str, Any],
    targets: list[dict[str, Any]],
    generated_at: datetime | None,
) -> list[dict[str, Any]]:
    target_dates = _target_profile_dates(targets)
    if not target_dates:
        return build_teamprofile_docs(
            match_stats_canonical=match_stats_canonical,
            match_results_canonical=match_results_canonical,
            raw_incidents=raw_incidents,
            raw_shotmaps=raw_shotmaps,
            support_docs=support_docs,
            generated_at=generated_at,
        )

    profile_docs: list[dict[str, Any]] = []
    for profile_date in target_dates:
        profile_docs.extend(
            build_teamprofile_docs(
                match_stats_canonical=match_stats_canonical,
                match_results_canonical=match_results_canonical,
                raw_incidents=raw_incidents,
                raw_shotmaps=raw_shotmaps,
                support_docs=support_docs,
                profile_date=profile_date,
                generated_at=generated_at,
            )
        )
    return profile_docs


def _profile_docs_cover_target_teams(
    profile_docs: list[dict[str, Any]],
    targets: list[dict[str, Any]],
) -> bool:
    if not targets:
        return True
    available = {
        (str(row.get("team_key") or ""), str(row.get("profile_date") or ""))
        for row in profile_docs
        if row.get("team_key") is not None
    }
    for target in targets:
        profile_date = _target_source_date(target)
        if not profile_date:
            continue
        for team_key_field in ("home_team_key", "away_team_key"):
            team_key = str(target.get(team_key_field) or "")
            if team_key and (team_key, profile_date) not in available:
                return False
    return True


def build_ephemeral_match_enrichment_documents(
    *,
    teamstats_dir: Path,
    support_docs: dict[str, Any],
    targets: list[dict[str, Any]],
    legacy_teamstats_database: Any | None = None,
) -> dict[str, list[dict[str, Any]]]:
    candidate_source_files = _candidate_source_files_for_targets(teamstats_dir, targets)
    source_rows = build_teamstats_source_rows(
        teamstats_dir,
        source_files=candidate_source_files or None,
    )
    selected_source_rows = _filter_source_rows_for_targets(source_rows, targets)
    documents = build_match_enrichment_documents(
        source_rows=selected_source_rows,
        support_docs=support_docs,
    )
    if _documents_cover_targets(documents, targets) or legacy_teamstats_database is None:
        return documents

    mongo_rows = build_teamstats_source_rows_from_database(
        legacy_teamstats_database,
        source_files=candidate_source_files or None,
    )
    mongo_selected_rows = _filter_source_rows_for_targets(mongo_rows, targets)
    mongo_documents = build_match_enrichment_documents(
        source_rows=mongo_selected_rows,
        support_docs=support_docs,
    )
    if _documents_cover_targets(mongo_documents, targets):
        return mongo_documents
    return documents


class InMemoryReadCollection:
    def __init__(self, docs: Iterable[dict[str, Any]]) -> None:
        self.docs = [deepcopy(doc) for doc in docs]

    def _matches(self, doc: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
                continue
            if actual != expected:
                return False
        return True

    def _apply_projection(self, doc: dict[str, Any], projection: dict[str, Any] | None) -> dict[str, Any]:
        if not projection:
            return deepcopy(doc)
        include_keys = [key for key, value in projection.items() if key != "_id" and value]
        if include_keys:
            return {key: deepcopy(doc.get(key)) for key in include_keys if key in doc}
        if projection.get("_id") == 0 and "_id" in doc:
            payload = deepcopy(doc)
            payload.pop("_id", None)
            return payload
        return deepcopy(doc)

    def find(self, query: dict[str, Any] | None = None, projection: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        query = query or {}
        return [
            self._apply_projection(doc, projection)
            for doc in self.docs
            if self._matches(doc, query)
        ]


class InMemoryReadDatabase(dict):
    def __getitem__(self, collection_name: str) -> InMemoryReadCollection:
        return dict.__getitem__(self, collection_name)


def build_ephemeral_model_read_database(
    *,
    teamstats_dir: Path,
    support_docs: dict[str, Any],
    targets: list[dict[str, Any]],
    generated_at: datetime | None = None,
    legacy_teamstats_database: Any | None = None,
) -> InMemoryReadDatabase:
    docs = build_ephemeral_match_enrichment_documents(
        teamstats_dir=teamstats_dir,
        support_docs=support_docs,
        targets=targets,
        legacy_teamstats_database=legacy_teamstats_database,
    )
    target_dates = sorted({date_str for row in targets if (date_str := _target_source_date(row))})
    profile_docs: list[dict[str, Any]] = []
    for profile_date in target_dates:
        profile_docs.extend(
            build_teamprofile_docs(
                match_stats_canonical=docs["match_stats_canonical"],
                match_results_canonical=docs["match_results"],
                raw_incidents=docs["raw_incidents"],
                raw_shotmaps=docs["raw_shotmaps"],
                support_docs=support_docs,
                profile_date=profile_date,
                generated_at=generated_at,
            )
        )

    return InMemoryReadDatabase(
        {
            TEAMPROFILES: InMemoryReadCollection(profile_docs),
            "match_results_canonical": InMemoryReadCollection(docs["match_results"]),
            "raw_match_statistics": InMemoryReadCollection(docs["raw_match_statistics"]),
            "fixtures_canonical": InMemoryReadCollection(docs["fixtures_canonical"]),
            "raw_incidents": InMemoryReadCollection(docs["raw_incidents"]),
            "raw_shotmaps": InMemoryReadCollection(docs["raw_shotmaps"]),
        }
    )


def build_v2_historical_model_read_database(
    *,
    read_database: Any,
    support_docs: dict[str, Any],
    targets: list[dict[str, Any]],
    generated_at: datetime | None = None,
) -> InMemoryReadDatabase | None:
    team_keys = _target_team_keys(targets)
    target_match_keys = _target_match_keys(targets)
    if not team_keys:
        return None

    result_rows = _dedupe_rows(
        [
            *(
                row
                for row in _read_collection_rows(
                    read_database,
                    MATCH_RESULTS_CANONICAL,
                    {"home_team_key": {"$in": sorted(team_keys)}},
                )
                if str(row.get("home_team_key") or "") in team_keys
                or str(row.get("away_team_key") or "") in team_keys
            ),
            *(
                row
                for row in _read_collection_rows(
                    read_database,
                    MATCH_RESULTS_CANONICAL,
                    {"away_team_key": {"$in": sorted(team_keys)}},
                )
                if str(row.get("home_team_key") or "") in team_keys
                or str(row.get("away_team_key") or "") in team_keys
            ),
        ],
        key_field="match_key",
    )
    if not result_rows:
        return None

    historical_match_keys = {
        str(row.get("match_key") or "")
        for row in result_rows
        if row.get("match_key") is not None
    }
    all_match_keys = sorted(target_match_keys | historical_match_keys)
    if not all_match_keys:
        return None

    fixtures_canonical = [
        row
        for row in _read_collection_rows(
            read_database,
            FIXTURES_CANONICAL,
            {"match_key": {"$in": all_match_keys}},
        )
        if str(row.get("match_key") or "") in all_match_keys
    ]
    raw_match_statistics = [
        row
        for row in _read_collection_rows(
            read_database,
            RAW_MATCH_STATISTICS,
            {"match_key": {"$in": all_match_keys}},
        )
        if str(row.get("match_key") or "") in all_match_keys
    ]
    match_stats_canonical = [
        row
        for row in _read_collection_rows(
            read_database,
            MATCH_STATS_CANONICAL,
            {"match_key": {"$in": all_match_keys}},
        )
        if str(row.get("match_key") or "") in all_match_keys
    ]
    raw_incidents = [
        row
        for row in _read_collection_rows(
            read_database,
            RAW_INCIDENTS,
            {"match_key": {"$in": all_match_keys}},
        )
        if str(row.get("match_key") or "") in all_match_keys
    ]
    raw_shotmaps = [
        row
        for row in _read_collection_rows(
            read_database,
            RAW_SHOTMAPS,
            {"match_key": {"$in": all_match_keys}},
        )
        if str(row.get("match_key") or "") in all_match_keys
    ]
    if not match_stats_canonical or not raw_match_statistics:
        return None

    profile_docs = _build_v2_historical_profile_docs(
        match_stats_canonical=match_stats_canonical,
        match_results_canonical=result_rows,
        raw_incidents=raw_incidents,
        raw_shotmaps=raw_shotmaps,
        support_docs=support_docs,
        targets=targets,
        generated_at=generated_at,
    )
    if not profile_docs or not _profile_docs_cover_target_teams(profile_docs, targets):
        return None

    return InMemoryReadDatabase(
        {
            TEAMPROFILES: InMemoryReadCollection(profile_docs),
            MATCH_RESULTS_CANONICAL: InMemoryReadCollection(result_rows),
            FIXTURES_CANONICAL: InMemoryReadCollection(fixtures_canonical),
            RAW_MATCH_STATISTICS: InMemoryReadCollection(raw_match_statistics),
            RAW_INCIDENTS: InMemoryReadCollection(raw_incidents),
            RAW_SHOTMAPS: InMemoryReadCollection(raw_shotmaps),
            MATCH_STATS_CANONICAL: InMemoryReadCollection(match_stats_canonical),
        }
    )


def resolve_historical_model_read_database(
    *,
    read_database: Any | None,
    teamstats_dir: Path,
    support_docs: dict[str, Any],
    targets: list[dict[str, Any]],
    generated_at: datetime | None = None,
    legacy_teamstats_database: Any | None = None,
) -> tuple[Any | None, str]:
    if read_database is not None:
        v2_model_read_database = build_v2_historical_model_read_database(
            read_database=read_database,
            support_docs=support_docs,
            targets=targets,
            generated_at=generated_at,
        )
        if v2_model_read_database is not None:
            return v2_model_read_database, "v2_canonical_ephemeral"

    if teamstats_dir.exists():
        return (
            build_ephemeral_model_read_database(
                teamstats_dir=teamstats_dir,
                support_docs=support_docs,
                targets=targets,
                generated_at=generated_at,
                legacy_teamstats_database=legacy_teamstats_database,
            ),
            "legacy_teamstats_ephemeral",
        )

    return read_database, "v2_database"
