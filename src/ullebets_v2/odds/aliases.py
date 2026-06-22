from __future__ import annotations


TEAM_NAME_ALIASES: dict[str, list[str]] = {
    "Wolverhampton": ["Wolves", "Wolverhampton Wanderers"],
    "West Ham United": ["West Ham", "West Ham Utd"],
    "Brighton & Hove Albion": ["Brighton"],
    "Tottenham Hotspur": ["Tottenham"],
    "Atlético Mineiro": ["Atlético Mineiro-MG"],
    "Cruzeiro": ["Cruzeiro-MG"],
    "Vasco da Gama": ["Vasco da Gama-RJ"],
    "Botafogo": ["Botafogo-RJ"],
    "Barcelona": ["FC Barcelona"],
    "Santos": ["Santos-SP"],
    "Fluminense": ["Fluminense-RJ"],
    "Flamengo": ["Flamengo-RJ"],
    "Corinthians": ["Corinthians-SP"],
    "Palmeiras": ["Palmeiras-SP"],
    "Mirassol": ["Mirassol-SP"],
    "Ceará": ["Ceará-CE", "Ceara"],
    "Bahia": ["Bahia-BA"],
    "Fortaleza": ["Fortaleza-CE"],
    "Vitória": ["Vitória-BA"],
    "São Paulo": ["São Paulo-SP"],
    "Juventude": ["Juventude-RS"],
    "Internacional": ["Internacional-RS"],
    "Sport Recife": ["Sport Recife-PE"],
    "Red Bull Bragantino": ["RB Bragantino-SP"],
    "Nottingham Forest": ["Nottingham"],
    "Leeds United": ["Leeds"],
    "SC Freiburg": ["Freiburg"],
    "VfB Stuttgart": ["Stuttgart"],
    "1. FSV Mainz 05": ["Mainz 05"],
    "Hamburger SV": ["Hamburg"],
    "FC Bayern München": ["Bayern München", "Bayern Munich"],
    "Bayer 04 Leverkusen": ["Bayer Leverkusen", "Leverkusen"],
    "Athletic Club": ["Athletic Bilbao"],
    "Deportivo Alavés": ["Alaves"],
    "Girona FC": ["Girona"],
    "Levante UD": ["Levante"],
    "SV Werder Bremen": ["Werder Bremen"],
    "Stade Brestois": ["Brest"],
    "Paris Saint-Germain": ["PSG"],
    "RC Lens": ["Lens"],
    "RC Strasbourg": ["Strasbourg"],
    "Stade Rennais": ["Rennes"],
    "Olympique Lyonnais": ["Lyon"],
    "Olympique de Marseille": ["Marseille"],
}


def get_team_aliases(team_name: str | None) -> list[str]:
    if not team_name:
        return []
    aliases = TEAM_NAME_ALIASES.get(team_name, [])
    return list(dict.fromkeys([team_name, *aliases]))
