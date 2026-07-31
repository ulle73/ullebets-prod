from __future__ import annotations

from typing import Any

from ullebets_v2.odds.aliases import get_team_aliases


STAT_PREFIX = "(?:Totala|Totalt antal|Antal)"
STAT_PATTERNS: list[tuple[str, str]] = [
    ("shotsOnGoal", rf"{STAT_PREFIX} skott på mål"),
    ("totalShots", rf"{STAT_PREFIX} skott(?! på mål)"),
    ("cornerKicks", rf"{STAT_PREFIX} hörnor"),
    ("yellowCards", rf"{STAT_PREFIX} kort"),
    ("freeKicks", rf"{STAT_PREFIX} frisparkar"),
    ("fouls", rf"(?:Totala utförda|{STAT_PREFIX}) fouls"),
    ("totalTackle", rf"{STAT_PREFIX} tacklingar"),
    ("offsides", rf"{STAT_PREFIX} offside"),
]


def _matches_pattern(label: str, pattern: str) -> bool:
    import re

    return re.search(pattern, label, flags=re.IGNORECASE) is not None


def parse_line(raw_value: Any) -> float | None:
    if raw_value is None:
        return None
    try:
        numeric = float(raw_value)
    except (TypeError, ValueError):
        return None
    if abs(numeric) >= 100:
        return round(numeric / 1000, 1)
    return round(numeric, 2)


def parse_decimal_odds(outcome: dict[str, Any] | None) -> float | None:
    if not outcome:
        return None
    decimal_value = outcome.get("oddsDecimal")
    if isinstance(decimal_value, (int, float)):
        return round(float(decimal_value), 2)
    numeric_odds = outcome.get("odds")
    if isinstance(numeric_odds, (int, float)):
        return round(float(numeric_odds) / 1000, 2)
    fractional = outcome.get("oddsFractional")
    if isinstance(fractional, str) and "/" in fractional:
        try:
            numerator, denominator = fractional.split("/", 1)
            return round(float(numerator) / float(denominator) + 1, 2)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    return None


def determine_scope(label: str | None, home_team: str | None, away_team: str | None) -> str:
    if not label:
        return "total"
    lowered = label.lower()
    if any(alias.lower() in lowered for alias in get_team_aliases(home_team)):
        return "home"
    if any(alias.lower() in lowered for alias in get_team_aliases(away_team)):
        return "away"
    return "total"


def determine_period(label: str | None) -> str:
    if not label:
        return "ALL"
    lowered = label.lower()
    if "första halvlek" in lowered or "1st" in lowered:
        return "1ST"
    if "andra halvlek" in lowered or "2nd" in lowered:
        return "2ND"
    return "ALL"


def is_player_specific_market(label: str | None) -> bool:
    if not label:
        return False
    import re

    return re.search(r"\bspelar(?:en|ens|e|are)\b", label, flags=re.IGNORECASE) is not None


def normalize_offer_entries(unibet_odds: Any) -> list[tuple[str, dict[str, Any]]]:
    if not unibet_odds:
        return []
    if isinstance(unibet_odds, list):
        entries: list[tuple[str, dict[str, Any]]] = []
        for offer in unibet_odds:
            if not isinstance(offer, dict):
                continue
            label = (
                offer.get("criterion", {}).get("label")
                or offer.get("betOffer", {}).get("criterion", {}).get("label")
                or ""
            )
            entries.append((str(label), offer))
        return entries
    if isinstance(unibet_odds, dict):
        return [(str(label), offer) for label, offer in unibet_odds.items() if isinstance(offer, dict)]
    return []


def map_unibet_odds(unibet_odds: Any, home_team: str | None = None, away_team: str | None = None) -> list[dict[str, Any]]:
    tuples: list[dict[str, Any]] = []
    for label, market in normalize_offer_entries(unibet_odds):
        if is_player_specific_market(label):
            continue

        stat_key = None
        for candidate_key, pattern in STAT_PATTERNS:
            if _matches_pattern(label, pattern):
                stat_key = candidate_key
                break
        if stat_key is None:
            continue

        outcomes = []
        if isinstance(market.get("outcomes"), list):
            outcomes = market["outcomes"]
        elif isinstance(market.get("betOffer", {}).get("outcomes"), list):
            outcomes = market["betOffer"]["outcomes"]
        if not outcomes:
            continue

        scope = determine_scope(label, home_team, away_team)
        period = determine_period(label)
        lines_by_value: dict[float, dict[str, float | None]] = {}
        for outcome in outcomes:
            if not isinstance(outcome, dict):
                continue
            line_value = parse_line(outcome.get("line", outcome.get("handicap")))
            if line_value is None:
                continue
            odds_value = parse_decimal_odds(outcome)
            if odds_value is None:
                continue
            direction_label = str(
                outcome.get("englishLabel") or outcome.get("label") or ""
            ).lower()
            direction = "under" if "under" in direction_label else "over"
            line_bucket = lines_by_value.setdefault(line_value, {"over": None, "under": None})
            line_bucket[direction] = odds_value

        for line_value, odds in lines_by_value.items():
            tuples.append(
                {
                    "statKey": stat_key,
                    "scope": scope,
                    "period": period,
                    "line": line_value,
                    "odds": odds,
                }
            )
    return tuples
