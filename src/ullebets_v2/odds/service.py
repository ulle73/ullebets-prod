from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ullebets_v2.fixtures.replay import build_fixture_documents, build_support_lookup, load_fixture_payload
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.odds.discovery import (
    build_list_view_raw_doc,
    extract_league_name,
    extract_event_list,
    find_unibet_event_for_match,
    resolve_unibet_league,
)
from ullebets_v2.odds.fetch import Transport, fetch_event_odds_payload, fetch_list_view_payload
from ullebets_v2.odds.mapper import map_unibet_odds
from ullebets_v2.odds.naming import normalize_league_name, normalize_team_name
from ullebets_v2.odds.persistence import persist_odds_records
from ullebets_v2.odds.reports import (
    build_odds_audit_rows,
    build_odds_health_rows,
    build_odds_parity_rows,
)
from ullebets_v2.support.schemas import stable_json_hash, slugify


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_match_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _tuple_hash(tuples: list[dict[str, Any]]) -> str:
    payload = sorted(
        [
            {
                "statKey": row.get("statKey"),
                "scope": row.get("scope"),
                "period": row.get("period"),
                "line": row.get("line"),
                "odds": row.get("odds"),
            }
            for row in tuples
        ],
        key=lambda row: (
            str(row.get("statKey") or ""),
            str(row.get("scope") or ""),
            str(row.get("period") or ""),
            float(row.get("line") or 0),
            str(row.get("odds") or ""),
        ),
    )
    return stable_json_hash(payload)


def load_replay_fixture_targets(
    *,
    dates: list[str],
    support_docs: dict[str, Any],
    old_repo_root: Path,
    legacy_match_database: Any | None = None,
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    source_dir = old_repo_root / "matches-for-date"
    for date_str in dates:
        source_path = source_dir / f"fixtures-{date_str}.json"
        if source_path.exists():
            payload = load_fixture_payload(source_path)
            source_path_for_docs = source_path
        else:
            payload = None
            if legacy_match_database is not None:
                for doc in legacy_match_database["match-for-date"].find({}, projection={"_id": 0, "full": 1}):
                    full = doc.get("full") or []
                    if not full:
                        continue
                    entry = full[0]
                    if str(entry.get("date") or "") != date_str:
                        continue
                    payload = {
                        "date": date_str,
                        "savedAt": entry.get("savedAt"),
                        "matches": list(entry.get("matches") or []),
                    }
                    break
            if payload is None:
                continue
            source_path_for_docs = source_path
        docs = build_fixture_documents(
            payload=payload,
            support_docs=support_docs,
            source_path=source_path_for_docs,
        )
        targets.extend(docs["canonical"])
    return targets


def _legacy_target_match_confidence(
    *,
    league_found: bool,
    home_found: bool,
    away_found: bool,
) -> str:
    if league_found and home_found and away_found:
        return "support_names"
    if league_found:
        return "league_only"
    return "unmatched"


def _fallback_legacy_team_key(league_key: str, team_name: Any, *, side: str) -> str:
    normalized = slugify(str(team_name)) if team_name else f"unknown-{side}"
    return f"{league_key}:{normalized or f'unknown-{side}'}"


def _legacy_target_start_time(legacy_doc: dict[str, Any]) -> datetime | None:
    for field_name in ("startTime", "matchStartTime", "kickoffAt"):
        parsed = _parse_match_time(legacy_doc.get(field_name))
        if parsed is not None:
            return parsed
    return None


def _legacy_match_candidate_score(
    *,
    source_match_id: Any,
    home_team_name: Any,
    away_team_name: Any,
    candidate_match_id: Any,
    candidate_home_team_name: Any,
    candidate_away_team_name: Any,
) -> int:
    score = 0
    if source_match_id is not None and candidate_match_id is not None and str(source_match_id) == str(candidate_match_id):
        score += 100
    if home_team_name and normalize_team_name(candidate_home_team_name) == normalize_team_name(home_team_name):
        score += 20
    if away_team_name and normalize_team_name(candidate_away_team_name) == normalize_team_name(away_team_name):
        score += 20
    return score


def _resolve_legacy_target_start_time(
    *,
    legacy_doc: dict[str, Any],
    legacy_match_database: Any | None,
) -> datetime | None:
    direct = _legacy_target_start_time(legacy_doc)
    if direct is not None or legacy_match_database is None:
        return direct

    match_date = str(legacy_doc.get("matchDate") or "").strip()
    if not match_date:
        return None
    source_match_id = legacy_doc.get("matchId")
    home_team_name = legacy_doc.get("homeTeam")
    away_team_name = legacy_doc.get("awayTeam")

    best_score = -1
    best_timestamp: int | None = None

    for doc in legacy_match_database["match-for-date"].find({}, projection={"_id": 0, "full": 1}):
        full = doc.get("full") or []
        if not full:
            continue
        entry = full[0]
        if str(entry.get("date") or "") != match_date:
            continue
        for row in entry.get("matches") or []:
            score = _legacy_match_candidate_score(
                source_match_id=source_match_id,
                home_team_name=home_team_name,
                away_team_name=away_team_name,
                candidate_match_id=row.get("id") or row.get("matchId"),
                candidate_home_team_name=(row.get("homeTeam") or {}).get("name"),
                candidate_away_team_name=(row.get("awayTeam") or {}).get("name"),
            )
            timestamp = row.get("startTimestamp") or row.get("timestamp")
            if score > best_score and timestamp:
                best_score = score
                best_timestamp = int(timestamp)
        if best_score >= 100 and best_timestamp is not None:
            return datetime.fromtimestamp(best_timestamp, tz=UTC)

    if best_timestamp is not None and best_score >= 40:
        return datetime.fromtimestamp(best_timestamp, tz=UTC)

    projection = {"_id": 0, "full": 1, "matches": 1}
    for doc in legacy_match_database["teamstats"].find({}, projection=projection):
        rows = doc.get("full") if isinstance(doc.get("full"), list) else doc.get("matches")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if str(row.get("date") or "") != match_date:
                continue
            score = _legacy_match_candidate_score(
                source_match_id=source_match_id,
                home_team_name=home_team_name,
                away_team_name=away_team_name,
                candidate_match_id=row.get("matchId") or row.get("id"),
                candidate_home_team_name=row.get("homeTeamName"),
                candidate_away_team_name=row.get("awayTeamName"),
            )
            timestamp = row.get("timestamp") or row.get("startTimestamp")
            if score > best_score and timestamp:
                best_score = score
                best_timestamp = int(timestamp)

    if best_timestamp is None or best_score < 40:
        return None
    return datetime.fromtimestamp(best_timestamp, tz=UTC)


def load_legacy_backtest_targets(
    *,
    dates: list[str],
    support_docs: dict[str, Any],
    legacy_backtest_database: Any | None,
    legacy_match_database: Any | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if legacy_backtest_database is None or not dates:
        return []

    rows = list(
        legacy_backtest_database["unibet-backtest"].find(
            {"matchDate": {"$in": list(dates)}},
            projection={"_id": 0},
        )
    )
    lookup = build_support_lookup(support_docs)
    selected_by_match_key: dict[str, dict[str, Any]] = {}

    for legacy_doc in rows:
        match_date = str(legacy_doc.get("matchDate") or "").strip()
        if not match_date:
            continue
        league_name = legacy_doc.get("league")
        normalized_league = slugify(str(league_name)) if league_name else "unknown-league"
        league_doc = lookup.leagues_by_slug.get(normalized_league) or lookup.leagues_by_name.get(normalized_league)
        league_key = str(league_doc["league_key"]) if league_doc else normalized_league

        home_team_name = legacy_doc.get("homeTeam")
        away_team_name = legacy_doc.get("awayTeam")
        home_team = lookup.teams_by_league_and_name.get((league_key, slugify(str(home_team_name)))) if home_team_name else None
        away_team = lookup.teams_by_league_and_name.get((league_key, slugify(str(away_team_name)))) if away_team_name else None

        home_team_key = (
            str(home_team["team_key"])
            if home_team and home_team.get("team_key")
            else _fallback_legacy_team_key(league_key, home_team_name, side="home")
        )
        away_team_key = (
            str(away_team["team_key"])
            if away_team and away_team.get("team_key")
            else _fallback_legacy_team_key(league_key, away_team_name, side="away")
        )
        identity_key = "|".join([league_key, match_date, home_team_key, away_team_key])
        source_match_id = legacy_doc.get("matchId")
        event_id = legacy_doc.get("eventId")
        match_key = (
            f"sofascore:{source_match_id}"
            if source_match_id is not None
            else f"legacy-unibet:{event_id}"
            if event_id is not None
            else f"legacy-unibet:{identity_key}"
        )
        updated_at = _parse_match_time(legacy_doc.get("updatedAt")) or _parse_match_time(legacy_doc.get("generatedAt"))
        selection_time = updated_at or datetime.min.replace(tzinfo=UTC)
        candidate = {
            "match_key": match_key,
            "identity_key": identity_key,
            "source_match_id": source_match_id,
            "source_type": "legacy_unibet_backtest",
            "source_date": match_date,
            "start_time": _resolve_legacy_target_start_time(
                legacy_doc=legacy_doc,
                legacy_match_database=legacy_match_database,
            ),
            "league_key": league_key,
            "league_id": league_doc.get("league_id") if league_doc else None,
            "league_name": league_doc.get("league_name") if league_doc else league_name,
            "home_team_key": home_team_key,
            "away_team_key": away_team_key,
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "mapping_confidence": _legacy_target_match_confidence(
                league_found=league_doc is not None,
                home_found=home_team is not None,
                away_found=away_team is not None,
            ),
            "legacy_event_id": str(event_id) if event_id is not None else None,
            "_selection_time": selection_time,
        }
        previous = selected_by_match_key.get(match_key)
        if previous is None or candidate["_selection_time"] > previous["_selection_time"]:
            selected_by_match_key[match_key] = candidate

    targets = sorted(
        [
            {key: value for key, value in row.items() if key != "_selection_time"}
            for row in selected_by_match_key.values()
        ],
        key=lambda row: (
            str(row.get("source_date") or ""),
            str(row.get("match_key") or ""),
        ),
    )
    if limit is not None and limit > 0:
        return targets[:limit]
    return targets


def load_fixture_targets_from_database(
    *,
    database: Any,
    dates: list[str] | None = None,
    max_days_ahead: int = 7,
    reference_time: datetime | None = None,
    league_key: str | None = None,
    league_name: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    now = reference_time or utc_now()
    query: dict[str, Any] = {}
    if dates:
        query["source_date"] = {"$in": list(dates)}
    else:
        query["start_time"] = {
            "$gte": now,
            "$lte": now + timedelta(days=max(0, max_days_ahead)),
        }
    if league_key:
        query["league_key"] = league_key
    elif league_name:
        query["league_name"] = league_name

    rows = list(database["fixtures_canonical"].find(query, projection={"_id": 0}))
    rows.sort(
        key=lambda row: (
            _parse_match_time(row.get("start_time")) or datetime.max.replace(tzinfo=UTC),
            str(row.get("match_key") or ""),
        )
    )
    if limit is not None and limit > 0:
        return rows[:limit]
    return rows


def _target_match_date(match: dict[str, Any]) -> str | None:
    source_date = match.get("source_date")
    if isinstance(source_date, str) and source_date.strip():
        return source_date
    start_time = match.get("start_time")
    if isinstance(start_time, datetime):
        return start_time.date().isoformat()
    if isinstance(start_time, str):
        parsed = _parse_match_time(start_time)
        if parsed is not None:
            return parsed.date().isoformat()
    return None


def _find_legacy_backtest_doc(
    *,
    legacy_backtest_database: Any | None,
    match: dict[str, Any],
) -> dict[str, Any] | None:
    if legacy_backtest_database is None:
        return None
    match_date = _target_match_date(match)
    if not match_date:
        return None

    candidates = list(
        legacy_backtest_database["unibet-backtest"].find(
            {"matchDate": match_date},
            projection={"_id": 0},
        )
    )
    if not candidates:
        return None

    source_match_id = match.get("source_match_id")
    target_home = normalize_team_name(match.get("home_team_name"))
    target_away = normalize_team_name(match.get("away_team_name"))
    target_league = normalize_league_name(match.get("league_name"))

    best_doc: dict[str, Any] | None = None
    best_score = -1
    for candidate in candidates:
        score = 0
        candidate_match_id = candidate.get("matchId")
        if source_match_id is not None and candidate_match_id is not None and str(candidate_match_id) == str(source_match_id):
            score += 100
        if normalize_team_name(candidate.get("homeTeam")) == target_home:
            score += 20
        if normalize_team_name(candidate.get("awayTeam")) == target_away:
            score += 20
        if target_league and normalize_league_name(candidate.get("league")) == target_league:
            score += 5
        if score > best_score:
            best_score = score
            best_doc = candidate

    return best_doc if best_score >= 40 else None


def _normalize_legacy_direction(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"över", "over"}:
        return "over"
    if text == "under":
        return "under"
    return None


def _build_legacy_tuples(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, float], dict[str, Any]] = {}
    for line in lines:
        stat_key = line.get("statKey")
        scope = line.get("scope")
        period = line.get("period")
        line_value = line.get("line")
        direction = _normalize_legacy_direction(line.get("condition"))
        odds_value = line.get("odds")
        if not stat_key or not scope or not period or direction is None:
            continue
        if not isinstance(odds_value, (int, float)) or odds_value <= 1:
            continue
        try:
            group_key = (
                str(stat_key),
                str(scope),
                str(period),
                float(line_value),
            )
        except (TypeError, ValueError):
            continue
        entry = grouped.setdefault(
            group_key,
            {
                "statKey": stat_key,
                "scope": scope,
                "period": period,
                "line": line_value,
                "odds": {},
            },
        )
        entry["odds"][direction] = float(odds_value)
    return sorted(
        grouped.values(),
        key=lambda row: (
            str(row.get("statKey") or ""),
            str(row.get("scope") or ""),
            str(row.get("period") or ""),
            float(row.get("line") or 0),
        ),
    )


def _parse_legacy_timestamp(document: dict[str, Any], *field_names: str) -> datetime | None:
    for field_name in field_names:
        parsed = _parse_match_time(document.get(field_name))
        if parsed is not None:
            return parsed
    return None


def _build_legacy_event_link_doc(
    *,
    match: dict[str, Any],
    legacy_doc: dict[str, Any],
    imported_at: datetime,
) -> dict[str, Any]:
    event_id = legacy_doc.get("eventId")
    return {
        "event_id": str(event_id) if event_id is not None else None,
        "event_url": legacy_doc.get("url"),
        "match_key": match["match_key"],
        "source_workflow": match.get("source_workflow"),
        "league_key": match.get("league_key"),
        "league_name": match.get("league_name"),
        "home_team_name": match.get("home_team_name"),
        "away_team_name": match.get("away_team_name"),
        "canonical_home_team_name": legacy_doc.get("homeTeam") or match.get("home_team_name"),
        "canonical_away_team_name": legacy_doc.get("awayTeam") or match.get("away_team_name"),
        "match_start_time": match.get("start_time"),
        "discovered_start_time": match.get("start_time"),
        "discovered_league_name": legacy_doc.get("league") or match.get("league_name"),
        "mapping_confidence": "legacy_replay",
        "source_provider": "legacy_unibet_backtest",
        "discovered_at": imported_at,
        "list_view_payload_hash": None,
    }


def _build_legacy_raw_doc(
    *,
    match: dict[str, Any],
    legacy_doc: dict[str, Any],
    imported_at: datetime,
) -> dict[str, Any]:
    payload_hash = stable_json_hash(legacy_doc)
    event_id = legacy_doc.get("eventId")
    return {
        "raw_key": "|".join(
            [
                "legacy_unibet_backtest",
                str(event_id) if event_id is not None else "",
                str(match["match_key"]),
                payload_hash,
            ]
        ),
        "payload_hash": payload_hash,
        "payload_kind": "legacy_unibet_backtest",
        "source_provider": "legacy_unibet_backtest",
        "source_url": legacy_doc.get("url"),
        "fetched_at": imported_at,
        "match_key": match["match_key"],
        "event_id": str(event_id) if event_id is not None else None,
        "league_key": match.get("league_key"),
        "league_name": match.get("league_name"),
        "match_start_time": match.get("start_time"),
        "payload": legacy_doc,
        "bet_offer_count": len(legacy_doc.get("lines") or []),
    }


def _build_legacy_import_payload(
    *,
    match: dict[str, Any],
    legacy_doc: dict[str, Any],
    fallback_time: datetime,
) -> dict[str, Any]:
    imported_at = _parse_legacy_timestamp(legacy_doc, "updatedAt", "generatedAt") or fallback_time
    event_id = legacy_doc.get("eventId")
    event_id_str = str(event_id) if event_id is not None else None
    tuples = _build_legacy_tuples(list(legacy_doc.get("lines") or []))
    raw_doc = _build_legacy_raw_doc(
        match=match,
        legacy_doc=legacy_doc,
        imported_at=imported_at,
    )
    return {
        "event_id": event_id_str,
        "tuples": tuples,
        "tuple_hash": _tuple_hash(tuples),
        "raw_doc": raw_doc,
        "event_link_doc": _build_legacy_event_link_doc(
            match=match,
            legacy_doc=legacy_doc,
            imported_at=imported_at,
        ),
        "market_offer_docs": _build_market_offer_docs(
            match=match,
            event_id=event_id_str,
            tuples=tuples,
            raw_payload_hash=raw_doc["payload_hash"],
            fetched_at=imported_at,
        ),
        "imported_at": imported_at,
    }


def inspect_fixture_target_window_from_database(
    *,
    database: Any,
    dates: list[str] | None = None,
    max_days_ahead: int = 7,
    reference_time: datetime | None = None,
    league_key: str | None = None,
    league_name: str | None = None,
    empty_horizon_days: int = 35,
) -> dict[str, Any]:
    now = reference_time or utc_now()
    selection_mode = "dates" if dates else "rolling_window"
    context: dict[str, Any] = {
        "target_source": "fixtures_canonical",
        "selection_mode": selection_mode,
        "league_key": league_key,
        "league_name": league_name,
    }
    if dates:
        available_rows = load_fixture_targets_from_database(
            database=database,
            dates=dates,
            league_key=league_key,
            league_name=league_name,
        )
        context.update(
            {
                "requested_dates": list(dates),
                "available_target_match_count": len(available_rows),
                "next_fixture_start_time": (
                    available_rows[0]["start_time"].isoformat()
                    if available_rows and isinstance(available_rows[0].get("start_time"), datetime)
                    else None
                ),
                "empty_reason": None if available_rows else "no_fixtures_for_requested_dates",
            }
        )
        return context

    requested_window_days = max(0, max_days_ahead)
    requested_rows = load_fixture_targets_from_database(
        database=database,
        max_days_ahead=requested_window_days,
        reference_time=now,
        league_key=league_key,
        league_name=league_name,
    )
    inspection_horizon_days = max(requested_window_days, max(0, empty_horizon_days))
    horizon_rows = load_fixture_targets_from_database(
        database=database,
        max_days_ahead=inspection_horizon_days,
        reference_time=now,
        league_key=league_key,
        league_name=league_name,
    )
    requested_window_end = now + timedelta(days=requested_window_days)
    later_rows = [
        row
        for row in horizon_rows
        if isinstance(row.get("start_time"), datetime) and row["start_time"] > requested_window_end
    ]
    if requested_rows:
        empty_reason = None
    elif not horizon_rows:
        empty_reason = "no_fixtures_in_source_horizon"
    else:
        empty_reason = "no_fixtures_in_requested_window_but_present_later"
    context.update(
        {
            "window_start": now.isoformat(),
            "window_end": requested_window_end.isoformat(),
            "requested_max_days_ahead": requested_window_days,
            "inspection_horizon_days": inspection_horizon_days,
            "available_target_match_count": len(requested_rows),
            "future_fixture_count_in_horizon": len(horizon_rows),
            "future_fixture_count_after_requested_window": len(later_rows),
            "next_fixture_start_time": (
                horizon_rows[0]["start_time"].isoformat()
                if horizon_rows and isinstance(horizon_rows[0].get("start_time"), datetime)
                else None
            ),
            "next_fixture_match_key": str(horizon_rows[0].get("match_key")) if horizon_rows else None,
            "empty_reason": empty_reason,
        }
    )
    return context


def build_smoke_targets_for_league(
    *,
    league_name: str,
    support_docs: dict[str, Any],
    transport: Transport | None = None,
    limit: int = 1,
    fetched_at: datetime | None = None,
    reference_time: datetime | None = None,
    max_days_ahead: int = 7,
) -> list[dict[str, Any]]:
    league_doc = resolve_unibet_league(support_docs, league_name=league_name)
    if league_doc is None:
        raise RuntimeError(f"No support league config found for {league_name!r}")
    base_url = league_doc.get("unibet_base_url")
    if not base_url:
        raise RuntimeError(f"Support league {league_name!r} is missing unibet_base_url")
    _, payload = fetch_list_view_payload(str(base_url), transport=transport)
    now = reference_time or fetched_at or utc_now()
    window_end = now + timedelta(days=max(0, max_days_ahead))
    targets: list[dict[str, Any]] = []
    events = sorted(
        extract_event_list(payload),
        key=lambda event: _parse_match_time(event.get("start")) or datetime.max.replace(tzinfo=UTC),
    )
    for event in events:
        if not event.get("homeName") or not event.get("awayName"):
            continue
        if event.get("homeName") == event.get("awayName"):
            continue
        event_league = extract_league_name(event)
        event_league_doc = resolve_unibet_league(support_docs, league_name=event_league) if event_league else None
        if event_league_doc is not None and event_league_doc.get("league_key") != league_doc.get("league_key"):
            continue
        if event_league and event_league_doc is None:
            if normalize_league_name(event_league) != normalize_league_name(league_doc.get("league_name")):
                continue
        start_time = _parse_match_time(event.get("start"))
        if start_time is None or start_time < now or start_time > window_end:
            continue
        targets.append(
            {
                "match_key": f"smoke:{event['id']}",
                "source_type": "smoke_live_listview",
                "source_match_id": None,
                "league_key": league_doc.get("league_key"),
                "league_name": league_doc.get("league_name"),
                "home_team_name": event.get("homeName"),
                "away_team_name": event.get("awayName"),
                "start_time": start_time,
                "status_type": event.get("state"),
                "season_id": None,
                "mapping_confidence": "smoke_live",
                "source_path": None,
                "captured_at": fetched_at or now,
            }
        )
        if len(targets) >= max(1, limit):
            break
    return targets


def _build_event_link_doc(
    *,
    match: dict[str, Any],
    event: Any,
    raw_payload_hash: str,
    fetched_at: datetime,
) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_url": event.event_url,
        "match_key": match["match_key"],
        "source_workflow": match.get("source_workflow"),
        "league_key": match.get("league_key"),
        "league_name": match.get("league_name"),
        "home_team_name": match.get("home_team_name"),
        "away_team_name": match.get("away_team_name"),
        "canonical_home_team_name": event.home_team_name,
        "canonical_away_team_name": event.away_team_name,
        "match_start_time": match.get("start_time"),
        "discovered_start_time": event.start,
        "discovered_league_name": event.league_name,
        "mapping_confidence": match.get("mapping_confidence"),
        "source_provider": "kambi",
        "discovered_at": fetched_at,
        "list_view_payload_hash": raw_payload_hash,
    }


def _build_event_odds_raw_doc(
    *,
    match: dict[str, Any],
    event_id: str,
    source_url: str,
    payload: Any,
    fetched_at: datetime,
) -> dict[str, Any]:
    payload_hash = stable_json_hash(payload)
    return {
        "raw_key": "|".join(
            [
                "event_odds",
                str(event_id),
                fetched_at.isoformat(),
                str(match["match_key"]),
                payload_hash,
            ]
        ),
        "payload_hash": payload_hash,
        "payload_kind": "event_odds",
        "source_provider": "kambi",
        "source_url": source_url,
        "fetched_at": fetched_at,
        "match_key": match["match_key"],
        "event_id": event_id,
        "league_key": match.get("league_key"),
        "league_name": match.get("league_name"),
        "match_start_time": match.get("start_time"),
        "payload": payload,
        "bet_offer_count": len(payload.get("betOffers", [])) if isinstance(payload, dict) else 0,
    }


def _build_market_offer_docs(
    *,
    match: dict[str, Any],
    event_id: str,
    tuples: list[dict[str, Any]],
    raw_payload_hash: str,
    fetched_at: datetime,
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for tuple_row in tuples:
        offer_key = "|".join(
            [
                match["match_key"],
                str(tuple_row.get("statKey")),
                str(tuple_row.get("scope")),
                str(tuple_row.get("period")),
                str(tuple_row.get("line")),
            ]
        )
        odds = tuple_row.get("odds", {})
        docs.append(
            {
                "offer_key": offer_key,
                "match_key": match["match_key"],
                "event_id": event_id,
                "league_key": match.get("league_key"),
                "league_name": match.get("league_name"),
                "home_team_name": match.get("home_team_name"),
                "away_team_name": match.get("away_team_name"),
                "stat_key": tuple_row.get("statKey"),
                "scope": tuple_row.get("scope"),
                "period": tuple_row.get("period"),
                "line": tuple_row.get("line"),
                "over_odds": odds.get("over"),
                "under_odds": odds.get("under"),
                "source_provider": "kambi",
                "raw_payload_hash": raw_payload_hash,
                "updated_at": fetched_at,
            }
        )
    return docs


def run_unibet_odds_ingest(
    *,
    targets: list[dict[str, Any]],
    support_docs: dict[str, Any],
    source_workflow: str,
    database: Any | None = None,
    dry_run: bool = False,
    transport: Transport | None = None,
    oracle: Any | None = None,
    legacy_backtest_database: Any | None = None,
    fetched_at: datetime | None = None,
    return_documents: bool = False,
) -> dict[str, Any]:
    now = fetched_at or utc_now()
    list_view_cache: dict[str, tuple[dict[str, Any], list[dict[str, Any]], str]] = {}
    raw_docs: list[dict[str, Any]] = []
    event_link_docs: list[dict[str, Any]] = []
    market_offer_docs: list[dict[str, Any]] = []
    match_rows: list[dict[str, Any]] = []

    for target in targets:
        match = dict(target)
        match["source_workflow"] = source_workflow
        row: dict[str, Any] = {
            "match_key": match["match_key"],
            "v2_event_id": None,
            "oracle_event_id": None,
            "v2_tuples": [],
            "oracle_tuples": [],
            "v2_offer_count": 0,
            "oracle_offer_count": 0,
            "oracle_requested": oracle is not None,
            "oracle_available": oracle is not None,
            "oracle_error": None,
            "historical_source_checked": legacy_backtest_database is not None,
            "historical_source_found": False,
            "historical_event_id": None,
            "historical_tuples": [],
            "historical_offer_count": 0,
            "error": None,
        }
        try:
            legacy_doc = _find_legacy_backtest_doc(
                legacy_backtest_database=legacy_backtest_database,
                match=match,
            )
            if legacy_doc is not None:
                row["historical_source_found"] = True
                row["historical_event_id"] = (
                    str(legacy_doc.get("eventId"))
                    if legacy_doc.get("eventId") is not None
                    else None
                )
                row["historical_snapshot_count"] = len(legacy_doc.get("snapshots") or [])
                imported = _build_legacy_import_payload(
                    match=match,
                    legacy_doc=legacy_doc,
                    fallback_time=now,
                )
                row["historical_tuples"] = imported["tuples"]
                row["historical_offer_count"] = len(imported["tuples"])
                row["historical_tuple_hash"] = imported["tuple_hash"]
                row["v2_event_id"] = imported["event_id"]
                row["v2_tuples"] = imported["tuples"]
                row["v2_offer_count"] = len(imported["tuples"])
                row["v2_tuple_hash"] = imported["tuple_hash"]
                row["imported_from_historical"] = True
                raw_docs.append(imported["raw_doc"])
                event_link_docs.append(imported["event_link_doc"])
                market_offer_docs.extend(imported["market_offer_docs"])
                match_rows.append(row)
                continue
            if legacy_backtest_database is not None:
                match_rows.append(row)
                continue
            oracle_event: dict[str, Any] | None = None
            if oracle is not None:
                try:
                    oracle_match = {
                        "homeTeam": match.get("home_team_name"),
                        "awayTeam": match.get("away_team_name"),
                        "leagueName": match.get("league_name"),
                        "timestamp": (
                            match.get("start_time").isoformat()
                            if isinstance(match.get("start_time"), datetime)
                            else match.get("start_time")
                        ),
                    }
                    oracle_event = oracle.lookup_event(oracle_match)
                    row["oracle_event_id"] = (
                        str(oracle_event.get("eventId"))
                        if isinstance(oracle_event, dict) and oracle_event.get("eventId") is not None
                        else None
                    )
                except Exception as exc:
                    row["oracle_available"] = False
                    row["oracle_error"] = {"type": type(exc).__name__, "message": str(exc)}

            league_doc = resolve_unibet_league(
                support_docs,
                league_key=match.get("league_key"),
                league_name=match.get("league_name"),
            )
            if league_doc is None or not league_doc.get("unibet_base_url"):
                raise RuntimeError("missing_unibet_league_config")

            league_key = str(league_doc["league_key"])
            if league_key not in list_view_cache:
                source_url, payload = fetch_list_view_payload(
                    str(league_doc["unibet_base_url"]),
                    transport=transport,
                )
                raw_doc = build_list_view_raw_doc(
                    league_doc=league_doc,
                    source_url=source_url,
                    payload=payload,
                    fetched_at=now,
                )
                raw_docs.append(raw_doc)
                list_view_cache[league_key] = (raw_doc, extract_event_list(payload), source_url)

            raw_list_view_doc, events, _ = list_view_cache[league_key]
            discovered_event = find_unibet_event_for_match(
                match=match,
                list_view_events=events,
                support_docs=support_docs,
            )
            if discovered_event is not None:
                row["v2_event_id"] = discovered_event.event_id
                event_link_docs.append(
                    _build_event_link_doc(
                        match=match,
                        event=discovered_event,
                        raw_payload_hash=raw_list_view_doc["payload_hash"],
                        fetched_at=now,
                    )
                )
                event_source_url, odds_payload = fetch_event_odds_payload(
                    discovered_event.event_id,
                    transport=transport,
                )
                raw_event_doc = _build_event_odds_raw_doc(
                    match=match,
                    event_id=discovered_event.event_id,
                    source_url=event_source_url,
                    payload=odds_payload,
                    fetched_at=now,
                )
                raw_docs.append(raw_event_doc)
                tuples = map_unibet_odds(
                    odds_payload.get("betOffers", []),
                    discovered_event.home_team_name,
                    discovered_event.away_team_name,
                )
                row["v2_tuples"] = tuples
                row["v2_offer_count"] = len(tuples)
                row["v2_tuple_hash"] = _tuple_hash(tuples)
                market_offer_docs.extend(
                    _build_market_offer_docs(
                        match=match,
                        event_id=discovered_event.event_id,
                        tuples=tuples,
                        raw_payload_hash=raw_event_doc["payload_hash"],
                        fetched_at=now,
                    )
                )

                if oracle is not None and row.get("oracle_available"):
                    try:
                        oracle_tuples = oracle.map_odds(
                            odds_payload.get("betOffers", []),
                            (
                                str(oracle_event.get("homeTeam"))
                                if isinstance(oracle_event, dict) and oracle_event.get("homeTeam")
                                else discovered_event.home_team_name
                            ),
                            (
                                str(oracle_event.get("awayTeam"))
                                if isinstance(oracle_event, dict) and oracle_event.get("awayTeam")
                                else discovered_event.away_team_name
                            ),
                        )
                        row["oracle_tuples"] = oracle_tuples
                        row["oracle_offer_count"] = len(oracle_tuples)
                        row["oracle_tuple_hash"] = _tuple_hash(oracle_tuples)
                    except Exception as exc:
                        row["oracle_available"] = False
                        row["oracle_error"] = {"type": type(exc).__name__, "message": str(exc)}
        except Exception as exc:
            row["error"] = {"type": type(exc).__name__, "message": str(exc)}
        match_rows.append(row)

    report_date = now.date().isoformat()
    parity_rows = build_odds_parity_rows(
        source_workflow=source_workflow,
        match_rows=match_rows,
        report_date=report_date,
    )
    audit_rows = build_odds_audit_rows(
        source_workflow=source_workflow,
        match_rows=match_rows,
        raw_docs=raw_docs,
        market_offer_docs=market_offer_docs,
        report_date=report_date,
    )
    health_rows = build_odds_health_rows(
        match_rows=match_rows,
        report_date=report_date,
    )

    summary: dict[str, Any] = {
        "job": "ingest_unibet_odds",
        "captured_at": now.isoformat(),
        "target_matches": len(targets),
        "raw_docs": len(raw_docs),
        "event_links": len(event_link_docs),
        "market_offers": len(market_offer_docs),
        "parity_reports": len(parity_rows),
        "audit_reports": len(audit_rows),
        "health_reports": len(health_rows),
        "matched_events": sum(1 for row in match_rows if row.get("v2_event_id")),
        "errors": sum(1 for row in match_rows if row.get("error")),
        "oracle_errors": sum(1 for row in match_rows if row.get("oracle_error")),
        "historical_source_missing": sum(
            1
            for row in match_rows
            if row.get("historical_source_checked") and not row.get("historical_source_found")
        ),
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
        "match_rows": match_rows,
    }
    if return_documents:
        summary["documents"] = {
            "raw_docs": raw_docs,
            "event_link_docs": event_link_docs,
            "market_offer_docs": market_offer_docs,
            "parity_rows": parity_rows,
            "audit_rows": audit_rows,
            "health_rows": health_rows,
        }
    job_metrics = {key: value for key, value in summary.items() if key != "match_rows"}
    job_metrics.pop("documents", None)

    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    job_collection = database["job_runs"]
    run_doc = build_job_run_started_doc(
        job_name="ingest_unibet_odds",
        source_workflow=source_workflow,
        target_window={"match_count": len(targets), "captured_at": now.isoformat()},
        job_args={"dry_run": False},
    )
    job_collection.insert_one(run_doc)
    try:
        metrics = persist_odds_records(
            database,
            raw_docs=raw_docs,
            event_link_docs=event_link_docs,
            market_offer_docs=market_offer_docs,
            parity_rows=parity_rows,
            audit_rows=audit_rows,
            health_rows=health_rows,
        )
        job_collection.update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics={**metrics, **job_metrics},
            ),
        )
    except Exception as exc:
        job_collection.update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="failed",
                metrics=job_metrics,
                error={"type": type(exc).__name__, "message": str(exc)},
            ),
        )
        raise
    return summary
