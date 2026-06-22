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


class OriginalJsOracle:
    def __init__(self, old_repo_root: Path) -> None:
        self.old_repo_root = old_repo_root

    def lookup_event(self, match_info: dict[str, Any]) -> dict[str, Any] | None:
        script = """
import { pathToFileURL } from 'node:url';
async function readStdin() {
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  return input.trim();
}
const repoRoot = process.argv[1];
const modulePath = process.argv[2];
process.chdir(repoRoot);
const { findUnibetEventForMatch } = await import(pathToFileURL(modulePath).href);
const payload = JSON.parse((await readStdin()) || '{}');
const result = await findUnibetEventForMatch(payload);
console.log(JSON.stringify(result));
"""
        module_path = str((self.old_repo_root / "lib" / "backtest" / "unibetAuto.js").resolve())
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(self.old_repo_root), module_path],
            input=json.dumps(match_info, ensure_ascii=False),
            text=True,
            capture_output=True,
            cwd=self.old_repo_root,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "original JS discovery failed")
        return _parse_json_from_node_output(completed.stdout)

    def map_odds(self, bet_offers: list[dict[str, Any]], home_team: str, away_team: str) -> list[dict[str, Any]]:
        script = """
import { pathToFileURL } from 'node:url';
async function readStdin() {
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  return input.trim();
}
const repoRoot = process.argv[1];
const modulePath = process.argv[2];
process.chdir(repoRoot);
const mapper = (await import(pathToFileURL(modulePath).href)).default;
const payload = JSON.parse((await readStdin()) || '{}');
const result = mapper(payload.betOffers || [], payload.homeTeam, payload.awayTeam);
console.log(JSON.stringify(result));
"""
        module_path = str((self.old_repo_root / "components" / "backtest" / "unibetOddsMapper.js").resolve())
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(self.old_repo_root), module_path],
            input=json.dumps(
                {
                    "betOffers": bet_offers,
                    "homeTeam": home_team,
                    "awayTeam": away_team,
                },
                ensure_ascii=False,
            ),
            text=True,
            capture_output=True,
            cwd=self.old_repo_root,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "original JS mapper failed")
        mapped = _parse_json_from_node_output(completed.stdout)
        return mapped if isinstance(mapped, list) else []
