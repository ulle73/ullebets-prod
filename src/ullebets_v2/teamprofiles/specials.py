from __future__ import annotations

from typing import Any


SCORE_STATES = ("leading", "trailing", "tied")
BASE_WINDOW_LABELS = ("0-10", "11-20", "21-30", "31-40", "41-50", "51-60", "61-70", "71-80", "81-90")
FIRST_GOAL_METRICS = (
    "concedeFirstPercentage",
    "scoreFirstPercentage",
    "averageTimeScoredFirst",
    "averageTimeConcededFirst",
)


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and float(value) == float(value)


def _normalize_added_minutes(value: Any) -> int:
    if not isinstance(value, (int, float)):
        return 0
    added = int(value)
    return added if 0 <= added <= 60 else 0


def _resolve_incident_time_seconds(incident: dict[str, Any] | None) -> int | None:
    if not isinstance(incident, dict):
        return None
    minute = incident.get("time")
    if not isinstance(minute, (int, float)):
        return None
    return max(0, int(minute * 60 + _normalize_added_minutes(incident.get("addedTime")) * 60))


def _resolve_shot_time_seconds(shot: dict[str, Any] | None) -> int | None:
    if not isinstance(shot, dict):
        return None
    explicit = shot.get("timeSeconds")
    if isinstance(explicit, (int, float)):
        return int(explicit)
    minute = shot.get("time")
    if not isinstance(minute, (int, float)):
        return None
    return max(0, int(minute * 60 + _normalize_added_minutes(shot.get("addedTime")) * 60))


def _resolve_match_duration(shot_entries: list[dict[str, Any]], incidents: list[dict[str, Any]]) -> int:
    default_duration = 90 * 60
    incident_times = [value for value in (_resolve_incident_time_seconds(item) for item in incidents) if value is not None]
    shot_times = [value for value in (_resolve_shot_time_seconds(item) for item in shot_entries) if value is not None]
    ft_incident = next(
        (
            item
            for item in incidents
            if item.get("text") == "FT" and item.get("incidentType") == "period"
        ),
        None,
    )
    ft_time = _resolve_incident_time_seconds(ft_incident)
    return max(default_duration, ft_time or 0, max(incident_times or [0]), max(shot_times or [0]))


def _determine_score_state(home_score: int, away_score: int, team_is_home: bool) -> str:
    team_score = home_score if team_is_home else away_score
    opp_score = away_score if team_is_home else home_score
    if team_score > opp_score:
        return "leading"
    if team_score < opp_score:
        return "trailing"
    return "tied"


def _arrify_incidents(payload: Any) -> list[dict[str, Any]]:
    candidates = []
    if isinstance(payload, dict):
        candidates.extend([payload.get("incidents"), payload.get("matchDetails", {}).get("incidents")])
    candidates.append(payload)
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _arrify_shotmap(payload: Any) -> list[dict[str, Any]]:
    candidates = []
    if isinstance(payload, dict):
        candidates.extend([payload.get("shotmap"), payload.get("matchDetails", {}).get("shotmap")])
    candidates.append(payload)
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _build_score_segments(incidents: list[dict[str, Any]], team_is_home: bool, match_duration: int) -> list[dict[str, Any]]:
    goals = _extract_goal_events(incidents)

    current_home = 0
    current_away = 0
    current_state = "tied"
    previous_time = 0
    segments: list[dict[str, Any]] = []

    for goal in goals:
        seconds = min(max(int(goal["seconds"]), previous_time), match_duration)
        if seconds > previous_time:
            segments.append({"start": previous_time, "end": seconds, "state": current_state})
        if goal["homeScore"] is not None and goal["awayScore"] is not None:
            current_home = int(goal["homeScore"])
            current_away = int(goal["awayScore"])
        elif goal["isHome"]:
            current_home += 1
        else:
            current_away += 1
        current_state = _determine_score_state(current_home, current_away, team_is_home)
        previous_time = seconds

    if not segments or match_duration > previous_time:
        start = previous_time if segments else 0
        if match_duration > start:
            segments.append({"start": start, "end": match_duration, "state": current_state})

    if not segments:
        segments.append({"start": 0, "end": match_duration, "state": current_state})
    return segments


def _extract_goal_events(incidents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    goals = []
    for item in incidents:
        if item.get("incidentType") != "goal":
            continue
        goals.append(
            {
                "seconds": _resolve_incident_time_seconds(item),
                "homeScore": item.get("homeScore") if isinstance(item.get("homeScore"), (int, float)) else None,
                "awayScore": item.get("awayScore") if isinstance(item.get("awayScore"), (int, float)) else None,
                "isHome": item.get("isHome"),
            }
        )
    goals = [item for item in goals if item["seconds"] is not None]
    goals.sort(key=lambda item: int(item["seconds"]))

    previous_home = 0
    previous_away = 0
    for goal in goals:
        is_home = goal["isHome"] if isinstance(goal["isHome"], bool) else None
        home_score = goal["homeScore"]
        away_score = goal["awayScore"]
        if is_home is None and home_score is not None and away_score is not None:
            if home_score > previous_home and away_score == previous_away:
                is_home = True
            elif away_score > previous_away and home_score == previous_home:
                is_home = False
        goal["isHome"] = is_home is True
        if home_score is not None and away_score is not None:
            previous_home = int(home_score)
            previous_away = int(away_score)
        elif goal["isHome"]:
            previous_home += 1
        else:
            previous_away += 1
    return goals


def _find_state_for_time(segments: list[dict[str, Any]], match_duration: int, time_seconds: int) -> str:
    if not segments:
        return "tied"
    clamped = min(max(time_seconds, 0), match_duration)
    for segment in segments:
        if segment["start"] <= clamped < segment["end"]:
            return str(segment["state"])
    return str(segments[-1]["state"])


def _count_shots_by_state(
    shots: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    match_duration: int,
) -> dict[str, int]:
    counts = {state: 0 for state in SCORE_STATES}
    if not segments:
        return counts
    for shot in shots:
        seconds = _resolve_shot_time_seconds(shot)
        if seconds is None:
            continue
        counts[_find_state_for_time(segments, match_duration, seconds)] += 1
    return counts


def _get_window_label_from_minute(minute: float) -> str:
    if minute <= 10:
        return BASE_WINDOW_LABELS[0]
    index = max(0, int(-(-minute // 10)) - 1)
    start = index * 10 + 1
    end = (index + 1) * 10
    return f"{start}-{end}"


def _count_shots_by_window(shots: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for shot in shots:
        seconds = _resolve_shot_time_seconds(shot)
        if seconds is None:
            continue
        label = _get_window_label_from_minute(seconds / 60)
        counts[label] = counts.get(label, 0) + 1
    return counts


def _window_sort_key(label: Any) -> tuple[int, int]:
    raw = str(label)
    rank_offset = 1 if raw.startswith("rank-") else 0
    target = raw[5:] if rank_offset else raw
    start = target.split("-", 1)[0]
    try:
        return (rank_offset, int(start))
    except ValueError:
        return (rank_offset, 9999)


def _prefer_payload(existing: dict[str, Any] | None, candidate: dict[str, Any], kind: str) -> dict[str, Any]:
    if existing is None:
        return candidate
    extractor = _arrify_incidents if kind == "incidents" else _arrify_shotmap
    existing_size = len(extractor(existing.get("payload")))
    candidate_size = len(extractor(candidate.get("payload")))
    if candidate_size > existing_size:
        return candidate
    return existing


def build_raw_payload_lookups(
    *,
    raw_incidents: list[dict[str, Any]],
    raw_shotmaps: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    incidents_by_match: dict[str, dict[str, Any]] = {}
    shotmaps_by_match: dict[str, dict[str, Any]] = {}
    for row in raw_incidents:
        match_key = str(row.get("match_key") or "")
        if match_key:
            incidents_by_match[match_key] = _prefer_payload(incidents_by_match.get(match_key), row, "incidents")
    for row in raw_shotmaps:
        match_key = str(row.get("match_key") or "")
        if match_key:
            shotmaps_by_match[match_key] = _prefer_payload(shotmaps_by_match.get(match_key), row, "shotmap")
    return (
        {match_key: row.get("payload") for match_key, row in incidents_by_match.items()},
        {match_key: row.get("payload") for match_key, row in shotmaps_by_match.items()},
    )


def compute_profile_specials(
    *,
    games: list[dict[str, Any]],
    match_type: str,
    incidents_by_match: dict[str, Any],
    shotmaps_by_match: dict[str, Any],
) -> dict[str, Any]:
    specials: dict[str, Any] = {
        "shotsPerMinute": {
            "for": {state: None for state in SCORE_STATES},
            "against": {state: None for state in SCORE_STATES},
        },
        "firstGoal": {metric: None for metric in FIRST_GOAL_METRICS},
        "shotsPerTenMinutes": {
            "for": {},
            "against": {},
        },
    }
    if not games:
        for label in BASE_WINDOW_LABELS:
            specials["shotsPerTenMinutes"]["for"][label] = None
            specials["shotsPerTenMinutes"]["against"][label] = None
        return specials

    team_is_home = match_type == "home"
    state_totals_for = {state: {"shots": 0, "minutes": 0.0} for state in SCORE_STATES}
    state_totals_against = {state: {"shots": 0, "minutes": 0.0} for state in SCORE_STATES}
    window_counts_for: dict[str, int] = {}
    window_counts_against: dict[str, int] = {}
    matches_with_shotmap = 0
    first_goal_stats = {
        "total": 0,
        "scoredFirst": 0,
        "concededFirst": 0,
        "scoredFirstTimeSum": 0.0,
        "concededFirstTimeSum": 0.0,
        "scoredFirstSamples": 0,
        "concededFirstSamples": 0,
    }

    for game in games:
        match_key = str(game.get("match_key") or "")
        shot_entries = _arrify_shotmap(shotmaps_by_match.get(match_key))
        incidents = _arrify_incidents(incidents_by_match.get(match_key))
        has_shotmap = bool(shot_entries)
        has_incidents = bool(incidents)

        if has_shotmap:
            matches_with_shotmap += 1
            team_shots = [shot for shot in shot_entries if shot.get("isHome") is team_is_home]
            opponent_shots = [shot for shot in shot_entries if shot.get("isHome") is not team_is_home]

            for label, count in _count_shots_by_window(team_shots).items():
                window_counts_for[label] = window_counts_for.get(label, 0) + count
            for label, count in _count_shots_by_window(opponent_shots).items():
                window_counts_against[label] = window_counts_against.get(label, 0) + count

            if has_incidents:
                match_duration = _resolve_match_duration(shot_entries, incidents)
                segments = _build_score_segments(incidents, team_is_home, match_duration)
                for segment in segments:
                    minutes = (segment["end"] - segment["start"]) / 60
                    if minutes <= 0:
                        continue
                    state = str(segment["state"])
                    state_totals_for[state]["minutes"] += minutes
                    state_totals_against[state]["minutes"] += minutes

                team_shots_by_state = _count_shots_by_state(team_shots, segments, match_duration)
                opp_shots_by_state = _count_shots_by_state(opponent_shots, segments, match_duration)
                for state in SCORE_STATES:
                    state_totals_for[state]["shots"] += team_shots_by_state[state]
                    state_totals_against[state]["shots"] += opp_shots_by_state[state]

        if has_incidents:
            goal_events = [
                {
                    "seconds": item["seconds"],
                    "isTeam": item["isHome"] is team_is_home,
                }
                for item in _extract_goal_events(incidents)
            ]
            if goal_events:
                first_goal_stats["total"] += 1
                first_goal = goal_events[0]
                minutes = float(first_goal["seconds"]) / 60
                if first_goal["isTeam"]:
                    first_goal_stats["scoredFirst"] += 1
                    first_goal_stats["scoredFirstTimeSum"] += minutes
                    first_goal_stats["scoredFirstSamples"] += 1
                else:
                    first_goal_stats["concededFirst"] += 1
                    first_goal_stats["concededFirstTimeSum"] += minutes
                    first_goal_stats["concededFirstSamples"] += 1

    for state in SCORE_STATES:
        for_minutes = state_totals_for[state]["minutes"]
        against_minutes = state_totals_against[state]["minutes"]
        specials["shotsPerMinute"]["for"][state] = (
            state_totals_for[state]["shots"] / for_minutes if for_minutes > 0 else None
        )
        specials["shotsPerMinute"]["against"][state] = (
            state_totals_against[state]["shots"] / against_minutes if against_minutes > 0 else None
        )

    if first_goal_stats["total"] > 0:
        specials["firstGoal"]["scoreFirstPercentage"] = first_goal_stats["scoredFirst"] / first_goal_stats["total"]
        specials["firstGoal"]["concedeFirstPercentage"] = first_goal_stats["concededFirst"] / first_goal_stats["total"]
    if first_goal_stats["scoredFirstSamples"] > 0:
        specials["firstGoal"]["averageTimeScoredFirst"] = (
            first_goal_stats["scoredFirstTimeSum"] / first_goal_stats["scoredFirstSamples"]
        )
    if first_goal_stats["concededFirstSamples"] > 0:
        specials["firstGoal"]["averageTimeConcededFirst"] = (
            first_goal_stats["concededFirstTimeSum"] / first_goal_stats["concededFirstSamples"]
        )

    window_labels = sorted(
        {*BASE_WINDOW_LABELS, *window_counts_for.keys(), *window_counts_against.keys()},
        key=lambda label: int(str(label).split("-", 1)[0]) if "-" in str(label) else 0,
    )
    for label in window_labels:
        if matches_with_shotmap > 0:
            specials["shotsPerTenMinutes"]["for"][label] = window_counts_for.get(label, 0) / matches_with_shotmap
            specials["shotsPerTenMinutes"]["against"][label] = window_counts_against.get(label, 0) / matches_with_shotmap
        else:
            specials["shotsPerTenMinutes"]["for"][label] = None
            specials["shotsPerTenMinutes"]["against"][label] = None

    return specials


def assign_special_ranks(profiles: list[dict[str, Any]]) -> None:
    if not profiles:
        return

    sides = ("for", "against")
    for side in sides:
        for state in SCORE_STATES:
            ranked = sorted(
                (
                    (index, profile.get("specials", {}).get("shotsPerMinute", {}).get(side, {}).get(state))
                    for index, profile in enumerate(profiles)
                ),
                key=lambda item: float(item[1]) if _is_finite_number(item[1]) else float("-inf"),
                reverse=True,
            )
            rank = 1
            for index, value in ranked:
                if _is_finite_number(value):
                    profiles[index]["specials"]["shotsPerMinute"][side][f"rank-{state}"] = rank
                    rank += 1
                else:
                    profiles[index]["specials"]["shotsPerMinute"][side][f"rank-{state}"] = None

    for side in sides:
        labels = sorted(
            {
                *BASE_WINDOW_LABELS,
                *(
                    label
                    for profile in profiles
                    for label in profile.get("specials", {}).get("shotsPerTenMinutes", {}).get(side, {}).keys()
                    if not str(label).startswith("rank-")
                ),
            },
            key=lambda label: int(str(label).split("-", 1)[0]) if "-" in str(label) else 0,
        )
        for label in labels:
            ranked = sorted(
                (
                    (index, profile.get("specials", {}).get("shotsPerTenMinutes", {}).get(side, {}).get(label))
                    for index, profile in enumerate(profiles)
                ),
                key=lambda item: float(item[1]) if _is_finite_number(item[1]) else float("-inf"),
                reverse=True,
            )
            rank = 1
            for index, value in ranked:
                profiles[index]["specials"]["shotsPerTenMinutes"][side][f"rank-{label}"] = rank if _is_finite_number(value) else None
                if _is_finite_number(value):
                    rank += 1

    for metric in FIRST_GOAL_METRICS:
        ascending = metric in {"averageTimeScoredFirst", "averageTimeConcededFirst"}
        ranked = [(index, profile.get("specials", {}).get("firstGoal", {}).get(metric)) for index, profile in enumerate(profiles)]
        ranked.sort(
            key=lambda item: float(item[1]) if _is_finite_number(item[1]) else (float("inf") if ascending else float("-inf")),
            reverse=not ascending,
        )
        rank = 1
        for index, value in ranked:
            profiles[index]["specials"]["firstGoal"][f"rank-{metric}"] = rank if _is_finite_number(value) else None
            if _is_finite_number(value):
                rank += 1


def compute_specials_league_average(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    league_average: dict[str, Any] = {
        "shotsPerMinute": {"for": {}, "against": {}},
        "firstGoal": {metric: None for metric in FIRST_GOAL_METRICS},
        "shotsPerTenMinutes": {"for": {}, "against": {}},
    }
    if not profiles:
        for side in ("for", "against"):
            for state in SCORE_STATES:
                league_average["shotsPerMinute"][side][state] = None
            for label in BASE_WINDOW_LABELS:
                league_average["shotsPerTenMinutes"][side][label] = None
        return league_average

    for side in ("for", "against"):
        for state in SCORE_STATES:
            values = [
                profile.get("specials", {}).get("shotsPerMinute", {}).get(side, {}).get(state)
                for profile in profiles
            ]
            numeric = [float(value) for value in values if _is_finite_number(value)]
            league_average["shotsPerMinute"][side][state] = sum(numeric) / len(numeric) if numeric else None

    for metric in FIRST_GOAL_METRICS:
        values = [profile.get("specials", {}).get("firstGoal", {}).get(metric) for profile in profiles]
        numeric = [float(value) for value in values if _is_finite_number(value)]
        league_average["firstGoal"][metric] = sum(numeric) / len(numeric) if numeric else None

    for side in ("for", "against"):
        labels = sorted(
            {
                *BASE_WINDOW_LABELS,
                *(
                    label
                    for profile in profiles
                    for label in profile.get("specials", {}).get("shotsPerTenMinutes", {}).get(side, {}).keys()
                ),
            },
            key=_window_sort_key,
        )
        for label in labels:
            values = [profile.get("specials", {}).get("shotsPerTenMinutes", {}).get(side, {}).get(label) for profile in profiles]
            numeric = [float(value) for value in values if _is_finite_number(value)]
            league_average["shotsPerTenMinutes"][side][label] = sum(numeric) / len(numeric) if numeric else None
    return league_average
