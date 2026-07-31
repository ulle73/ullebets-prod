# Ullebets agent instructions

These instructions apply to the entire repository.

## Mandatory reading order

Before inspecting code, changing files, or running a test:

1. Read `docs/work-log.md` in full.
2. Read `docs/app-readiness-checklist.md`.
3. Read the latest linked backend/model detail document relevant to the task.
4. Run `git status --short --branch` and preserve unrelated user changes.
5. Check whether `.codegraph/` exists. If it does not, run
   `codegraph init -i`. Use CodeGraph before larger code changes.
6. Identify what is already verified and test only the remaining gap unless
   relevant code, configuration, credentials, mappings, or source behavior
   changed.

Do not treat old conversation memory as current state when the work log or
runtime evidence says otherwise.

## Mandatory work-log update

Every work session that changes code, data, configuration, documentation, or
verified runtime state must update `docs/work-log.md` before completion.
If readiness changed, update `docs/app-readiness-checklist.md` in the same
session. Check a box only when current evidence proves the complete statement.

Each entry must record:

- Date and concise objective
- Status using the vocabulary defined in the log
- Files or subsystems changed
- Exact commands or scenarios tested
- Exact results, counts, and failures
- New technical or data insight
- What remains unproven or blocked
- The next test that is actually justified

Keep detailed model tables in `docs/ev-model-experiments.md` and detailed
backend acceptance state in `docs/v2-backend-verification-status.md`. The work
log should summarize and link to those sources rather than duplicate every
row.

Never write secrets, connection strings, API keys, tokens, or `.env` contents
to the work log.

## Evidence rules

- `VERIFIED` means a current command, test, database query, or artifact proves
  the claim.
- `PARTIAL` means the path works but required coverage or lifecycle evidence
  is incomplete.
- `FAILED` means a real reproducible failure exists.
- `UNPROVEN` means the required time window or source data has not existed yet.
- `BLOCKED` means progress requires new external data or a state change.
- `REJECTED` means an experiment was tested and failed its predefined gate.
- `NOT STARTED` means a required product area has no completed implementation
  yet.

An empty fixture or odds response is not automatically `FAILED`. It can be a
valid empty result when no source events exist.

Do not report historical ROI as proven forward +EV. Do not report aggregate
operational export ROI as model ROI. Out-of-domain model scores must remain
excluded from selection, ROI, CLV, and promotion evidence.

## Repository safety

- V2 writes must hard-fail unless `MONGODB_DB=ullebets_v2`.
- `app` and `ullebets_unibet` are read-only references, never V2 targets.
- Raw source data is immutable input; derived outputs must be rebuildable.
- Do not mutate frozen score rows, settled outcomes, model artifacts, or policy
  registries after forward outcomes become available.
- Do not change model/backtest logic merely to improve inspected historical
  outcomes.
- Do not rerun expensive historical experiments already recorded in the work
  log unless the input data, implementation, or explicit hypothesis changed.
- Never revert unrelated dirty-worktree changes.

## Engineering standard

Be skeptical. The most expensive unknown is whether a historical edge survives
new in-domain forward matches, not whether another filter can improve already
inspected ROI.

Prefer small, reproducible, leakage-safe tests with a predefined retention
gate. Preserve negative results. If evidence is missing, say `UNPROVEN` or
`BLOCKED` rather than guessing.
