# V6 Full-Domain Checkpoint Journal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically record, group, settle, and evaluate every supported positive-EV V6 checkpoint observation without mutating frozen V1 evidence.

**Architecture:** Extend the existing immutable score -> forward bet -> settlement -> CLV -> forward result pipeline with a new checkpoint-observation policy. Storage and evaluation retain each snapshot; the read API alone groups observations by market and exposes aggregate ROI/CLV metrics.

**Tech Stack:** Python 3.13, pandas, MongoDB/PyMongo, pytest, React 19, TypeScript, TanStack Query, Vitest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-23-v6-checkpoint-journal-design.md`

## Global Constraints

- Never mutate `forward_policy_registry_v1` or old forward rows.
- V2 writes must hard-fail unless `MONGODB_DB=ullebets_v2`.
- Every checkpoint observation is immutable and has stake `1.0` unit.
- Grouping is read-only; settlement, ROI, and CLV retain each observation.
- Unsupported stat keys never receive V6 probability or EV values.
- No forward ROI or CLV claim is `VERIFIED` until current runtime evidence proves it.

---

### Task 1: Register the supported V6 checkpoint policy

**Files:**
- Create: `src/ullebets_v2/ev_model/support.py`
- Create: `models/ev/forward_policy_registry_v2.json`
- Modify: `src/ullebets_v2/ev_model/score_evaluation.py`
- Test: `tests/v2/test_ev_policy_registry.py`
- Test: `tests/v2/test_ev_score_evaluation.py`

**Interfaces:**
- Produces: `classify_v6_market_support(stat_key, scope, period) -> dict[str, object]` and recursive `any_of` policy filtering.
- Produces: policy `v6_full_domain_checkpoint_journal_v2` with `selection_granularity="checkpoint_observation"`.

- [ ] **Step 1: Write failing registry and filter tests**

```python
def test_v2_forward_registry_adds_full_domain_checkpoint_journal():
    policy = load_policy_registry(PATH)["policies"][-1]
    assert policy["selection_granularity"] == "checkpoint_observation"
    assert policy["minimum_ev"] == 0.0
    assert policy["maximum_ev"] is None

def test_policy_filter_any_of_keeps_corners_both_sides_and_shots_over_only():
    rows = filter_policy_scores(SCORES, FILTERS)
    assert {(row["stat_key"], row["direction"]) for row in rows} == {
        ("cornerKicks", "over"), ("cornerKicks", "under"),
        ("shotsOnGoal", "over"), ("totalShots", "over"),
    }
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `python -m pytest tests/v2/test_ev_policy_registry.py tests/v2/test_ev_score_evaluation.py -q`

Expected: failure because V2 registry, support contract, and `any_of` are absent.

- [ ] **Step 3: Implement the support contract, recursive filter, and immutable overlay registry**

```python
V6_STAT_DIRECTIONS = {
    "cornerKicks": ("over", "under"),
    "shotsOnGoal": ("over",),
    "totalShots": ("over",),
}

def filter_policy_scores(scores, filters):
    any_of = filters.get("any_of")
    base = _filter_all(scores, {k: v for k, v in filters.items() if k != "any_of"})
    if any_of is None:
        return base
    allowed_keys = {row["score_key"] for clause in any_of for row in _filter_all(base, clause)}
    return [row for row in base if row["score_key"] in allowed_keys]
```

- [ ] **Step 4: Run the focused tests and confirm they pass**

Run: `python -m pytest tests/v2/test_ev_policy_registry.py tests/v2/test_ev_score_evaluation.py -q`

Expected: all selected tests pass and V1 expectations remain unchanged.

### Task 2: Persist every eligible checkpoint observation idempotently

**Files:**
- Modify: `src/ullebets_v2/ev_model/forward_predictions.py`
- Modify: `src/ullebets_v2/forward_exposures.py`
- Modify: `scripts/forward_v2/score_ev_shadow_model.py`
- Test: `tests/v2/test_ev_forward_predictions.py`
- Test: `tests/v2/test_forward_exposures.py`

**Interfaces:**
- Consumes: policy field `selection_granularity` from Task 1.
- Produces: `snapshot_label`, `snapshot_type`, and `selection_granularity` on each prediction.
- Produces: `forward_evaluation_key(row) -> str`, which includes snapshot identity only for checkpoint observations.

- [ ] **Step 1: Write failing provenance and canonicalization tests**

```python
def test_checkpoint_policy_prediction_keeps_snapshot_provenance():
    row = build_registered_policy_prediction_docs(SCORES, policy=POLICY, ...)[0]
    assert row["snapshot_label"] == "T_MINUS_2H"
    assert row["selection_granularity"] == "checkpoint_observation"

def test_checkpoint_observations_are_distinct_evaluation_units_but_one_display_group():
    canonical, audit = canonicalize_forward_bet_docs([T3D, T2H])
    assert len(canonical) == 2
    assert len({row["canonical_exposure_key"] for row in canonical}) == 1
    assert audit["collapsed_duplicate_count"] == 0
```

- [ ] **Step 2: Run focused tests and confirm they fail**

Run: `python -m pytest tests/v2/test_ev_forward_predictions.py tests/v2/test_forward_exposures.py -q`

- [ ] **Step 3: Propagate checkpoint fields and make canonicalization granularity-aware**

```python
def forward_evaluation_key(row):
    group_key = forward_exposure_key(row)
    if row.get("selection_granularity") != "checkpoint_observation":
        return group_key
    snapshot = row.get("snapshot_key") or row.get("odds_snapshot_time")
    return f"{group_key}:checkpoint:{stable_json_hash({'snapshot': str(snapshot)})}"
```

The scorer skips the old whole-match freeze only when the selected policy is a
checkpoint-observation policy. Existing immutable score and prediction keys
make reruns idempotent.

- [ ] **Step 4: Run focused tests and confirm they pass**

Run: `python -m pytest tests/v2/test_ev_forward_predictions.py tests/v2/test_forward_exposures.py -q`

### Task 3: Preserve checkpoint provenance through settlement and CLV

**Files:**
- Modify: `src/ullebets_v2/clv_tracking/service.py`
- Modify: `src/ullebets_v2/forward_results/service.py`
- Test: `tests/v2/test_settlement.py`
- Test: `tests/v2/test_clv_tracking.py`
- Test: `tests/v2/test_forward_results.py`

**Interfaces:**
- Consumes: granularity-aware canonical rows from Task 2.
- Produces: one settlement, CLV row, and result row per checkpoint prediction key.
- Preserves: `canonical_exposure_key`, `snapshot_label`, `snapshot_type`, `selection_granularity`, `expected_roi_units`.

- [ ] **Step 1: Write failing two-checkpoint lifecycle tests**

```python
def test_two_checkpoint_observations_each_settle_and_track_clv():
    summary = run_forward_result_refresh(forward_bet_docs=[T3D, T2H], ...)
    assert len(summary["result_docs"]) == 2
    assert {row["snapshot_label"] for row in summary["result_docs"]} == {
        "T_MINUS_3D", "T_MINUS_2H",
    }
    assert all(row["stake_units"] == 1.0 for row in summary["result_docs"])
```

- [ ] **Step 2: Run lifecycle tests and confirm they fail**

Run: `python -m pytest tests/v2/test_settlement.py tests/v2/test_clv_tracking.py tests/v2/test_forward_results.py -q`

- [ ] **Step 3: Propagate the immutable checkpoint fields through normalized CLV and result documents**

```python
for field in (
    "canonical_exposure_key", "snapshot_label", "snapshot_type",
    "selection_granularity", "expected_roi_units",
):
    result_doc[field] = row.get(field)
```

- [ ] **Step 4: Run lifecycle tests and confirm they pass**

Run: `python -m pytest tests/v2/test_settlement.py tests/v2/test_clv_tracking.py tests/v2/test_forward_results.py -q`

### Task 4: Group observations and expose horizon performance in the read API

**Files:**
- Modify: `src/ullebets_v2/forward_exposures.py`
- Modify: `src/ullebets_v2/read_api/service.py`
- Modify: `src/ullebets_v2/read_api/http.py`
- Test: `tests/v2/test_forward_exposures.py`
- Test: `tests/v2/test_read_api.py`
- Test: `tests/v2/test_read_api_contracts.py`

**Interfaces:**
- Produces: `group_forward_observation_docs(rows) -> list[dict[str, Any]]`.
- Produces: `checkpoint` query support on `/auto` and `/results`.
- Produces grouped fields: `observationCount`, `checkpointLabels`, `bestSnapshotLabel`, `groupStakeUnits`, `groupPnlUnits`, `groupRoiUnits`, `officialClvCount`, `beatClosingLineCount`, `clvBeatRate`, `averageClvPct`.

- [ ] **Step 1: Write failing grouping, pagination, and checkpoint-filter tests**

```python
def test_auto_groups_same_market_after_checkpoint_filtering_and_shows_best_ev():
    payload = read_auto(DB, checkpoint="T_MINUS_2H")
    assert payload["summary"]["observations"] == 1
    assert payload["selections"][0]["bestSnapshotLabel"] == "T_MINUS_2H"

def test_results_group_aggregates_one_unit_per_observation():
    payload = read_results(DB)
    row = payload["rows"][0]
    assert row["observationCount"] == 2
    assert row["groupStakeUnits"] == 2.0
    assert row["groupPnlUnits"] == 1.8
```

- [ ] **Step 2: Run read tests and confirm they fail**

Run: `python -m pytest tests/v2/test_forward_exposures.py tests/v2/test_read_api.py tests/v2/test_read_api_contracts.py -q`

- [ ] **Step 3: Implement server-side grouping before pagination and summaries over underlying observations**

```python
representative = min(
    group,
    key=lambda row: (-float(row.get("expected_roi_units") or float("-inf")), observation_time(row), selection_key(row)),
)
representative["observation_count"] = len(group)
representative["group_stake_units"] = sum(float(row.get("stake_units") or 0) for row in group)
representative["group_pnl_units"] = sum(float(row.get("pnl_units") or 0) for row in group)
```

- [ ] **Step 4: Add V6 support state to normalized match-market offers**

```python
support = classify_v6_market_support(row.get("stat_key"), row.get("scope"), row.get("period"))
return {**offer, "modelSupport": support["status"], "supportedDirections": support["directions"]}
```

- [ ] **Step 5: Run read tests and confirm they pass**

Run: `python -m pytest tests/v2/test_forward_exposures.py tests/v2/test_read_api.py tests/v2/test_read_api_contracts.py -q`

### Task 5: Render the simple grouped journal and model support

**Files:**
- Modify: `frontend/src/domain/types.ts`
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/data/workflow-query.ts`
- Modify: `frontend/src/domain/workflow-filter-options.ts`
- Modify: `frontend/src/pages/AutoPage.tsx`
- Modify: `frontend/src/pages/ResultsLoopPage.tsx`
- Modify: `frontend/src/pages/MatchDetailPage.tsx`
- Modify: `frontend/src/components/ForwardResultTable.tsx`
- Modify: `frontend/src/styles/auto-exposures.css`
- Test: `frontend/src/app/step2-drilldowns.test.tsx`
- Test: `frontend/src/app/step3-workflow-pages.test.tsx`

**Interfaces:**
- Consumes: grouped read models and checkpoint query from Task 4.
- Produces: URL-shareable stat, scope, period, direction, and checkpoint filters.
- Shows: best EV representative plus observation/ROI/CLV aggregates.

- [ ] **Step 1: Write failing frontend contract tests**

```tsx
expect(params(lastAutoCall).get('checkpoint')).toBe('T_MINUS_2H');
expect(screen.getByText('3 observationer')).toBeInTheDocument();
expect(screen.getByText('V6-modell saknas')).toBeInTheDocument();
```

- [ ] **Step 2: Run focused frontend tests and confirm they fail**

Run: `npm test -- --run src/app/step2-drilldowns.test.tsx src/app/step3-workflow-pages.test.tsx`

- [ ] **Step 3: Extend types, query parsing, filters, grouped metrics, and support badges**

```typescript
export interface AutoQuery extends ApiQuery {
  checkpoint?: string;
}

export const CHECKPOINT_OPTIONS = [
  { value: '', label: 'Alla checkpoints' },
  { value: 'T_MINUS_3D', label: 'T-3D' },
  { value: 'T_MINUS_2D', label: 'T-2D' },
  { value: 'T_MINUS_1D', label: 'T-1D' },
  { value: 'T_MINUS_2H', label: 'T-2H' },
  { value: 'T_MINUS_30M', label: 'T-30' },
  { value: 'T_MINUS_10M', label: 'T-10' },
];
```

- [ ] **Step 4: Run focused tests and build**

Run: `npm test -- --run src/app/step2-drilldowns.test.tsx src/app/step3-workflow-pages.test.tsx`

Run: `npm run build`

Expected: tests and production build pass.

### Task 6: Wire automatic scoring and post-match refresh

**Files:**
- Modify: `.github/workflows/v2-odds-scheduler.yml`
- Modify: `.github/workflows/run-unibet-closing.yml`
- Modify: `.github/workflows/ev-shadow-forward.yml`
- Modify: `.github/workflows/ev-shadow-settlement.yml`
- Modify: `tests/v2/test_automation_contract.py`

**Interfaces:**
- Consumes: V2 policy and checkpoint observation behavior from Tasks 1-3.
- Produces: automatic score -> settle -> CLV -> read-result lifecycle.

- [ ] **Step 1: Write failing workflow contract tests**

```python
assert "forward_policy_registry_v2.json" in odds_scheduler
assert "v6_full_domain_checkpoint_journal_v2" in closing_workflow
assert settlement_workflow.index("settle_forward_bets.py") < settlement_workflow.index("refresh_clv_tracking.py") < settlement_workflow.index("refresh_forward_results.py")
```

- [ ] **Step 2: Run automation tests and confirm they fail**

Run: `python -m pytest tests/v2/test_automation_contract.py -q`

- [ ] **Step 3: Update all active and recovery scorers plus the hourly lifecycle workflow**

Every V6 scoring command uses the V2 registry and policy. The settlement
workflow invokes the three existing idempotent jobs in dependency order.

- [ ] **Step 4: Run automation tests and confirm they pass**

Run: `python -m pytest tests/v2/test_automation_contract.py -q`

### Task 7: Verify the complete change and record evidence

**Files:**
- Modify: `docs/work-log.md`
- Modify when evidence changes: `docs/app-readiness-checklist.md`
- Modify: `docs/v2-backend-verification-status.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: current reproducible evidence and explicit remaining runtime unknowns.

- [ ] **Step 1: Run the complete relevant Python suite**

Run: `python -m pytest tests/v2/test_ev_policy_registry.py tests/v2/test_ev_score_evaluation.py tests/v2/test_ev_forward_predictions.py tests/v2/test_forward_exposures.py tests/v2/test_settlement.py tests/v2/test_clv_tracking.py tests/v2/test_forward_results.py tests/v2/test_read_api.py tests/v2/test_read_api_contracts.py tests/v2/test_automation_contract.py -q`

- [ ] **Step 2: Run complete frontend verification**

Run from `frontend`: `npm test -- --run`

Run from `frontend`: `npm run lint`

Run from `frontend`: `npm run build`

- [ ] **Step 3: Run dry-run policy scoring with fixture data or an empty valid window**

Run: `python scripts/forward_v2/score_ev_shadow_model.py --repo-root . --artifact models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/ev_scope_interaction_recency45_asof_capped_v6_shadow.joblib --manifest models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/model_manifest.json --score-only --selection-policy-registry models/ev/forward_policy_registry_v2.json --selection-policy-id v6_full_domain_checkpoint_journal_v2 --dry-run`

Expected: process succeeds; an empty upcoming window is a valid empty result.

- [ ] **Step 4: Update evidence documents without claiming live forward proof**

Record exact commands, counts, failures, new policy boundary, and the remaining
`UNPROVEN` future settlement/official-closing lifecycle in the work log and
backend verification document.

- [ ] **Step 5: Review the diff and commit only scoped files**

Run: `git diff --check`

Run: `git status --short`

Do not add the unrelated `.playwright-cli/` directory.
