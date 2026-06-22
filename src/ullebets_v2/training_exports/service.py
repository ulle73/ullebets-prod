from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.teamprofiles.service import build_teamprofile_docs
from ullebets_v2.training_exports.features import (
    FEATURE_MODES,
    build_dataset_key,
    build_feature_names,
    build_sample_bundle,
)
from ullebets_v2.training_exports.persistence import persist_training_export_records
from ullebets_v2.training_exports.reports import (
    build_training_export_audit_rows,
    build_training_export_health_rows,
    build_training_export_parity_rows,
)


TRAIN_END_DATE = datetime(2025, 10, 15, tzinfo=UTC)
VAL_END_DATE = datetime(2025, 11, 5, tzinfo=UTC)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _split_name_for_date(value: str | None) -> str:
    if not value:
        return "test"
    date_value = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    if date_value < TRAIN_END_DATE:
        return "train"
    if date_value < VAL_END_DATE:
        return "val"
    return "test"


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback
    return numeric if numeric == numeric else fallback


def _shots_per_ten_average(profile: dict[str, Any]) -> float:
    values = [
        _safe_float(value)
        for key, value in profile.get("specials", {}).get("shotsPerTenMinutes", {}).get("for", {}).items()
        if not str(key).startswith("rank-") and value is not None
    ]
    return sum(values) / len(values) if values else 0.0


def _profile_history(profile: dict[str, Any], stat_key: str, period: str) -> list[dict[str, Any]]:
    for_node = profile.get("statistics", {}).get("for", {}).get(stat_key, {}).get(period, {})
    against_node = profile.get("statistics", {}).get("against", {}).get(stat_key, {}).get(period, {})
    history = for_node.get("history") or against_node.get("history") or []
    return history if isinstance(history, list) else []


def _build_wma_snapshot(profile: dict[str, Any], stat_key: str, period: str, orientation: str) -> dict[str, float]:
    history = _profile_history(profile, stat_key, period)
    field = "val" if orientation == "for" else "oppVal"

    def compute(window: int) -> float:
        relevant = history[:window]
        if not relevant:
            return 0.0
        weighted_sum = 0.0
        total_weight = 0.0
        for index, row in enumerate(relevant):
            weight = 0.9 ** index
            weighted_sum += _safe_float(row.get(field)) * weight
            total_weight += weight
        return weighted_sum / total_weight if total_weight else 0.0

    return {
        "recent": compute(5),
        "medium": compute(15),
        "long": compute(30),
    }


def _build_profile_snapshot(profile: dict[str, Any], stat_key: str, period: str) -> dict[str, Any]:
    stat_node = profile.get("statistics", {}).get("for", {}).get(stat_key, {}).get(period, {})
    against_node = profile.get("statistics", {}).get("against", {}).get(stat_key, {}).get(period, {})
    return {
        "statValue": _safe_float(stat_node.get("value")),
        "statRank": _safe_float(stat_node.get("rank"), 50.0),
        "rankFor": _safe_float(profile.get("rankFor"), 50.0),
        "rankAgainst": _safe_float(profile.get("rankAgainst"), 50.0),
        "scoreFirstPct": _safe_float(profile.get("specials", {}).get("firstGoal", {}).get("scoreFirstPercentage"), 50.0),
        "shotsPerMinute": {
            "leading": _safe_float(profile.get("specials", {}).get("shotsPerMinute", {}).get("for", {}).get("leading")),
            "trailing": _safe_float(profile.get("specials", {}).get("shotsPerMinute", {}).get("for", {}).get("trailing")),
            "tied": _safe_float(profile.get("specials", {}).get("shotsPerMinute", {}).get("for", {}).get("tied")),
        },
        "shotsPerTenMinutes": _shots_per_ten_average(profile),
        "extraFor": profile.get("statistics", {}).get("for", {}),
        "extraAgainst": profile.get("statistics", {}).get("against", {}),
        "againstValue": _safe_float(against_node.get("value")),
        "againstRank": _safe_float(against_node.get("rank"), 50.0),
    }


def _build_formula_predictions(ev_details: dict[str, Any] | None) -> dict[str, float]:
    predictions: dict[str, float] = {}
    for key, value in (ev_details or {}).items():
        if str(key).startswith("raw"):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        predictions[str(key)] = numeric
    return predictions


def _load_training_sources(database: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    settled_docs = list(database["settled_bets_v2"].find({"settlement_status": "settled"}, projection={"_id": 0}))
    market_offers = list(database["market_offers"].find({}, projection={"_id": 0}))
    match_results = list(database["match_results_canonical"].find({}, projection={"_id": 0}))
    match_stats = list(database["match_stats_canonical"].find({}, projection={"_id": 0}))
    raw_incidents = list(database["raw_incidents"].find({}, projection={"_id": 0}))
    raw_shotmaps = list(database["raw_shotmaps"].find({}, projection={"_id": 0}))
    return settled_docs, market_offers, match_results, match_stats, raw_incidents, raw_shotmaps


def run_training_export_build(
    *,
    source_workflow: str,
    support_docs: dict[str, Any],
    settled_docs: list[dict[str, Any]] | None = None,
    market_offer_docs: list[dict[str, Any]] | None = None,
    match_results_canonical: list[dict[str, Any]] | None = None,
    match_stats_canonical: list[dict[str, Any]] | None = None,
    raw_incidents: list[dict[str, Any]] | None = None,
    raw_shotmaps: list[dict[str, Any]] | None = None,
    database: Any | None = None,
    dry_run: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    now = generated_at or utc_now()
    if any(source is None for source in (settled_docs, market_offer_docs, match_results_canonical, match_stats_canonical, raw_incidents, raw_shotmaps)):
        if database is None:
            settled_docs = settled_docs or []
            market_offer_docs = market_offer_docs or []
            match_results_canonical = match_results_canonical or []
            match_stats_canonical = match_stats_canonical or []
            raw_incidents = raw_incidents or []
            raw_shotmaps = raw_shotmaps or []
        else:
            loaded = _load_training_sources(database)
            settled_docs = loaded[0] if settled_docs is None else settled_docs
            market_offer_docs = loaded[1] if market_offer_docs is None else market_offer_docs
            match_results_canonical = loaded[2] if match_results_canonical is None else match_results_canonical
            match_stats_canonical = loaded[3] if match_stats_canonical is None else match_stats_canonical
            raw_incidents = loaded[4] if raw_incidents is None else raw_incidents
            raw_shotmaps = loaded[5] if raw_shotmaps is None else raw_shotmaps

    settled_docs = settled_docs or []
    market_offer_docs = market_offer_docs or []
    match_results_canonical = match_results_canonical or []
    match_stats_canonical = match_stats_canonical or []
    raw_incidents = raw_incidents or []
    raw_shotmaps = raw_shotmaps or []

    results_by_match = {
        str(row.get("match_key")): row
        for row in match_results_canonical
        if row.get("match_key") is not None
    }
    offers_by_key = {
        str(row.get("offer_key")): row
        for row in market_offer_docs
        if row.get("offer_key") is not None
    }
    support_teams = {str(row["team_key"]): row for row in support_docs.get("teams", [])}

    profile_cache: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    skipped_reason_counts: Counter[str] = Counter()
    training_export_docs: list[dict[str, Any]] = []

    unique_dates = sorted(
        {
            str(results_by_match[str(doc.get("match_key"))]["source_date"])
            for doc in settled_docs
            if str(doc.get("match_key")) in results_by_match and results_by_match[str(doc.get("match_key"))].get("source_date")
        }
    )
    for source_date in unique_dates:
        profiles = build_teamprofile_docs(
            match_stats_canonical=match_stats_canonical,
            match_results_canonical=match_results_canonical,
            raw_incidents=raw_incidents,
            raw_shotmaps=raw_shotmaps,
            support_docs=support_docs,
            profile_date=source_date,
            generated_at=now,
        )
        profile_cache[source_date] = {
            (str(profile["team_key"]), str(profile["match_type"])): profile
            for profile in profiles
        }

    for settled in settled_docs:
        match_key = str(settled.get("match_key") or "")
        result_row = results_by_match.get(match_key)
        if result_row is None:
            skipped_reason_counts["missing_match_result"] += 1
            continue
        offer_row = offers_by_key.get(str(settled.get("offer_key") or ""))
        if offer_row is None:
            skipped_reason_counts["missing_market_offer"] += 1
            continue
        source_date = str(result_row.get("source_date") or "")
        profiles = profile_cache.get(source_date, {})
        home_team_key = str(result_row.get("home_team_key") or "")
        away_team_key = str(result_row.get("away_team_key") or "")
        home_profile = profiles.get((home_team_key, "home"))
        away_profile = profiles.get((away_team_key, "away"))
        if home_profile is None or away_profile is None:
            skipped_reason_counts["missing_profile_snapshot"] += 1
            continue

        stat_key = str(settled.get("stat_key") or "")
        scope = "total" if str(settled.get("scope") or "").lower() in {"total", "all"} else str(settled.get("scope") or "")
        period = str(settled.get("period") or "")
        target = settled.get("actual_value")
        if not isinstance(target, (int, float)):
            skipped_reason_counts["missing_target_value"] += 1
            continue

        home_team_support = support_teams.get(home_team_key, {})
        away_team_support = support_teams.get(away_team_key, {})
        base_context = {
            "statKey": stat_key,
            "scope": scope,
            "period": period,
            "target": float(target),
            "market": {
                "line": settled.get("line_value"),
                "overOdds": offer_row.get("over_odds"),
                "underOdds": offer_row.get("under_odds"),
            },
            "teams": {
                "home": {
                    "optaRank": home_team_support.get("opta_rank"),
                    "optaRating": home_team_support.get("opta_rating"),
                    "wmaFor": _build_wma_snapshot(home_profile, stat_key, period, "for"),
                    "wmaAgainst": _build_wma_snapshot(home_profile, stat_key, period, "against"),
                    "profile": _build_profile_snapshot(home_profile, stat_key, period),
                },
                "away": {
                    "optaRank": away_team_support.get("opta_rank"),
                    "optaRating": away_team_support.get("opta_rating"),
                    "wmaFor": _build_wma_snapshot(away_profile, stat_key, period, "for"),
                    "wmaAgainst": _build_wma_snapshot(away_profile, stat_key, period, "against"),
                    "profile": _build_profile_snapshot(away_profile, stat_key, period),
                },
            },
            "formulaPredictions": _build_formula_predictions(settled.get("ev_details")),
            "metadata": {
                "matchId": match_key,
                "date": source_date,
                "homeTeam": result_row.get("home_team_name"),
                "awayTeam": result_row.get("away_team_name"),
                "source": "settled_bets_v2",
                "supervised": False,
                "line": _safe_float(settled.get("line_value")),
                "odds": _safe_float(settled.get("selected_odds")),
                "selectionKey": settled.get("selection_key"),
                "settlementResult": settled.get("settlement_result"),
                "profileDate": source_date,
            },
        }
        split = _split_name_for_date(source_date)
        dataset_key = build_dataset_key(stat_key, scope, period)
        for feature_mode in FEATURE_MODES:
            sample = build_sample_bundle(base_context, feature_mode)
            training_export_docs.append(
                {
                    "export_key": f"{settled.get('selection_key')}|{feature_mode}",
                    "selection_key": settled.get("selection_key"),
                    "match_key": match_key,
                    "offer_key": settled.get("offer_key"),
                    "source_date": source_date,
                    "dataset_key": dataset_key,
                    "split": split,
                    "feature_mode": feature_mode,
                    "stat_key": stat_key,
                    "scope": scope,
                    "period": period,
                    "target": float(target),
                    "market": {
                        "line": settled.get("line_value"),
                        "selected_odds": settled.get("selected_odds"),
                        "over_odds": offer_row.get("over_odds"),
                        "under_odds": offer_row.get("under_odds"),
                    },
                    "sample": sample,
                    "profile_context": {
                        "home": base_context["teams"]["home"]["profile"],
                        "away": base_context["teams"]["away"]["profile"],
                    },
                    "created_at": now,
                }
            )

    report_date = now.date().isoformat()
    parity_rows = build_training_export_parity_rows(
        source_workflow=source_workflow,
        settled_docs=settled_docs,
        training_export_docs=training_export_docs,
        skipped_reason_counts=dict(skipped_reason_counts),
        report_date=report_date,
    )
    audit_rows = build_training_export_audit_rows(
        source_workflow=source_workflow,
        settled_docs=settled_docs,
        training_export_docs=training_export_docs,
        skipped_reason_counts=dict(skipped_reason_counts),
        report_date=report_date,
    )
    health_rows = build_training_export_health_rows(
        training_export_docs=training_export_docs,
        skipped_reason_counts=dict(skipped_reason_counts),
        report_date=report_date,
    )
    summary: dict[str, Any] = {
        "job": "build_training_exports",
        "generated_at": now.isoformat(),
        "settled_samples": len(settled_docs),
        "training_exports": len(training_export_docs),
        "feature_mode_counts": dict(Counter(row["feature_mode"] for row in training_export_docs)),
        "split_counts": dict(Counter(row["split"] for row in training_export_docs)),
        "dataset_counts": dict(Counter(row["dataset_key"] for row in training_export_docs)),
        "skipped_reason_counts": dict(skipped_reason_counts),
        "parity_reports": len(parity_rows),
        "audit_reports": len(audit_rows),
        "health_reports": len(health_rows),
        "parity_status_counts": dict(Counter(row["parity_status"] for row in parity_rows)),
        "audit_status_counts": dict(Counter(row["status"] for row in audit_rows)),
        "health_status_counts": dict(Counter(row["status"] for row in health_rows)),
        "feature_name_counts": {mode: len(build_feature_names(mode)) for mode in FEATURE_MODES},
        "training_export_docs": training_export_docs,
    }
    if dry_run:
        return summary
    if database is None:
        raise RuntimeError("database is required when dry_run is False.")

    run_doc = build_job_run_started_doc(
        job_name="build_training_exports",
        source_workflow=source_workflow,
        target_window={"settled_sample_count": len(settled_docs), "generated_at": now.isoformat()},
        job_args={"dry_run": False},
    )
    database["job_runs"].insert_one(run_doc)
    job_metrics = {key: value for key, value in summary.items() if key != "training_export_docs"}
    try:
        persistence_metrics = persist_training_export_records(
            database,
            training_export_docs=training_export_docs,
            parity_rows=parity_rows,
            audit_rows=audit_rows,
            health_rows=health_rows,
        )
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(status="succeeded", metrics={**persistence_metrics, **job_metrics}),
        )
    except Exception as exc:
        database["job_runs"].update_one(
            {"run_id": run_doc["run_id"]},
            build_job_run_finished_update(
                status="failed",
                metrics=job_metrics,
                error={"type": type(exc).__name__, "message": str(exc)},
            ),
        )
        raise
    return summary
