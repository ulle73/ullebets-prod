from __future__ import annotations

from typing import Any


def to_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric == numeric else None


def settle_line(
    *,
    actual_value: Any,
    line_value: Any,
    direction: str,
    odds_decimal: Any,
    stake_units: Any = 1,
) -> dict[str, Any] | None:
    actual = to_float(actual_value)
    line = to_float(line_value)
    if actual is None or line is None:
        return None

    normalized_direction = "under" if str(direction).lower() == "under" else "over"
    if actual == line:
        return {
            "settlement_result": "push",
            "win": None,
            "roi_units": 0.0,
            "pnl_units": 0.0,
            "stake_units": to_float(stake_units) or 1.0,
        }

    is_win = actual > line if normalized_direction == "over" else actual < line
    odds = to_float(odds_decimal)
    roi_units = (odds - 1.0) if is_win and odds is not None and odds > 1 else (0.0 if is_win else -1.0)
    stake = to_float(stake_units) or 1.0
    return {
        "settlement_result": "win" if is_win else "loss",
        "win": bool(is_win),
        "roi_units": round(float(roi_units), 2),
        "pnl_units": round(float(roi_units) * stake, 2),
        "stake_units": stake,
    }
