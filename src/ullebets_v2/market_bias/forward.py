from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from ullebets_v2.market_bias.domain import build_observation_docs, select_main_line
from ullebets_v2.market_bias.service import MarketBiasCandidate


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value) / 1000 if abs(float(value)) >= 1e12 else float(value)
        return datetime.fromtimestamp(seconds, tz=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _canonical_hash(row: dict[str, Any]) -> str:
    payload = {key: value for key, value in row.items() if key != "_id"}
    encoded = json.dumps(payload, default=str, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _audit() -> dict[str, Any]:
    return {
        "accepted_observation_count": 0,
        "missing_actual_count": 0,
        "timing_rejection_count": 0,
        "missing_result_availability_count": 0,
        "qualifying_line_failure_count": 0,
    }


def load_forward_candidates(
    database: Any,
    *,
    from_date: str,
    to_date: str,
    as_of: datetime,
    run_id: str,
) -> tuple[list[MarketBiasCandidate], dict[str, Any]]:
    audit = _audit()
    fixtures = list(
        database["fixtures_canonical"].find(
            {"source_date": {"$gte": from_date, "$lte": to_date}}
        )
    )
    match_keys = [str(row["match_key"]) for row in fixtures if row.get("match_key")]
    if not match_keys:
        return [], audit

    query = {"match_key": {"$in": match_keys}}
    results = {
        str(row["match_key"]): row
        for row in database["match_results_canonical"].find(query)
        if row.get("match_key")
    }
    stats_by_match: dict[str, list[dict[str, Any]]] = {}
    for row in database["match_stats_canonical"].find(query):
        stats_by_match.setdefault(str(row.get("match_key")), []).append(row)
    snapshots_by_match: dict[str, list[dict[str, Any]]] = {}
    for row in database["market_snapshots"].find(query):
        snapshots_by_match.setdefault(str(row.get("match_key")), []).append(row)

    candidates: list[MarketBiasCandidate] = []
    for fixture in fixtures:
        match_key = str(fixture.get("match_key") or "")
        result = results.get(match_key)
        outcome_available_at = _time(result.get("fetched_at")) if result else None
        if outcome_available_at is None or outcome_available_at >= as_of:
            audit["missing_result_availability_count"] += 1
            continue

        match_start_time = _time(fixture.get("start_time") or fixture.get("match_start_time"))
        for stat in stats_by_match.get(match_key, []):
            actual_value = stat.get("actual_value")
            if actual_value is None:
                audit["missing_actual_count"] += 1
                continue

            context = (stat.get("stat_key"), stat.get("scope"), stat.get("period"))
            eligible: list[dict[str, Any]] = []
            for snapshot in snapshots_by_match.get(match_key, []):
                snapshot_context = (
                    snapshot.get("stat_key"),
                    snapshot.get("market_scope", snapshot.get("scope")),
                    snapshot.get("period"),
                )
                snapshot_time = _time(snapshot.get("snapshot_time"))
                if snapshot_context != context:
                    continue
                if (
                    snapshot.get("invalid_for_model")
                    or snapshot_time is None
                    or match_start_time is None
                    or snapshot_time >= match_start_time
                ):
                    audit["timing_rejection_count"] += 1
                    continue
                eligible.append(
                    {
                        **snapshot,
                        "snapshot_time": snapshot_time,
                        "line_value": snapshot.get("line"),
                        "market_scope": snapshot.get("market_scope", snapshot.get("scope")),
                    }
                )

            selected = select_main_line(
                snapshots=eligible,
                match_start_time=match_start_time,
            )
            if selected is None:
                audit["qualifying_line_failure_count"] += 1
                continue

            docs = build_observation_docs(
                selected=selected,
                actual_value=float(actual_value),
                fixture={
                    "match_key": match_key,
                    "source_match_id": fixture.get("source_match_id", match_key),
                    "league_key": fixture["league_key"],
                    "home_team_key": fixture["home_team_key"],
                    "away_team_key": fixture["away_team_key"],
                    "match_start_time": match_start_time,
                },
                outcome_available_at=outcome_available_at,
                source_kind="v2_forward",
                source_record_key=f"v2:{match_key}:{context}",
                source_payload_hash=_canonical_hash(stat),
                run_id=run_id,
            )
            candidates.append(MarketBiasCandidate(observation_docs=tuple(docs)))
            audit["accepted_observation_count"] += len(docs)

    if candidates:
        candidates[0] = MarketBiasCandidate(
            observation_docs=candidates[0].observation_docs,
            metrics=audit,
        )
    return candidates, audit
