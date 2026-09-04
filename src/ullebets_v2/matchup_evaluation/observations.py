from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from math import isfinite
from typing import Any, Iterable

from pymongo import UpdateOne


MATCHUP_EVALUATION_POLICY_VERSION = "matchup-eval-v1"
CHECKPOINT_LABEL = "T_MINUS_1D"
COMPARABLE_ODDS_MIN = 1.80
COMPARABLE_ODDS_MAX = 2.20
FINGERPRINT_EXCLUDED_FIELDS = {"_id", "journaled_at", "observation_fingerprint_sha256"}
DATABASE_QUERY_BATCH_SIZE = 100


class ImmutableMatchupObservationConflict(RuntimeError):
    pass


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=UTC)
        parsed = parsed.astimezone(UTC)
        # BSON persists datetimes with millisecond precision. Hash that durable
        # representation so a freshly written observation still validates
        # after a database round trip.
        parsed = parsed.replace(microsecond=(parsed.microsecond // 1000) * 1000)
        return parsed.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def _utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)


def observation_key(match_key: str, stat_key: str, period: str, scope: str) -> str:
    values = [match_key, stat_key, period, scope]
    if any(not str(value).strip() for value in values):
        raise ValueError("matchup observation identity requires match, stat, period, and scope")
    return "|".join([MATCHUP_EVALUATION_POLICY_VERSION, *map(str, values), CHECKPOINT_LABEL])


def observation_fingerprint(doc: dict[str, Any]) -> str:
    payload = {key: value for key, value in doc.items() if key not in FINGERPRINT_EXCLUDED_FIELDS}
    encoded = json.dumps(
        _json_value(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def select_comparable_offer(snapshot_rows: Iterable[dict[str, Any]], direction: str) -> dict[str, Any] | None:
    direction = direction.lower()
    if direction not in {"over", "under"}:
        return None
    candidates: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for source in snapshot_rows:
        row = dict(source)
        if row.get("snapshot_label") != CHECKPOINT_LABEL or row.get("invalid_for_model") is True:
            continue
        line = _finite_float(row.get("line"))
        over_odds = _finite_float(row.get("over_odds"))
        under_odds = _finite_float(row.get("under_odds"))
        selected_odds = over_odds if direction == "over" else under_odds
        observed_at = _utc_datetime(row.get("snapshot_time"))
        kickoff = _utc_datetime(row.get("match_start_time"))
        if None in (line, over_odds, under_odds, selected_odds, observed_at):
            continue
        if over_odds <= 1.0 or under_odds <= 1.0 or not COMPARABLE_ODDS_MIN <= selected_odds <= COMPARABLE_ODDS_MAX:
            continue
        if kickoff is not None and observed_at >= kickoff:
            continue
        candidates.append(((abs(selected_odds - 2.0), observed_at, line, str(row.get("offer_key") or "")), row))
    return dict(min(candidates, key=lambda item: item[0])[1]) if candidates else None


def _context_matches(row: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return all(str(row.get(field) or "") == str(candidate.get(field) or "") for field in ("match_key", "stat_key", "period", "scope"))


def build_matchup_observation_docs(
    *,
    fixture: dict[str, Any],
    matchup_rows: list[dict[str, Any]],
    market_snapshot_rows: list[dict[str, Any]],
    captured_at: datetime,
) -> list[dict[str, Any]]:
    kickoff = _utc_datetime(fixture.get("start_time"))
    captured = _utc_datetime(captured_at)
    if kickoff is None or captured is None:
        raise ValueError("fixture kickoff and captured_at are required")
    minutes_to_kickoff = (kickoff - captured).total_seconds() / 60.0
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in matchup_rows:
        key = tuple(str(row.get(field) or "") for field in ("match_key", "stat_key", "period", "scope"))
        if all(key):
            grouped.setdefault(key, []).append(row)
    docs: list[dict[str, Any]] = []
    for (_, stat_key, period, scope), rows in sorted(grouped.items()):
        by_direction = {str(row.get("condition") or "").lower(): row for row in rows if str(row.get("condition") or "").lower() in {"over", "under"}}
        over = by_direction.get("over")
        under = by_direction.get("under")
        if over is None or under is None:
            continue
        over_score = _finite_float(over.get("score"))
        under_score = _finite_float(under.get("score"))
        if over_score is None or under_score is None:
            continue
        tie = over_score == under_score
        selected = None if tie else over if over_score > under_score else under
        direction = None if selected is None else str(selected.get("condition")).lower()
        offer_rows = [row for row in market_snapshot_rows if _context_matches(over, row)]
        offer = select_comparable_offer(offer_rows, direction or "")
        timing_valid = 18 * 60 <= minutes_to_kickoff < 36 * 60
        forecast = selected.get("forecast") if selected and isinstance(selected.get("forecast"), dict) else {}
        exclusion_reason = "direction_tie" if tie else None if timing_valid else "outside_t1d_window"
        doc = {
            "observation_key": observation_key(str(fixture["match_key"]), stat_key, period, scope),
            "policy_version": MATCHUP_EVALUATION_POLICY_VERSION,
            "checkpoint_label": CHECKPOINT_LABEL,
            "evidence_class": "forward",
            "match_key": str(fixture["match_key"]),
            "fixture_date_stockholm": fixture.get("fixture_date_stockholm"),
            "match_start_time": kickoff,
            "league_key": fixture.get("league_key"),
            "league_name": fixture.get("league_name"),
            "home_team_name": fixture.get("home_team_name"),
            "away_team_name": fixture.get("away_team_name"),
            "stat_key": stat_key,
            "stat_label": (selected or over).get("stat_label"),
            "period": period,
            "period_label": (selected or over).get("period_label"),
            "scope": scope,
            "selected_direction": direction,
            "score": _finite_float((selected or over).get("score")),
            "rank_position": (selected or over).get("rank_position"),
            "league_baseline": _finite_float(forecast.get("leagueBaseline")),
            "ranking_method": (selected or over).get("ranking_method"),
            "ranking_window_matches": (selected or over).get("ranking_window_matches"),
            "ranking_recency_half_life_days": (selected or over).get("ranking_recency_half_life_days"),
            "captured_at": captured,
            "minutes_to_kickoff": minutes_to_kickoff,
            "valid_for_predictor": bool(direction and timing_valid),
            "market_eligibility": "eligible" if offer is not None else "no_exact_market",
            "offer_key": offer.get("offer_key") if offer else None,
            "snapshot_key": offer.get("snapshot_key") if offer else None,
            "line_value": _finite_float(offer.get("line")) if offer else None,
            "selected_odds": _finite_float(offer.get(f"{direction}_odds")) if offer and direction else None,
            "exclusion_reason": exclusion_reason,
            "journaled_at": captured,
        }
        doc["observation_fingerprint_sha256"] = observation_fingerprint(doc)
        docs.append(doc)
    return docs


def persist_matchup_observations(collection: Any, docs: Iterable[dict[str, Any]]) -> dict[str, int]:
    metrics = {"inserted": 0, "existing": 0, "conflicts": 0}
    prepared: dict[str, dict[str, Any]] = {}
    for source in docs:
        doc = dict(source)
        key = str(doc.get("observation_key") or "")
        fingerprint = observation_fingerprint(doc)
        if not key or doc.get("observation_fingerprint_sha256") != fingerprint:
            metrics["conflicts"] += 1
            raise ImmutableMatchupObservationConflict(f"invalid immutable matchup observation fingerprint: {key}")
        if key in prepared and observation_fingerprint(prepared[key]) != fingerprint:
            metrics["conflicts"] += 1
            raise ImmutableMatchupObservationConflict(f"duplicate immutable matchup observation conflict: {key}")
        prepared[key] = doc
    keys = list(prepared)
    existing: dict[str, dict[str, Any]] = {}
    for start in range(0, len(keys), DATABASE_QUERY_BATCH_SIZE):
        batch = keys[start : start + DATABASE_QUERY_BATCH_SIZE]
        existing.update(
            {
                str(row.get("observation_key")): row
                for row in collection.find(
                    {"observation_key": {"$in": batch}},
                    projection={"_id": 0},
                )
            }
        )
    for key, stored in existing.items():
        stored_fp = observation_fingerprint(stored)
        if stored.get("observation_fingerprint_sha256") != stored_fp or stored_fp != observation_fingerprint(prepared[key]):
            metrics["conflicts"] += 1
            raise ImmutableMatchupObservationConflict(f"immutable matchup observation conflict: {key}")
    metrics["existing"] = len(existing)
    missing = [(key, doc) for key, doc in prepared.items() if key not in existing]
    if missing:
        bulk_write = getattr(collection, "bulk_write", None)
        if callable(bulk_write):
            for start in range(0, len(missing), 100):
                batch = missing[start : start + 100]
                result = bulk_write([UpdateOne({"observation_key": key}, {"$setOnInsert": doc}, upsert=True) for key, doc in batch], ordered=False)
                inserted = int(result.upserted_count)
                metrics["inserted"] += inserted
                metrics["existing"] += len(batch) - inserted
        elif hasattr(collection, "docs"):
            collection.docs.extend(dict(doc) for _, doc in missing)
            metrics["inserted"] = len(missing)
        else:
            for key, doc in missing:
                collection.update_one({"observation_key": key}, {"$setOnInsert": doc}, upsert=True)
            metrics["inserted"] = len(missing)
    return metrics
