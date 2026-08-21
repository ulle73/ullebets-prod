from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

import duckdb

from ullebets_v2.market_bias.domain import build_observation_docs, select_main_line
from ullebets_v2.market_bias.service import MarketBiasCandidate


def _rows(path: Path) -> list[dict[str, Any]]:
    return duckdb.sql("SELECT * FROM read_parquet(?)", params=[str(path)]).df().to_dict("records")


def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def build_bootstrap_candidates(directory: Path, *, support_docs: dict[str, Any], as_of: datetime, run_id: str) -> tuple[list[MarketBiasCandidate], dict[str, Any]]:
    snapshots = _rows(directory / "market_snapshots.parquet")
    lines = {str(row["match_id"]): row for row in _rows(directory / "market_lines.parquet")}
    teams = support_docs.get("teams", [])
    leagues = support_docs.get("leagues", [])
    league_map = {_norm(row.get("league_name")): str(row.get("league_key")) for row in leagues if row.get("league_key")}
    by_id: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_name: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for team in teams:
        league = str(team.get("league_key") or "")
        for source_id in (team.get("source_team_id"), team.get("opta_id")):
            if source_id not in {None, ""}:
                by_id.setdefault((league, str(source_id)), []).append(team)
        by_name.setdefault((league, _norm(team.get("team_name"))), []).append(team)
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in snapshots:
        grouped.setdefault((str(row.get("match_id")), str(row.get("stat_key")), str(row.get("scope")), str(row.get("period"))), []).append(row)
    candidates: list[MarketBiasCandidate] = []
    audit = {"accepted_observation_count": 0, "ambiguous_identity_count": 0, "unmatched_identity_count": 0, "timing_rejection_count": 0, "qualifying_line_failure_count": 0}
    for (match_id, stat, scope, period), rows in grouped.items():
        line = lines.get(match_id)
        if not line or not line.get("has_authoritative_teamstats_outcome"):
            continue
        league_key = league_map.get(_norm(line.get("league_name")))
        kickoff = _time(line.get("kickoff_ts"))
        if not league_key or kickoff is None:
            audit["unmatched_identity_count"] += 1
            continue
        def resolve(side: str) -> dict[str, Any] | None:
            source_id = line.get(f"{side}_team_id")
            matches = by_id.get((league_key, str(source_id)), []) if source_id not in {None, ""} else []
            if not matches:
                matches = by_name.get((league_key, _norm(line.get(f"{side}_team_name"))), [])
            if len(matches) != 1:
                audit["ambiguous_identity_count" if len(matches) > 1 else "unmatched_identity_count"] += 1
                return None
            return matches[0]
        home, away = resolve("home"), resolve("away")
        if home is None or away is None:
            continue
        normalized = [{"snapshot_key": sha256(f"{match_id}|{r.get('bet_key')}|{r.get('snapshot_fetched_at')}".encode()).hexdigest(), "snapshot_label": r.get("snapshot_type"), "snapshot_time": _time(r.get("snapshot_fetched_at")), "invalid_for_model": False, "line_value": r.get("line_value"), "over_odds": r.get("odds_decimal") if r.get("direction") == "over" else None, "under_odds": r.get("odds_decimal") if r.get("direction") == "under" else None, "offer_key": r.get("bet_key"), "market_scope": r.get("scope"), "stat_key": r.get("stat_key"), "period": r.get("period")} for r in rows if r.get("is_primary_modeled_stat")]
        selected = select_main_line(snapshots=normalized, match_start_time=kickoff)
        if selected is None:
            audit["qualifying_line_failure_count"] += 1
            continue
        docs = build_observation_docs(selected=selected, actual_value=float(line["actual_value"]), fixture={"match_key": f"offline:{match_id}", "source_match_id": match_id, "league_key": league_key, "home_team_key": home["team_key"], "away_team_key": away["team_key"], "match_start_time": kickoff}, outcome_available_at=kickoff + timedelta(hours=3), source_kind="offline_v1_bootstrap", source_record_key=f"offline:{match_id}:{stat}:{scope}:{period}", source_payload_hash=sha256(repr(sorted(line.items())).encode()).hexdigest(), run_id=run_id)
        candidates.append(MarketBiasCandidate(observation_docs=tuple(docs)))
        audit["accepted_observation_count"] += len(docs)
    return candidates, audit
