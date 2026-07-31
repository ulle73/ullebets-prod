from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ullebets_v2.fixtures.replay import load_fixture_payload


LEGACY_MATCH_FOR_DATE_SOURCE_DIR = Path("mongodb-match-for-date")


def _iter_legacy_fixture_entries(document: dict[str, Any]) -> list[dict[str, Any]]:
    full = document.get("full")
    if isinstance(full, list):
        return [entry for entry in full if isinstance(entry, dict)]
    if isinstance(document.get("matches"), list):
        return [document]
    return []


def _parse_saved_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return datetime.min.replace(tzinfo=UTC)
    return datetime.min.replace(tzinfo=UTC)


def load_legacy_match_for_date_payload(
    *,
    legacy_match_database: Any,
    date_str: str,
) -> dict[str, Any] | None:
    best_entry: dict[str, Any] | None = None
    best_score: tuple[int, datetime] | None = None
    projection = {"_id": 0, "full": 1, "date": 1, "savedAt": 1, "matches": 1, "sources": 1, "calls": 1, "successes": 1, "failures": 1}
    for document in legacy_match_database["match-for-date"].find({}, projection=projection):
        for entry in _iter_legacy_fixture_entries(document):
            if str(entry.get("date") or "") != date_str:
                continue
            score = (
                len(entry.get("matches") or []),
                _parse_saved_at(entry.get("savedAt")),
            )
            if best_score is None or score > best_score:
                best_entry = entry
                best_score = score

    if best_entry is None:
        return None

    payload: dict[str, Any] = {
        "date": date_str,
        "savedAt": best_entry.get("savedAt"),
        "matches": list(best_entry.get("matches") or []),
    }
    for field_name in ("sources", "calls", "successes", "failures"):
        if field_name in best_entry:
            payload[field_name] = best_entry.get(field_name)
    return payload


def load_old_payloads_by_date(
    *,
    source_dir: Path,
    dates: list[str],
    legacy_match_database: Any | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Path]]:
    payloads: dict[str, dict[str, Any]] = {}
    source_paths_by_date: dict[str, Path] = {}
    for date_str in dates:
        source_path = source_dir / f"fixtures-{date_str}.json"
        if source_path.exists():
            payloads[date_str] = load_fixture_payload(source_path)
            source_paths_by_date[date_str] = source_path
            continue
        if legacy_match_database is None:
            continue
        payload = load_legacy_match_for_date_payload(
            legacy_match_database=legacy_match_database,
            date_str=date_str,
        )
        if payload is None:
            continue
        payloads[date_str] = payload
        source_paths_by_date[date_str] = LEGACY_MATCH_FOR_DATE_SOURCE_DIR / f"fixtures-{date_str}.json"
    return payloads, source_paths_by_date


def resolve_fixture_oracle_context(
    *,
    mode: str,
    dates: list[str],
    old_repo_root: Path,
    legacy_oracle_dir: Path | None = None,
    legacy_match_database: Any | None = None,
) -> tuple[Path | None, dict[str, dict[str, Any]], dict[str, Path]]:
    if mode == "replay":
        source_dir = legacy_oracle_dir or (old_repo_root / "matches-for-date")
        payloads, source_paths_by_date = load_old_payloads_by_date(
            source_dir=source_dir,
            dates=dates,
            legacy_match_database=legacy_match_database,
        )
        return source_dir, payloads, source_paths_by_date

    if legacy_oracle_dir is None:
        return None, {}, {}

    payloads, source_paths_by_date = load_old_payloads_by_date(
        source_dir=legacy_oracle_dir,
        dates=dates,
        legacy_match_database=legacy_match_database,
    )
    return legacy_oracle_dir, payloads, source_paths_by_date
