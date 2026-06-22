from __future__ import annotations

from pathlib import Path
import json
import subprocess
from typing import Any


def _parse_json_from_node_output(stdout: str) -> Any:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return None
    for line in reversed(lines):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise RuntimeError(f"Could not parse JSON from node output: {stdout}")


class OriginalJsAutoAnalysisOracle:
    def __init__(self, old_repo_root: Path) -> None:
        self.old_repo_root = old_repo_root

    def rank_model_snapshots(
        self,
        *,
        model_snapshot_docs: list[dict[str, Any]],
        run_meta: dict[str, Any],
        learning_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        script = """
import { pathToFileURL } from 'node:url';
async function readStdin() {
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  return input.trim();
}
function toTimestamp(value) {
  if (!value) return null;
  const date = new Date(value);
  const ts = date.getTime();
  return Number.isFinite(ts) ? ts : null;
}
function sortByStrategyThenEv(a, b) {
  if ((b?.strategyScore || 0) !== (a?.strategyScore || 0)) {
    return (b?.strategyScore || 0) - (a?.strategyScore || 0);
  }
  return (b?.primaryEv || 0) - (a?.primaryEv || 0);
}
const repoRoot = process.argv[1];
const resultSummaryPath = process.argv[2];
const storePath = process.argv[3];
process.chdir(repoRoot);
const { scoreResultForStrategy, matchesStrategyFilters } = await import(pathToFileURL(resultSummaryPath).href);
const {
  sanitizeAutoAnalysisBet,
  sanitizeAutoAnalysisRun,
  sanitizeAnalysisSnapshot,
} = await import(pathToFileURL(storePath).href);
const payload = JSON.parse((await readStdin()) || '{}');
const runMeta = payload.runMeta || {};
const snapshots = Array.isArray(payload.modelSnapshots) ? payload.modelSnapshots : [];
const learningProfile = payload.learningProfile || null;
const createdAt = runMeta.createdAt ? new Date(runMeta.createdAt) : new Date();
const strategyId = runMeta.strategyId || 'balanced';
const strategyLabel = runMeta.strategyLabel || strategyId;
const countsByMatchKey = new Map();
for (const snapshot of snapshots) {
  const matchKey = String(snapshot?.match_key || '');
  countsByMatchKey.set(matchKey, (countsByMatchKey.get(matchKey) || 0) + 1);
}
const candidates = [];
const byMatchKey = new Map();
for (const snapshot of snapshots) {
  const evDetails = snapshot?.ev_details && typeof snapshot.ev_details === 'object' ? snapshot.ev_details : {};
  const pseudoResult = {
    params: {
      home: snapshot?.home_team_name,
      away: snapshot?.away_team_name,
      over: snapshot?.direction === 'under' ? false : true,
      line: snapshot?.line_value,
      scope: snapshot?.scope,
      stat: snapshot?.stat_key,
      period: snapshot?.period,
      form: 'all',
      neutralGround: false,
      odds: snapshot?.selected_odds,
    },
    primaryEv: snapshot?.primary_ev ?? null,
    matches: snapshot?.sample_size ?? null,
    leagueName: snapshot?.league_name ?? null,
    ...evDetails,
  };
  const scored = scoreResultForStrategy(pseudoResult, strategyId, learningProfile);
  const passesStrategyFilters = matchesStrategyFilters(scored, strategyId);
  const matchId = snapshot?.source_match_id ?? snapshot?.match_key ?? null;
  const matchPayload = {
    matchId,
    homeTeamName: snapshot?.home_team_name ?? null,
    awayTeamName: snapshot?.away_team_name ?? null,
    leagueName: snapshot?.league_name ?? null,
    matchDate: snapshot?.match_start_time ?? null,
    timestamp: toTimestamp(snapshot?.match_start_time),
  };
  const sanitized = sanitizeAutoAnalysisBet({
    run: {
      runId: runMeta.runId,
      runKey: runMeta.runKey,
      date: runMeta.date,
      strategyId,
      strategyLabel,
      source: runMeta.source,
      checkpointKey: runMeta.checkpointKey ?? null,
      checkpointLabel: runMeta.checkpointLabel ?? null,
      checkpointTargetDays: runMeta.checkpointTargetDays ?? null,
    },
    match: matchPayload,
    candidate: scored,
    marketCount: countsByMatchKey.get(String(snapshot?.match_key || '')) || 0,
    eventUrl: snapshot?.event_url ?? null,
    checkpointKey: runMeta.checkpointKey ?? null,
    checkpointLabel: runMeta.checkpointLabel ?? null,
    checkpointTargetDays: runMeta.checkpointTargetDays ?? null,
    wasShownInUi: passesStrategyFilters,
    isBestBetForMatch: false,
    passesStrategyFilters,
    stakeUnits: 1,
    createdAt,
  });
  const candidate = {
    ...sanitized,
    selectionKey: snapshot?.selection_key ?? null,
    matchKey: snapshot?.match_key ?? null,
    sourceMatchId: matchId != null ? String(matchId) : null,
    offerKey: snapshot?.offer_key ?? null,
    strategyScore: scored?.strategyScore ?? null,
    ranking: scored?.ranking ?? null,
    proof: scored?.proof ?? null,
    riskFlags: Array.isArray(scored?.riskFlags) ? scored.riskFlags : [],
    rankReasons: Array.isArray(scored?.rankReasons) ? scored.rankReasons : [],
    entries: Array.isArray(scored?.entries) ? scored.entries : [],
    confidenceScore: scored?.confidenceScore ?? sanitized?.confidenceScore ?? null,
    agreementPct: scored?.agreementPct ?? sanitized?.agreementPct ?? null,
    sampleSize: scored?.sampleSize ?? snapshot?.sample_size ?? null,
    primaryEv: scored?.primaryEv ?? snapshot?.primary_ev ?? null,
    rationale: scored?.rationale ?? sanitized?.rationale ?? null,
  };
  candidates.push(candidate);
  const matchKey = String(snapshot?.match_key || '');
  const bucket = byMatchKey.get(matchKey) || [];
  bucket.push(candidate);
  byMatchKey.set(matchKey, bucket);
}
const shortlist = [];
for (const bucket of byMatchKey.values()) {
  const qualifying = bucket.filter((candidate) => candidate.passesStrategyFilters).sort(sortByStrategyThenEv);
  const best = qualifying[0];
  if (!best) continue;
  best.isBestBetForMatch = true;
  shortlist.push(best);
}
shortlist.sort(sortByStrategyThenEv);
const run = sanitizeAutoAnalysisRun({
  runId: runMeta.runId,
  runKey: runMeta.runKey,
  date: runMeta.date,
  strategyId,
  strategyLabel,
  source: runMeta.source,
  checkpointKey: runMeta.checkpointKey ?? null,
  checkpointLabel: runMeta.checkpointLabel ?? null,
  checkpointTargetDays: runMeta.checkpointTargetDays ?? null,
  analyzedMatches: byMatchKey.size,
  marketCount: candidates.length,
  candidateCount: candidates.length,
  qualifyingCandidateCount: candidates.filter((candidate) => candidate.passesStrategyFilters).length,
  shortlistCount: shortlist.length,
  provenCount: shortlist.filter((candidate) => candidate?.proof?.historicalReady).length,
  createdAt,
  updatedAt: createdAt,
});
const snapshotDoc = sanitizeAnalysisSnapshot({
  runId: run.runId,
  runKey: run.runKey,
  date: run.date,
  strategyId: run.strategyId,
  strategyLabel: run.strategyLabel,
  checkpointKey: run.checkpointKey ?? null,
  checkpointLabel: run.checkpointLabel ?? null,
  checkpointTargetDays: run.checkpointTargetDays ?? null,
  analyzedMatches: run.analyzedMatches,
  shortlist,
  createdAt,
});
console.log(JSON.stringify({
  run,
  candidates,
  shortlist,
  snapshot: snapshotDoc,
}));
"""
        result_summary_path = str((self.old_repo_root / "lib" / "backtest" / "resultSummary.js").resolve())
        store_path = str((self.old_repo_root / "lib" / "autoAnalysis" / "store.js").resolve())
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(self.old_repo_root), result_summary_path, store_path],
            input=json.dumps(
                {
                    "runMeta": run_meta,
                    "modelSnapshots": model_snapshot_docs,
                    "learningProfile": learning_profile,
                },
                ensure_ascii=False,
                default=str,
            ),
            text=True,
            capture_output=True,
            cwd=self.old_repo_root,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "original JS auto analysis oracle failed")
        parsed = _parse_json_from_node_output(completed.stdout)
        if not isinstance(parsed, dict):
            return {"run": {}, "candidates": [], "shortlist": [], "snapshot": {}}
        return {
            "run": parsed.get("run", {}) if isinstance(parsed.get("run"), dict) else {},
            "candidates": parsed.get("candidates", []) if isinstance(parsed.get("candidates"), list) else [],
            "shortlist": parsed.get("shortlist", []) if isinstance(parsed.get("shortlist"), list) else [],
            "snapshot": parsed.get("snapshot", {}) if isinstance(parsed.get("snapshot"), dict) else {},
        }
