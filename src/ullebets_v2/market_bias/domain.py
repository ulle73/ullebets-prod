from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from math import sqrt
from statistics import NormalDist
from typing import Any, Iterable, Literal

MARKET_BIAS_METHOD_VERSION = "main_line_residual_v1"
PRIMARY_BIAS_STATS = frozenset({"cornerKicks", "totalShots", "shotsOnGoal"})
MAX_OBSERVATIONS = 12
RECENCY_HALF_LIFE_DAYS = 45.0
PRIOR_ALPHA = 3.0
PRIOR_BETA = 3.0
MIN_REAL_OBSERVATIONS = 6
MIN_EFFECTIVE_OBSERVATIONS = 4.0

SourceKind = Literal["offline_v1_bootstrap", "v2_forward"]


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def _required_text(row: dict[str, Any], field: str) -> str:
    value = str(row.get(field) or "").strip()
    if not value:
        raise ValueError(f"{field} is required.")
    return value


def _number(row: dict[str, Any], field: str) -> float:
    value = row.get(field)
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric.")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric.") from exc


def select_main_line(*, snapshots: Iterable[dict[str, Any]], match_start_time: datetime) -> dict[str, Any] | None:
    """Select a reproducible near-even over line from the latest valid batch."""
    kickoff = _as_utc(match_start_time)
    if kickoff is None:
        raise ValueError("match_start_time must be a datetime.")
    valid: list[tuple[datetime, dict[str, Any], float]] = []
    for snapshot in snapshots:
        snapshot_time = _as_utc(snapshot.get("snapshot_time"))
        if snapshot_time is None or snapshot_time >= kickoff or snapshot.get("invalid_for_model") is True:
            continue
        try:
            over_odds = _number(snapshot, "over_odds")
        except ValueError:
            continue
        if 1.70 <= over_odds <= 2.30:
            valid.append((snapshot_time, dict(snapshot), over_odds))
    if not valid:
        return None
    latest_time = max(row[0] for row in valid)
    latest_batch = [row for row in valid if row[0] == latest_time]
    latest_batch.sort(
        key=lambda row: (
            abs(row[2] - 2.0),
            _number(row[1], "line_value"),
            str(row[1].get("offer_key") or ""),
            str(row[1].get("snapshot_key") or ""),
        )
    )
    selected = latest_batch[0][1]
    selected["snapshot_time"] = latest_time
    selected["over_odds"] = latest_batch[0][2]
    return selected


def _observation_key(*, match_key: str, team_key: str, venue_context: str, market_scope: str, stat_key: str, period: str, snapshot_key: str) -> str:
    identity = "|".join((match_key, team_key, venue_context, market_scope, stat_key, period, snapshot_key))
    return f"market-bias:{sha256(identity.encode('utf-8')).hexdigest()}"


def build_observation_docs(
    *,
    selected: dict[str, Any],
    actual_value: float,
    fixture: dict[str, Any],
    outcome_available_at: datetime,
    source_kind: SourceKind,
    source_record_key: str,
    source_payload_hash: str,
    run_id: str,
) -> list[dict[str, Any]]:
    """Build contextual immutable observations from one exact canonical outcome."""
    market_scope = _required_text(selected, "market_scope")
    if market_scope not in {"home", "away", "total"}:
        raise ValueError("market_scope must be home, away, or total.")
    stat_key = _required_text(selected, "stat_key")
    if stat_key not in PRIMARY_BIAS_STATS:
        raise ValueError("stat_key is not supported for market bias.")
    period = _required_text(selected, "period")
    line_value = _number(selected, "line_value")
    actual = float(actual_value)
    snapshot_time = _as_utc(selected.get("snapshot_time"))
    match_start_time = _as_utc(fixture.get("match_start_time"))
    available_at = _as_utc(outcome_available_at)
    if snapshot_time is None or match_start_time is None or available_at is None:
        raise ValueError("snapshot, match start, and outcome availability timestamps are required.")
    if snapshot_time >= match_start_time:
        raise ValueError("market-bias observation cannot use snapshot at or after kickoff.")
    snapshot_key = _required_text(selected, "snapshot_key")
    match_key = _required_text(fixture, "match_key")
    base = {
        "match_key": match_key,
        "source_match_id": _required_text(fixture, "source_match_id"),
        "league_key": _required_text(fixture, "league_key"),
        "market_scope": market_scope,
        "stat_key": stat_key,
        "period": period,
        "line_value": line_value,
        "over_odds": _number(selected, "over_odds"),
        "under_odds": selected.get("under_odds"),
        "actual_value": actual,
        "residual_value": actual - line_value,
        "line_result": "over" if actual > line_value else "under" if actual < line_value else "push",
        "snapshot_key": snapshot_key,
        "snapshot_label": _required_text(selected, "snapshot_label"),
        "snapshot_time": snapshot_time,
        "match_start_time": match_start_time,
        "minutes_to_kickoff": (match_start_time - snapshot_time).total_seconds() / 60.0,
        "outcome_available_at": available_at,
        "source_kind": source_kind,
        "source_record_key": _required_text({"source_record_key": source_record_key}, "source_record_key"),
        "source_payload_hash": _required_text({"source_payload_hash": source_payload_hash}, "source_payload_hash"),
        "line_selection_method": "latest_valid_prematch_near_even_over",
        "method_version": MARKET_BIAS_METHOD_VERSION,
        "created_at": available_at,
        "run_id": _required_text({"run_id": run_id}, "run_id"),
    }
    contexts = (
        [("home_team_key", "home")]
        if market_scope == "home"
        else [("away_team_key", "away")]
        if market_scope == "away"
        else [("home_team_key", "home"), ("away_team_key", "away")]
    )
    docs: list[dict[str, Any]] = []
    for team_field, venue_context in contexts:
        team_key = _required_text(fixture, team_field)
        docs.append(
            {
                **base,
                "team_key": team_key,
                "venue_context": venue_context,
                "observation_key": _observation_key(
                    match_key=match_key,
                    team_key=team_key,
                    venue_context=venue_context,
                    market_scope=market_scope,
                    stat_key=stat_key,
                    period=period,
                    snapshot_key=snapshot_key,
                ),
            }
        )
    return docs


def build_profile_key(
    *,
    profile_date: str,
    team_key: str,
    league_key: str,
    venue_context: str,
    market_scope: str,
    stat_key: str,
    period: str,
    method_version: str,
) -> str:
    return "|".join(("market-bias", profile_date, team_key, league_key, venue_context, market_scope, stat_key, period, method_version))


def build_bias_profile(
    observations: Iterable[dict[str, Any]],
    *,
    as_of: datetime,
    profile_date: str,
    run_id: str,
) -> dict[str, Any]:
    """Build one exact-context profile using only results available before ``as_of``."""
    cutoff = _as_utc(as_of)
    if cutoff is None:
        raise ValueError("as_of must be a datetime.")
    eligible: list[dict[str, Any]] = []
    for observation in observations:
        snapshot_time = _as_utc(observation.get("snapshot_time"))
        match_start_time = _as_utc(observation.get("match_start_time"))
        outcome_available_at = _as_utc(observation.get("outcome_available_at"))
        if (
            snapshot_time is None
            or match_start_time is None
            or outcome_available_at is None
            or snapshot_time >= match_start_time
            or outcome_available_at >= cutoff
            or match_start_time >= cutoff
            or observation.get("invalid_for_model") is True
        ):
            continue
        eligible.append({**observation, "snapshot_time": snapshot_time, "match_start_time": match_start_time})
    if not eligible:
        raise ValueError("No leakage-safe market-bias observations are available.")
    eligible.sort(key=lambda row: (row["match_start_time"], row["observation_key"]), reverse=True)
    context_fields = ("team_key", "league_key", "venue_context", "market_scope", "stat_key", "period")
    identity = eligible[0]
    if any(any(row.get(field) != identity.get(field) for field in context_fields) for row in eligible):
        raise ValueError("All observations must share one exact market-bias context.")
    window = eligible[:MAX_OBSERVATIONS]

    weighted_over = weighted_non_push = weighted_residual = total_weight = squared_weight = 0.0
    over_count = under_count = push_count = 0
    quality_counts: dict[str, int] = {}
    for row in window:
        age_days = max(0.0, (cutoff - row["match_start_time"]).total_seconds() / 86400.0)
        weight = 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)
        total_weight += weight
        squared_weight += weight * weight
        result = str(row.get("line_result") or "")
        residual = _number(row, "residual_value")
        weighted_residual += weight * residual
        label = str(row.get("snapshot_label") or "missing")
        quality_counts[label] = quality_counts.get(label, 0) + 1
        if result == "over":
            over_count += 1
            weighted_over += weight
            weighted_non_push += weight
        elif result == "under":
            under_count += 1
            weighted_non_push += weight
        elif result == "push":
            push_count += 1
        else:
            raise ValueError("line_result must be over, under, or push.")
    non_push_count = over_count + under_count
    posterior_rate = (PRIOR_ALPHA + weighted_over) / (PRIOR_ALPHA + PRIOR_BETA + weighted_non_push)
    weighted_mean = weighted_residual / total_weight if total_weight else 0.0
    shrunk_mean = weighted_residual / (PRIOR_ALPHA + PRIOR_BETA + total_weight)
    effective_n = total_weight * total_weight / squared_weight if squared_weight else 0.0
    standard_error = sqrt(max(posterior_rate * (1.0 - posterior_rate), 1e-12) / max(effective_n, 1e-12))
    confidence = NormalDist().cdf(abs(posterior_rate - 0.5) / standard_error)
    sufficient = len(window) >= MIN_REAL_OBSERVATIONS and effective_n >= MIN_EFFECTIVE_OBSERVATIONS
    if not sufficient:
        direction, strength = "insufficient", "none"
    elif (posterior_rate > 0.5 and shrunk_mean <= 0.0) or (posterior_rate < 0.5 and shrunk_mean >= 0.0) or confidence < 0.80:
        direction, strength = "neutral", "none"
    else:
        direction = "over" if posterior_rate > 0.5 else "under"
        strength = "very_strong" if confidence >= 0.97 else "strong" if confidence >= 0.90 else "lean"
    profile_key = build_profile_key(
        profile_date=profile_date,
        team_key=_required_text(identity, "team_key"),
        league_key=_required_text(identity, "league_key"),
        venue_context=_required_text(identity, "venue_context"),
        market_scope=_required_text(identity, "market_scope"),
        stat_key=_required_text(identity, "stat_key"),
        period=_required_text(identity, "period"),
        method_version=MARKET_BIAS_METHOD_VERSION,
    )
    return {
        "profile_key": profile_key,
        "profile_date": profile_date,
        "as_of": cutoff,
        **{field: identity[field] for field in context_fields},
        "method_version": MARKET_BIAS_METHOD_VERSION,
        "direction": direction,
        "strength": strength,
        "sample_size": len(window),
        "non_push_sample_size": non_push_count,
        "effective_sample_size": effective_n,
        "over_count": over_count,
        "under_count": under_count,
        "push_count": push_count,
        "raw_over_rate": over_count / non_push_count if non_push_count else None,
        "posterior_over_rate": posterior_rate,
        "weighted_mean_residual": weighted_mean,
        "shrunk_mean_residual": shrunk_mean,
        "direction_confidence": confidence,
        "latest_observation_at": max(row["match_start_time"] for row in window),
        "oldest_observation_at": min(row["match_start_time"] for row in window),
        "snapshot_quality_counts": quality_counts,
        "observation_keys": [str(row["observation_key"]) for row in window],
        "generated_at": cutoff,
        "run_id": _required_text({"run_id": run_id}, "run_id"),
    }
