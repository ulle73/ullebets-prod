from __future__ import annotations

from typing import Any


def _numeric_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def extract_stat_rows(match: dict) -> list[dict]:
    rows: list[dict] = []
    statistics = ((match.get("matchDetails") or {}).get("statistics")) or []
    if not isinstance(statistics, list):
        return rows

    for period_block in statistics:
        if not isinstance(period_block, dict):
            continue
        period = period_block.get("period")
        groups = period_block.get("groups") or []
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            items = group.get("statisticsItems") or []
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                home_value = _numeric_or_none(item.get("homeValue"))
                away_value = _numeric_or_none(item.get("awayValue"))
                total_value = None
                if home_value is not None and away_value is not None:
                    total_value = home_value + away_value

                base_row = {
                    "match_id": str(match.get("matchId")) if match.get("matchId") is not None else None,
                    "kickoff_ts": match.get("timestamp"),
                    "match_date": match.get("date"),
                    "home_team_name": match.get("homeTeamName"),
                    "away_team_name": match.get("awayTeamName"),
                    "period": period,
                    "stat_group": group.get("groupName"),
                    "stat_item_key": item.get("key"),
                    "stat_item_name": item.get("name"),
                    "total_value": total_value,
                }

                rows.append(
                    {
                        **base_row,
                        "team_role": "home",
                        "team_name": match.get("homeTeamName"),
                        "opponent_name": match.get("awayTeamName"),
                        "team_value": home_value,
                        "opponent_value": away_value,
                    }
                )
                rows.append(
                    {
                        **base_row,
                        "team_role": "away",
                        "team_name": match.get("awayTeamName"),
                        "opponent_name": match.get("homeTeamName"),
                        "team_value": away_value,
                        "opponent_value": home_value,
                    }
                )
    return rows
