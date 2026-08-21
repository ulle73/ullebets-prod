from __future__ import annotations
from datetime import datetime
from hashlib import sha256
from typing import Any
from ullebets_v2.market_bias.domain import build_observation_docs, select_main_line
from ullebets_v2.market_bias.service import MarketBiasCandidate

def load_forward_candidates(database: Any, *, from_date: str, to_date: str, run_id: str) -> tuple[list[MarketBiasCandidate], dict[str, int]]:
    fixtures = [row for row in database["fixtures_canonical"].find({}) if from_date <= str(row.get("source_date") or row.get("start_time"))[:10] <= to_date]
    results = {row.get("match_key"): row for row in database["match_results_canonical"].find({})}
    stats = list(database["match_stats_canonical"].find({}))
    snapshots = list(database["market_snapshots"].find({}))
    candidates=[]; audit={"accepted_observation_count":0,"missing_actual_count":0,"timing_rejection_count":0,"qualifying_line_failure_count":0}
    for fixture in fixtures:
        match_key=fixture.get("match_key"); result=results.get(match_key)
        if not result or not result.get("fetched_at"): continue
        for stat in stats:
            if stat.get("match_key") != match_key: continue
            scope=stat.get("scope"); period=stat.get("period"); key=(stat.get("stat_key"),scope,period)
            rows=[]
            for snap in snapshots:
                if snap.get("match_key") != match_key or (snap.get("stat_key"), snap.get("market_scope", snap.get("scope")), snap.get("period")) != key: continue
                rows.append({**snap,"line_value":snap.get("line"),"market_scope":snap.get("market_scope",snap.get("scope"))})
            selected=select_main_line(snapshots=rows,match_start_time=fixture.get("start_time") or fixture.get("match_start_time"))
            if not selected: audit["qualifying_line_failure_count"]+=1; continue
            docs=build_observation_docs(selected=selected,actual_value=float(stat["actual_value"]),fixture={"match_key":match_key,"source_match_id":fixture.get("source_match_id",match_key),"league_key":fixture["league_key"],"home_team_key":fixture["home_team_key"],"away_team_key":fixture["away_team_key"],"match_start_time":fixture.get("start_time") or fixture.get("match_start_time")},outcome_available_at=result["fetched_at"],source_kind="v2_forward",source_record_key=f"v2:{match_key}:{key}",source_payload_hash=sha256(repr(stat).encode()).hexdigest(),run_id=run_id)
            candidates.append(MarketBiasCandidate(observation_docs=tuple(docs))); audit["accepted_observation_count"]+=len(docs)
    return candidates,audit
