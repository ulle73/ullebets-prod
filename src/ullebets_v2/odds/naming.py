from __future__ import annotations

from typing import Any
import re
import unicodedata

from ullebets_v2.odds.aliases import TEAM_NAME_ALIASES


def normalize_team_name(name: Any) -> str:
    if not name:
        return ""
    return _normalize_text(name, remove_years=False, and_to_word=True)


def normalize_league_name(name: Any) -> str:
    return _normalize_text(name, remove_years=True, and_to_word=False)


def _normalize_text(name: Any, *, remove_years: bool, and_to_word: bool) -> str:
    if not name:
        return ""
    text = str(name).lower()
    if remove_years:
        text = re.sub(r"\d{4}/\d{2}|\d{2}/\d{2}|\d{4}-\d{2}|\d{4}-\d{4}", "", text)
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    if and_to_word:
        text = text.replace("&", "and")
    text = text.replace("’", "").replace("'", "").replace("`", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def generate_name_variants(name: str | None) -> set[str]:
    variants: set[str] = set()
    if not name:
        return variants
    variants.add(name)
    variants.add(name.replace("-", " "))
    variants.add(name.replace("&", "and"))
    variants.add(name.replace(".", ""))
    variants.add(re.sub(r"\b(?:FC|CF|AC|AFC|Club|The)\b", "", name, flags=re.IGNORECASE).strip())
    return {variant for variant in variants if variant}


def generate_league_variants(name: str | None) -> list[str]:
    if not name:
        return []
    variants = {
        name,
        re.sub(r"\d{4}-\d{2}", "", name),
        re.sub(r"\d{4}/\d{2}", "", name),
        re.sub(r"\d{2}/\d{2}", "", name),
        re.sub(r"\d{4}-\d{4}", "", name),
        name.replace("-", " "),
    }
    return [variant.strip() for variant in variants if variant and variant.strip()]


def build_alias_map(support_docs: dict[str, Any], custom_aliases: dict[str, list[str]] | None = None) -> dict[str, str]:
    alias_map: dict[str, str] = {}

    def add_alias(alias: str | None, canonical: str | None) -> None:
        if not alias or not canonical:
            return
        normalized = normalize_team_name(alias)
        if normalized and normalized not in alias_map:
            alias_map[normalized] = canonical

    for team in support_docs.get("teams", []):
        team_name = team.get("team_name")
        for variant in generate_name_variants(team_name):
            add_alias(variant, team_name)

    for canonical, aliases in (custom_aliases or TEAM_NAME_ALIASES).items():
        for variant in generate_name_variants(canonical):
            add_alias(variant, canonical)
        for alias in aliases:
            for variant in generate_name_variants(alias):
                add_alias(variant, canonical)

    return alias_map


def build_league_map(support_docs: dict[str, Any]) -> dict[str, str]:
    league_map: dict[str, str] = {}
    for league in support_docs.get("leagues", []):
        league_name = league.get("league_name")
        for variant in generate_league_variants(league_name):
            normalized = normalize_league_name(variant)
            if normalized and normalized not in league_map:
                league_map[normalized] = league_name
    return league_map


def resolve_team_name(name: str | None, alias_map: dict[str, str]) -> str | None:
    normalized = normalize_team_name(name)
    if not normalized:
        return None
    if normalized in alias_map:
        return alias_map[normalized]
    cleaned = re.sub(r"\b(?:fc|cf|ac|afc|club|the)\b", "", normalized).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return alias_map.get(cleaned) if cleaned else None


def canonicalize_team_name(name: str | None, alias_map: dict[str, str]) -> str | None:
    resolved = resolve_team_name(name, alias_map)
    if resolved:
        return resolved
    return str(name).strip() if isinstance(name, str) and name.strip() else None


def canonicalize_league_name(name: str | None, league_map: dict[str, str]) -> str | None:
    normalized = normalize_league_name(name)
    if normalized and normalized in league_map:
        return league_map[normalized]
    return str(name).strip() if isinstance(name, str) and name.strip() else None
