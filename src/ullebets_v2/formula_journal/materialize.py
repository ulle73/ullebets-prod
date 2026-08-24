from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import hashlib
from pathlib import Path
from typing import Any, Iterable

from ullebets_v2.ev_model.domain import score_feature_value
from ullebets_v2.formula_journal.observations import (
    build_js_observation_docs,
    build_ml_observation_docs,
    persist_formula_observations,
)
from ullebets_v2.storage.collections import (
    EV_MODEL_SCORES,
    FIXTURES_CANONICAL,
    FORMULA_OBSERVATIONS,
    MARKET_SNAPSHOTS,
)


def fingerprint_js_runtime(runtime_root: Path) -> str:
    sources = sorted(
        path for path in runtime_root.rglob("*.js") if path.is_file()
    )
    if not sources:
        raise FileNotFoundError(f"JS runtime has no source files: {runtime_root}")
    digest = hashlib.sha256()
    for path in sources:
        relative = path.relative_to(runtime_root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _find_rows(
    collection: Any,
    query: dict[str, Any],
    *,
    sort: list[tuple[str, int]] | None = None,
) -> list[dict[str, Any]]:
    cursor = collection.find(query, projection={"_id": 0})
    if sort and hasattr(cursor, "sort"):
        cursor = cursor.sort(sort)
    return [dict(row) for row in cursor]


def _snapshot_group_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("match_key") or ""),
        str(row.get("snapshot_label") or ""),
        str(row.get("snapshot_time") or ""),
    )


def _market_signature(row: dict[str, Any]) -> tuple[str, str, str, float]:
    return (
        str(row.get("stat_key") or row.get("statKey") or ""),
        str(row.get("scope") or ""),
        str(row.get("period") or ""),
        float(row.get("line") if row.get("line") is not None else row["line_value"]),
    )


def _oracle_offer(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "statKey": row["stat_key"],
        "scope": row["scope"],
        "period": row["period"],
        "line": float(row["line"]),
        "odds": {
            "over": row.get("over_odds"),
            "under": row.get("under_odds"),
        },
    }


def _match_info(fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "matchId": fixture.get("source_match_id") or fixture["match_key"],
        "matchKey": fixture["match_key"],
        "homeTeam": fixture.get("home_team_name"),
        "awayTeam": fixture.get("away_team_name"),
        "homeTeamKey": fixture.get("home_team_key"),
        "awayTeamKey": fixture.get("away_team_key"),
        "sourceDate": fixture.get("source_date") or fixture.get("fixture_date_stockholm"),
        "startTime": fixture.get("start_time"),
    }


def annotate_score_domain(
    score: dict[str, Any],
    training_domain: dict[str, Iterable[str]],
) -> dict[str, Any]:
    annotated = dict(score)
    status = "in_domain"
    for field, supported_values in training_domain.items():
        value = score_feature_value(score, field)
        if value is None:
            status = "missing_domain_feature"
            break
        if str(value) not in {str(item) for item in supported_values}:
            status = "out_of_domain"
            break
    annotated["formula_domain_status"] = status
    return annotated


def materialize_formula_observations(
    *,
    database: Any,
    oracle: Any,
    registry: dict[str, Any],
    runtime_sha256: str,
    now: datetime | None = None,
    match_keys: Iterable[str] | None = None,
    training_domains_by_model: dict[str, dict[str, Iterable[str]]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    current_time = now or datetime.now(tz=UTC)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    else:
        current_time = current_time.astimezone(UTC)
    requested_match_keys = sorted({str(value) for value in match_keys or [] if value})
    snapshot_query: dict[str, Any] = {
        "invalid_for_model": {"$ne": True},
        "snapshot_time": {"$lte": current_time},
        "captured_at": {"$lte": current_time},
        "match_start_time": {"$gt": current_time},
    }
    if requested_match_keys:
        snapshot_query["match_key"] = {"$in": requested_match_keys}
    snapshot_rows = _find_rows(
        database[MARKET_SNAPSHOTS],
        snapshot_query,
        sort=[("match_key", 1), ("snapshot_time", 1), ("offer_key", 1)],
    )
    snapshot_rows = [
        row
        for row in snapshot_rows
        if row.get("snapshot_time") is not None
        and row.get("match_start_time") is not None
        and row["snapshot_time"] < row["match_start_time"]
    ]
    snapshot_match_keys = sorted(
        {str(row["match_key"]) for row in snapshot_rows if row.get("match_key")}
    )
    fixture_match_keys = sorted(set(requested_match_keys or snapshot_match_keys))
    fixture_query = (
        {"match_key": {"$in": fixture_match_keys}}
        if fixture_match_keys
        else {}
    )
    fixture_rows = _find_rows(database[FIXTURES_CANONICAL], fixture_query)
    fixtures_by_match = {
        str(row["match_key"]): row
        for row in fixture_rows
        if row.get("match_key")
    }

    grouped_snapshots: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in snapshot_rows:
        grouped_snapshots[_snapshot_group_key(row)].append(row)

    js_docs: list[dict[str, Any]] = []
    oracle_errors: list[dict[str, Any]] = []
    skipped_missing_fixture = 0
    for group_key in sorted(grouped_snapshots):
        group = grouped_snapshots[group_key]
        match_key = group_key[0]
        fixture = fixtures_by_match.get(match_key)
        if fixture is None:
            skipped_missing_fixture += len(group)
            continue
        built = oracle.build_match_lines(
            match_info=_match_info(fixture),
            offers=[_oracle_offer(row) for row in group],
        )
        for error in built.get("errors", []):
            oracle_errors.append({"match_key": match_key, "snapshot_label": group_key[1], **dict(error)})
        snapshots_by_signature = {
            _market_signature(row): row
            for row in group
        }
        enriched_lines: list[dict[str, Any]] = []
        for line in built.get("lines", []):
            snapshot = snapshots_by_signature.get(_market_signature(line))
            if snapshot is None:
                oracle_errors.append(
                    {
                        "match_key": match_key,
                        "snapshot_label": group_key[1],
                        "message": "oracle_line_has_no_exact_snapshot",
                        "stat_key": line.get("statKey"),
                        "scope": line.get("scope"),
                        "period": line.get("period"),
                        "line": line.get("line"),
                    }
                )
                continue
            enriched_lines.append(
                {
                    **line,
                    "match_key": match_key,
                    "snapshot_key": snapshot["snapshot_key"],
                    "offer_key": snapshot.get("offer_key"),
                    "snapshot_label": snapshot.get("snapshot_label"),
                    "snapshot_type": snapshot.get("snapshot_type"),
                    "odds_snapshot_time": snapshot.get("snapshot_time"),
                    "match_start_time": snapshot.get("match_start_time"),
                    "league_key": snapshot.get("league_key") or fixture.get("league_key"),
                    "league_name": snapshot.get("league_name") or fixture.get("league_name"),
                    "home_team_name": snapshot.get("home_team_name") or fixture.get("home_team_name"),
                    "away_team_name": snapshot.get("away_team_name") or fixture.get("away_team_name"),
                }
            )
        js_docs.extend(
            build_js_observation_docs(
                lines=enriched_lines,
                context={"match_key": match_key},
                runtime_sha256=runtime_sha256,
                registry=registry,
                journaled_at=current_time,
            )
        )

    registered_model_ids = sorted(
        str(row["model_id"])
        for row in registry.get("frozen_models", [])
        if row.get("model_id")
    )
    score_query: dict[str, Any] = {
        "model_id": {"$in": registered_model_ids},
        "score_created_at": {"$lte": current_time},
    }
    score_match_keys = requested_match_keys or snapshot_match_keys
    if score_match_keys:
        score_query["match_key"] = {"$in": score_match_keys}
    score_rows = (
        _find_rows(
            database[EV_MODEL_SCORES],
            score_query,
            sort=[("model_id", 1), ("score_created_at", 1), ("score_key", 1)],
        )
        if registered_model_ids
        else []
    )
    annotated_scores: list[dict[str, Any]] = []
    domains = training_domains_by_model or {}
    domain_unverified_scores = 0
    for score in score_rows:
        model_id = str(score.get("model_id") or "")
        training_domain = domains.get(model_id)
        if training_domain is None:
            annotated = dict(score)
            annotated["formula_domain_status"] = "domain_unverified"
            domain_unverified_scores += 1
        else:
            annotated = annotate_score_domain(score, training_domain)
        annotated_scores.append(annotated)
    ml_docs = build_ml_observation_docs(
        scores=annotated_scores,
        registry=registry,
        fixtures_by_match=fixtures_by_match,
        journaled_at=current_time,
    )

    all_docs = [*js_docs, *ml_docs]
    persistence = {"inserted": 0, "existing": 0, "conflicts": 0}
    if not dry_run:
        persistence = persist_formula_observations(
            database[FORMULA_OBSERVATIONS],
            all_docs,
        )
    return {
        "snapshot_rows": len(snapshot_rows),
        "snapshot_groups": len(grouped_snapshots),
        "fixture_rows": len(fixture_rows),
        "skipped_missing_fixture": skipped_missing_fixture,
        "oracle_error_count": len(oracle_errors),
        "oracle_errors": oracle_errors,
        "js_observations": len(js_docs),
        "ml_score_rows": len(score_rows),
        "ml_observations": len(ml_docs),
        "domain_unverified_scores": domain_unverified_scores,
        "positive_ev_observations": sum(
            1 for row in all_docs if row.get("shadow_stake_units") == 1.0
        ),
        "observations": len(all_docs),
        "persistence": persistence,
        "dry_run": dry_run,
    }
