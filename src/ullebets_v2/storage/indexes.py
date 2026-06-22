from __future__ import annotations

from typing import Any

from pymongo.database import Database


def build_core_index_plan() -> list[dict[str, Any]]:
    return [
        {
            "collection": "job_runs",
            "indexes": [
                {"keys": [("run_id", 1)], "name": "run_id_unique", "unique": True},
                {"keys": [("job_name", 1), ("started_at", -1)], "name": "job_name_started_at"},
                {"keys": [("status", 1), ("started_at", -1)], "name": "status_started_at"},
            ],
        },
        {
            "collection": "parity_reports",
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
            "collection": "audit_reports",
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
            "collection": "health_reports",
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
            "collection": "support_sources",
            "indexes": [
                {"keys": [("source_key", 1)], "name": "source_key_unique", "unique": True},
                {"keys": [("source_name", 1), ("captured_at", -1)], "name": "source_name_captured_at"},
                {"keys": [("source_type", 1), ("source_version", 1)], "name": "source_type_version"},
                {"keys": [("captured_at", -1)], "name": "captured_at"},
            ],
        },
        {
            "collection": "support_leagues",
            "indexes": [
                {"keys": [("league_key", 1)], "name": "league_key_unique", "unique": True},
                {"keys": [("league_name", 1)], "name": "league_name"},
            ],
        },
        {
            "collection": "support_teams",
            "indexes": [
                {"keys": [("team_key", 1)], "name": "team_key_unique", "unique": True},
                {"keys": [("league_key", 1), ("team_name", 1)], "name": "league_key_team_name"},
                {"keys": [("opta_id", 1)], "name": "opta_id"},
            ],
        },
        {
            "collection": "support_rankings",
            "indexes": [
                {
                    "keys": [("league_key", 1), ("ranking_type", 1)],
                    "name": "league_key_ranking_type",
                    "unique": True,
                }
            ],
        },
        {
            "collection": "raw_fixtures",
            "indexes": [
                {"keys": [("payload_hash", 1)], "name": "payload_hash"},
                {"keys": [("fetched_at", -1)], "name": "fetched_at"},
                {"keys": [("source_event_id", 1)], "name": "source_event_id"},
            ],
        },
        {
            "collection": "fixtures_canonical",
            "indexes": [
                {"keys": [("match_key", 1)], "name": "match_key_unique", "unique": True},
                {"keys": [("start_time", 1), ("league_key", 1)], "name": "start_time_league_key"},
            ],
        },
        {
            "collection": "fixture_source_links",
            "indexes": [
                {"keys": [("link_key", 1)], "name": "link_key_unique", "unique": True},
                {"keys": [("match_key", 1), ("source_date", 1)], "name": "match_key_source_date"},
                {"keys": [("source_match_id", 1), ("source_date", 1)], "name": "source_match_id_source_date"},
            ],
        },
        {
            "collection": "raw_match_statistics",
            "indexes": [
                {"keys": [("match_key", 1), ("fetched_at", -1)], "name": "match_key_fetched_at"},
                {"keys": [("payload_hash", 1)], "name": "payload_hash"},
            ],
        },
        {
            "collection": "raw_incidents",
            "indexes": [
                {"keys": [("match_key", 1), ("fetched_at", -1)], "name": "match_key_fetched_at"},
                {"keys": [("payload_hash", 1)], "name": "payload_hash"},
            ],
        },
        {
            "collection": "raw_shotmaps",
            "indexes": [
                {"keys": [("match_key", 1), ("fetched_at", -1)], "name": "match_key_fetched_at"},
                {"keys": [("payload_hash", 1)], "name": "payload_hash"},
            ],
        },
        {
            "collection": "raw_results",
            "indexes": [
                {"keys": [("match_key", 1), ("fetched_at", -1)], "name": "match_key_fetched_at"},
                {"keys": [("payload_hash", 1)], "name": "payload_hash"},
            ],
        },
        {
            "collection": "match_results_canonical",
            "indexes": [
                {"keys": [("match_key", 1)], "name": "match_key_unique", "unique": True},
                {"keys": [("source_date", 1), ("league_key", 1)], "name": "source_date_league_key"},
            ],
        },
        {
            "collection": "match_stats_canonical",
            "indexes": [
                {
                    "keys": [("match_key", 1), ("stat_key", 1), ("period", 1), ("scope", 1)],
                    "name": "match_stat_period_scope",
                    "unique": True,
                }
            ],
        },
        {
            "collection": "teamprofiles_v2",
            "indexes": [
                {"keys": [("team_key", 1), ("profile_date", 1)], "name": "team_profile_date", "unique": True}
            ],
        },
        {
            "collection": "matchups_score_v2",
            "indexes": [
                {"keys": [("match_key", 1), ("snapshot_date", 1)], "name": "match_key_snapshot_date"}
            ],
        },
        {
            "collection": "matchups_league_avg_v2",
            "indexes": [
                {"keys": [("league_key", 1), ("snapshot_date", 1)], "name": "league_key_snapshot_date"}
            ],
        },
        {
            "collection": "raw_odds_kambi",
            "indexes": [
                {"keys": [("raw_key", 1)], "name": "raw_key_unique", "unique": True},
                {"keys": [("payload_hash", 1)], "name": "payload_hash"},
                {"keys": [("event_id", 1), ("fetched_at", -1)], "name": "event_id_fetched_at"},
                {"keys": [("match_key", 1), ("fetched_at", -1)], "name": "match_key_fetched_at"},
            ],
        },
        {
            "collection": "unibet_event_links",
            "indexes": [
                {"keys": [("event_id", 1)], "name": "event_id_unique", "unique": True},
                {"keys": [("match_key", 1)], "name": "match_key"},
            ],
        },
        {
            "collection": "market_offers",
            "indexes": [
                {"keys": [("offer_key", 1)], "name": "offer_key_unique", "unique": True},
                {"keys": [("match_key", 1), ("stat_key", 1)], "name": "match_key_stat_key"},
            ],
        },
        {
            "collection": "market_snapshots",
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
            "collection": "model_snapshots",
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
            "collection": "settled_bets_v2",
            "indexes": [
                {"keys": [("settlement_key", 1)], "name": "settlement_key_unique", "unique": True},
                {"keys": [("bet_key", 1)], "name": "bet_key"},
                {"keys": [("settlement_status", 1), ("settled_at", -1)], "name": "settlement_status_settled_at"},
            ],
        },
        {
            "collection": "closing_lines_v2",
            "indexes": [
                {
                    "keys": [("match_key", 1), ("offer_key", 1), ("closing_snapshot_time", 1)],
                    "name": "match_offer_closing_time",
                    "unique": True,
                }
            ],
        },
        {
            "collection": "clv_tracking_v2",
            "indexes": [
                {"keys": [("bet_key", 1)], "name": "bet_key_unique", "unique": True}
            ],
        },
        {
            "collection": "forward_bets_v2",
            "indexes": [
                {"keys": [("prediction_key", 1)], "name": "prediction_key_unique", "unique": True},
                {"keys": [("match_start_time", 1)], "name": "match_start_time"},
            ],
        },
        {
            "collection": "analysis_runs_v2",
            "indexes": [
                {"keys": [("run_id", 1)], "name": "run_id_unique", "unique": True}
            ],
        },
        {
            "collection": "analysis_snapshots_v2",
            "indexes": [
                {"keys": [("analysis_key", 1)], "name": "analysis_key_unique", "unique": True}
            ],
        },
        {
            "collection": "analysis_candidates_v2",
            "indexes": [
                {"keys": [("candidate_key", 1)], "name": "candidate_key_unique", "unique": True}
            ],
        },
        {
            "collection": "training_exports_v2",
            "indexes": [
                {"keys": [("export_key", 1)], "name": "export_key_unique", "unique": True}
            ],
        },
    ]


def bootstrap_indexes(database: Database, plan: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    index_plan = plan or build_core_index_plan()
    applied: list[dict[str, Any]] = []
    for collection_plan in index_plan:
        collection = database[collection_plan["collection"]]
        created_names: list[str] = []
        for index_spec in collection_plan["indexes"]:
            options = {key: value for key, value in index_spec.items() if key not in {"keys"}}
            created_names.append(collection.create_index(index_spec["keys"], **options))
        applied.append({"collection": collection.name, "indexes": created_names})
    return applied
