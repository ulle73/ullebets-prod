# Durable Closing and Unified Results Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reliably capture accepted T-30 and preferred T-10 closing odds on free GitHub-hosted runners, then expose truthful checkpoint-labelled CLV and exact-market odds movement in one `Spel & resultat` surface.

**Architecture:** A portable Python watch-session service owns UTC timing, MongoDB lease/heartbeat recovery, and calls the existing idempotent closing capture path from one bounded GitHub job. Closing policy V2 accepts T-30 for product CLV and prefers T-10 without changing the existing T-10-only promotion evidence; the existing Auto read service becomes the single grouped API for the unified frontend.

**Tech Stack:** Python 3.13, PyMongo-compatible V2 storage, pytest, GitHub Actions YAML, React 19, TypeScript 6, TanStack Query, Radix UI, Vitest, ESLint, Vite.

---

## Working rules

- Work only in `C:/dev/ullebets-prod/.worktrees/durable-closing-results` on `codex/durable-closing-results`.
- Keep `MONGODB_DB=ullebets_v2` fail-closed behavior on every write path.
- Do not write to production during local tests; use fakes or `--dry-run`.
- Preserve raw snapshots, frozen scores, forward bets, settled outcomes, and model registries.
- Use TDD for every behavior task: red test, minimal implementation, green test, commit.
- Use Node `C:/Users/ryd/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe` for frontend gates.
- The initial full frontend baseline had one process-level fork-worker timeout; `remaining-routes.test.tsx` passed `5/5` in isolation. Treat future product assertion failures as real, but rerun a worker-start timeout once in isolation before diagnosis.

### Task 1: Repair checkpoint provenance at the real adapter boundary

**Files:**

- Modify: `src/ullebets_v2/ev_model/v2_forward_adapter.py:332-449`
- Modify: `tests/v2/test_ev_forward_adapter.py`
- Modify: `tests/v2/test_ev_forward_predictions.py`

**Step 1: Write the failing adapter test**

Add a canonical market fixture containing `snapshot_label="T_MINUS_3D"` and
`snapshot_type="forward"`, run it through `build_v2_forward_prediction_frame`,
and assert the returned prediction row carries both fields:

```python
prediction_frame, _ = build_v2_forward_prediction_frame(
    snapshot_docs=[snapshot_doc],
    primary_stat_docs=history_docs,
    availability_buffer_hours=0,
)
row = prediction_frame.iloc[0]
assert row["snapshot_label"] == "T_MINUS_3D"
assert row["snapshot_type"] == "forward"
```

Extend the forward-prediction persistence test to consume that adapter-shaped
row instead of injecting the label only after scoring.

**Step 2: Run the focused tests and verify red**

Run:

```powershell
python -m pytest tests/v2/test_ev_forward_adapter.py tests/v2/test_ev_forward_predictions.py -q
```

Expected: FAIL because `snapshot_label`/`snapshot_type` are absent from the
prediction frame.

**Step 3: Implement the minimal provenance pass-through**

Add both values to the adapter source row and passthrough columns:

```python
"snapshot_label": market.snapshot_label,
"snapshot_type": market.snapshot_type,
```

```python
passthrough_columns = [
    "match_key",
    "snapshot_key",
    "snapshot_label",
    "snapshot_type",
    "offer_key",
    # existing entity fields
]
```

Do not synthesize labels from keys; persist source provenance exactly.

**Step 4: Run the focused tests and verify green**

Run the same pytest command.

Expected: all focused tests PASS.

**Step 5: Commit**

```powershell
git add src/ullebets_v2/ev_model/v2_forward_adapter.py tests/v2/test_ev_forward_adapter.py tests/v2/test_ev_forward_predictions.py
git commit -m "fix: preserve forward checkpoint provenance"
```

### Task 2: Add versioned accepted-closing semantics without changing promotion evidence

**Files:**

- Modify: `src/ullebets_v2/closing/service.py:23-160`
- Modify: `src/ullebets_v2/clv_tracking/service.py:437-591`
- Modify: `src/ullebets_v2/forward_results/service.py:250-430`
- Modify: `src/ullebets_v2/ev_model/forward_evaluation.py:160-190`
- Modify: `src/ullebets_v2/ev_model/score_evaluation.py:350-380`
- Modify: `tests/v2/test_closing_capture.py`
- Modify: `tests/v2/test_clv_tracking.py`
- Modify: `tests/v2/test_forward_results.py`
- Modify: `tests/v2/test_ev_forward_evaluation.py`
- Modify: `tests/v2/test_ev_score_evaluation.py`

**Step 1: Write failing policy tests**

Add assertions for a T-30-only close:

```python
assert closing["closing_quality"] == "t30"
assert closing["closing_policy_version"] == "accepted_t30_t10_v2"
assert closing["accepted_for_product_clv"] is True
assert closing["eligible_for_promotion_clv"] is False

assert clv["clv_status"] == "tracked"
assert clv["accepted_clv"] is True
assert clv["official_clv"] is False
assert clv["closing_checkpoint"] == "T_MINUS_30M"
```

Add the T-10 upgrade assertions:

```python
assert upgraded["closing_quality"] == "t10"
assert upgraded["accepted_for_product_clv"] is True
assert upgraded["eligible_for_promotion_clv"] is True
```

Prove existing evaluation/promotion summaries still exclude T-30 while forward
product results include it in accepted CLV counts.

**Step 2: Run the focused tests and verify red**

Run:

```powershell
python -m pytest tests/v2/test_closing_capture.py tests/v2/test_clv_tracking.py tests/v2/test_forward_results.py tests/v2/test_ev_forward_evaluation.py tests/v2/test_ev_score_evaluation.py -q
```

Expected: FAIL on missing policy/accepted fields and the legacy
`tracked_fallback_t30` product status.

**Step 3: Implement the V2 policy fields**

Define constants in the closing service:

```python
CLOSING_POLICY_VERSION = "accepted_t30_t10_v2"
PRODUCT_ACCEPTED_QUALITIES = frozenset({"t30", "t10"})
PROMOTION_ELIGIBLE_QUALITIES = frozenset({"t10"})
```

Normalize new T-30 rows to `closing_quality="t30"`, but keep read compatibility
for historical `t30_fallback`. Persist explicit product/promotion flags and the
actual checkpoint. In CLV tracking, calculate signed CLV for either accepted
quality and keep `official_clv`/promotion eligibility T-10-only.

In forward results, add accepted CLV fields without removing existing official
fields:

```python
"accepted_clv": bool(clv_row and clv_row.get("accepted_clv")),
"accepted_clv_count": accepted_count,
"t10_clv_count": t10_count,
"t30_clv_count": t30_count,
"average_accepted_clv_pct": accepted_average,
"accepted_beat_closing_line_count": accepted_beats,
```

**Step 4: Run the focused tests and verify green**

Run the same pytest command.

Expected: all focused tests PASS and promotion-only assertions remain
T-10-only.

**Step 5: Commit**

```powershell
git add src/ullebets_v2/closing/service.py src/ullebets_v2/clv_tracking/service.py src/ullebets_v2/forward_results/service.py src/ullebets_v2/ev_model/forward_evaluation.py src/ullebets_v2/ev_model/score_evaluation.py tests/v2/test_closing_capture.py tests/v2/test_clv_tracking.py tests/v2/test_forward_results.py tests/v2/test_ev_forward_evaluation.py tests/v2/test_ev_score_evaluation.py
git commit -m "feat: accept t30 product closing with t10 upgrade"
```

### Task 3: Build deterministic watch-session planning and lease recovery

**Files:**

- Create: `src/ullebets_v2/closing/session.py`
- Modify: `src/ullebets_v2/storage/collections.py`
- Modify: `src/ullebets_v2/storage/indexes.py`
- Create: `tests/v2/test_closing_watch_session.py`
- Modify: `tests/v2/test_storage_contract.py`

**Step 1: Write failing pure planning tests**

Test session activation, target times, multiple kickoffs, terminal states, and
the next wake interval without sleeping:

```python
plan = build_watch_session_plan(
    fixture_docs=[fixture(start="2026-08-27T18:00:00Z")],
    snapshot_docs=[],
    now=dt("2026-08-27T14:00:00Z"),
    lookahead_hours=4.0,
)
assert plan["should_watch"] is True
assert plan["matches"][0]["next_checkpoint"] == "T_MINUS_30M"
assert plan["matches"][0]["next_attempt_at"] == dt("2026-08-27T17:25:00Z")
```

Add tests showing T-30 success moves the next target to T-10, T-10 success is
terminal, and kickoff with neither capture is `closing_missed`.

**Step 2: Run and verify red**

Run:

```powershell
python -m pytest tests/v2/test_closing_watch_session.py tests/v2/test_storage_contract.py -q
```

Expected: collection/service symbols do not exist.

**Step 3: Implement the pure plan and lease store**

Add `CLOSING_WATCH_SESSIONS = "closing_watch_sessions"` plus a unique
`session_key` index and lease-expiry lookup index.

Implement:

```python
def build_watch_session_plan(*, fixture_docs, snapshot_docs, now, lookahead_hours=4.0) -> dict: ...

def claim_watch_session(*, collection, session_key, owner_id, now, lease_seconds=180) -> dict | None: ...

def heartbeat_watch_session(*, collection, session_key, owner_id, now, lease_seconds=180, state) -> bool: ...

def release_watch_session(*, collection, session_key, owner_id, now, status, summary) -> bool: ...
```

Use one atomic `find_one_and_update` claim filter that permits a missing,
expired, or same-owner lease. Heartbeat and release must fail when `owner_id`
does not match so a stale runner cannot overwrite its replacement.

**Step 4: Add lease behavior tests and verify green**

Test claim, competing owner rejection, heartbeat extension, expired takeover,
stale-owner fencing, and terminal release. Run the same pytest command.

Expected: all tests PASS.

**Step 5: Commit**

```powershell
git add src/ullebets_v2/closing/session.py src/ullebets_v2/storage/collections.py src/ullebets_v2/storage/indexes.py tests/v2/test_closing_watch_session.py tests/v2/test_storage_contract.py
git commit -m "feat: add recoverable closing watch sessions"
```

### Task 4: Add the bounded watcher CLI and GitHub session workflow

**Files:**

- Create: `scripts/forward_v2/watch_closing_window.py`
- Modify: `scripts/forward_v2/capture_closing_snapshots.py`
- Modify: `.github/workflows/run-unibet-closing.yml`
- Modify: `.github/workflows/v2-odds-scheduler.yml`
- Modify: `src/ullebets_v2/verification/automation.py`
- Modify: `tests/v2/test_closing_watch.py`
- Modify: `tests/v2/test_automation_contract.py`

**Step 1: Write failing orchestration tests**

Inject a fake clock, sleeper, capture callable, and in-memory session store:

```python
summary = run_watch_session(
    database=fake_db,
    owner_id="run-123",
    now=fake_clock.now,
    sleep=fake_clock.sleep,
    capture=fake_capture,
    lookahead_hours=4.0,
    max_session_seconds=19_800,
    poll_seconds=60,
)
assert fake_capture.calls == [t30_attempt, t10_attempt]
assert summary["t30_captured_matches"] == 1
assert summary["t10_captured_matches"] == 1
```

Add restart-after-T-30, transient error retry, valid empty result, missed-both,
lease-lost, dry-run-no-write, and bounded-runtime tests.

Update automation contract tests to require:

- off-peak redundant seed cron;
- no workflow enable/disable commands;
- session CLI invocation;
- timeout less than six hours;
- existing global closing concurrency with `cancel-in-progress: false`;
- ordinary scheduler still excludes T-30/T-10.

**Step 2: Run and verify red**

Run:

```powershell
python -m pytest tests/v2/test_closing_watch.py tests/v2/test_closing_watch_session.py tests/v2/test_automation_contract.py -q
```

Expected: FAIL because the session CLI/workflow contract is absent.

**Step 3: Implement the watcher orchestration**

Implement `run_watch_session` as dependency-injected application logic and keep
`main()` limited to config/database/argument wiring. Poll no faster than once
per minute and sleep only until the next heartbeat or planned capture. Reuse
the existing closing capture service so derived refresh and idempotency remain
centralized.

CLI contract:

```text
--lookahead-hours 4
--max-session-minutes 330
--poll-seconds 60
--lease-seconds 180
--owner-id <github-run-id-attempt>
--dry-run
```

Change `run-unibet-closing.yml` to an always-enabled session seed such as
`cron: "7,22,37,52 * * * *"`, pass a timeout of 330 minutes, and invoke the
watcher CLI. Remove workflow state toggling from `v2-odds-scheduler.yml`.

**Step 4: Run focused tests and CLI dry-run**

Run:

```powershell
python -m pytest tests/v2/test_closing_watch.py tests/v2/test_closing_watch_session.py tests/v2/test_automation_contract.py -q
python scripts/forward_v2/watch_closing_window.py --lookahead-hours 4 --max-session-minutes 1 --poll-seconds 1 --dry-run
```

Expected: tests PASS; dry-run returns a structured summary and performs no
writes/captures.

**Step 5: Commit**

```powershell
git add scripts/forward_v2/watch_closing_window.py scripts/forward_v2/capture_closing_snapshots.py .github/workflows/run-unibet-closing.yml .github/workflows/v2-odds-scheduler.yml src/ullebets_v2/verification/automation.py tests/v2/test_closing_watch.py tests/v2/test_closing_watch_session.py tests/v2/test_automation_contract.py
git commit -m "feat: run durable free closing watch sessions"
```

### Task 5: Expose accepted CLV and exact-market movement in the Auto read contract

**Files:**

- Modify: `src/ullebets_v2/forward_exposures.py`
- Modify: `src/ullebets_v2/read_api/service.py:900-1110`
- Modify: `tests/v2/test_forward_exposures.py`
- Modify: `tests/v2/test_read_api_contracts.py`
- Modify: `frontend/src/domain/types.ts:300-440`
- Modify: `frontend/src/data/api.ts`

**Step 1: Write failing grouping/read tests**

Create a grouped checkpoint journal containing two saved-odds observations and
one exact-market closing timeline. Assert:

```python
row = response["selections"][0]
assert row["acceptedClvCount"] == 2
assert row["t30ClvCount"] == 2
assert row["t10ClvCount"] == 0
assert row["beatClosingLineCount"] == 1
assert row["averageAcceptedClvPct"] == 0.5
assert row["closingStatus"] == "accepted"
assert row["closingQuality"] == "t30"
assert row["oddsHistory"] == [
    {
        "snapshotLabel": "T_MINUS_3D",
        "observedAt": "2026-08-24T18:00:00Z",
        "odds": 1.90,
        "lineValue": 3.5,
        "selected": True,
        "closing": False,
    },
    {
        "snapshotLabel": "T_MINUS_30M",
        "observedAt": "2026-08-27T17:30:00Z",
        "odds": 1.84,
        "lineValue": 3.5,
        "selected": False,
        "closing": True,
    },
]
```

Add a guard fixture with another line/direction and prove it is excluded from
the movement series.

**Step 2: Run and verify red**

Run:

```powershell
python -m pytest tests/v2/test_forward_exposures.py tests/v2/test_read_api_contracts.py -q
```

Expected: FAIL on missing accepted/movement fields.

**Step 3: Implement one server-side grouped contract**

Extend grouping to aggregate accepted comparisons over underlying immutable
observations and deduplicate/sort price history by observation time plus stable
snapshot key. Preserve line/direction identity. Map snake-case persistence
fields to the camel-case read contract in `_forward_selection_read_model`.

Add TypeScript types:

```ts
export interface OddsHistoryPoint {
  snapshotLabel: string | null;
  observedAt: string | null;
  odds: number | null;
  lineValue: number | null;
  selected: boolean;
  closing: boolean;
  closingQuality?: 't10' | 't30' | null;
}
```

Keep old optional official fields for compatibility.

**Step 4: Run backend tests and TypeScript**

Run:

```powershell
python -m pytest tests/v2/test_forward_exposures.py tests/v2/test_read_api_contracts.py -q
& 'C:/Users/ryd/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' frontend/node_modules/typescript/bin/tsc -b frontend/tsconfig.json --pretty false
```

Expected: focused tests and typecheck PASS.

**Step 5: Commit**

```powershell
git add src/ullebets_v2/forward_exposures.py src/ullebets_v2/read_api/service.py tests/v2/test_forward_exposures.py tests/v2/test_read_api_contracts.py frontend/src/domain/types.ts frontend/src/data/api.ts
git commit -m "feat: expose accepted clv and odds movement"
```

### Task 6: Unify navigation and render truthful CLV states

**Files:**

- Modify: `frontend/src/components/TopNav.tsx`
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/pages/AutoPage.tsx`
- Modify: `frontend/src/domain/formatters.ts`
- Modify: `frontend/src/styles/workflow-pages.css`
- Modify: `frontend/src/app/step1-navigation.test.tsx`
- Modify: `frontend/src/app/step3-workflow-pages.test.tsx`
- Create: `frontend/src/app/unified-results.test.tsx`

**Step 1: Write failing navigation/status tests**

Assert the nav contains exactly one forward destination labelled
`Spel & resultat`, and `/resultatloop` redirects to
`/auto?status=settled`.

Render four rows and assert:

```ts
expect(screen.getByText('Slog closing +3,5 % · T-30')).toBeVisible();
expect(screen.getByText('Missade closing −1,8 % · T-10')).toBeVisible();
expect(screen.getByText('Väntar på closing')).toBeVisible();
expect(screen.getByText('Closing missad')).toBeVisible();
expect(screen.queryByText('CLV saknas')).not.toBeInTheDocument();
```

Assert model EV and CLV have separate column headers.

**Step 2: Run and verify red**

Run from `frontend`:

```powershell
& 'C:/Users/ryd/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' node_modules/vitest/vitest.mjs run src/app/step1-navigation.test.tsx src/app/step3-workflow-pages.test.tsx src/app/unified-results.test.tsx --pool=forks --maxWorkers=1 --fileParallelism=false
```

Expected: FAIL because duplicate nav/routes and accepted CLV UI remain.

**Step 3: Implement the unified page**

- Rename the `/auto` nav label to `Spel & resultat`.
- Remove the Resultatloop nav item.
- Replace its route element with a redirect preserving a settled status query.
- Add URL-backed `open`, `settled`, and `excluded` status choices to Auto.
- Add accepted CLV/closing columns and coverage cards.
- Do not display T-30 as missing or as T-10.
- Keep existing model-family/stat/scope/period/direction/checkpoint filters.

**Step 4: Run focused frontend tests**

Run the same Vitest command.

Expected: focused files PASS.

**Step 5: Commit**

```powershell
git add frontend/src/components/TopNav.tsx frontend/src/app/App.tsx frontend/src/pages/AutoPage.tsx frontend/src/domain/formatters.ts frontend/src/styles/workflow-pages.css frontend/src/app/step1-navigation.test.tsx frontend/src/app/step3-workflow-pages.test.tsx frontend/src/app/unified-results.test.tsx
git commit -m "feat: unify forward plays and results"
```

### Task 7: Add accessible odds-movement detail

**Files:**

- Create: `frontend/src/components/OddsMovementPanel.tsx`
- Modify: `frontend/src/pages/AutoPage.tsx`
- Modify: `frontend/src/styles/workflow-pages.css`
- Modify: `frontend/src/app/unified-results.test.tsx`

**Step 1: Write failing interaction tests**

Use `userEvent` to activate the odds control by click and keyboard. Assert the
same dialog/popover exposes chronological points, selected/closing labels, and
can be closed with Escape:

```ts
await user.click(screen.getByRole('button', { name: /Visa oddsrörelse/i }));
expect(screen.getByRole('dialog', { name: /Oddsrörelse/i })).toBeVisible();
expect(screen.getByText('T-3D · 1,90')).toBeVisible();
expect(screen.getByText('T-30 · 1,84 · Closing')).toBeVisible();
await user.keyboard('{Escape}');
expect(screen.queryByRole('dialog', { name: /Oddsrörelse/i })).not.toBeInTheDocument();
```

**Step 2: Run and verify red**

Run:

```powershell
& 'C:/Users/ryd/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' node_modules/vitest/vitest.mjs run src/app/unified-results.test.tsx --pool=forks --maxWorkers=1 --fileParallelism=false
```

Expected: FAIL because the control/dialog does not exist.

**Step 3: Implement with existing Radix primitives**

Use the installed Radix Dialog or Tooltip primitives, but make click/focus the
durable interaction. Render one ordered list of exact-market points, actual
timestamps, odds, selected marker, closing marker, and checkpoint quality.
Hover may open a preview, but all information must remain reachable by keyboard
and touch.

**Step 4: Run focused tests, typecheck, and lint**

Run:

```powershell
& 'C:/Users/ryd/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' node_modules/vitest/vitest.mjs run src/app/unified-results.test.tsx --pool=forks --maxWorkers=1 --fileParallelism=false
& 'C:/Users/ryd/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' node_modules/typescript/bin/tsc -b --pretty false
& 'C:/Users/ryd/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' node_modules/eslint/bin/eslint.js . --max-warnings=0
```

Expected: all commands PASS.

**Step 5: Commit**

```powershell
git add frontend/src/components/OddsMovementPanel.tsx frontend/src/pages/AutoPage.tsx frontend/src/styles/workflow-pages.css frontend/src/app/unified-results.test.tsx
git commit -m "feat: show accessible odds movement"
```

### Task 8: Update reports, readiness evidence, and complete local verification

**Files:**

- Modify: `src/ullebets_v2/clv_tracking/reports.py`
- Modify: `src/ullebets_v2/closing/reports.py`
- Modify: `docs/work-log.md`
- Modify: `docs/app-readiness-checklist.md`
- Modify: `docs/v2-backend-verification-status.md`
- Test: `tests/v2/test_clv_tracking.py`
- Test: `tests/v2/test_closing_capture.py`
- Test: `tests/v2/test_automation_contract.py`

**Step 1: Write failing report assertions**

Require reports to split `t10`, `t30`, waiting, and missed counts and to avoid
calling accepted T-30 `missing_closing_line` or official T-10:

```python
assert report["accepted_product_clv_rows"] == 2
assert report["t10_clv_rows"] == 1
assert report["t30_clv_rows"] == 1
assert report["promotion_eligible_clv_rows"] == 1
```

**Step 2: Run and verify red**

Run:

```powershell
python -m pytest tests/v2/test_closing_capture.py tests/v2/test_clv_tracking.py tests/v2/test_automation_contract.py -q
```

Expected: FAIL on missing split metrics.

**Step 3: Implement reporting and documentation**

Add the split metrics to persisted audit/health summaries. Update the work log
with exact files, commands, counts, failures, new insight, remaining live gap,
and next justified production test. Update readiness only for locally proven
implementation; keep the real hosted watch lifecycle `PARTIAL` until a real
match proves it.

**Step 4: Run all verification gates**

Backend:

```powershell
python -m pytest tests/v2 -q
python -m compileall -q src/ullebets_v2 scripts/forward_v2
```

Frontend from `frontend` with Node 24.19:

```powershell
& 'C:/Users/ryd/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' node_modules/vitest/vitest.mjs run --pool=forks --maxWorkers=1 --fileParallelism=false
& 'C:/Users/ryd/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' node_modules/typescript/bin/tsc -b --pretty false
& 'C:/Users/ryd/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' node_modules/eslint/bin/eslint.js . --max-warnings=0
& 'C:/Users/ryd/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' node_modules/vite/bin/vite.js build
```

Repository:

```powershell
git diff --check
git status --short --branch
```

Expected: `529+` backend tests PASS; all frontend tests PASS without product
assertion failures; typecheck/lint/build/compileall/diff-check PASS. If the
known Vitest fork-worker startup timeout recurs, rerun the affected files
individually and record both results rather than hiding the full-suite failure.

**Step 5: Commit final evidence**

```powershell
git add src/ullebets_v2/clv_tracking/reports.py src/ullebets_v2/closing/reports.py tests/v2/test_clv_tracking.py tests/v2/test_closing_capture.py tests/v2/test_automation_contract.py docs/work-log.md docs/app-readiness-checklist.md docs/v2-backend-verification-status.md
git commit -m "docs: verify durable closing and unified results"
```

### Task 9: Review branch scope before delivery

**Files:** None expected beyond prior tasks.

**Step 1: Inspect all commits and files**

```powershell
git log --oneline main..HEAD
git diff --stat main...HEAD
git diff --check main...HEAD
git status --short --branch
```

Expected: only approved watcher, closing/CLV, provenance, read API, unified UI,
tests, and required docs are present; `.playwright-cli/` is absent from the
branch.

**Step 2: Verify no unsafe semantic drift**

Search for promotion and closing labels:

```powershell
rg -n "official_clv|eligible_for_promotion_clv|accepted_for_product_clv|t30_fallback|closing_policy_version" src tests frontend docs
```

Expected: product acceptance includes T-30; existing promotion metrics remain
T-10-only; compatibility handling is explicit.

**Step 3: Commit only if review repairs were required**

```powershell
git add <reviewed-files>
git commit -m "fix: address closing lifecycle review"
```

Expected: clean worktree and review-ready branch.
