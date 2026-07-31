from __future__ import annotations

from typing import Any
import unicodedata


OPTA_RANKINGS_URL = "https://dataviz.theanalyst.com/opta-power-rankings/pr-reference.json"

_RAW_NAME_OVERRIDES = {
    "1. FC Heidenheim": "Heidenheim",
    "1. FC Köln": "Köln",
    "1. FC Union Berlin": "Union Berlin",
    "1. FSV Mainz 05": "Mainz 05",
    "Angers": "Angers SCO",
    "AS Monaco": "Monaco",
    "Atlético Madrid": "Atlético de Madrid",
    "Auckland FC": "Auckland",
    "Bayer 04 Leverkusen": "Bayer Leverkusen",
    "Bournemouth": "AFC Bournemouth",
    "Celta Vigo": "Celta de Vigo",
    "Deportivo Alavés": "Alavés",
    "FC Augsburg": "Augsburg",
    "FC Bayern München": "Bayern München",
    "FC St. Pauli": "St. Pauli",
    "Girona FC": "Girona",
    "Levante UD": "Levante UD",
    "Macarthur FC": "Macarthur FC",
    "Olympique de Marseille": "Olympique de Marseille",
    "RC Lens": "Lens",
    "RC Strasbourg": "Strasbourg",
    "Red Bull Bragantino": "Red Bull Bragantino",
    "SC Freiburg": "SC Freiburg",
    "Stade Brestois": "Brest",
    "Stade Rennais": "Rennes",
    "SV Werder Bremen": "SV Werder Bremen",
    "Sydney FC": "Sydney FC",
    "TSG Hoffenheim": "Hoffenheim",
    "VfB Stuttgart": "Stuttgart",
    "VfL Wolfsburg": "Wolfsburg",
    "Wolverhampton": "Wolverhampton Wanderers",
}


def normalize_name(value: Any) -> str:
    normalized = unicodedata.normalize("NFD", str(value or "").strip().lower())
    asciiish = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return " ".join(asciiish.split())


NAME_OVERRIDES = {
    normalize_name(key): value
    for key, value in _RAW_NAME_OVERRIDES.items()
}


def extract_opta_rows(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [row for row in payload["data"] if isinstance(row, dict)]
    raise ValueError("Opta payload must be a list or a dict with a 'data' list.")


def _coerce_int(value: Any, fallback: Any = None) -> int | None:
    try:
        coerced = int(float(value))
    except (TypeError, ValueError):
        return fallback if isinstance(fallback, int) else None
    return coerced


def _coerce_float(value: Any, fallback: Any = None) -> float | None:
    try:
        coerced = float(value)
    except (TypeError, ValueError):
        return fallback if isinstance(fallback, int | float) else None
    return coerced


def _index_opta_rows(opta_rows: list[dict[str, Any]]) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[int, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for row in extract_opta_rows(opta_rows):
        opta_id = _coerce_int(row.get("optaId"))
        if opta_id is not None and opta_id not in by_id:
            by_id[opta_id] = row
        for candidate in (
            row.get("contestantName"),
            row.get("contestantShortName"),
            row.get("contestantClubName"),
        ):
            key = normalize_name(candidate)
            if key and key not in by_name:
                by_name[key] = row
    return by_id, by_name


def merge_opta_fields(
    teams: list[dict[str, Any]],
    opta_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = extract_opta_rows(opta_rows)
    opta_by_id, opta_by_name = _index_opta_rows(rows)

    merged: list[dict[str, Any]] = []
    for team in teams:
        updated = dict(team)
        local_opta_id = _coerce_int(updated.get("opta_id"))
        matched_row = opta_by_id.get(local_opta_id) if local_opta_id is not None else None
        match_method: str | None = "opta_id" if matched_row is not None else None

        if matched_row is None:
            team_name = updated.get("team_name")
            team_name_key = normalize_name(team_name)
            override_name = NAME_OVERRIDES.get(team_name_key)
            lookup_key = normalize_name(override_name or team_name)
            matched_row = opta_by_name.get(lookup_key)
            if matched_row is not None:
                match_method = "name_override" if override_name else "name_exact"

        if matched_row is not None:
            updated["opta_id"] = _coerce_int(matched_row.get("optaId"), fallback=local_opta_id)
            updated["opta_rank"] = _coerce_int(matched_row.get("rank"), fallback=updated.get("opta_rank"))
            updated["opta_rating"] = _coerce_float(
                matched_row.get("currentRating"),
                fallback=updated.get("opta_rating"),
            )
            updated["opta_source_status"] = "matched"
            updated["opta_match_method"] = match_method
        else:
            updated["opta_source_status"] = "not_loaded" if not rows else "unmatched"
            updated["opta_match_method"] = None

        merged.append(updated)
    return merged
