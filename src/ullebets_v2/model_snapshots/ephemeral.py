from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ullebets_v2.enrichment.replay import build_match_enrichment_documents, build_teamstats_source_rows
from ullebets_v2.odds.naming import normalize_team_name
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


def build_ephemeral_match_enrichment_documents(
    *,
    teamstats_dir: Path,
    support_docs: dict[str, Any],
    targets: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    source_rows = build_teamstats_source_rows(teamstats_dir)
    selected_source_rows = _filter_source_rows_for_targets(source_rows, targets)
    return build_match_enrichment_documents(
        source_rows=selected_source_rows,
        support_docs=support_docs,
    )


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
) -> InMemoryReadDatabase:
    docs = build_ephemeral_match_enrichment_documents(
        teamstats_dir=teamstats_dir,
        support_docs=support_docs,
        targets=targets,
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
            "teamprofiles_v2": InMemoryReadCollection(profile_docs),
            "match_results_canonical": InMemoryReadCollection(docs["match_results"]),
            "raw_match_statistics": InMemoryReadCollection(docs["raw_match_statistics"]),
            "fixtures_canonical": InMemoryReadCollection(docs["fixtures_canonical"]),
            "raw_incidents": InMemoryReadCollection(docs["raw_incidents"]),
            "raw_shotmaps": InMemoryReadCollection(docs["raw_shotmaps"]),
        }
    )
