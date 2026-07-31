# Ullebets work log

Last updated: 2026-07-31

This is the mandatory first-read project log. It records what has already been
tested, what currently works, what failed, the strongest insights, and what is
still worth testing. Detailed evidence remains in the linked reports.

## Status vocabulary

- `VERIFIED`: current evidence proves the claim.
- `PARTIAL`: the path works, but required coverage is incomplete.
- `FAILED`: a reproducible defect exists.
- `UNPROVEN`: the required event, source payload, or lifecycle window has not
  happened yet.
- `BLOCKED`: progress requires new external data or another state change.
- `REJECTED`: a tested experiment failed its predefined retention gate.
- `NOT STARTED`: a required product area has no completed implementation yet.

Valid empty source responses are not failures when no matches or markets exist.

## Current project state

### Repository and data boundaries

- `VERIFIED`: V2 is preserved on `feature/ullebets-v2-backend` and has been
  merge-verified for `main`.
- `VERIFIED`: V2 writes target only `ullebets_v2`.
- `VERIFIED`: `app` and `ullebets_unibet` are read-only reference sources.
- `VERIFIED`: raw and canonical/derived data are separated.
- `VERIFIED`: V2 collection names are suffix-free; old `*_v2` names are legacy
  cleanup aliases only.
- `VERIFIED`: the full V2 Python test suite currently passes, `386/386`.

### Backend

- `VERIFIED`: support sync, fixture ingest, finished-match enrichment,
  teamprofiles, Kambi event linking, raw odds, normalized offers, model
  snapshots, analysis, prediction exports, forward rows, settlement jobs, and
  audit jobs run against `ullebets_v2`.
- `VERIFIED`: four finished Brazil matches were enriched with raw statistics,
  incidents, shotmaps, results, canonical results, and 27 canonical primary
  stat rows per match.
- `VERIFIED`: settlement, CLV, and forward results share the timing contract
  `odds_snapshot_time <= prediction_created_at < match_start_time`.
- `VERIFIED`: three rows violating prediction-freeze timing are retained for
  audit but excluded from outcomes, PnL, ROI, and CLV.
- `VERIFIED`: simulated write-time snapshots were invalidated without changing
  raw Kambi payloads or immutable predictions.
- `FAILED`: all six Brazil T-10 windows passed with zero valid T-10 snapshots
  and zero closing lines. The local workflow was not running remotely, and
  heartbeat delivery occurred after the windows.
- `UNPROVEN`: valid live closing-line materialization and subsequent CLV still
  require a new future prematch window.
- `VERIFIED`: the final Brazil match was enriched with statistics, incidents,
  shotmap, result, canonical result, and 27 canonical primary-stat rows.
- `VERIFIED`: post-match settlement now contains 64 valid settled operational
  rows and 3 timing-excluded rows; forward results match those counts.
- `PARTIAL`: source connectivity diagnostics still contain endpoint failures,
  although the production fixture, enrichment, and odds paths succeeded in
  tested windows.

Detailed backend state:
[v2-backend-verification-status.md](v2-backend-verification-status.md).

Overall product readiness:
[app-readiness-checklist.md](app-readiness-checklist.md).

### Recommended EV model

- `VERIFIED`: the serialized V6 artifact exists and its SHA-256 matches its
  manifest.
- `VERIFIED`: registry V5 resolves to 20 immutable policies with fingerprint
  `5b8a699fc874d9f967aaaab81b68ff85f61c28dbf5fb634860f768b04889794d`.
- `VERIFIED`: the strongest historical policy is
  `v6_scope_interaction_corners_away_total_primary_challenger`.
- `VERIFIED`: policy definition is corners, away or total scope, ALL/1ST/2ND,
  model EV strictly above 7.5% and below 25%, rolling 90-day training, and a
  45-day recency half-life.
- `VERIFIED`: historical result is 156 bets over 99 matches, +44.70 units,
  +28.65% ROI, and a match-clustered 95% interval of +11.33% to +45.27%.
- `VERIFIED`: one bet per match returned +30.02%; a 0.10 decimal price haircut
  retained +22.05%; every leave-one-league/window result remained positive.
- `PARTIAL`: the result is historically positive but not forward-confirmed.
- `BLOCKED`: the latest direct V2 score-archive audit found 48 V6 score rows,
  all from Brasileirão Série A and all outside the fitted training domain.
  There are 0 in-domain V6 scores, selections, settlements, ROI rows, or CLV
  rows.

Supported V6 leagues are A-League Men, Bundesliga, La Liga, Ligue 1, Premier
League, and Italian Serie A. Brazilian scores must remain diagnostic only.

Detailed model history:
[ev-model-experiments.md](ev-model-experiments.md).

### Model-search conclusion

- `VERIFIED`: experiments 000-077 are documented.
- `REJECTED`: count residuals and count/V6 ensembles did not improve V6.
- `REJECTED`: movement and alternate-line ladder features slightly improved
  calibration but did not prove incremental ROI over V6.
- `REJECTED`: the 90/5/5 V6/movement/ladder blend returned +31.97%
  descriptively, but its paired improvement interval crossed zero.
- `REJECTED`: prequential microstructure weighting also failed the paired
  retention gate.
- `REJECTED`: exact-as-of HGB returned -8.42% on the V6 corner policy.
- `REJECTED`: exact-as-of market-residual HGB returned -12.20%.
- `REJECTED`: small positive total-shots HGB slices had only 27-28 bets and
  failed window stability.
- `VERIFIED`: the conservative historical comparison family is now 454.
- `BLOCKED`: further filtering or weighting on the same November-May outcomes
  is data mining, not new evidence. The next justified model test is untouched
  in-domain forward settlement.

## Do not rerun without a changed reason

- Do not rerun experiments 000-077 on the same inputs merely to search for a
  higher historical ROI.
- Do not alter registry V5 from inspected history.
- Do not use current Brazilian OOD scores as model ROI or promotion evidence.
- Do not rerun already accepted support, fixture, enrichment, odds, analysis,
  and export windows unless related code, credentials, mappings, or source
  behavior changed.
- Do not simulate future timestamps in write mode.
- Do not treat missing T-10/closing evidence as a code failure before a real
  due window exists.

## Next justified tests

1. Deploy the closing scheduler to the environment that actually runs jobs.
2. Capture and verify the next future real due T-10 window.
3. Materialize a valid prematch closing line and refresh CLV from it.
4. Score future matches from one of V6's six supported leagues before kickoff.
5. Settle those in-domain selections without changing artifact, features,
   thresholds, scopes, periods, or registry.
6. Evaluate forward ROI and CLV only after sufficient untouched observations
   exist.

## Chronological entries

### 2026-07-31 - T-10 scheduler ownership and release verification

Status: `VERIFIED`

Objective:
Make the deployed scheduler, rather than a manual monitor, own repeated odds
capture and closing/CLV updates.

Changes:

- The regular checkpoint workflow captures all configured horizons except
  `T_MINUS_10M`.
- The five-minute closing workflow exclusively owns `T_MINUS_10M` to prevent
  a checkpoint race from suppressing closing-line materialization.
- A successful closing-line materialization now refreshes CLV tracking and
  forward results in the same workflow.
- Pytest uses importlib mode so the complete V1 and V2 suites can be collected
  together despite duplicate test basenames.

Tests:

```text
python -m pytest -q
```

Results:

- `386 passed`.
- Targeted checkpoint, closing downstream, and workflow contract tests:
  `23 passed`.
- `git diff --check` found no whitespace errors.
- Feature commits `7557729` and `6009db9` were merged without conflicts in a
  clean worktree based on `origin/main`; the merged checkout also passed
  `386/386` tests.

Insight:
The backend code already contained the capture mechanisms, but an undeployed
workflow and overlapping T-10 ownership made the live behavior unreliable.
The closing job is now the single T-10 owner and its derived outputs are part
of the same automated path.

Remaining:

- A future live fixture is still required to prove a persisted production
  T-10 snapshot, closing line, and CLV row end to end.

Next:

- Deploy the committed workflows to the default branch, then inspect the next
  real T-10 job run rather than running another manual polling loop.

### 2026-07-31 - Brazil post-match completion and missed T-10 audit

Status: `PARTIAL`

Objective:
Verify the final post-match chain and determine whether any real T-10,
closing-line, or CLV evidence was persisted.

Changes:

- Refreshed live match enrichment for source date `2026-07-30`.
- Refreshed forward settlement, CLV tracking, and forward results.
- Stopped the obsolete heartbeat after the final T-10 window was missed.

Tests:

```text
python scripts/forward_v2/ingest_match_enrichment.py --mode live --fixture-source db --date 2026-07-30 --source-workflow postmatch-final-live
python scripts/forward_v2/settle_forward_bets.py --source-workflow postmatch-final-live
python scripts/forward_v2/refresh_clv_tracking.py --mode paths-or-db
python scripts/forward_v2/refresh_forward_results.py
```

Results:

- Final match `Coritiba 0-1 Cruzeiro` has raw statistics, incidents, shotmap,
  result, canonical result, 252 canonical stat rows, and 27 primary-stat rows.
- Its 9 forward rows settled: 4 wins and 5 losses.
- Across all 67 current forward rows: 64 settled, 3 timing-excluded, 26 wins,
  and 38 losses.
- The five timing-valid EV shadow rows settled at 2 wins, 3 losses, and
  `-1.17` units (`-23.40%` descriptive ROI). They are Brazilian
  out-of-domain diagnostics, not valid V6 forward evidence.
- There are 0 valid T-10 snapshots, 0 closing lines, 0 tracked CLV rows, and 0
  duplicate snapshot-key groups.
- CLV remains 64 `missing_closing_line` and 3 `invalid_snapshot_timing`.

Insight:
The post-match backend works, but the closing acceptance failed operationally,
not mathematically. A local uncommitted workflow schedule and a delayed
thread heartbeat are not a production scheduler.

Remaining:

- Deploy a real scheduler.
- Capture a future T-10 window.
- Materialize closing odds and calculate CLV.

Next:
Select the next fixture with active Kambi markets only after the closing job is
running in the actual execution environment.

### 2026-07-30 - Real T-10, closing, and CLV preflight

Status: `PARTIAL`

Objective:
Prepare and monitor the first non-simulated T-10 capture through closing-line
materialization and CLV refresh.

Changes:

- Closing and CLV dry-runs now read the real V2 database while remaining
  write-free.
- Manual closing workflow labels no longer crash parity reporting.
- Heartbeat `ullebets-v2-postmatch-pass-30-juli` now covers the actual T-10
  windows and post-match follow-ups on 30-31 July.

Tests:

```text
python -m pytest tests/v2/test_checkpoint_capture.py tests/v2/test_closing_capture.py tests/v2/test_clv_tracking.py tests/v2/test_config_and_safety.py -q
python scripts/forward_v2/capture_closing_snapshots.py --mode fixture-db --source-workflow manual-t10-preflight --date 2026-07-30 --date 2026-07-31 --dry-run
python scripts/forward_v2/refresh_clv_tracking.py --mode paths-or-db --dry-run
```

Results:

- `27/27` targeted tests pass.
- Six future Brazil fixtures are present.
- Four kick off at `2026-07-30T18:00:00Z`, one at `22:30:00Z`, and one at
  `2026-07-31T00:30:00Z`.
- Current target history contains `319` valid T-2D/T-1D market snapshots.
- Current targets contain `31` forward bets, `0` closing lines, and `31`
  persisted CLV rows waiting on a closing line.
- Full CLV dry-run reads `67` tracked bets: `64` missing closing lines and `3`
  excluded for invalid snapshot timing.
- Preflight correctly selects `0` due matches before the first T-10 window.
- A later real-time check at `2026-07-30T23:39Z` found that five of the six
  fixture windows had passed with `0` valid T-10 snapshots and `0` closing
  lines. The final fixture starts at `2026-07-31T00:30Z`.

Insight:
The current zero closing/CLV coverage is not a database failure, but the first
five live windows were missed by the scheduled heartbeat. The final current
acceptance window opens at approximately `2026-07-31T00:15Z`.

Remaining:

- Capture a real due target without `--now` or `--dry-run`.
- Prove raw Kambi, valid T-10 snapshots, closing lines, and refreshed CLV in
  `ullebets_v2`.

Next:
The heartbeat now polls every five minutes through the final live T-10 window.
Run the real write path there and update this log only from persisted evidence.

### 2026-07-30 - End-to-end app readiness checklist

Status: `VERIFIED`

Objective:
Create one saved checkbox view showing what already works and every remaining
requirement before the complete app can be considered production-ready.

Changes:

- Added `docs/app-readiness-checklist.md`.
- Added the checklist to the mandatory `AGENTS.md` reading order.
- Linked the checklist from README and this work log.
- Applied a strict rule: only fully evidenced behavior receives `[x]`.

Results:

- Backend foundation, tested live ingest, canonical enrichment, odds ingest,
  analysis, settlement mechanics, audits, and model artifacts are checked.
- Live T-10, closing/CLV, in-domain V6 evidence, full output parity, standalone
  V2 runtime, frontend, deployment, alerting, and operational acceptance remain
  unchecked with short reasons.

Insight:
The backend is substantially implemented, but the complete app is not ready.
The remaining work is now visible without reading the full technical reports.

Next:
Update the same checklist whenever new runtime evidence changes a readiness
statement.

### 2026-07-30 - Persistent work log and agent protocol

Status: `VERIFIED`

Objective:
Create one durable first-read log so future work does not repeat expensive
tests or lose negative findings.

Changes:

- Added root `AGENTS.md`.
- Added this `docs/work-log.md`.
- Added the mandatory reading order and log link to `README.md`.
- Standardized evidence vocabulary and required log-entry fields.

Verification:

- Confirmed `AGENTS.md` and `docs/work-log.md` exist.
- Confirmed README links resolve locally.
- Confirmed the work log points to both detailed status documents.

Insight:
The project already had detailed reports, but no single mandatory entry point
that told a new agent what not to rerun.

Next:
Every later code, data, configuration, or runtime-verification session must
append or update an entry before completion.

### 2026-07-30 - Experiment 077 exact-as-of HGB

Status: `REJECTED`

Objective:
Test whether a genuinely nonlinear model family beats V6 after applying the
final leakage-safe snapshot-as-of contract.

Test:

```powershell
python scripts/offline_v2/run_ev_exact_asof_hgb_challenger.py `
  --bootstrap-iterations 100000
```

Results:

- Exact V6/HGB prediction universe: 8,822/8,822.
- Timing, forbidden-feature, duplicate-key, and universe violations: 0.
- HGB corner away/total: 424 bets, -8.42%, 2/6 positive windows.
- Residual HGB: 275 bets, -12.20%, 1/6 positive windows.
- Both paired intervals versus V6 were entirely negative.
- Full V2 regression suite: 355 passed.

Insight:
Nonlinear boosting is materially worse than regularized logistic V6 on the
corrected feature contract. More model complexity is not the missing edge.

Artifacts:
`data/v2/ev_model/experiment_077_exact_asof_hgb/`.

### 2026-07-30 - Experiments 075-076 combined microstructure

Status: `REJECTED`

Objective:
Combine snapshot movement and simultaneous alternate-line ladder information
without using future snapshots or current-window outcomes.

Results:

- Rebuilt movement and ladder matrices matched cached 14,033-row artifacts.
- All model prediction universes matched at 8,822 rows.
- 90% V6 / 5% movement / 5% ladder: 146 bets, +31.97%.
- Paired improvement versus V6: +3.31 ROI points, 95% interval -1.63 to +9.01.
- Prequential version: 147 bets, +30.91%.
- Prequential paired interval: -2.08 to +7.35.
- Neither variant proved incremental edge.

Insight:
Microstructure improves calibration slightly, but nearly every selected bet
already belongs to V6. It is a calibration shadow, not a new betting policy.

Artifacts:

- `data/v2/ev_model/experiment_075_combined_microstructure/`
- `data/v2/ev_model/experiment_076_prequential_combined_microstructure/`

### 2026-07-30 - Live timing, enrichment, and score-domain audit

Status: `PARTIAL`

Objective:
Verify only the remaining live/post-match lifecycle items for the Brazil
window.

Results:

- Four finished matches enriched successfully.
- A transport `TimeoutError` was normalized into the existing fallback path.
- Three post-freeze odds rows were excluded from settlement, ROI, and CLV.
- Real T-10 closing capture remains unproven.
- Direct V6 evaluator dry-run found 48/48 scores outside the training domain.
- V6 in-domain scores, selections, settlements, ROI, and CLV: all 0.

Insight:
Brazil data proves pipeline mechanics but cannot prove the European/Australian
model. Domain filtering is correctly failing closed.

### 2026-07-28 - V2 backend acceptance pass

Status: `VERIFIED`

Objective:
Exercise the V2 backend chain against the real `ullebets_v2` database.

Results:

- Support sync, fixture ingest, finished-match enrichment, teamprofiles, odds
  ingest, normalized offers, model snapshots, analysis, exports, and forward
  persistence completed.
- Six of six tested upcoming fixtures linked to Kambi events.
- Empty source dates were treated as valid empty responses rather than system
  failures.

Detailed evidence:
[v2-backend-verification-status.md](v2-backend-verification-status.md).

## Entry template

Copy this section for future work and insert the new entry above older entries.

````markdown
### YYYY-MM-DD - Short title

Status: `VERIFIED|PARTIAL|FAILED|UNPROVEN|BLOCKED|REJECTED`

Objective:
What was being proved or changed.

Changes:
- Files, collections, jobs, or configuration changed.

Tests:
```text
exact command or scenario
```

Results:
- Exact counts, pass/fail state, and important errors.

Insight:
What became known that was not known before.

Remaining:
- What is still unproven or blocked.

Next:
- The next justified test, not a generic wish list.
````
