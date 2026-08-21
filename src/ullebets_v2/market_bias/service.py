from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Literal

from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.market_bias.domain import build_bias_profile
from ullebets_v2.market_bias.persistence import persist_market_bias_reports, persist_observations, persist_profiles
from ullebets_v2.market_bias.reports import build_market_bias_audit_rows, build_market_bias_health_rows
from ullebets_v2.storage.collections import MARKET_BIAS_OBSERVATIONS


EXISTING_OBSERVATION_QUERY_BATCH_SIZE = 100


@dataclass(frozen=True)
class MarketBiasCandidate:
    """Adapter-neutral candidate output; rejected rows stay in metrics, not observations."""

    observation_docs: tuple[dict[str, Any], ...]
    metrics: dict[str, Any] = field(default_factory=dict)


def _metric_counts(observations: list[dict[str, Any]], candidates: list[MarketBiasCandidate]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for candidate in candidates:
        for key, value in candidate.metrics.items():
            if isinstance(value, int):
                metrics[key] = int(metrics.get(key, 0)) + value
            elif isinstance(value, dict):
                target = metrics.setdefault(key, {})
                for nested_key, nested_value in value.items():
                    target[nested_key] = int(target.get(nested_key, 0)) + int(nested_value)
    keys = [str(row.get("observation_key") or "") for row in observations]
    metrics["duplicate_observation_key_count"] = int(metrics.get("duplicate_observation_key_count", 0)) + (len(keys) - len(set(keys)))
    metrics["counts_by_stat"] = dict(Counter(str(row.get("stat_key") or "missing") for row in observations))
    metrics["counts_by_scope"] = dict(Counter(str(row.get("market_scope") or "missing") for row in observations))
    metrics["counts_by_period"] = dict(Counter(str(row.get("period") or "missing") for row in observations))
    metrics["counts_by_league"] = dict(Counter(str(row.get("league_key") or "missing") for row in observations))
    metrics["counts_by_snapshot_label"] = dict(Counter(str(row.get("snapshot_label") or "missing") for row in observations))
    return metrics


def _profile_documents(*, observations: list[dict[str, Any]], as_of: datetime, profile_date: str, run_id: str) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = {}
    fields = ("team_key", "league_key", "venue_context", "market_scope", "stat_key", "period")
    for observation in observations:
        key = tuple(str(observation.get(field) or "") for field in fields)
        groups.setdefault(key, []).append(observation)
    return [
        build_bias_profile(rows, as_of=as_of, profile_date=profile_date, run_id=run_id)
        for _, rows in sorted(groups.items())
    ]


def _context_key(observation: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    fields = ("team_key", "league_key", "venue_context", "market_scope", "stat_key", "period")
    return tuple(str(observation.get(field) or "") for field in fields)


def _load_existing_observations(
    *,
    database: Any | None,
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if database is None or not incoming:
        return []
    collection = database[MARKET_BIAS_OBSERVATIONS]
    # An empty collection has no history to merge; avoid thousands of Cosmos $or clauses.
    if collection.find_one({}, projection={"_id": 1}) is None:
        return []
    contexts = sorted({_context_key(observation) for observation in incoming})
    fields = ("team_key", "league_key", "venue_context", "market_scope", "stat_key", "period")
    rows: list[dict[str, Any]] = []
    for start in range(0, len(contexts), EXISTING_OBSERVATION_QUERY_BATCH_SIZE):
        batch = contexts[start : start + EXISTING_OBSERVATION_QUERY_BATCH_SIZE]
        query = {"$or": [dict(zip(fields, context, strict=True)) for context in batch]}
        rows.extend(dict(row) for row in collection.find(query, projection={"_id": 0}))
    return rows


def _dedupe_observations(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {str(observation["observation_key"]): observation for observation in existing}
    merged.update({str(observation["observation_key"]): observation for observation in incoming})
    return list(merged.values())


def run_market_bias_refresh(
    *,
    source_workflow: str,
    source_kind: Literal["offline_v1_bootstrap", "v2_forward"],
    candidates: Iterable[MarketBiasCandidate],
    as_of: datetime,
    profile_date: str,
    database: Any | None,
    dry_run: bool,
) -> dict[str, Any]:
    candidate_rows = list(candidates)
    candidate_docs = [dict(doc) for candidate in candidate_rows for doc in candidate.observation_docs]
    if any(row.get("source_kind") != source_kind for row in candidate_docs):
        raise ValueError("candidate observation source_kind does not match refresh source_kind.")
    if dry_run:
        return _run_refresh(
            source_workflow=source_workflow,
            source_kind=source_kind,
            candidate_rows=candidate_rows,
            observation_docs=candidate_docs,
            as_of=as_of,
            profile_date=profile_date,
            database=database,
            run_id=str(candidate_docs[0].get("run_id") or "market-bias-dry-run") if candidate_docs else "market-bias-dry-run",
            persist=False,
        )
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")
    run_doc = build_job_run_started_doc(
        job_name="refresh_market_bias",
        source_workflow=source_workflow,
        target_window={"as_of": as_of, "profile_date": profile_date, "source_kind": source_kind},
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    try:
        summary = _run_refresh(
            source_workflow=source_workflow,
            source_kind=source_kind,
            candidate_rows=candidate_rows,
            observation_docs=[{**doc, "run_id": run_doc["run_id"]} for doc in candidate_docs],
            as_of=as_of,
            profile_date=profile_date,
            database=database,
            run_id=str(run_doc["run_id"]),
            persist=True,
        )
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(status="succeeded", metrics={key: value for key, value in summary.items() if key not in {"observation_docs", "profile_docs", "audit_rows", "health_rows"}}),
        )
    except BaseException as exc:
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(status="failed", metrics={"source_row_count": len(candidate_rows)}, error={"type": type(exc).__name__, "message": str(exc)}),
        )
        raise
    return summary


def _run_refresh(
    *,
    source_workflow: str,
    source_kind: Literal["offline_v1_bootstrap", "v2_forward"],
    candidate_rows: list[MarketBiasCandidate],
    observation_docs: list[dict[str, Any]],
    as_of: datetime,
    profile_date: str,
    database: Any | None,
    run_id: str,
    persist: bool,
) -> dict[str, Any]:
    metrics = _metric_counts(observation_docs, candidate_rows)
    if metrics["duplicate_observation_key_count"]:
        raise ValueError("duplicate market-bias observation keys are fatal.")
    existing = _load_existing_observations(database=database, incoming=observation_docs)
    profile_observations = _dedupe_observations(existing, observation_docs)
    profile_docs = _profile_documents(observations=profile_observations, as_of=as_of, profile_date=profile_date, run_id=run_id) if profile_observations else []
    metrics.update(
        {
            "source_row_count": sum(bool(candidate.observation_docs) for candidate in candidate_rows),
            "accepted_observation_count": len(observation_docs),
            "profile_count": len(profile_docs),
        }
    )
    audit_rows = build_market_bias_audit_rows(source_workflow=source_workflow, metrics=metrics, report_date=profile_date)
    health_rows = build_market_bias_health_rows(metrics=metrics, report_date=profile_date)
    summary: dict[str, Any] = {
        "job": "refresh_market_bias",
        "run_id": run_id,
        "source_kind": source_kind,
        "observation_docs": observation_docs,
        "profile_docs": profile_docs,
        "audit_rows": audit_rows,
        "health_rows": health_rows,
        **metrics,
    }
    if persist:
        if database is None:
            raise RuntimeError("database is required when persistence is enabled.")
        persistence_metrics = persist_observations(database, observation_docs)
        persistence_metrics.update(persist_profiles(database, profile_docs))
        persistence_metrics.update(persist_market_bias_reports(database, audit_rows=audit_rows, health_rows=health_rows))
        summary.update(persistence_metrics)
    return summary
