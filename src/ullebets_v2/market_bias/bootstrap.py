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
    line_columns = {row[0] for row in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [line_path]).fetchall()}
    line_types = {
        row[0]: str(row[1]).upper()
        for row in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [line_path]).fetchall()
    }
    required = ["match_id", "bet_key", "stat_key", "period", "scope", "direction", "line_value", "actual_value", "league_name", "home_team_name", "away_team_name", "home_team_id", "away_team_id", "kickoff_ts", "teamstats_saved_at", "generated_at", "has_authoritative_teamstats_outcome"]
    line_projection = ", ".join(
        column if column in line_columns else f"NULL AS {column}"
        for column in required
    )
    kickoff_type = line_types.get("kickoff_ts", "")
    if any(token in kickoff_type for token in ("INT", "DOUBLE", "FLOAT", "DECIMAL")):
        kickoff_expression = (
            "to_timestamp(CASE WHEN abs(kickoff_ts) >= 1000000000000 "
            "THEN kickoff_ts / 1000 ELSE kickoff_ts END)"
        )
    else:
        kickoff_expression = "try_cast(kickoff_ts AS TIMESTAMPTZ)"
    joined_rows = _rows(
        con,
        f"""
        WITH snapshots AS (
            SELECT
                match_id, bet_key, snapshot_type, snapshot_fetched_at, stat_key,
                period, scope, direction, line_value, odds_decimal
            FROM read_parquet(?)
            WHERE is_primary_modeled_stat = true
              AND direction IN ('over', 'under')
        ), authoritative_line_rows AS (
            SELECT {line_projection}
            FROM read_parquet(?)
            WHERE has_authoritative_teamstats_outcome = true
        ), authoritative_lines AS (
            SELECT * EXCLUDE (line_rank)
            FROM (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY match_id, bet_key
                    ORDER BY
                        teamstats_saved_at DESC NULLS LAST,
                        kickoff_ts DESC NULLS LAST,
                        try_cast(generated_at AS TIMESTAMPTZ) DESC NULLS LAST,
                        league_name,
                        home_team_name,
                        away_team_name
                ) AS line_rank
                FROM authoritative_line_rows
            )
            WHERE line_rank = 1
        ), counted_lines AS (
            SELECT *, COUNT(*) OVER (
                PARTITION BY match_id, stat_key, period, scope, direction, line_value
            ) AS tuple_match_count
            FROM authoritative_lines
        ), exact_rows AS (
            SELECT snapshots.*, lines.*
            FROM snapshots
            JOIN counted_lines AS lines
              ON snapshots.match_id = lines.match_id
             AND snapshots.bet_key = lines.bet_key
        ), fallback_rows AS (
            SELECT snapshots.*, lines.*
            FROM snapshots
            JOIN counted_lines AS lines
              ON snapshots.match_id = lines.match_id
             AND snapshots.stat_key = lines.stat_key
             AND snapshots.period = lines.period
             AND snapshots.scope = lines.scope
             AND snapshots.direction = lines.direction
             AND snapshots.line_value = lines.line_value
             AND lines.tuple_match_count = 1
            LEFT JOIN exact_rows AS exact
              ON snapshots.match_id = exact.match_id
             AND snapshots.bet_key = exact.bet_key
            WHERE exact.match_id IS NULL
        ), joined AS (
            SELECT * FROM exact_rows
            UNION ALL
            SELECT * FROM fallback_rows
        ), deduped_joined AS (
            SELECT * EXCLUDE (side_rank)
            FROM (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY
                        match_id, stat_key, period, scope,
                        snapshot_fetched_at, line_value, direction
                    ORDER BY abs(odds_decimal - 2.00), bet_key, odds_decimal
                ) AS side_rank
                FROM joined
            )
            WHERE side_rank = 1
        ), ranked_over AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY match_id, stat_key, period, scope
                ORDER BY
                    CASE WHEN try_cast(snapshot_fetched_at AS TIMESTAMPTZ) < {kickoff_expression}
                         THEN 0 ELSE 1 END,
                    snapshot_fetched_at DESC,
                    abs(odds_decimal - 2.00),
                    line_value,
                    bet_key
            ) AS selection_rank
            FROM deduped_joined
            WHERE direction = 'over'
              AND odds_decimal BETWEEN 1.70 AND 2.30
        ), selected_lines AS (
            SELECT match_id, stat_key, period, scope, snapshot_fetched_at, line_value
            FROM ranked_over
            WHERE selection_rank = 1
        )
        SELECT
            match_id AS snapshot_match_id,
            bet_key AS snapshot_bet_key,
            snapshot_type,
            snapshot_fetched_at,
            stat_key AS snapshot_stat_key,
            period AS snapshot_period,
            scope AS snapshot_scope,
            direction AS snapshot_direction,
            line_value AS snapshot_line_value,
            odds_decimal,
            {", ".join(f"{column} AS line_{column}" for column in required)}
        FROM deduped_joined
        JOIN selected_lines USING (match_id, stat_key, period, scope, snapshot_fetched_at, line_value)
        """,
        [snapshot_path, line_path],
    )
    league_keys: dict[str, str] = {}
    for league in support_docs.get("leagues", []):
        for alias in [league.get("league_name"), league.get("league_key"), *(league.get("unibet_lookup_slugs") or [])]:
            league_keys[_norm(alias)] = str(league["league_key"])
    team_ids: dict[tuple[str, str], list[dict[str, Any]]] = {}
    team_names: dict[tuple[str, str], list[dict[str, Any]]] = {}
    team_aliases: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for team in support_docs.get("teams", []):
        league_key = str(team.get("league_key") or "")
        for source_id in (team.get("team_id"), team.get("source_team_id")):
            if source_id not in {None, ""}:
                team_ids.setdefault((league_key, str(source_id)), []).append(team)
        team_names.setdefault((league_key, _norm(team.get("team_name"))), []).append(team)
        for alias in [*(team.get("aliases") or []), *(team.get("team_aliases") or [])]:
            team_aliases.setdefault((league_key, _norm(alias)), []).append(team)
    batches: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in joined_rows:
        snapshot = {
            "match_id": row["snapshot_match_id"],
            "bet_key": row["snapshot_bet_key"],
            "snapshot_type": row["snapshot_type"],
            "snapshot_fetched_at": row["snapshot_fetched_at"],
            "stat_key": row["snapshot_stat_key"],
            "period": row["snapshot_period"],
            "scope": row["snapshot_scope"],
            "direction": row["snapshot_direction"],
            "line_value": row["snapshot_line_value"],
            "odds_decimal": row["odds_decimal"],
        }
        line = {column: row[f"line_{column}"] for column in required}
        key = (snapshot["match_id"], snapshot["stat_key"], snapshot["period"], snapshot["scope"])
        batches.setdefault(key, []).append({"snapshot": snapshot, "line": line})
    audit: dict[str, Any] = {"accepted_observation_count": 0, "unmatched_identity_count": 0, "ambiguous_identity_count": 0, "timing_rejection_count": 0, "missing_actual_count": 0, "duplicate_observation_key_count": 0, "source_hash_conflict_count": 0, "qualifying_line_failure_count": 0, "mapping_method_counts": {"exact_id": 0, "exact_name": 0, "configured_alias": 0}, "counts_by_league": {}, "counts_by_stat": {}, "counts_by_scope": {}, "counts_by_period": {}, "counts_by_snapshot_label": {}}
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
            if not matches:
                matches = team_aliases.get((league_key, _norm(line.get(f"{side}_team_name"))), []); method = "configured_alias"
            if len(matches) != 1:
                audit["ambiguous_identity_count" if len(matches) > 1 else "unmatched_identity_count"] += 1; break
            audit["mapping_method_counts"][method] += 1; resolved.append(matches[0])
        if len(resolved) != 2: continue
        price_rows: dict[tuple[Any, ...], dict[str, Any]] = {}
        for item in batch:
            source = item["snapshot"]
            price_key = (source["snapshot_fetched_at"], source["line_value"])
            snapshot_identity = {
                "match_id": source["match_id"],
                "stat_key": source["stat_key"],
                "scope": source["scope"],
                "period": source["period"],
                "snapshot_fetched_at": source["snapshot_fetched_at"],
                "line_value": source["line_value"],
            }
            row = price_rows.setdefault(price_key, {"snapshot_key": sha256(json.dumps(snapshot_identity, default=str, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "snapshot_label": source["snapshot_type"] or "OFFLINE_UNKNOWN", "snapshot_time": _time(source["snapshot_fetched_at"]), "invalid_for_model": False, "line_value": source["line_value"], "over_odds": None, "under_odds": None, "offer_key": source["bet_key"], "market_scope": source["scope"], "stat_key": source["stat_key"], "period": source["period"], "source_bet_key": source["bet_key"], "source_line": item["line"]})
            row[f"{source['direction']}_odds"] = source["odds_decimal"]
            if source["direction"] == "over":
                row["source_bet_key"] = source["bet_key"]
                row["source_line"] = item["line"]
        selected = select_main_line(snapshots=price_rows.values(), match_start_time=kickoff)
        if selected is None:
            audit["qualifying_line_failure_count"] += 1; continue
        selected_line = selected["source_line"]
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
    else:
        candidates.append(MarketBiasCandidate(observation_docs=(), metrics=audit))
    return candidates, audit
