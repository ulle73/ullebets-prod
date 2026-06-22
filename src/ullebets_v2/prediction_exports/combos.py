from __future__ import annotations

from typing import Any


def build_combos(
    lines: list[dict[str, Any]],
    *,
    legs: int = 2,
    min_odds: float = 1.8,
    max_odds: float = 2.2,
    max_lines: int = 32,
    max_combos: int = 14,
) -> list[dict[str, Any]]:
    sanitized_legs = max(1, min(int(legs), 4))
    sanitized_min_odds = max(1.0, float(min_odds))
    sanitized_max_odds = max(sanitized_min_odds, float(max_odds))
    valid_lines = sorted(
        [
            {
                **line,
                "primary_ev": float(line.get("primary_ev") or 0.0),
                "selected_odds": float(line.get("selected_odds") or line.get("odds") or 0.0),
            }
            for line in lines
            if float(line.get("selected_odds") or line.get("odds") or 0.0) > 1.0
        ],
        key=lambda row: (row.get("primary_ev") or 0.0, row.get("selected_odds") or 0.0),
        reverse=True,
    )[: max(1, int(max_lines))]
    if not valid_lines:
        return []

    target_legs = 1 if sanitized_legs == 1 else min(sanitized_legs, len(valid_lines))
    combos: list[dict[str, Any]] = []
    seen: set[str] = set()

    def record_combo(candidate_lines: list[dict[str, Any]], total_odds: float, total_ev: float) -> None:
        combo_id = "|".join(str(line.get("selection_key") or line.get("bet_key")) for line in candidate_lines)
        if combo_id in seen:
            return
        seen.add(combo_id)
        combos.append(
            {
                "combo_id": combo_id,
                "legs": [dict(line) for line in candidate_lines],
                "combined_odds": round(total_odds, 2),
                "total_primary_ev": round(total_ev, 2),
            }
        )

    def can_add_line(existing: list[dict[str, Any]], candidate: dict[str, Any]) -> bool:
        return all(existing_line.get("match_key") != candidate.get("match_key") for existing_line in existing)

    def walk(start_index: int, current_lines: list[dict[str, Any]], current_odds: float, current_ev: float) -> None:
        if len(current_lines) == target_legs:
            if sanitized_min_odds <= current_odds <= sanitized_max_odds:
                record_combo(current_lines, current_odds, current_ev)
            return
        for index in range(start_index, len(valid_lines)):
            if len(combos) >= max_combos:
                break
            candidate = valid_lines[index]
            next_odds = current_odds * float(candidate.get("selected_odds") or 1.0)
            if next_odds > sanitized_max_odds * 1.25:
                continue
            if not can_add_line(current_lines, candidate):
                continue
            current_lines.append(candidate)
            walk(index + 1, current_lines, next_odds, current_ev + float(candidate.get("primary_ev") or 0.0))
            current_lines.pop()

    if target_legs == 1:
        for line in valid_lines:
            total_odds = float(line.get("selected_odds") or 0.0)
            if sanitized_min_odds <= total_odds <= sanitized_max_odds:
                record_combo([line], total_odds, float(line.get("primary_ev") or 0.0))
    else:
        walk(0, [], 1.0, 0.0)

    return sorted(combos, key=lambda row: row.get("total_primary_ev") or 0.0, reverse=True)[:max_combos]
