from __future__ import annotations

from typing import Any

from pymongo.database import Database

from ullebets_v2.storage.collections import (
    ANALYSIS_CANDIDATES,
    ANALYSIS_RUNS,
    ANALYSIS_SNAPSHOTS,
    AUDIT_REPORTS,
    CLOSING_LINES,
    CLV_TRACKING,
    EV_MODEL_SCORES,
    FIXTURES_CANONICAL,
    FIXTURE_SOURCE_LINKS,
    FORWARD_BETS,
    FORWARD_RESULTS,
    HEALTH_REPORTS,
    JOB_RUNS,
    MARKET_BIAS_OBSERVATIONS,
    MARKET_BIAS_PROFILES,
    MARKET_OFFERS,
    MARKET_SNAPSHOTS,
    MATCHUPS_LEAGUE_AVG,
    MATCHUPS_SCORE,
    MATCH_RESULTS_CANONICAL,
    MATCH_STATS_CANONICAL,
    MODEL_SNAPSHOTS,
    PARITY_REPORTS,
    PREDICTION_EXPORTS,
    RAW_FIXTURES,
    RAW_INCIDENTS,
    RAW_MATCH_STATISTICS,
    RAW_ODDS_KAMBI,
    RAW_RESULTS,
    RAW_SHOTMAPS,
    SETTLED_BETS,
    SUPPORT_LEAGUES,
    SUPPORT_RANKINGS,
    SUPPORT_SOURCES,
    SUPPORT_TEAMS,
    TEAMPROFILES,
    TRAINING_EXPORTS,
    UNIBET_EVENT_LINKS,
)


def build_core_index_plan() -> list[dict[str, Any]]:
    return [
        {
            "collection": JOB_RUNS,
            "indexes": [
                {"keys": [("run_id", 1)], "name": "run_id_unique", "unique": True},
                {"keys": [("job_name", 1), ("started_at", -1)], "name": "job_name_started_at"},
                {"keys": [("status", 1), ("started_at", -1)], "name": "status_started_at"},
            ],
        },
        {
            "collection": PARITY_REPORTS,
            "indexes": [
                {
                    "keys": [("old_workflow", 1), ("report_date", 1)],
                    "name": "workflow_report_date",
                    "unique": True,
                },
                {"keys": [("parity_status", 1), ("report_date", -1)], "name": "parity_status_report_date"},
            ],
        },
        {
            "collection": AUDIT_REPORTS,
            "indexes": [
                {
                    "keys": [("audit_type", 1), ("report_date", 1), ("scope_key", 1)],
                    "name": "audit_scope_unique",
                    "unique": True,
                },
                {"keys": [("status", 1), ("report_date", -1)], "name": "audit_status_report_date"},
            ],
        },
        {
            "collection": HEALTH_REPORTS,
            "indexes": [
                {
                    "keys": [("job_name", 1), ("report_date", 1)],
                    "name": "health_job_date_unique",
                    "unique": True,
                },
                {"keys": [("status", 1), ("report_date", -1)], "name": "health_status_report_date"},
            ],
        },
        {
            "collection": SUPPORT_SOURCES,
            "indexes": [
                {"keys": [("source_key", 1)], "name": "source_key_unique", "unique": True},
                {"keys": [("source_name", 1), ("captured_at", -1)], "name": "source_name_captured_at"},
                {"keys": [("source_type", 1), ("source_version", 1)], "name": "source_type_version"},
                {"keys": [("captured_at", -1)], "name": "captured_at"},
            ],
        },
        {
            "collection": SUPPORT_LEAGUES,
            "indexes": [
                {"keys": [("league_key", 1)], "name": "league_key_unique", "unique": True},
                {"keys": [("league_name", 1)], "name": "league_name"},
            ],
        },
        {
            "collection": SUPPORT_TEAMS,
            "indexes": [
                {"keys": [("team_key", 1)], "name": "team_key_unique", "unique": True},
                {"keys": [("league_key", 1), ("team_name", 1)], "name": "league_key_team_name"},
                {"keys": [("opta_id", 1)], "name": "opta_id"},
            ],
        },
        {
            "collection": SUPPORT_RANKINGS,
            "indexes": [
                {
                    "keys": [("league_key", 1), ("ranking_type", 1)],
                    "name": "league_key_ranking_type",
                    "unique": True,
                }
            ],
        },
        {
            "collection": RAW_FIXTURES,
            "indexes": [
                {"keys": [("payload_hash", 1)], "name": "payload_hash"},
                {"keys": [("fetched_at", -1)], "name": "fetched_at"},
                {"keys": [("source_event_id", 1)], "name": "source_event_id"},
            ],
        },
        {
            "collection": FIXTURES_CANONICAL,
            "indexes": [
                {"keys": [("match_key", 1)], "name": "match_key_unique", "unique": True},
                {"keys": [("start_time", 1), ("league_key", 1)], "name": "start_time_league_key"},
            ],
        },
        {
            "collection": FIXTURE_SOURCE_LINKS,
            "indexes": [
                {"keys": [("link_key", 1)], "name": "link_key_unique", "unique": True},
                {"keys": [("match_key", 1), ("source_date", 1)], "name": "match_key_source_date"},
                {"keys": [("source_match_id", 1), ("source_date", 1)], "name": "source_match_id_source_date"},
            ],
        },
        {
            "collection": RAW_MATCH_STATISTICS,
            "indexes": [
                {"keys": [("raw_key", 1)], "name": "raw_key_unique", "unique": True},
                {"keys": [("match_key", 1), ("fetched_at", -1)], "name": "match_key_fetched_at"},
                {"keys": [("payload_hash", 1)], "name": "payload_hash"},
            ],
        },
        {
            "collection": RAW_INCIDENTS,
            "indexes": [
                {"keys": [("raw_key", 1)], "name": "raw_key_unique", "unique": True},
                {"keys": [("match_key", 1), ("fetched_at", -1)], "name": "match_key_fetched_at"},
                {"keys": [("payload_hash", 1)], "name": "payload_hash"},
            ],
        },
        {
            "collection": RAW_SHOTMAPS,
            "indexes": [
                {"keys": [("raw_key", 1)], "name": "raw_key_unique", "unique": True},
                {"keys": [("match_key", 1), ("fetched_at", -1)], "name": "match_key_fetched_at"},
                {"keys": [("payload_hash", 1)], "name": "payload_hash"},
            ],
        },
        {
            "collection": RAW_RESULTS,
            "indexes": [
                {"keys": [("raw_key", 1)], "name": "raw_key_unique", "unique": True},
                {"keys": [("match_key", 1), ("fetched_at", -1)], "name": "match_key_fetched_at"},
                {"keys": [("payload_hash", 1)], "name": "payload_hash"},
            ],
        },
        {
            "collection": MATCH_RESULTS_CANONICAL,
            "indexes": [
                {"keys": [("match_key", 1)], "name": "match_key_unique", "unique": True},
                {"keys": [("source_date", 1), ("league_key", 1)], "name": "source_date_league_key"},
            ],
        },
        {
            "collection": MATCH_STATS_CANONICAL,
            "indexes": [
                {
                    "keys": [("match_key", 1), ("stat_key", 1), ("period", 1), ("scope", 1)],
                    "name": "match_stat_period_scope",
                    "unique": True,
                }
            ],
        },
        {
            "collection": TEAMPROFILES,
            "indexes": [
                {
                    "keys": [("team_key", 1), ("profile_date", 1), ("match_type", 1)],
                    "name": "team_profile_date_match_type",
                    "unique": True,
                },
                {
                    "keys": [("league_key", 1), ("profile_date", 1), ("match_type", 1)],
                    "name": "league_profile_date_match_type",
                    "unique": False,
                },
            ],
        },
        {
            "collection": MATCHUPS_SCORE,
            "indexes": [
                {"keys": [("entry_key", 1)], "name": "entry_key_unique", "unique": True},
                {"keys": [("match_key", 1), ("snapshot_date", 1)], "name": "match_key_snapshot_date"},
                {"keys": [("snapshot_date", 1), ("condition", 1), ("score", -1)], "name": "snapshot_condition_score"},
                {"keys": [("snapshot_date", 1), ("outcome_status", 1)], "name": "snapshot_outcome_status"},
            ],
        },
        {
            "collection": MATCHUPS_LEAGUE_AVG,
            "indexes": [
                {"keys": [("entry_key", 1)], "name": "entry_key_unique", "unique": True},
                {"keys": [("league_key", 1), ("snapshot_date", 1)], "name": "league_key_snapshot_date"},
                {"keys": [("snapshot_date", 1), ("ranking_bucket", 1), ("score", -1)], "name": "snapshot_bucket_score"},
                {"keys": [("snapshot_date", 1), ("outcome_status", 1)], "name": "snapshot_outcome_status"},
            ],
        },
        {
            "collection": MARKET_BIAS_OBSERVATIONS,
            "indexes": [
                {"keys": [("observation_key", 1)], "name": "observation_key_unique", "unique": True},
                {
                    "keys": [
                        ("team_key", 1),
                        ("venue_context", 1),
                        ("market_scope", 1),
                        ("stat_key", 1),
                        ("period", 1),
                        ("outcome_available_at", -1),
                    ],
                    "name": "team_context_outcome_available",
                },
                {
                    "keys": [("match_key", 1), ("stat_key", 1), ("market_scope", 1), ("period", 1)],
                    "name": "match_market_context",
                },
            ],
        },
        {
            "collection": MARKET_BIAS_PROFILES,
            "indexes": [
                {"keys": [("profile_key", 1)], "name": "profile_key_unique", "unique": True},
                {
                    "keys": [
                        ("profile_date", 1),
                        ("team_key", 1),
                        ("venue_context", 1),
                        ("market_scope", 1),
                        ("stat_key", 1),
                        ("period", 1),
                    ],
                    "name": "profile_date_team_context",
                },
            ],
        },
        {
            "collection": RAW_ODDS_KAMBI,
            "indexes": [
                {"keys": [("raw_key", 1)], "name": "raw_key_unique", "unique": True},
                {"keys": [("payload_hash", 1)], "name": "payload_hash"},
                {"keys": [("event_id", 1), ("fetched_at", -1)], "name": "event_id_fetched_at"},
                {"keys": [("match_key", 1), ("fetched_at", -1)], "name": "match_key_fetched_at"},
            ],
        },
        {
            "collection": UNIBET_EVENT_LINKS,
            "indexes": [
                {"keys": [("event_id", 1)], "name": "event_id_unique", "unique": True},
                {"keys": [("match_key", 1)], "name": "match_key"},
            ],
        },
        {
            "collection": MARKET_OFFERS,
            "indexes": [
                {"keys": [("offer_key", 1)], "name": "offer_key_unique", "unique": True},
                {"keys": [("match_key", 1), ("stat_key", 1)], "name": "match_key_stat_key"},
            ],
        },
        {
            "collection": MARKET_SNAPSHOTS,
            "indexes": [
                {
                    "keys": [("match_key", 1), ("offer_key", 1), ("snapshot_label", 1)],
                    "name": "match_offer_snapshot_label",
                    "unique": True,
                },
                {"keys": [("snapshot_time", 1), ("match_start_time", 1)], "name": "snapshot_time_match_start_time"},
                {"keys": [("invalid_for_model", 1), ("snapshot_time", -1)], "name": "invalid_for_model_snapshot_time"},
            ],
        },
        {
            "collection": MODEL_SNAPSHOTS,
            "indexes": [
                {
                    "keys": [("selection_key", 1)],
                    "name": "selection_key_unique",
                    "unique": True,
                },
                {"keys": [("match_key", 1), ("snapshot_mode", 1), ("snapshot_time", -1)], "name": "match_mode_time"},
                {"keys": [("bet_key", 1)], "name": "bet_key"},
            ],
        },
        {
            "collection": EV_MODEL_SCORES,
            "indexes": [
                {
                    "keys": [("score_key", 1)],
                    "name": "score_key_unique",
                    "unique": True,
                },
                {
                    "keys": [
                        ("model_id", 1),
                        ("score_created_at", -1),
                    ],
                    "name": "model_id_score_created_at",
                },
                {
                    "keys": [
                        ("match_key", 1),
                        ("odds_snapshot_time", -1),
                    ],
                    "name": "match_key_odds_snapshot_time",
                },
                {
                    "keys": [
                        ("valid_for_policy_evaluation", 1),
                        ("match_start_time", 1),
                    ],
                    "name": "valid_policy_match_start",
                },
            ],
        },
        {
            "collection": SETTLED_BETS,
            "indexes": [
                {"keys": [("settlement_key", 1)], "name": "settlement_key_unique", "unique": True},
                {"keys": [("bet_key", 1)], "name": "bet_key"},
                {"keys": [("prediction_key", 1)], "name": "prediction_key"},
                {"keys": [("settlement_status", 1), ("settled_at", -1)], "name": "settlement_status_settled_at"},
                {"keys": [("selection_source", 1), ("settled_at", -1)], "name": "selection_source_settled_at"},
            ],
        },
        {
            "collection": CLOSING_LINES,
            "indexes": [
                {
                    "keys": [("closing_key", 1)],
                    "name": "closing_key_unique",
                    "unique": True,
                },
                {"keys": [("match_key", 1), ("closing_snapshot_time", -1)], "name": "match_key_closing_time"},
                {"keys": [("offer_key", 1)], "name": "offer_key"},
            ],
        },
        {
            "collection": CLV_TRACKING,
            "drop_indexes": ["tracking_key_unique"],
            "indexes": [
                {"keys": [("clv_key", 1)], "name": "clv_key_unique", "unique": True},
                {"keys": [("tracking_key", 1)], "name": "tracking_key"},
                {"keys": [("bet_key", 1)], "name": "bet_key"},
                {"keys": [("clv_status", 1), ("closing_snapshot_time", -1)], "name": "clv_status_closing_time"},
            ],
        },
        {
            "collection": FORWARD_BETS,
            "indexes": [
                {"keys": [("prediction_key", 1)], "name": "prediction_key_unique", "unique": True},
                {"keys": [("canonical_exposure_key", 1)], "name": "canonical_exposure_key"},
                {"keys": [("selection_key", 1)], "name": "selection_key"},
                {
                    "keys": [
                        ("selection_policy_id", 1),
                        ("match_key", 1),
                    ],
                    "name": "selection_policy_match",
                },
                {"keys": [("export_mode", 1), ("saved_at", -1)], "name": "export_mode_saved_at"},
                {"keys": [("match_start_time", 1)], "name": "match_start_time"},
            ],
        },
        {
            "collection": FORWARD_RESULTS,
            "indexes": [
                {"keys": [("result_loop_key", 1)], "name": "result_loop_key_unique", "unique": True},
                {"keys": [("prediction_key", 1)], "name": "prediction_key"},
                {"keys": [("result_loop_status", 1), ("match_start_time", 1)], "name": "status_match_start_time"},
                {"keys": [("timing_status", 1), ("saved_at", -1)], "name": "timing_status_saved_at"},
            ],
        },
        {
            "collection": PREDICTION_EXPORTS,
            "indexes": [
                {"keys": [("prediction_key", 1)], "name": "prediction_key_unique", "unique": True},
                {"keys": [("export_mode", 1), ("run_id", 1)], "name": "export_mode_run_id"},
                {"keys": [("event_date", 1), ("export_mode", 1)], "name": "event_date_export_mode"},
            ],
        },
        {
            "collection": ANALYSIS_RUNS,
            "indexes": [
                {"keys": [("run_id", 1)], "name": "run_id_unique", "unique": True}
            ],
        },
        {
            "collection": ANALYSIS_SNAPSHOTS,
            "indexes": [
                {"keys": [("analysis_key", 1)], "name": "analysis_key_unique", "unique": True}
            ],
        },
        {
            "collection": ANALYSIS_CANDIDATES,
            "indexes": [
                {"keys": [("candidate_key", 1)], "name": "candidate_key_unique", "unique": True}
            ],
        },
        {
            "collection": TRAINING_EXPORTS,
            "indexes": [
                {"keys": [("export_key", 1)], "name": "export_key_unique", "unique": True}
            ],
        },
    ]


def _derive_clv_key(row: dict[str, Any]) -> str | None:
    for field in ("prediction_key", "tracking_key", "selection_key", "clv_key"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value
    object_id = row.get("_id")
    return f"legacy:{object_id}" if object_id is not None else None


def _clv_row_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("saved_at") or ""),
        str(row.get("refreshed_at") or ""),
        str(row.get("_id") or ""),
    )


def _repair_clv_tracking_collection(collection: Any) -> dict[str, int]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    cursor = collection.find(
        {},
        projection={
            "_id": 1,
            "clv_key": 1,
            "prediction_key": 1,
            "selection_key": 1,
            "tracking_key": 1,
            "saved_at": 1,
            "refreshed_at": 1,
        },
    )
    for row in cursor:
        clv_key = _derive_clv_key(row)
        if clv_key is None:
            continue
        grouped.setdefault(clv_key, []).append({**row, "_derived_clv_key": clv_key})

    repaired = 0
    deleted = 0
    for rows in grouped.values():
        rows.sort(key=_clv_row_sort_key, reverse=True)
        keeper = rows[0]
        if keeper.get("clv_key") != keeper["_derived_clv_key"]:
            collection.update_one({"_id": keeper["_id"]}, {"$set": {"clv_key": keeper["_derived_clv_key"]}})
            repaired += 1
        for duplicate in rows[1:]:
            collection.delete_one({"_id": duplicate["_id"]})
            deleted += 1
    return {"repaired": repaired, "deleted": deleted}


def bootstrap_indexes(database: Database, plan: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    index_plan = plan or build_core_index_plan()
    applied: list[dict[str, Any]] = []
    for collection_plan in index_plan:
        collection = database[collection_plan["collection"]]
        repaired_docs = 0
        deleted_docs = 0
        if collection_plan["collection"] == CLV_TRACKING:
            repair_metrics = _repair_clv_tracking_collection(collection)
            repaired_docs = repair_metrics["repaired"]
            deleted_docs = repair_metrics["deleted"]
        existing_indexes = collection.index_information()
        dropped_names: list[str] = []
        for index_name in collection_plan.get("drop_indexes", []):
            if index_name in existing_indexes and index_name != "_id_":
                collection.drop_index(index_name)
                dropped_names.append(index_name)
        created_names: list[str] = []
        for index_spec in collection_plan["indexes"]:
            options = {key: value for key, value in index_spec.items() if key not in {"keys"}}
            created_names.append(collection.create_index(index_spec["keys"], **options))
        applied.append(
            {
                "collection": collection.name,
                "repaired_docs": repaired_docs,
                "deleted_docs": deleted_docs,
                "dropped_indexes": dropped_names,
                "indexes": created_names,
            }
        )
    return applied
