from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.matchups.form_profiles import (
    MATCHUP_FORM_METHOD,
    MATCHUP_FORM_RECENCY_HALF_LIFE_DAYS,
    MATCHUP_FORM_WINDOW_MATCHES,
    build_matchup_form_profiles,
)
from ullebets_v2.matchups.persistence import persist_matchup_records
from ullebets_v2.matchups.reports import (
    build_matchup_audit_rows,
    build_matchup_health_rows,
    build_matchup_parity_rows,
)
from ullebets_v2.storage.collections import MARKET_BIAS_PROFILES, MATCHUPS_LEAGUE_AVG, MATCHUPS_SCORE, TEAMPROFILES


PERIODS = (
    ("ALL", "Hela matchen"),
    ("1ST", "Första halvlek"),
    ("2ND", "Andra halvlek"),
)

STATS_FOR_VIEW = (
    ("shotsOnGoal", "Skott på mål"),
    ("totalShots", "Totala skott"),
    ("cornerKicks", "Hörnor"),
    ("fouls", "Fouls"),
    ("yellowCards", "Gula kort"),
    ("throwIns", "Inkast"),
    ("offsides", "Offsides"),
    ("totalTackle", "Tacklingar"),
    ("freeKicks", "Frisparkar"),
)

SCOPE_TOTAL = "TOTAL"
SCOPE_HOME = "HOME_TEAM"
SCOPE_AWAY = "AWAY_TEAM"
FORECAST_SCOPE_MAP = {"total": SCOPE_TOTAL, "home": SCOPE_HOME, "away": SCOPE_AWAY}

STAT_CONFIG: dict[str, dict[str, Any]] = {
    "totalShots": {
        "market_stat": "totalShots",
        "drivers": [
            {"stat": "finalThirdEntries", "type": "for"},
            {"stat": "touchesInOppBox", "type": "for"},
            {"stat": "totalShots", "type": "against"},
        ],
    },
    "shotsOnGoal": {
        "market_stat": "shotsOnGoal",
        "drivers": [
            {"stat": "bigChanceCreated", "type": "for"},
            {"stat": "bigChanceCreated", "type": "against"},
        ],
    },
    "cornerKicks": {
        "market_stat": "cornerKicks",
        "drivers": [
            {"stat": "totalShotsOutsideBox", "type": "for"},
            {"stat": "blockedScoringAttempt", "type": "against"},
            {"stat": "accurateCross", "type": "for"},
        ],
    },
    "fouls": {
        "market_stat": "fouls",
        "drivers": [
            {"stat": "dribblesPercentage", "type": "for"},
            {"stat": "totalTackle", "type": "for"},
        ],
    },
    "freeKicks": {
        "market_stat": "freeKicks",
        "drivers": [
            {"stat": "dribblesPercentage", "type": "for"},
            {"stat": "totalTackle", "type": "for"},
        ],
    },
    "yellowCards": {
        "market_stat": "yellowCards",
        "drivers": [{"stat": "fouls", "type": "for"}],
    },
    "throwIns": {
        "market_stat": "throwIns",
        "drivers": [
            {"stat": "accurateCross", "type": "for"},
            {"stat": "totalClearance", "type": "against"},
        ],
    },
    "offsides": {
        "market_stat": "offsides",
        "drivers": [
            {"stat": "accurateThroughBall", "type": "for"},
            {"stat": "offsides", "type": "against"},
        ],
    },
    "goalKicks": {
        "market_stat": "goalKicks",
        "drivers": [
            {"stat": "shotsOffGoal", "type": "for"},
            {"stat": "shotsOffGoal", "type": "against"},
        ],
    },
    "totalTackle": {
        "market_stat": "totalTackle",
        "drivers": [
            {"stat": "dribblesPercentage", "type": "against"},
            {"stat": "duelWonPercent", "type": "for"},
        ],
    },
}


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _to_num(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric == numeric else None


def _get_period_node(metric_node: dict[str, Any] | None, period: str) -> dict[str, Any] | None:
    if not isinstance(metric_node, dict):
        return None
    node = metric_node.get(period) or metric_node.get("ALL")
    return node if isinstance(node, dict) else None


def _read_rank(profile: dict[str, Any], stat_group: str, stat_key: str, period: str) -> float | None:
    node = (
        profile.get("statistics", {})
        .get(stat_group, {})
        .get(stat_key, {})
    )
    period_node = _get_period_node(node, period)
    return _to_num(period_node.get("rank") if period_node else None)


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _market_bias_profile_summary(profile: dict[str, Any], *, team_name: Any) -> dict[str, Any]:
    fields = (
        "team_key", "venue_context", "direction", "strength", "sample_size",
        "non_push_sample_size", "over_count", "under_count", "push_count",
        "posterior_over_rate", "shrunk_mean_residual", "direction_confidence",
        "method_version",
    )
    summary = {field: profile.get(field) for field in fields}
    summary["team_name"] = team_name
    return summary


def _index_market_bias_profiles(profiles: list[dict[str, Any]]) -> dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]]:
    indexed: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    fields = ("team_key", "league_key", "venue_context", "market_scope", "stat_key", "period")
    for profile in profiles:
        key = tuple(str(profile.get(field) or "") for field in fields)
        if all(key):
            indexed[key].append(profile)
    return indexed


def _latest_market_bias_profile(
    indexed: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]],
    *,
    team_key: str,
    league_key: str,
    venue_context: str,
    market_scope: str,
    stat_key: str,
    period: str,
    match_start_time: Any,
) -> dict[str, Any] | None:
    kickoff = _as_utc(match_start_time)
    if kickoff is None:
        return None
    key = (team_key, league_key, venue_context, market_scope, stat_key, period)
    eligible = [profile for profile in indexed.get(key, []) if (_as_utc(profile.get("as_of")) or kickoff) < kickoff]
    return max(eligible, key=lambda profile: _as_utc(profile.get("as_of")) or datetime.min.replace(tzinfo=UTC)) if eligible else None


def _market_bias_payload(
    pair: dict[str, Any],
    *,
    scope: str,
    stat_key: str,
    period: str,
    indexed_profiles: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    sides = (("home", pair["home"]),) if scope == "home" else (("away", pair["away"]),) if scope == "away" else (("home", pair["home"]), ("away", pair["away"]))
    profiles = []
    for venue_context, team in sides:
        profile = _latest_market_bias_profile(
            indexed_profiles,
            team_key=str(team["team_key"]),
            league_key=str(pair["league_key"] or ""),
            venue_context=venue_context,
            market_scope=scope,
            stat_key=stat_key,
            period=period,
            match_start_time=pair.get("start_time"),
        )
        if profile is not None:
            profiles.append(_market_bias_profile_summary(profile, team_name=team.get("name")))
    return {"scope": scope, "profiles": profiles}


def _league_size_from_meta(profile: dict[str, Any]) -> int | None:
    meta = profile.get("meta", {})
    for key in ("leagueTeamCount", "leagueSize", "teamsInLeague"):
        numeric = _to_num(meta.get(key))
        if numeric is not None:
            return int(numeric)
    return None


def _round_score(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 1)


def _round_ratio(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _normalize_pair_score(avg_pair: float, league_max: int, mode: str) -> float:
    minimum = 2
    maximum = 2 * league_max
    clamped = max(minimum, min(maximum, avg_pair))
    raw = (maximum - clamped) / (maximum - minimum) if mode == "over" else (clamped - minimum) / (maximum - minimum)
    return round(raw * 1000) / 10


def _adjust_single_pair(pair_sum: float, league_max: int) -> float:
    mean = league_max + 1
    adjusted = mean + (pair_sum - mean) / (2 ** 0.5)
    minimum = 2
    maximum = 2 * league_max
    return max(minimum, min(maximum, adjusted))


def _get_team_stat_value(profile: dict[str, Any], orientation: str, stat_key: str, period: str) -> float | None:
    node = profile.get("statistics", {}).get(orientation, {}).get(stat_key, {})
    period_node = _get_period_node(node, period)
    return _to_num(period_node.get("value") if period_node else None)


def _get_league_average_value(profile: dict[str, Any], orientation: str, stat_key: str, period: str) -> float | None:
    node = profile.get("statistics", {}).get("leagueAverage", {}).get(orientation, {}).get(stat_key, {})
    period_node = _get_period_node(node, period)
    return _to_num(period_node.get("value") if period_node else None)


def _calculate_baseline(stat_key: str, period: str, home_profile: dict[str, Any], away_profile: dict[str, Any]) -> dict[str, Any]:
    mapping = STAT_CONFIG.get(stat_key, {})
    market_stat = str(mapping.get("market_stat") or stat_key)
    home_for = _get_team_stat_value(home_profile, "for", market_stat, period)
    home_against = _get_team_stat_value(home_profile, "against", market_stat, period)
    away_for = _get_team_stat_value(away_profile, "for", market_stat, period)
    away_against = _get_team_stat_value(away_profile, "against", market_stat, period)

    home_league_for = _get_league_average_value(home_profile, "for", market_stat, period)
    home_league_against = _get_league_average_value(home_profile, "against", market_stat, period)
    away_league_for = _get_league_average_value(away_profile, "for", market_stat, period)
    away_league_against = _get_league_average_value(away_profile, "against", market_stat, period)

    total_baseline = ((home_for + away_against) + (away_for + home_against)) / 2 if None not in (home_for, away_against, away_for, home_against) else None
    home_baseline = (home_for + away_against) / 2 if None not in (home_for, away_against) else None
    away_baseline = (away_for + home_against) / 2 if None not in (away_for, home_against) else None

    total_league_baseline = ((home_league_for + away_league_against) + (away_league_for + home_league_against)) / 2 if None not in (home_league_for, away_league_against, away_league_for, home_league_against) else None
    home_league_baseline = (home_league_for + away_league_against) / 2 if None not in (home_league_for, away_league_against) else None
    away_league_baseline = (away_league_for + home_league_against) / 2 if None not in (away_league_for, home_league_against) else None

    return {
        "market_stat": market_stat,
        "perScope": {
            SCOPE_TOTAL: total_baseline,
            SCOPE_HOME: home_baseline,
            SCOPE_AWAY: away_baseline,
        },
        "league": {
            "perScope": {
                SCOPE_TOTAL: total_league_baseline,
                SCOPE_HOME: home_league_baseline,
                SCOPE_AWAY: away_league_baseline,
            }
        },
    }


def _calculate_style_modifier(stat_key: str, period: str, home_profile: dict[str, Any], away_profile: dict[str, Any]) -> dict[str, Any]:
    recipe = STAT_CONFIG.get(stat_key, {})
    drivers = recipe.get("drivers", [])
    if not drivers:
        return {
            "perScope": {SCOPE_TOTAL: None, SCOPE_HOME: None, SCOPE_AWAY: None},
            "sampleSizes": {SCOPE_TOTAL: 0, SCOPE_HOME: 0, SCOPE_AWAY: 0},
        }

    total_mods: list[float] = []
    home_mods: list[float] = []
    away_mods: list[float] = []
    for driver in drivers:
        orientation = "against" if driver.get("type") == "against" else "for"
        stat = str(driver.get("stat"))
        home_value = _get_team_stat_value(home_profile, orientation, stat, period)
        away_value = _get_team_stat_value(away_profile, orientation, stat, period)
        home_league_avg = _get_league_average_value(home_profile, orientation, stat, period)
        away_league_avg = _get_league_average_value(away_profile, orientation, stat, period)

        home_modifier = (home_value / home_league_avg) if None not in (home_value, home_league_avg) and home_league_avg != 0 else None
        away_modifier = (away_value / away_league_avg) if None not in (away_value, away_league_avg) and away_league_avg != 0 else None

        if home_modifier is not None:
            total_mods.append(home_modifier)
        if away_modifier is not None:
            total_mods.append(away_modifier)
        if driver.get("type") == "for":
            if home_modifier is not None:
                home_mods.append(home_modifier)
            if away_modifier is not None:
                away_mods.append(away_modifier)
        else:
            if away_modifier is not None:
                home_mods.append(away_modifier)
            if home_modifier is not None:
                away_mods.append(home_modifier)

    def average(values: list[float]) -> float | None:
        return (sum(values) / len(values)) if values else None

    return {
        "perScope": {
            SCOPE_TOTAL: average(total_mods),
            SCOPE_HOME: average(home_mods),
            SCOPE_AWAY: average(away_mods),
        },
        "sampleSizes": {
            SCOPE_TOTAL: len(total_mods),
            SCOPE_HOME: len(home_mods),
            SCOPE_AWAY: len(away_mods),
        },
    }


def _compute_forecast_bundle(stat_key: str, period: str, home_profile: dict[str, Any], away_profile: dict[str, Any]) -> dict[str, Any]:
    baseline = _calculate_baseline(stat_key, period, home_profile, away_profile)
    style_modifier = _calculate_style_modifier(stat_key, period, home_profile, away_profile)
    adjusted: dict[str, float | None] = {}
    normalized: dict[str, float | None] = {}
    for scope in (SCOPE_TOTAL, SCOPE_HOME, SCOPE_AWAY):
        baseline_value = baseline["perScope"].get(scope)
        if baseline_value is None:
            adjusted[scope] = None
            normalized[scope] = None
            continue
        modifier = style_modifier["perScope"].get(scope)
        safe_modifier = modifier if modifier is not None else 1
        adjusted_value = baseline_value * safe_modifier
        league_baseline = baseline["league"]["perScope"].get(scope)
        adjusted[scope] = adjusted_value
        normalized[scope] = adjusted_value / league_baseline if league_baseline not in (None, 0) else None
    return {
        "baseline": baseline,
        "styleModifier": style_modifier,
        "adjusted": adjusted,
        "normalized": normalized,
    }


def _select_latest_profiles(teamprofile_docs: list[dict[str, Any]], snapshot_date: str) -> dict[tuple[str, str], dict[str, Any]]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for row in teamprofile_docs:
        team_key = str(row.get("team_key") or "")
        match_type = str(row.get("match_type") or "")
        profile_date = _profile_effective_date(row)
        if not team_key or not match_type:
            continue
        if profile_date is None or profile_date > snapshot_date:
            continue
        key = (team_key, match_type)
        existing = selected.get(key)
        if existing is None or _profile_order_key(existing) < _profile_order_key(row):
            selected[key] = row
    return selected


def _profile_effective_date(profile: dict[str, Any]) -> str | None:
    profile_date = str(profile.get("profile_date") or "")
    if profile_date != "current":
        return profile_date or None
    generated_at = profile.get("generated_at") or profile.get("meta", {}).get("savedAt")
    if isinstance(generated_at, datetime):
        return generated_at.astimezone(UTC).date().isoformat()
    if isinstance(generated_at, str) and len(generated_at) >= 10:
        return generated_at[:10]
    return None


def _profile_order_key(profile: dict[str, Any]) -> tuple[str, int, str]:
    effective_date = _profile_effective_date(profile) or ""
    is_current = 1 if str(profile.get("profile_date") or "") == "current" else 0
    generated_at = profile.get("generated_at")
    return effective_date, is_current, str(generated_at or "")


def _build_pairs(target_matches: list[dict[str, Any]], teamprofile_docs: list[dict[str, Any]], snapshot_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    profile_lookup = _select_latest_profiles(teamprofile_docs, snapshot_date)
    pairs: list[dict[str, Any]] = []
    missing_matches: list[dict[str, Any]] = []
    for match in target_matches:
        home_key = str(match.get("home_team_key") or "")
        away_key = str(match.get("away_team_key") or "")
        home_profile = profile_lookup.get((home_key, "home"))
        away_profile = profile_lookup.get((away_key, "away"))
        if home_profile is None or away_profile is None:
            missing_matches.append(
                {
                    "match_key": match.get("match_key"),
                    "has_home_profile": home_profile is not None,
                    "has_away_profile": away_profile is not None,
                }
            )
            continue
        pairs.append(
            {
                "match_key": match.get("match_key"),
                "source_match_id": match.get("source_match_id"),
                "league_key": match.get("league_key"),
                "league_id": match.get("league_id"),
                "league_name": match.get("league_name"),
                "start_time": match.get("start_time"),
                "home": {
                    "team_key": home_key,
                    "id": match.get("home_team_id") or home_profile.get("meta", {}).get("lagId"),
                    "name": home_profile.get("meta", {}).get("lagnamn") or match.get("home_team_name"),
                    "profile": home_profile,
                },
                "away": {
                    "team_key": away_key,
                    "id": match.get("away_team_id") or away_profile.get("meta", {}).get("lagId"),
                    "name": away_profile.get("meta", {}).get("lagnamn") or match.get("away_team_name"),
                    "profile": away_profile,
                },
            }
        )
    return pairs, missing_matches


def _assign_ranks(entries: list[dict[str, Any]], *, top_field: str = "condition") -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entries:
        grouped[str(row.get(top_field) or "default")].append(row)
    ranked: list[dict[str, Any]] = []
    for group_key, rows in grouped.items():
        ordered = sorted(
            rows,
            key=lambda row: (
                -(float(row.get("sort_key") or row.get("score") or float("-inf"))),
                str(row.get("entry_key") or ""),
            ),
        )
        for index, row in enumerate(ordered, start=1):
            ranked.append({**row, "rank_position": index, "is_top_50": index <= 50, top_field: group_key})
    return ranked


def build_matchups_score_docs(
    *,
    target_matches: list[dict[str, Any]],
    teamprofile_docs: list[dict[str, Any]],
    market_bias_profile_docs: list[dict[str, Any]] | None = None,
    snapshot_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pairs, missing_matches = _build_pairs(
        target_matches,
        build_matchup_form_profiles(teamprofile_docs),
        snapshot_date,
    )
    entries: list[dict[str, Any]] = []
    market_bias_profiles = _index_market_bias_profiles(market_bias_profile_docs or [])
    for pair in pairs:
        league_max = _league_size_from_meta(pair["home"]["profile"]) or _league_size_from_meta(pair["away"]["profile"]) or 20
        for stat_key, stat_label in STATS_FOR_VIEW:
            for period_key, period_label in PERIODS:
                hf = _read_rank(pair["home"]["profile"], "for", stat_key, period_key)
                ha = _read_rank(pair["home"]["profile"], "against", stat_key, period_key)
                af = _read_rank(pair["away"]["profile"], "for", stat_key, period_key)
                aa = _read_rank(pair["away"]["profile"], "against", stat_key, period_key)
                if None in (hf, ha, af, aa):
                    continue
                sum_home = hf + aa
                sum_away = af + ha
                avg_pair = (sum_home + sum_away) / 2
                forecast_bundle = _compute_forecast_bundle(stat_key, period_key, pair["home"]["profile"], pair["away"]["profile"])
                base = {
                    "snapshot_date": snapshot_date,
                    "match_key": pair["match_key"],
                    "source_match_id": pair["source_match_id"],
                    "league_key": pair["league_key"],
                    "league_id": pair["league_id"],
                    "league_name": pair["league_name"],
                    "match": f"{pair['home']['name']} vs {pair['away']['name']}",
                    "home_team_name": pair["home"]["name"],
                    "away_team_name": pair["away"]["name"],
                    "home_team_id": pair["home"]["id"],
                    "away_team_id": pair["away"]["id"],
                    "stat_key": stat_key,
                    "stat_label": stat_label,
                    "period": period_key,
                    "period_label": period_label,
                    "home_behaviour": pair["home"]["profile"].get("behaviour"),
                    "away_behaviour": pair["away"]["profile"].get("behaviour"),
                    "ranking_method": MATCHUP_FORM_METHOD,
                    "ranking_window_matches": MATCHUP_FORM_WINDOW_MATCHES,
                    "ranking_recency_half_life_days": MATCHUP_FORM_RECENCY_HALF_LIFE_DAYS,
                }
                for scope, scope_basis in (
                    ("total", avg_pair),
                    ("home", _adjust_single_pair(sum_home, league_max)),
                    ("away", _adjust_single_pair(sum_away, league_max)),
                ):
                    bundle_scope = FORECAST_SCOPE_MAP[scope]
                    league_baseline = forecast_bundle.get("baseline", {}).get("league", {}).get("perScope", {}).get(bundle_scope)
                    market_bias = _market_bias_payload(pair, scope=scope, stat_key=stat_key, period=period_key, indexed_profiles=market_bias_profiles)
                    for condition in ("over", "under"):
                        score = _round_score(_normalize_pair_score(scope_basis, league_max, condition))
                        entries.append(
                            {
                                **base,
                                "entry_key": f"{snapshot_date}|{pair['match_key']}|{stat_key}|{period_key}|{scope}|{condition}",
                                "scope": scope,
                                "condition": condition,
                                "score": score,
                                "sort_key": score,
                                "market_bias": market_bias,
                                "forecast": {"leagueBaseline": league_baseline},
                            }
                        )
    return _assign_ranks(entries, top_field="condition"), missing_matches


def build_matchups_league_avg_docs(
    *,
    target_matches: list[dict[str, Any]],
    teamprofile_docs: list[dict[str, Any]],
    market_bias_profile_docs: list[dict[str, Any]] | None = None,
    snapshot_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pairs, missing_matches = _build_pairs(
        target_matches,
        build_matchup_form_profiles(teamprofile_docs),
        snapshot_date,
    )
    entries: list[dict[str, Any]] = []
    market_bias_profiles = _index_market_bias_profiles(market_bias_profile_docs or [])
    for pair in pairs:
        for stat_key, stat_label in STATS_FOR_VIEW:
            for period_key, period_label in PERIODS:
                forecast_bundle = _compute_forecast_bundle(stat_key, period_key, pair["home"]["profile"], pair["away"]["profile"])
                for scope, bundle_scope in FORECAST_SCOPE_MAP.items():
                    normalized = forecast_bundle.get("normalized", {}).get(bundle_scope)
                    if normalized is None:
                        continue
                    market_bias = _market_bias_payload(pair, scope=scope, stat_key=stat_key, period=period_key, indexed_profiles=market_bias_profiles)
                    for ranking_bucket, sort_key in (("over", normalized), ("under", -normalized)):
                        entries.append(
                            {
                                "entry_key": f"{snapshot_date}|{pair['match_key']}|{stat_key}|{period_key}|{scope}|{ranking_bucket}|ratio",
                                "snapshot_date": snapshot_date,
                                "match_key": pair["match_key"],
                                "source_match_id": pair["source_match_id"],
                                "league_key": pair["league_key"],
                                "league_id": pair["league_id"],
                                "league_name": pair["league_name"],
                                "match": f"{pair['home']['name']} vs {pair['away']['name']}",
                                "home_team_name": pair["home"]["name"],
                                "away_team_name": pair["away"]["name"],
                                "stat_key": stat_key,
                                "stat_label": stat_label,
                                "period": period_key,
                                "period_label": period_label,
                                "scope": scope,
                                "condition": "ratio",
                                "ranking_bucket": ranking_bucket,
                                "score": _round_ratio(normalized),
                                "sort_key": sort_key,
                                "market_bias": market_bias,
                                "home_behaviour": pair["home"]["profile"].get("behaviour"),
                                "away_behaviour": pair["away"]["profile"].get("behaviour"),
                                "ranking_method": MATCHUP_FORM_METHOD,
                                "ranking_window_matches": MATCHUP_FORM_WINDOW_MATCHES,
                                "ranking_recency_half_life_days": MATCHUP_FORM_RECENCY_HALF_LIFE_DAYS,
                                "forecast": {
                                    "baseline": forecast_bundle.get("baseline", {}).get("perScope", {}).get(bundle_scope),
                                    "leagueBaseline": forecast_bundle.get("baseline", {}).get("league", {}).get("perScope", {}).get(bundle_scope),
                                    "styleModifier": forecast_bundle.get("styleModifier", {}).get("perScope", {}).get(bundle_scope),
                                    "normalized": normalized,
                                    "driverSampleSize": forecast_bundle.get("styleModifier", {}).get("sampleSizes", {}).get(bundle_scope, 0),
                                },
                            }
                        )
    return _assign_ranks(entries, top_field="ranking_bucket"), missing_matches


def _load_teamprofiles(
    database: Any,
    snapshot_date: str,
    target_matches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    league_keys = sorted({str(row.get("league_key") or "") for row in target_matches if row.get("league_key")})
    if not league_keys:
        return []
    current_rows = list(
        database[TEAMPROFILES].find(
            {"league_key": {"$in": league_keys}, "profile_date": "current"},
            projection={"_id": 0},
        )
    )
    usable_current = [row for row in current_rows if (_profile_effective_date(row) or "") <= snapshot_date]
    if usable_current:
        required_pairs = {
            (str(row.get("home_team_key") or ""), "home")
            for row in target_matches
            if row.get("home_team_key")
        } | {
            (str(row.get("away_team_key") or ""), "away")
            for row in target_matches
            if row.get("away_team_key")
        }
        current_pairs = {
            (str(row.get("team_key") or ""), str(row.get("match_type") or ""))
            for row in usable_current
        }
        missing_team_keys = sorted({team_key for team_key, match_type in required_pairs if (team_key, match_type) not in current_pairs})
        if not missing_team_keys:
            return usable_current
        fallback_rows = list(
            database[TEAMPROFILES].find(
                {"team_key": {"$in": missing_team_keys}},
                projection={"_id": 0},
            )
        )
        return [
            row
            for row in [*usable_current, *fallback_rows]
            if (_profile_effective_date(row) or "") <= snapshot_date
        ]

    rows = list(
        database[TEAMPROFILES].find(
            {"league_key": {"$in": league_keys}},
            projection={"_id": 0},
        )
    )
    return [row for row in rows if (_profile_effective_date(row) or "") <= snapshot_date]


def _load_market_bias_profiles(database: Any, target_matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    league_keys = sorted({str(row.get("league_key") or "") for row in target_matches if row.get("league_key")})
    team_keys = sorted(
        {
            str(row.get(team_field) or "")
            for row in target_matches
            for team_field in ("home_team_key", "away_team_key")
            if row.get(team_field)
        }
    )
    if not league_keys or not team_keys:
        return []
    return list(
        database[MARKET_BIAS_PROFILES].find(
            {"league_key": {"$in": league_keys}, "team_key": {"$in": team_keys}},
            projection={"_id": 0},
        )
    )


def _run_matchup_build(
    *,
    source_workflow: str,
    job_name: str,
    collection_name: str,
    audit_type: str,
    target_matches: list[dict[str, Any]],
    teamprofile_docs: list[dict[str, Any]] | None,
    market_bias_profile_docs: list[dict[str, Any]] | None,
    snapshot_date: str,
    database: Any | None,
    dry_run: bool,
    generated_at: datetime | None,
    builder,
) -> dict[str, Any]:
    captured_at = generated_at or utc_now()
    profiles = teamprofile_docs
    if profiles is None:
        if database is None:
            profiles = []
        else:
            profiles = _load_teamprofiles(database, snapshot_date, target_matches)
    bias_profiles = market_bias_profile_docs
    if bias_profiles is None:
        bias_profiles = _load_market_bias_profiles(database, target_matches) if database is not None else []
    entry_docs, missing_matches = builder(
        target_matches=target_matches,
        teamprofile_docs=profiles or [],
        market_bias_profile_docs=bias_profiles,
        snapshot_date=snapshot_date,
    )
    parity_rows = build_matchup_parity_rows(
        source_workflow=source_workflow,
        job_name=job_name,
        output_collection=collection_name,
        target_matches=target_matches,
        entry_docs=entry_docs,
        missing_matches=missing_matches,
        report_date=snapshot_date,
    )
    audit_rows = build_matchup_audit_rows(
        audit_type=audit_type,
        scope_key=f"{source_workflow}:{collection_name}",
        target_matches=target_matches,
        entry_docs=entry_docs,
        missing_matches=missing_matches,
        report_date=snapshot_date,
    )
    health_rows = build_matchup_health_rows(
        job_name=job_name,
        target_matches=target_matches,
        entry_docs=entry_docs,
        missing_matches=missing_matches,
        report_date=snapshot_date,
    )
    summary: dict[str, Any] = {
        "job": job_name,
        "generated_at": captured_at.isoformat(),
        "snapshot_date": snapshot_date,
        "target_matches": len(target_matches),
        "teamprofiles": len(profiles or []),
        "entries": len(entry_docs),
        "missing_profile_matches": len(missing_matches),
        "parity_reports": len(parity_rows),
        "audit_reports": len(audit_rows),
        "health_reports": len(health_rows),
        "parity_status_counts": {
            status: sum(1 for row in parity_rows if row["parity_status"] == status)
            for status in sorted({row["parity_status"] for row in parity_rows})
        },
        "audit_status_counts": {
            status: sum(1 for row in audit_rows if row["status"] == status)
            for status in sorted({row["status"] for row in audit_rows})
        },
        "health_status_counts": {
            status: sum(1 for row in health_rows if row["status"] == status)
            for status in sorted({row["status"] for row in health_rows})
        },
        "entry_docs": entry_docs,
        "missing_matches": missing_matches,
    }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name=job_name,
        source_workflow=source_workflow,
        target_window={"snapshot_date": snapshot_date, "target_match_count": len(target_matches)},
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {key: value for key, value in summary.items() if key not in {"entry_docs", "missing_matches"}}
    try:
        persistence_metrics = persist_matchup_records(
            database,
            collection_name=collection_name,
            snapshot_date=snapshot_date,
            entry_docs=entry_docs,
            parity_rows=parity_rows,
            audit_rows=audit_rows,
            health_rows=health_rows,
        )
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics={**persistence_metrics, **job_metrics},
            ),
        )
    except Exception as exc:
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="failed",
                metrics=job_metrics,
                error={"type": type(exc).__name__, "message": str(exc)},
            ),
        )
        raise
    return summary


def run_matchups_score_build(
    *,
    source_workflow: str,
    target_matches: list[dict[str, Any]],
    snapshot_date: str,
    teamprofile_docs: list[dict[str, Any]] | None = None,
    market_bias_profile_docs: list[dict[str, Any]] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return _run_matchup_build(
        source_workflow=source_workflow,
        job_name="build_matchups_score",
        collection_name=MATCHUPS_SCORE,
        audit_type="matchups_score",
        target_matches=target_matches,
        teamprofile_docs=teamprofile_docs,
        market_bias_profile_docs=market_bias_profile_docs,
        snapshot_date=snapshot_date,
        database=database,
        dry_run=dry_run,
        generated_at=generated_at,
        builder=build_matchups_score_docs,
    )


def run_matchups_league_avg_build(
    *,
    source_workflow: str,
    target_matches: list[dict[str, Any]],
    snapshot_date: str,
    teamprofile_docs: list[dict[str, Any]] | None = None,
    market_bias_profile_docs: list[dict[str, Any]] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return _run_matchup_build(
        source_workflow=source_workflow,
        job_name="build_matchups_league_avg",
        collection_name=MATCHUPS_LEAGUE_AVG,
        audit_type="matchups_league_avg",
        target_matches=target_matches,
        teamprofile_docs=teamprofile_docs,
        market_bias_profile_docs=market_bias_profile_docs,
        snapshot_date=snapshot_date,
        database=database,
        dry_run=dry_run,
        generated_at=generated_at,
        builder=build_matchups_league_avg_docs,
    )
