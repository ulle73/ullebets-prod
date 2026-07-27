from __future__ import annotations

from pathlib import Path
import json
import subprocess
from typing import Any

from ullebets_v2.model_snapshots.data_adapter import V2ModelDataAdapter


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


class OriginalJsModelOracle:
    model_source = "original_js_model_oracle"

    def __init__(self, old_repo_root: Path) -> None:
        self.old_repo_root = old_repo_root

    def build_match_lines(
        self,
        *,
        match_info: dict[str, Any],
        offers: list[dict[str, Any]],
        defaults: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        script = """
import { pathToFileURL } from 'node:url';
async function readStdin() {
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  return input.trim();
}
const repoRoot = process.argv[1];
const evEnginePath = process.argv[2];
const primaryEvPath = process.argv[3];
const keysPath = process.argv[4];
process.chdir(repoRoot);
const { calculateEvForBet, clearTeamDataCache } = await import(pathToFileURL(evEnginePath).href);
const { pickPrimaryEvSelection } = await import(pathToFileURL(primaryEvPath).href);
const { buildBetKey } = await import(pathToFileURL(keysPath).href);
const payload = JSON.parse((await readStdin()) || '{}');
const match = payload.matchInfo || {};
const defaults = payload.defaults || {};
const tuples = Array.isArray(payload.offers) ? payload.offers : [];
const lines = [];
const errors = [];
for (const tuple of tuples) {
  for (const direction of ['over', 'under']) {
    const oddValue = tuple?.odds?.[direction];
    if (!(typeof oddValue === 'number' && Number.isFinite(oddValue) && oddValue > 1)) continue;
    try {
      const betParams = {
        homeTeam: match.homeTeam,
        awayTeam: match.awayTeam,
        stat: tuple.statKey,
        scope: tuple.scope,
        period: tuple.period,
        line: tuple.line,
        over: direction === 'over',
        odds: Number(oddValue),
        form: defaults.form ?? 'all',
        neutralGround: defaults.neutralGround ?? false,
        home_importance: defaults.home_importance ?? 5,
        away_importance: defaults.away_importance ?? 5,
      };
      const result = await calculateEvForBet(betParams);
      const selection = pickPrimaryEvSelection({
        evDetails: result?.evDetails || {},
        statKey: tuple.statKey,
        scope: tuple.scope,
        period: tuple.period,
      });
      lines.push({
        betKey: buildBetKey({
          matchId: match.matchId,
          homeTeam: match.homeTeam,
          awayTeam: match.awayTeam,
          stat: tuple.statKey,
          scope: tuple.scope,
          period: tuple.period,
          line: tuple.line,
          over: direction === 'over',
          form: defaults.form ?? 'all',
          neutralGround: defaults.neutralGround ?? false,
        }),
        statKey: tuple.statKey,
        line: tuple.line,
        condition: direction === 'over' ? 'över' : 'under',
        direction,
        period: tuple.period,
        scope: tuple.scope,
        odds: Number(oddValue),
        value: result?.value ?? selection?.evPct ?? null,
        evDetails: result?.evDetails || {},
        primaryFormulaKey: selection?.formulaKey ?? null,
        primaryValueKey: selection?.valueKey ?? null,
        sampleSize: result?.matches ?? null,
        homeTeam: match.homeTeam,
        awayTeam: match.awayTeam,
        actual: null,
        win: null,
      });
    } catch (error) {
      errors.push({
        statKey: tuple?.statKey || null,
        scope: tuple?.scope || null,
        period: tuple?.period || null,
        line: tuple?.line ?? null,
        direction,
        message: error?.message || String(error),
      });
    }
  }
}
clearTeamDataCache();
console.log(JSON.stringify({ lines, errors }));
"""
        ev_engine_path = str((self.old_repo_root / "lib" / "engines" / "ev-engine.js").resolve())
        primary_ev_path = str((self.old_repo_root / "lib" / "backtest" / "primaryEvSelection.js").resolve())
        keys_path = str((self.old_repo_root / "lib" / "core" / "keys.js").resolve())
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(self.old_repo_root), ev_engine_path, primary_ev_path, keys_path],
            input=json.dumps(
                {
                    "matchInfo": match_info,
                    "offers": offers,
                    "defaults": defaults or {},
                },
                ensure_ascii=False,
            ),
            text=True,
            capture_output=True,
            cwd=self.old_repo_root,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "original JS model line build failed")
        parsed = _parse_json_from_node_output(completed.stdout)
        if not isinstance(parsed, dict):
            return {"lines": [], "errors": [{"message": "invalid_oracle_response"}]}
        return {
            "lines": parsed.get("lines", []) if isinstance(parsed.get("lines"), list) else [],
            "errors": parsed.get("errors", []) if isinstance(parsed.get("errors"), list) else [],
        }


class V2JsModelOracle:
    model_source = "v2_js_model_oracle"

    def __init__(
        self,
        read_database: Any,
        support_docs: dict[str, Any],
        *,
        runtime_root: Path | None = None,
    ) -> None:
        self.read_database = read_database
        self.support_docs = support_docs
        self.runtime_root = runtime_root or (Path(__file__).resolve().parent / "js_runtime")
        self.data_adapter = V2ModelDataAdapter(read_database, support_docs)

    def build_match_lines(
        self,
        *,
        match_info: dict[str, Any],
        offers: list[dict[str, Any]],
        defaults: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        script = """
import path from 'node:path';
import { pathToFileURL } from 'node:url';
async function readStdin() {
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  return input.trim();
}
const runtimeRoot = process.argv[1];
const enginePath = path.join(runtimeRoot, 'backtest', 'engine.js');
const primaryEvPath = path.join(runtimeRoot, 'backtest', 'primaryEvSelection.js');
const keysPath = path.join(runtimeRoot, 'core', 'keys.js');
const { calculateEVFromData } = await import(pathToFileURL(enginePath).href);
const { pickPrimaryEvSelection } = await import(pathToFileURL(primaryEvPath).href);
const { buildBetKey } = await import(pathToFileURL(keysPath).href);
const payload = JSON.parse((await readStdin()) || '{}');
const match = payload.matchInfo || {};
const defaults = payload.defaults || {};
const fetchedData = payload.fetchedData || {};
const tuples = Array.isArray(payload.offers) ? payload.offers : [];
const lines = [];
const errors = [];
for (const tuple of tuples) {
  for (const direction of ['over', 'under']) {
    const oddValue = tuple?.odds?.[direction];
    if (!(typeof oddValue === 'number' && Number.isFinite(oddValue) && oddValue > 1)) continue;
    try {
      const betParams = {
        homeTeam: match.homeTeam,
        awayTeam: match.awayTeam,
        stat: tuple.statKey,
        scope: tuple.scope,
        period: tuple.period,
        line: tuple.line,
        over: direction === 'over',
        odds: Number(oddValue),
        form: defaults.form ?? 'all',
        neutralGround: defaults.neutralGround ?? false,
        home_importance: defaults.home_importance ?? 5,
        away_importance: defaults.away_importance ?? 5,
        matchDate: match.sourceDate ?? null,
      };
      const result = await calculateEVFromData(betParams, fetchedData);
      const selection = pickPrimaryEvSelection({
        evDetails: result?.evDetails || {},
        statKey: tuple.statKey,
        scope: tuple.scope,
        period: tuple.period,
      });
      lines.push({
        betKey: buildBetKey({
          matchId: match.matchId,
          homeTeam: match.homeTeam,
          awayTeam: match.awayTeam,
          stat: tuple.statKey,
          scope: tuple.scope,
          period: tuple.period,
          line: tuple.line,
          over: direction === 'over',
          form: defaults.form ?? 'all',
          neutralGround: defaults.neutralGround ?? false,
        }),
        statKey: tuple.statKey,
        line: tuple.line,
        condition: direction === 'over' ? 'över' : 'under',
        direction,
        period: tuple.period,
        scope: tuple.scope,
        odds: Number(oddValue),
        value: result?.value ?? selection?.evPct ?? null,
        evDetails: result?.evDetails || {},
        primaryFormulaKey: selection?.formulaKey ?? null,
        primaryValueKey: selection?.valueKey ?? null,
        sampleSize: result?.matches ?? null,
        homeTeam: match.homeTeam,
        awayTeam: match.awayTeam,
        actual: null,
        win: null,
      });
    } catch (error) {
      errors.push({
        statKey: tuple?.statKey || null,
        scope: tuple?.scope || null,
        period: tuple?.period || null,
        line: tuple?.line ?? null,
        direction,
        message: error?.message || String(error),
      });
    }
  }
}
console.log(JSON.stringify({ lines, errors }));
"""
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(self.runtime_root)],
            input=json.dumps(
                {
                    "matchInfo": match_info,
                    "offers": offers,
                    "defaults": defaults or {},
                    "fetchedData": self.data_adapter.build_fetched_data(match_info),
                },
                ensure_ascii=False,
                default=str,
            ),
            text=True,
            capture_output=True,
            cwd=self.runtime_root,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "v2 JS model line build failed")
        parsed = _parse_json_from_node_output(completed.stdout)
        if not isinstance(parsed, dict):
            return {"lines": [], "errors": [{"message": "invalid_oracle_response"}]}
        return {
            "lines": parsed.get("lines", []) if isinstance(parsed.get("lines"), list) else [],
            "errors": parsed.get("errors", []) if isinstance(parsed.get("errors"), list) else [],
        }
