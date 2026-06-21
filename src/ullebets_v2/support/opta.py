from __future__ import annotations

from typing import Any


def merge_opta_fields(
    teams: list[dict[str, Any]],
    opta_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    opta_by_id = {
        str(row.get("optaId")): row
        for row in opta_rows
        if row.get("optaId") is not None
    }

    merged: list[dict[str, Any]] = []
    for team in teams:
        updated = dict(team)
        opta_id = updated.get("opta_id")
        row = opta_by_id.get(str(opta_id)) if opta_id is not None else None
        if row:
            updated["opta_rank"] = row.get("rank")
            updated["opta_rating"] = row.get("currentRating")
        merged.append(updated)
    return merged
