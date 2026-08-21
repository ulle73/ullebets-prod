from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from unicodedata import normalize

import duckdb

from ullebets_v2.market_bias.domain import build_observation_docs, select_main_line
from ullebets_v2.market_bias.service import MarketBiasCandidate


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value) / 1000 if abs(float(value)) >= 1e12 else float(value)
        return datetime.fromtimestamp(seconds, tz=UTC)
    if isinstance(value, str) and value.strip().replace(".", "", 1).isdigit():
        seconds = float(value) / 1000 if abs(float(value)) >= 1e12 else float(value)
        return datetime.fromtimestamp(seconds, tz=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _norm(value: Any) -> str:
    return " ".join(normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold().replace("-", " ").split())


def _rows(connection: duckdb.DuckDBPyConnection, sql: str, params: list[str]) -> list[dict[str, Any]]:
    cursor = connection.execute(sql, params)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def _increment_distribution(audit: dict[str, Any], docs: list[dict[str, Any]]) -> None:
    distributions = {
        "counts_by_league": "league_key",
        "counts_by_stat": "stat_key",
        "counts_by_scope": "market_scope",
        "counts_by_period": "period",
        "counts_by_snapshot_label": "snapshot_label",
    }
    for document in docs:
        for metric, field in distributions.items():
            value = str(document.get(field) or "missing")
            audit[metric][value] = int(audit[metric].get(value, 0)) + 1


def build_bootstrap_candidates(directory: Path, *, support_docs: dict[str, Any], as_of: datetime, run_id: str) -> tuple[list[MarketBiasCandidate], dict[str, Any]]:
    con = duckdb.connect()
    snapshot_path = str(directory / "market_snapshots.parquet")
    line_path = str(directory / "market_lines.parquet")
    snapshots = _rows(con, "SELECT match_id, bet_key, snapshot_type, snapshot_fetched_at, stat_key, period, scope, direction, line_value, odds_decimal FROM read_parquet(?) WHERE is_primary_modeled_stat = true AND direction IN ('over', 'under')", [snapshot_path])
    line_columns = {row[0] for row in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [line_path]).fetchall()}
    required = ["match_id", "bet_key", "stat_key", "period", "scope", "direction", "line_value", "actual_value", "league_name", "home_team_name", "away_team_name", "home_team_id", "away_team_id", "kickoff_ts", "teamstats_saved_at", "has_authoritative_teamstats_outcome"]
    projection = ", ".join(
        f"lines.{column}" if column in line_columns else f"NULL AS {column}"
        for column in required
    )
    lines = _rows(
        con,
        f"""
        WITH selected_snapshots AS (
            SELECT DISTINCT match_id, bet_key, stat_key, period, scope, direction, line_value
            FROM read_parquet(?)
            WHERE is_primary_modeled_stat = true
              AND direction IN ('over', 'under')
        )
        SELECT {projection}
        FROM read_parquet(?) AS lines
        WHERE lines.has_authoritative_teamstats_outcome = true
          AND EXISTS (
              SELECT 1
              FROM selected_snapshots AS snapshots
              WHERE snapshots.match_id = lines.match_id
                AND (
                    snapshots.bet_key = lines.bet_key
                    OR (
                        snapshots.stat_key = lines.stat_key
                        AND snapshots.period = lines.period
                        AND snapshots.scope = lines.scope
                        AND snapshots.direction = lines.direction
                        AND snapshots.line_value = lines.line_value
                    )
                )
          )
        """,
        [snapshot_path, line_path],
    )
    exact = {(str(row["match_id"]), str(row.get("bet_key"))): row for row in lines}
    tuple_lines: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for line in lines:
        key = (str(line["match_id"]), line["stat_key"], line["scope"], line["period"], line["line_value"], line["direction"])
        tuple_lines.setdefault(key, []).append(line)
    league_keys: dict[str, str] = {}
    for league in support_docs.get("leagues", []):
        for alias in [league.get("league_name"), league.get("league_key"), *(league.get("unibet_lookup_slugs") or [])]:
            league_keys[_norm(alias)] = str(league["league_key"])
    team_ids: dict[tuple[str, str], list[dict[str, Any]]] = {}
    team_names: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for team in support_docs.get("teams", []):
        league_key = str(team.get("league_key") or "")
        for source_id in (team.get("team_id"), team.get("source_team_id")):
            if source_id not in {None, ""}:
                team_ids.setdefault((league_key, str(source_id)), []).append(team)
        team_names.setdefault((league_key, _norm(team.get("team_name"))), []).append(team)
    batches: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for snapshot in snapshots:
        line = exact.get((str(snapshot["match_id"]), str(snapshot.get("bet_key"))))
        if line is None:
            fallback = tuple_lines.get((str(snapshot["match_id"]), snapshot["stat_key"], snapshot["scope"], snapshot["period"], snapshot["line_value"], snapshot["direction"]), [])
            line = fallback[0] if len(fallback) == 1 else None
        if line is None:
            continue
        key = (snapshot["match_id"], snapshot["stat_key"], snapshot["period"], snapshot["scope"])
        batches.setdefault(key, []).append({"snapshot": snapshot, "line": line})
    audit: dict[str, Any] = {"accepted_observation_count": 0, "unmatched_identity_count": 0, "ambiguous_identity_count": 0, "timing_rejection_count": 0, "missing_actual_count": 0, "duplicate_observation_key_count": 0, "source_hash_conflict_count": 0, "qualifying_line_failure_count": 0, "mapping_method_counts": {"exact_id": 0, "exact_name": 0}, "counts_by_league": {}, "counts_by_stat": {}, "counts_by_scope": {}, "counts_by_period": {}, "counts_by_snapshot_label": {}}
    candidates: list[MarketBiasCandidate] = []
    for _, batch in batches.items():
        line = batch[0]["line"]
        kickoff = _time(line.get("kickoff_ts"))
        available = _time(line.get("teamstats_saved_at")) or (kickoff + timedelta(hours=3) if kickoff else None)
        league_key = league_keys.get(_norm(line.get("league_name")))
        if kickoff is None or available is None or available >= as_of:
            audit["timing_rejection_count"] += 1; continue
        if line.get("actual_value") is None:
            audit["missing_actual_count"] += 1; continue
        if not league_key:
            audit["unmatched_identity_count"] += 1; continue
        resolved: list[dict[str, Any]] = []
        for side in ("home", "away"):
            matches = team_ids.get((league_key, str(line.get(f"{side}_team_id"))), [])
            method = "exact_id"
            if not matches:
                matches = team_names.get((league_key, _norm(line.get(f"{side}_team_name"))), []); method = "exact_name"
            if len(matches) != 1:
                audit["ambiguous_identity_count" if len(matches) > 1 else "unmatched_identity_count"] += 1; break
            audit["mapping_method_counts"][method] += 1; resolved.append(matches[0])
        if len(resolved) != 2: continue
        price_rows: dict[tuple[Any, ...], dict[str, Any]] = {}
        for item in batch:
            source = item["snapshot"]
            price_key = (source["snapshot_fetched_at"], source["line_value"])
            row = price_rows.setdefault(price_key, {"snapshot_key": sha256(str(price_key).encode()).hexdigest(), "snapshot_label": source["snapshot_type"] or "OFFLINE_UNKNOWN", "snapshot_time": _time(source["snapshot_fetched_at"]), "invalid_for_model": False, "line_value": source["line_value"], "over_odds": None, "under_odds": None, "offer_key": source["bet_key"], "market_scope": source["scope"], "stat_key": source["stat_key"], "period": source["period"], "source_bet_key": source["bet_key"]})
            row[f"{source['direction']}_odds"] = source["odds_decimal"]
            if source["direction"] == "over":
                row["source_bet_key"] = source["bet_key"]
        selected = select_main_line(snapshots=price_rows.values(), match_start_time=kickoff)
        if selected is None:
            audit["qualifying_line_failure_count"] += 1; continue
        selected_line = exact.get((str(line["match_id"]), str(selected["source_bet_key"])))
        if selected_line is None:
            audit["missing_actual_count"] += 1; continue
        first = batch[0]["snapshot"]
        payload = json.dumps(selected_line, default=str, sort_keys=True, separators=(",", ":"))
        docs = build_observation_docs(selected=selected, actual_value=float(selected_line["actual_value"]), fixture={"match_key": f"offline:{first['match_id']}", "source_match_id": str(first["match_id"]), "league_key": league_key, "home_team_key": resolved[0]["team_key"], "away_team_key": resolved[1]["team_key"], "match_start_time": kickoff}, outcome_available_at=available, source_kind="offline_v1_bootstrap", source_record_key=f"offline:{first['match_id']}:{selected['source_bet_key']}", source_payload_hash=sha256(payload.encode()).hexdigest(), run_id=run_id)
        candidates.append(MarketBiasCandidate(observation_docs=tuple(docs)))
        audit["accepted_observation_count"] += len(docs)
        _increment_distribution(audit, docs)
    observation_keys = [
        str(document.get("observation_key") or "")
        for candidate in candidates
        for document in candidate.observation_docs
    ]
    audit["duplicate_observation_key_count"] = len(observation_keys) - len(set(observation_keys))
    if candidates:
        first = candidates[0]
        candidates[0] = MarketBiasCandidate(
            observation_docs=first.observation_docs,
            metrics=audit,
        )
    return candidates, audit
