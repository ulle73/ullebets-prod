from __future__ import annotations

from typing import Any

JOB_RUNS = "job_runs"
PARITY_REPORTS = "parity_reports"
AUDIT_REPORTS = "audit_reports"
HEALTH_REPORTS = "health_reports"

SUPPORT_SOURCES = "support_sources"
SUPPORT_LEAGUES = "support_leagues"
SUPPORT_TEAMS = "support_teams"
SUPPORT_RANKINGS = "support_rankings"

RAW_FIXTURES = "raw_fixtures"
FIXTURES_CANONICAL = "fixtures_canonical"
FIXTURE_SOURCE_LINKS = "fixture_source_links"

RAW_MATCH_STATISTICS = "raw_match_statistics"
RAW_INCIDENTS = "raw_incidents"
RAW_SHOTMAPS = "raw_shotmaps"
RAW_RESULTS = "raw_results"
MATCH_RESULTS_CANONICAL = "match_results_canonical"
MATCH_STATS_CANONICAL = "match_stats_canonical"

TEAMPROFILES = "teamprofiles"
MATCHUPS_SCORE = "matchups_score"
MATCHUPS_LEAGUE_AVG = "matchups_league_avg"
MARKET_BIAS_OBSERVATIONS = "market_bias_observations"
MARKET_BIAS_PROFILES = "market_bias_profiles"

RAW_ODDS_KAMBI = "raw_odds_kambi"
UNIBET_EVENT_LINKS = "unibet_event_links"
MARKET_OFFERS = "market_offers"
MARKET_SNAPSHOTS = "market_snapshots"
MODEL_SNAPSHOTS = "model_snapshots"
EV_MODEL_SCORES = "ev_model_scores"
FORMULA_OBSERVATIONS = "formula_observations"
FORMULA_RESULTS = "formula_results"

SETTLED_BETS = "settled_bets"
CLOSING_LINES = "closing_lines"
CLOSING_WATCH_SESSIONS = "closing_watch_sessions"
CLV_TRACKING = "clv_tracking"
FORWARD_BETS = "forward_bets"
FORWARD_RESULTS = "forward_results"
PREDICTION_EXPORTS = "prediction_exports"

ANALYSIS_RUNS = "analysis_runs"
ANALYSIS_SNAPSHOTS = "analysis_snapshots"
ANALYSIS_CANDIDATES = "analysis_candidates"
TRAINING_EXPORTS = "training_exports"

CANONICAL_COLLECTION_NAMES = (
    JOB_RUNS,
    PARITY_REPORTS,
    AUDIT_REPORTS,
    HEALTH_REPORTS,
    SUPPORT_SOURCES,
    SUPPORT_LEAGUES,
    SUPPORT_TEAMS,
    SUPPORT_RANKINGS,
    RAW_FIXTURES,
    FIXTURES_CANONICAL,
    FIXTURE_SOURCE_LINKS,
    RAW_MATCH_STATISTICS,
    RAW_INCIDENTS,
    RAW_SHOTMAPS,
    RAW_RESULTS,
    MATCH_RESULTS_CANONICAL,
    MATCH_STATS_CANONICAL,
    TEAMPROFILES,
    MATCHUPS_SCORE,
    MATCHUPS_LEAGUE_AVG,
    MARKET_BIAS_OBSERVATIONS,
    MARKET_BIAS_PROFILES,
    RAW_ODDS_KAMBI,
    UNIBET_EVENT_LINKS,
    MARKET_OFFERS,
    MARKET_SNAPSHOTS,
    MODEL_SNAPSHOTS,
    EV_MODEL_SCORES,
    FORMULA_OBSERVATIONS,
    FORMULA_RESULTS,
    SETTLED_BETS,
    CLOSING_LINES,
    CLOSING_WATCH_SESSIONS,
    CLV_TRACKING,
    FORWARD_BETS,
    FORWARD_RESULTS,
    PREDICTION_EXPORTS,
    ANALYSIS_RUNS,
    ANALYSIS_SNAPSHOTS,
    ANALYSIS_CANDIDATES,
    TRAINING_EXPORTS,
)

# Legacy bootstrap names kept only for cleanup/migration of the initial mixed layout.
LEGACY_SUFFIX_COLLECTION_RENAMES = {
    "teamprofiles_v2": TEAMPROFILES,
    "matchups_score_v2": MATCHUPS_SCORE,
    "matchups_league_avg_v2": MATCHUPS_LEAGUE_AVG,
    "settled_bets_v2": SETTLED_BETS,
    "closing_lines_v2": CLOSING_LINES,
    "clv_tracking_v2": CLV_TRACKING,
    "forward_bets_v2": FORWARD_BETS,
    "prediction_exports_v2": PREDICTION_EXPORTS,
    "analysis_runs_v2": ANALYSIS_RUNS,
    "analysis_snapshots_v2": ANALYSIS_SNAPSHOTS,
    "analysis_candidates_v2": ANALYSIS_CANDIDATES,
    "training_exports_v2": TRAINING_EXPORTS,
}

LEGACY_SUFFIX_COLLECTION_NAMES = tuple(LEGACY_SUFFIX_COLLECTION_RENAMES)


def list_known_collection_names(database: Any) -> set[str]:
    if hasattr(database, "list_collection_names"):
        return set(database.list_collection_names())
    if isinstance(database, dict):
        return set(database.keys())
    raise TypeError("Database object must expose list_collection_names() or behave like a mapping.")


def inspect_collection_name_contract(database: Any) -> dict[str, object]:
    visible_names = list_known_collection_names(database)
    legacy_suffix_collections = sorted(name for name in visible_names if name in LEGACY_SUFFIX_COLLECTION_RENAMES)
    canonical_collections = sorted(name for name in visible_names if name in CANONICAL_COLLECTION_NAMES)
    unexpected_collections = sorted(
        name
        for name in visible_names
        if name not in CANONICAL_COLLECTION_NAMES
        and name not in LEGACY_SUFFIX_COLLECTION_RENAMES
        and not name.startswith("system.")
    )
    status = "ok" if not legacy_suffix_collections and not unexpected_collections else "warn"
    return {
        "status": status,
        "visible_collection_count": len(visible_names),
        "canonical_collection_count": len(canonical_collections),
        "legacy_suffix_collection_count": len(legacy_suffix_collections),
        "unexpected_collection_count": len(unexpected_collections),
        "legacy_suffix_collections": legacy_suffix_collections,
        "unexpected_collections": unexpected_collections,
    }
