# Ullebets V2 Market Bias Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable V2 market-bias pipeline and a compact visual explanation on matchup cards, without changing matchup ranking, V6, forward selection, ROI, or CLV.

**Architecture:** Persist immutable line-versus-result observations separately from reproducible rolling profiles. Bootstrap observations once from audited local Parquet, refresh new observations only from V2 collections, attach the latest leakage-safe profile to matchup output, and serialize one typed API contract to a dedicated visual rail in the frontend.

**Tech Stack:** Python 3.13, PyMongo/Cosmos Mongo API, DuckDB/Parquet, pytest, React 19, TypeScript 6, Vitest, CSS.

**Spec:** [2026-08-21-market-bias-v2-design.md](../specs/2026-08-21-market-bias-v2-design.md)

## Global Constraints

- All writes must pass the existing `MONGODB_DB=ullebets_v2` safety guard.
- `app`, `ullebets_unibet`, and the original repository remain read-only references and are never runtime dependencies.
- Only `cornerKicks`, `totalShots`, and `shotsOnGoal` are included initially; ingestion code remains registry-driven.
- Snapshot eligibility is strict: `snapshot_time < match_start_time` and `invalid_for_model != true`.
- Match, league, team, stat, scope, and period mappings must be exact or configured aliases; never fuzzy-write.
- The existing matchup `score`, `sort_key`, `rank_position`, membership, and V6 paths must remain byte-for-byte equivalent for identical inputs.
- Bias is contextual evidence, not a probability, EV estimate, recommendation, or ranking input.
- No historical bootstrap write is allowed until its dry-run mapping and leakage report passes review.

---

## Task 1: Register Storage Contracts And Indexes

**Files:**
- Modify: `src/ullebets_v2/storage/collections.py`
- Modify: `src/ullebets_v2/storage/indexes.py`
- Modify: `tests/v2/test_config_and_safety.py`

- [ ] **Step 1: Add failing collection-contract tests**

Assert that `market_bias_observations` and `market_bias_profiles` are canonical suffix-free collections and that the index plan contains the required unique and lookup indexes.

```python
assert MARKET_BIAS_OBSERVATIONS in CANONICAL_COLLECTION_NAMES
assert MARKET_BIAS_PROFILES in CANONICAL_COLLECTION_NAMES

observation_plan = next(
    row for row in build_core_index_plan()
    if row["collection"] == MARKET_BIAS_OBSERVATIONS
)
assert any(index["name"] == "observation_key_unique" and index["unique"] for index in observation_plan["indexes"])
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `python -m pytest tests/v2/test_config_and_safety.py -q`

- [ ] **Step 3: Add collection constants and indexes**

Add:

```python
MARKET_BIAS_OBSERVATIONS = "market_bias_observations"
MARKET_BIAS_PROFILES = "market_bias_profiles"
```

Indexes:

```python
{
    "collection": MARKET_BIAS_OBSERVATIONS,
    "indexes": [
        {"keys": [("observation_key", 1)], "name": "observation_key_unique", "unique": True},
        {
            "keys": [
                ("team_key", 1), ("venue_context", 1), ("market_scope", 1),
                ("stat_key", 1), ("period", 1), ("outcome_available_at", -1),
            ],
            "name": "team_context_outcome_available",
        },
        {
            "keys": [("match_key", 1), ("stat_key", 1), ("market_scope", 1), ("period", 1)],
            "name": "match_market_context",
        },
    ],
}
```

Add an equivalent unique `profile_key` index and a profile-date/team/context lookup index for `MARKET_BIAS_PROFILES`.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest tests/v2/test_config_and_safety.py -q`

Commit: `git commit -m "feat: register market bias storage"`

---

## Task 2: Implement Pure Observation And Profile Domain Logic

**Files:**
- Create: `src/ullebets_v2/market_bias/__init__.py`
- Create: `src/ullebets_v2/market_bias/domain.py`
- Create: `tests/v2/test_market_bias_domain.py`

- [ ] **Step 1: Write failing tests for line selection**

Cover latest valid prematch batch, rejection at/equal kickoff, deterministic odds-nearest-2.00 tie breaks, shots with over-only odds, corners with both sides, and no qualifying line outside 1.70-2.30.

```python
selected = select_main_line(
    snapshots=snapshots,
    match_start_time=kickoff,
)
assert selected["snapshot_label"] == "T_MINUS_30M"
assert selected["over_odds"] == 1.98
assert selected["line_value"] == 10.5
```

- [ ] **Step 2: Write failing tests for exact outcome semantics**

Test `actual > line -> over`, `actual < line -> under`, and equality -> `push`. Test total markets producing two team-context observations while home/away markets produce one correctly owned observation.

- [ ] **Step 3: Write failing tests for rolling profiles**

Cover latest 12 observations, 45-day half-life, Beta(3,3) prior, residual shrinkage, effective sample size, minimum six real observations/effective four, push counts, sign disagreement -> neutral, and historical cutoff exclusion.

```python
profile = build_bias_profile(observations, as_of=cutoff)
assert profile["sample_size"] == 12
assert profile["method_version"] == MARKET_BIAS_METHOD_VERSION
assert profile["direction"] in {"over", "under", "neutral", "insufficient"}
```

- [ ] **Step 4: Run tests and confirm failure**

Run: `python -m pytest tests/v2/test_market_bias_domain.py -q`

- [ ] **Step 5: Implement constants and pure functions**

Use explicit constants:

```python
MARKET_BIAS_METHOD_VERSION = "main_line_residual_v1"
PRIMARY_BIAS_STATS = frozenset({"cornerKicks", "totalShots", "shotsOnGoal"})
MAX_OBSERVATIONS = 12
RECENCY_HALF_LIFE_DAYS = 45.0
PRIOR_ALPHA = 3.0
PRIOR_BETA = 3.0
MIN_REAL_OBSERVATIONS = 6
MIN_EFFECTIVE_OBSERVATIONS = 4.0
```

Keep these public interfaces stable: `select_main_line` accepts snapshots and
kickoff and returns one selected row or `None`; `build_observation_docs`
accepts the selected row, exact actual, fixture, availability timestamp,
source kind, and run ID and returns contextual observations;
`build_bias_profile` accepts observations plus an explicit cutoff/profile date;
`build_profile_key` accepts the complete context identity and method version.

Use a normal approximation from `statistics.NormalDist` for directional confidence; do not add a runtime dependency.

- [ ] **Step 6: Verify and commit**

Run: `python -m pytest tests/v2/test_market_bias_domain.py -q`

Commit: `git commit -m "feat: calculate auditable market bias"`

---

## Task 3: Add Immutable Persistence, Audits, Health, And Job Runs

**Files:**
- Create: `src/ullebets_v2/market_bias/persistence.py`
- Create: `src/ullebets_v2/market_bias/reports.py`
- Create: `src/ullebets_v2/market_bias/service.py`
- Create: `tests/v2/test_market_bias_service.py`

- [ ] **Step 1: Write persistence failure tests**

Test exact replay as idempotent, new insert, immutable source hash conflict as fatal, profile upsert by `profile_key`, and no writes in dry-run.

```python
with pytest.raises(ImmutableMarketBiasConflict):
    persist_observations(database, [changed_payload_same_observation_key])
```

- [ ] **Step 2: Write report-contract tests**

Require audit metrics for timing rejection, missing actual, unmatched identity, invalid row, duplicate key, hash conflict, qualifying-line failure, and counts by stat/scope/period/league/snapshot label. Require one `job_runs` lifecycle for write-mode jobs.

- [ ] **Step 3: Implement bounded writes and strict conflict checks**

Before upserting an existing observation, compare its immutable fingerprint over source identity, selected line, actual, snapshot timestamp, kickoff, and outcome availability. Exact replay is unchanged; any mismatch raises.

- [ ] **Step 4: Implement the shared run service**

Expose one orchestration function, `run_market_bias_refresh`, used by both
adapters. Its keyword-only inputs are `source_workflow: str`,
`source_kind: Literal["offline_v1_bootstrap", "v2_forward"]`,
`candidates: Iterable[MarketBiasCandidate]`, `as_of: datetime`,
`profile_date: str`, `database: Any | None`, and `dry_run: bool`; it returns a
`dict[str, Any]` summary.

It must return observation/profile documents and complete metrics in dry-run, and persist observations, profiles, audit/health reports, and `job_runs` in write mode.

- [ ] **Step 5: Verify and commit**

Run: `python -m pytest tests/v2/test_market_bias_service.py tests/v2/test_job_runs.py -q`

Commit: `git commit -m "feat: persist and audit market bias"`

---

## Task 4: Build The Audited Historical Bootstrap Adapter

**Files:**
- Create: `src/ullebets_v2/market_bias/bootstrap.py`
- Create: `scripts/forward_v2/import_market_bias_history.py`
- Create: `tests/v2/test_market_bias_bootstrap.py`

- [ ] **Step 1: Write fixture-Parquet tests**

Create small temporary Parquet fixtures with exact-ID, exact-name, configured-alias, ambiguous, unmatched, post-start, push, and duplicate scenarios. Assert only safe mappings become candidates.

- [ ] **Step 2: Implement a read-only DuckDB adapter**

Read only:

```text
data/derived/offline_v1/normalized/market_snapshots.parquet
data/derived/offline_v1/normalized/market_lines.parquet
data/derived/offline_v1/normalized/matches.parquet
```

Resolve identities in this order: exact source ID, exact normalized name in exact league, configured unique alias in exact league, otherwise exclude. Persist mapping method and source hashes in accepted records.

- [ ] **Step 3: Implement the CLI safety contract**

```powershell
python scripts/forward_v2/import_market_bias_history.py `
  --as-of 2026-08-21T00:00:00Z `
  --report-path data/v2/market_bias/bootstrap-audit.json `
  --dry-run
```

The CLI must default to dry-run unless `--write` is explicitly supplied. `--write` must still call `ensure_v2_database` and fail unless the database is exactly `ullebets_v2`.

- [ ] **Step 4: Run the real dry-run and review the gate**

Record exact accepted/unmatched/ambiguous/timing-invalid/hash-conflict counts and distributions. Stop before write if any included post-start row, ambiguous mapping, duplicate identity, or immutable conflict exists.

- [ ] **Step 5: Verify and commit the adapter**

Run: `python -m pytest tests/v2/test_market_bias_bootstrap.py tests/v2/test_market_bias_service.py -q`

Commit: `git commit -m "feat: bootstrap market bias history"`

---

## Task 5: Add V2-Only Forward Refresh And Production Automation

**Files:**
- Create: `src/ullebets_v2/market_bias/forward.py`
- Create: `scripts/forward_v2/refresh_market_bias.py`
- Modify: `.github/workflows/update-teamstats-and-teamprofiles.yml`
- Modify: `tests/v2/test_market_bias_service.py`
- Modify: `tests/v2/test_automation_contract.py`

- [ ] **Step 1: Write failing forward-reader tests**

Use only `fixtures_canonical`, `market_snapshots`, `match_stats_canonical`, and `match_results_canonical`. Test exact actual mapping, persisted result availability, missing snapshots, after-start exclusion, and a rerun that creates no duplicates.

- [ ] **Step 2: Implement the forward candidate loader**

Query a bounded finished-match window. Load latest valid prematch snapshot batches per market context, canonical actuals, kickoff, and result availability. Never query local Parquet or legacy databases in this path.

- [ ] **Step 3: Implement the CLI**

```powershell
python scripts/forward_v2/refresh_market_bias.py `
  --from-date 2026-08-20 `
  --to-date 2026-08-20 `
  --as-of 2026-08-21T05:00:00Z `
  --source-workflow update-teamstats-and-teamprofiles.yml `
  --dry-run
```

- [ ] **Step 4: Chain refresh after result/teamprofile enrichment**

Add `refresh_market_bias.py` after `build_teamprofiles.py`. Keep the repository's workflow convention of including `--dry-run` in the command template because `v2-python-job.yml` removes it in write mode and retains it for manual dry-runs.

- [ ] **Step 5: Verify and commit**

Run: `python -m pytest tests/v2/test_market_bias_service.py tests/v2/test_automation_contract.py tests/v2/test_workflow_runner.py -q`

Commit: `git commit -m "feat: refresh market bias from v2 results"`

---

## Task 6: Attach Bias To Matchups Without Affecting Ranking

**Files:**
- Modify: `src/ullebets_v2/matchups/service.py`
- Modify: `tests/v2/test_matchups.py`

- [ ] **Step 1: Add a ranking-invariance regression test**

Build identical matchup inputs once with no bias profiles and once with profiles. Assert all ranking fields and entry membership are unchanged while `market_bias` differs.

```python
for before, after in zip(without_bias, with_bias, strict=True):
    assert before["entry_key"] == after["entry_key"]
    assert before["score"] == after["score"]
    assert before["sort_key"] == after["sort_key"]
    assert before["rank_position"] == after["rank_position"]
```

- [ ] **Step 2: Replace teamprofile compatibility reads**

Remove the teamprofile-based `_read_market_bias` helper. Load
`MARKET_BIAS_PROFILES` independently and index profiles by exact
team/league/venue/scope/stat/period context. Select the newest profile with
`as_of < fixture.start_time`.

- [ ] **Step 3: Use one uniform persisted payload**

Store `market_bias` as:

```python
{
    "scope": "total",
    "profiles": [
        {
            "team_key": "premier-league:1",
            "team_name": "Arsenal",
            "venue_context": "home",
            "direction": "over",
            "strength": "strong",
            "sample_size": 10,
            "non_push_sample_size": 10,
            "over_count": 7,
            "under_count": 3,
            "push_count": 0,
            "posterior_over_rate": 0.625,
            "shrunk_mean_residual": 1.4,
            "direction_confidence": 0.93,
            "method_version": "main_line_residual_v1",
        }
    ],
}
```

Home/away scope contains one profile. Total scope contains home and away profiles in deterministic home/away order. Missing/insufficient profiles remain explicit.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest tests/v2/test_matchups.py tests/v2/test_matchup_form_profiles.py -q`

Commit: `git commit -m "feat: attach market bias to matchups"`

---

## Task 7: Publish A Typed Read-API Contract

**Files:**
- Modify: `src/ullebets_v2/read_api/service.py`
- Modify: `tests/v2/test_read_api.py`
- Modify: `tests/v2/test_read_api_contracts.py`

- [ ] **Step 1: Write failing serialization tests**

Assert camelCase output, deterministic home/away order, explicit insufficient state, and null for no profile. Also assert no internal provenance hashes or observation key arrays are sent to dashboard cards.

- [ ] **Step 2: Add explicit serializer functions**

Implement `_market_bias_profile_summary` and `_market_bias_summary`; do not pass arbitrary Mongo objects through `_iso`.

```python
return {
    "scope": value.get("scope"),
    "profiles": [
        {
            "teamKey": row.get("team_key"),
            "teamName": row.get("team_name"),
            "venueContext": row.get("venue_context"),
            "direction": row.get("direction"),
            "strength": row.get("strength"),
            "sampleSize": row.get("sample_size"),
            "nonPushSampleSize": row.get("non_push_sample_size"),
            "overCount": row.get("over_count"),
            "underCount": row.get("under_count"),
            "pushCount": row.get("push_count"),
            "posteriorOverRate": row.get("posterior_over_rate"),
            "shrunkMeanResidual": row.get("shrunk_mean_residual"),
            "directionConfidence": row.get("direction_confidence"),
            "methodVersion": row.get("method_version"),
        }
        for row in value.get("profiles", [])
    ],
}
```

- [ ] **Step 3: Verify and commit**

Run: `python -m pytest tests/v2/test_read_api.py tests/v2/test_read_api_contracts.py -q`

Commit: `git commit -m "feat: expose typed market bias summaries"`

---

## Task 8: Build The Compact Pedagogical UI

**Files:**
- Modify: `frontend/src/domain/types.ts`
- Create: `frontend/src/components/MarketBiasIndicator.tsx`
- Create: `frontend/src/components/MarketBiasIndicator.test.tsx`
- Modify: `frontend/src/components/SignalCard.tsx`
- Modify: `frontend/src/styles/live-data.css`
- Modify: `frontend/src/app/App.test.tsx`
- Modify: `frontend/src/app/step1-navigation.test.tsx`

- [ ] **Step 1: Add the typed frontend contract**

```typescript
export type MarketBiasDirection = 'over' | 'under' | 'neutral' | 'insufficient';
export type MarketBiasStrength = 'none' | 'lean' | 'strong' | 'very_strong';

export interface MarketBiasProfileSummary {
  teamKey: string;
  teamName: string;
  venueContext: 'home' | 'away';
  direction: MarketBiasDirection;
  strength: MarketBiasStrength;
  sampleSize: number;
  nonPushSampleSize: number;
  overCount: number;
  underCount: number;
  pushCount: number;
  posteriorOverRate: number;
  shrunkMeanResidual: number;
  directionConfidence: number;
  methodVersion: string;
}

export interface MarketBiasSummary {
  scope: 'total' | 'home' | 'away';
  profiles: MarketBiasProfileSummary[];
}
```

Change `MatchupEntry.marketBias` from `unknown` to `MarketBiasSummary | null`.

- [ ] **Step 2: Write component tests before implementation**

Test one-profile home/away cards, two-profile total cards, under/over/neutral/insufficient states, marker clamping, signed residual formatting, `7/10` count display, confidence segments, and accessible labels.

- [ ] **Step 3: Implement one visual grammar**

Each profile row must fit in roughly 48 pixels and contain no explanatory paragraph:

```text
ARSENAL                         +1,4   7/10   ▮▮▮
UNDER  ───────────────●────────────────────  ÖVER
```

Rules:

- Title the section `Mot Unibet-linan`.
- Use one full-width rail with fixed `UNDER` and `ÖVER` endpoints and a visible neutral midpoint.
- Place the marker from `posteriorOverRate`, clamped to 5-95% so it remains visible.
- Show `shrunkMeanResidual` as a signed number next to the team name.
- Show `overCount/nonPushSampleSize`; pushes remain available in the accessible label.
- Show confidence as three compact segments derived from `strength`, not a vague wordy paragraph.
- Total scope shows home and away teams as two stacked rows; home/away scope shows one row.
- Insufficient data uses a centered hollow marker and muted `n < 6`, not a fabricated neutral result.
- Keep the league baseline beside the bias block as the comparison unit.
- Use shape, labels, and position as well as color; provide a complete Swedish `aria-label`/tooltip for screen readers.

- [ ] **Step 4: Replace the generic formatter**

Delete `formatBias()` from `SignalCard.tsx` and render:

```tsx
<MarketBiasIndicator
  bias={signal.marketBias}
  leagueBaseline={signal.leagueBaseline}
/>
```

- [ ] **Step 5: Verify responsive behavior**

At desktop width, both total rows remain aligned inside the card. At 600px, labels, residual, sample, and confidence stay on one row without horizontal scrolling; rails retain full width.

- [ ] **Step 6: Run frontend gates and commit**

Run:

```powershell
cd frontend
npm run test -- MarketBiasIndicator.test.tsx
npm run typecheck
npm run lint
npm run build
```

Commit: `git commit -m "feat: visualize market bias on matchup cards"`

---

## Task 9: Bootstrap, Rebuild, And Prove End-To-End Behavior

**Files:**
- Modify: `docs/work-log.md`
- Modify: `docs/app-readiness-checklist.md` only if complete current evidence changes readiness
- Modify: `docs/v2-backend-verification-status.md`
- Generated local artifact, not committed: `data/v2/market_bias/bootstrap-audit.json`

- [ ] **Step 1: Run all static and unit gates**

```powershell
python -m pytest tests/v2 -q
cd frontend
npm run test
npm run typecheck
npm run lint
npm run build
```

- [ ] **Step 2: Run index and database safety smoke tests**

Run `bootstrap_indexes.py --dry-run` against the configured V2 environment and explicitly verify that a non-`ullebets_v2` database name hard-fails.

- [ ] **Step 3: Run and review the real bootstrap dry-run**

Acceptance gates before write:

- zero included post-start snapshots
- zero ambiguous/fuzzy writes
- zero duplicate observation keys
- zero immutable conflicts
- every accepted row has exact actual, kickoff, snapshot time, team, league, stat, scope, and period
- accepted/unmatched counts are broken down by league and mapping method

- [ ] **Step 4: Persist the approved bootstrap and prove idempotency**

Run the same command once with `--write`, then immediately rerun it. The second run must add zero observations, produce identical profile values, and report zero conflicts.

- [ ] **Step 5: Rebuild target-date matchups**

Build both matchup collections for a current fixture date. Compare entry keys, score, sort key, ranks, and counts against the pre-bias snapshot; only `market_bias` may differ.

- [ ] **Step 6: Smoke-test the read API and frontend**

Open a date with populated matchup cards and verify:

- home/away card: one correctly owned team row
- total card: two rows in home/away order
- direction and signed residual agree with stored profile
- `7/10`-style counts agree with stored observations
- insufficient data remains visually explicit
- no card implies V6 probability or EV

- [ ] **Step 7: Update evidence documents**

Record exact commands, counts, mapping exclusions, test totals, performance, remaining live-forward uncertainty, and the next justified production refresh. Never mark forward bias refresh verified from bootstrap-only evidence.

- [ ] **Step 8: Final verification and commit**

Run: `git diff --check`

Commit: `git commit -m "docs: verify v2 market bias rollout"`

---

## Definition Of Done

- Historical observations and profiles exist in V2 with complete source lineage and zero leakage/identity conflicts.
- Forward refresh reads only V2 collections and is idempotent.
- Bias attaches to matchup cards without changing any ranking or V6 output.
- API uses a typed, bounded contract rather than arbitrary Mongo payloads.
- The UI communicates direction, magnitude, evidence, and confidence visually with no explanatory text blocks.
- Python and frontend test, typecheck, lint, and production build gates pass.
- Work log and readiness evidence distinguish bootstrap proof from future live-forward proof.
