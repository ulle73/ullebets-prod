from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from ullebets_v2.matchups.service import run_matchups_score_build
from ullebets_v2.storage.collections import FIXTURES_CANONICAL, MARKET_SNAPSHOTS, MATCHUP_OBSERVATIONS, MATCHUPS_SCORE

from .observations import CHECKPOINT_LABEL, build_matchup_observation_docs, persist_matchup_observations


def materialize_matchup_observations(*, database: Any, match_keys: Iterable[str], captured_at: datetime, dry_run: bool = False) -> dict[str, Any]:
    requested = sorted({str(value) for value in match_keys if value})
    fixtures = list(database[FIXTURES_CANONICAL].find({"match_key": {"$in": requested}}, projection={"_id": 0})) if requested else []
    snapshots = list(database[MARKET_SNAPSHOTS].find({"match_key": {"$in": requested}, "snapshot_label": CHECKPOINT_LABEL}, projection={"_id": 0})) if requested else []
    persisted_rows = list(database[MATCHUPS_SCORE].find({"match_key": {"$in": requested}}, projection={"_id": 0})) if requested else []
    docs = []
    generated_rankings = 0
    for fixture in fixtures:
        match_key = str(fixture.get("match_key") or "")
        fixture_date = str(fixture.get("fixture_date_stockholm") or "")
        matchup_rows = [row for row in persisted_rows if row.get("match_key") == match_key and row.get("snapshot_date") == fixture_date]
        if not matchup_rows:
            summary = run_matchups_score_build(
                source_workflow="materialize-matchup-observations",
                target_matches=[fixture], snapshot_date=fixture_date, database=database, dry_run=True, generated_at=captured_at,
            )
            matchup_rows = summary.get("entry_docs") or []
            generated_rankings += len(matchup_rows)
        fixture_snapshots = [row for row in snapshots if row.get("match_key") == match_key]
        docs.extend(build_matchup_observation_docs(fixture=fixture, matchup_rows=matchup_rows, market_snapshot_rows=fixture_snapshots, captured_at=captured_at))
    persistence = {"inserted": 0, "existing": 0, "conflicts": 0} if dry_run else persist_matchup_observations(database[MATCHUP_OBSERVATIONS], docs)
    return {"requested_matches": len(requested), "matched_fixtures": len(fixtures), "generated_ranking_rows": generated_rankings, "observation_docs": len(docs), "persistence": persistence, "docs": docs if dry_run else []}
