from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator


def build_match_index_row(match: dict, source_name: str, source_kind: str) -> dict:
    return {
        "source_name": source_name,
        "source_kind": source_kind,
        "match_id": str(match.get("matchId")) if match.get("matchId") is not None else None,
        "match_date": match.get("date"),
        "kickoff_ts": match.get("timestamp"),
        "saved_at": match.get("savedAt"),
        "home_team_name": match.get("homeTeamName"),
        "away_team_name": match.get("awayTeamName"),
        "home_team_id": str(match.get("homeTeamId")) if match.get("homeTeamId") is not None else None,
        "away_team_id": str(match.get("awayTeamId")) if match.get("awayTeamId") is not None else None,
        "has_statistics": bool((match.get("matchDetails") or {}).get("statistics")),
        "has_incidents": bool(match.get("incidents")),
        "has_shotmap": bool(match.get("shotmap")),
        "odds_keys": json.dumps(
            sorted((match.get("odds") or {}).keys()) if isinstance(match.get("odds"), dict) else []
        ),
    }


def iter_teamstats_files(teamstats_dir: Path) -> Iterator[Path]:
    for path in sorted(teamstats_dir.glob("*.json")):
        if path.is_file():
            yield path


def load_teamstats_document(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_teamstats_match_index(teamstats_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for path in iter_teamstats_files(teamstats_dir):
        document = load_teamstats_document(path)
        for match in document.get("full") or []:
            if isinstance(match, dict):
                rows.append(build_match_index_row(match=match, source_name=path.name, source_kind="local_file"))
    return rows


def build_teamstats_match_index_from_documents(documents: list[dict], source_name: str) -> list[dict]:
    rows: list[dict] = []
    for document in documents:
        for match in document.get("full") or []:
            if isinstance(match, dict):
                rows.append(build_match_index_row(match=match, source_name=source_name, source_kind="mongo"))
    return rows
