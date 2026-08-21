# Ullebets work log

Last updated: 2026-08-21

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

- `VERIFIED`: V2 is preserved on `feature/ullebets-v2-backend`, merged to
  `main`, and deployed through active GitHub Actions workflows.
- `VERIFIED`: V2 writes target only `ullebets_v2`.
- `VERIFIED`: `app` and `ullebets_unibet` are read-only reference sources.
- `VERIFIED`: raw and canonical/derived data are separated.
- `VERIFIED`: V2 collection names are suffix-free; old `*_v2` names are legacy
  cleanup aliases only.
- `VERIFIED`: the full V2 Python test suite currently passes, `449/449` in
  the current reconciled `style-1` checkout.

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
- `VERIFIED`: scheduled `V2 EV Shadow Forward` runtime drift exposed by run
  `30668128118` is fixed. Production write-mode run `30672830616` passed all
  four frozen scorers on the manifest-compatible runtime.
- `VERIFIED`: scheduled workflows are write-mode by default. Their command
  templates include `--dry-run`, but the shared runner removes that flag when
  the workflow input is false. Manual dry-run remains available as a safety
  control.
- `VERIFIED`: the latest completed match date for every followed league is now
  stored in V2. Across 41 matches, raw statistics, incidents, shotmaps,
  results, canonical results, and all 1,107 primary stat rows are complete.
- `VERIFIED`: live T-2D capture has 161 valid prematch rows across two
  matches, and live T-1D capture has 244 valid rows across three matches.
- `VERIFIED`: the hourly production scheduler is active. Hosted run
  `30949327663` succeeded, saw all 10 upcoming Brazil fixtures, correctly
  found zero due checkpoints, and persisted audit/health status `ok`.
- `VERIFIED`: a current read-only Kambi dry-run linked 10/10 upcoming
  fixtures, returned 11 raw payload documents and 607 normalized offers, with
  zero source or mapping errors.
- `UNPROVEN`: T-30, T-10, closing-line materialization, and valid
  closing-based CLV still have no persisted live evidence.
- `VERIFIED`: the 5-8 August production window persisted valid T-3D `678`,
  T-2D `799`, T-1D `817`, and T-2H `242` odds rows. All rows are before
  kickoff, and the current-cycle duplicate-snapshot-key audit found `0` groups.
- `FAILED`: hosted closing workflow run `31271905639` failed before its capture
  command. Its lean runner installs only `pymongo`, but then imports
  `ullebets_v2.automation`; the source package is neither installed nor on
  `PYTHONPATH`. At `2026-08-08T18:51Z`, eight minutes before Grêmio - São
  Paulo, no T-30/T-10 row or closing line had been stored.
- `VERIFIED`: commit `030a401` adds the repository's `src/` directory to the
  shared runner `PYTHONPATH`. Hosted dry-run `31273361050` completed the
  formerly failing import and closing command with zero errors. It had zero
  due targets because the next fixture was still outside its closing window.
- `PARTIAL`: V6 scoring is now downstream of each production checkpoint or
  closing capture that persists at least one new snapshot. The separate
  ten-minute scoring schedule is removed; a hosted write-mode due window must
  still prove the complete chain.
- `VERIFIED`: V2 rebuilt the full dated teamprofile snapshot in the production
  database: 585 matches, 147,408 canonical stat rows, 1,107 incidents, 1,105
  shotmaps, and 265 teamprofiles. The completed job recorded matched parity
  plus `ok` audit and health reports.
- `VERIFIED`: teamprofile persistence now uses the database's existing unique
  identity (`team_key`, `profile_date`, `match_type`) rather than an
  unindexed `profile_key`. The immediate full idempotent rebuild succeeded;
  its write stage completed in 123.7 seconds after the historical read/build.
- `VERIFIED`: V6 score persistence now compares raw feature values with an
  absolute `1e-12` tolerance and independently validates their derived feature
  fingerprint. A production-database rerun reused 105 frozen scores with zero
  conflicts; 49 were precision-equivalent rows. It created zero forward bets.

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

1. Verify the next hosted `update-teamstats-and-teamprofiles.yml` run executes
   the repaired teamprofile persistence on `main`.
2. Verify the next hosted V6 checkpoint/scorer rerun records no immutable
   conflict on `main`.
3. Verify the next current T-3D capture.
4. Verify the subsequent T-2H, T-30, and T-10 captures without manual time
   simulation.
5. Materialize a valid prematch closing line and refresh CLV from it.
6. Score future matches from one of V6's six supported leagues before kickoff.
7. Settle those in-domain selections without changing artifact, features,
   thresholds, scopes, periods, or registry.
8. Evaluate forward ROI and CLV only after sufficient untouched observations
   exist.

## Chronological entries

### 2026-08-21 - V2 market-bias Tasks 6-8 integration

Status: `PARTIAL`

Objective:
Attach the independent market-bias profile context to matchup reads, expose a
typed read contract, and render it on matchup cards without changing ranking,
V6, selection, ROI, or CLV behavior.

Results:
- Task 6 matchup regression passed `9/9`: entry keys, scores, sort keys,
  rank positions, and membership remain invariant with bias profiles present.
- Task 7 API contract regression passed `22/22`: only typed camelCase
  summaries are exposed, total profiles are home/away ordered, and absent
  profiles are `null`.
- Task 8 component and app regression passed `5/5`; full frontend suite
  passed `54/54` in `111.28s`; typecheck, lint, and production build passed.

Insight:
Market bias is loaded from `market_bias_profiles` independently of
teamprofiles and only when its `as_of` is strictly before fixture kickoff.

Remaining:
- `UNPROVEN`: a live completed forward market-bias lifecycle.

Next:
Observe a completed-match forward refresh before treating the feature as
operationally proven.

### 2026-08-21 - V2 market-bias Tasks 4-5 adapters

Status: `PARTIAL`

Objective:
Add the read-only offline bootstrap adapter and V2-only forward refresh
foundation without bootstrap writes, matchup changes, or model changes.

Results:
- Historical dry-run command completed read-only with `16,386` accepted,
  `0` unmatched, `0` ambiguous, `0` timing-invalid, `0` missing actuals,
  `0` duplicate keys, and `438` qualifying-line rejections. It created no
  observations or profiles because `--write` was not supplied.
- Exact source IDs resolved `25,286` team identities; no name fallback or
  configured alias was needed. The compact local audit records the accepted distributions and
  bounded metrics without embedding observation/profile documents.
- Focused adapter suites passed `43/43` in `5.97s`; full V2 suite passed `464/464` in
  `61.97s`; `python -m compileall -q src scripts`, `git diff --check`, and
  `codegraph sync` passed.

Insight:
The source adapter must select an exact `match_id + bet_key` outcome for the
chosen OVER price, not a match-level row. Its line-independent context grouping
now chooses only one main line per market context.
Existing observation replay is bounded to `100` exact-context clauses per
Cosmos `$or` query, verified with a `101`-context service regression test.

Remaining:
- `UNPROVEN`: a deliberate bootstrap write and its immutable persistence
  lifecycle; this batch was explicitly read-only.
- `UNPROVEN`: live scheduled forward refresh against a completed match.

Next:
Review the compact bootstrap audit and authorize a separately audited write
only if the historical import is needed; otherwise observe a completed-match
forward refresh.

### 2026-08-21 - V2 market-bias Tasks 1-3 foundation

Status: `PARTIAL`

Objective:
Implement only the V2 market-bias storage contracts, pure domain calculation,
and immutable refresh-service foundation. Matchup ranking, V6, model, ROI,
CLV, API, and frontend were intentionally unchanged.

Changes:
- Added suffix-free `market_bias_observations` and `market_bias_profiles`
  collection contracts plus unique and context lookup indexes.
- Added deterministic prematch main-line selection, exact outcome/context
  observations, leakage-safe rolling profiles, immutable persistence, audit /
  health rows, and `job_runs` lifecycle orchestration.

Tests:
```text
python -m pytest tests/v2 -q
python -m compileall -q src
git diff --check
```

Results:
- Full V2 regression: `452 passed in 23.73s`; `compileall` passed and
  `git diff --check 44c6d50..HEAD` reported no errors.

Insight:
The initial foundation is database-adapter-neutral and fails closed on source
evidence changes, duplicate observation keys, post-kickoff snapshots, and
outcomes unavailable at the explicit profile cutoff.

Remaining:
- `UNPROVEN`: audited Parquet bootstrap mapping/coverage, V2 forward candidate
  adapter, production database index application, scheduled orchestration,
  matchup/read-API integration, and frontend rendering.
- No database write or live market-bias result occurred in this task group.

Next:
Implement the audited bootstrap adapter with dry-run identity/mapping report
before permitting the first V2 market-bias database write.

### 2026-08-21 - V2 market-bias production design

Status: `NOT STARTED` for implementation. The architecture and acceptance
contract are approved and documented; no production code, database data,
matchup ranking, or V6 behavior changed in this session.

Objective: replace the empty legacy-compatible `market_bias` field with an
auditable team tendency against comparable Unibet prematch lines.

Evidence and decisions:

- Current V2 contains 15,208 market snapshots, including 14,711 valid
  prematch rows, but only 135 finished primary-market contexts currently join
  directly to canonical actuals.
- The audited offline corpus contains 11,917 preliminary eligible main-line
  contexts over 1,017 matches before canonical V2 team/league mapping.
- The selected architecture uses a one-time audited Parquet bootstrap followed
  by idempotent forward refreshes from V2-only collections.
- Bias uses the latest valid prematch capture, an over line nearest 2.00 within
  1.70-2.30, exact stat/scope/period outcomes, a rolling 12-match window,
  45-day recency half-life, and neutral small-sample shrinkage.
- Bias remains matchup context only. Matchup ranking and frozen V6 model,
  prediction, selection, ROI, and CLV paths remain unchanged.

Design:

- [2026-08-21-market-bias-v2-design.md](superpowers/specs/2026-08-21-market-bias-v2-design.md)

Remaining:

- Execute the reviewed implementation plan.
- Audit exact historical team/league mapping before any bootstrap write.
- Implement, verify, and deploy the observation, profile, automation, API, and
  frontend layers.

Next:

- Execute the implementation plan task by task with TDD and stop the bootstrap
  before its first write if the mapping/leakage acceptance gate fails.

Implementation plan:

- [2026-08-21-market-bias-v2-implementation.md](superpowers/plans/2026-08-21-market-bias-v2-implementation.md)

### 2026-08-14 - Matchup ranking form, day replacement, and Cosmos persistence

Status: `PARTIAL`. The V2 matchup presentation layer is verified against the
production V2 database. It does not change V6, backtest features, artifacts,
or frozen forward predictions.

Objective: rank today's matchups from each team's recent, scope-correct form
without stale fixture rows distorting the visible top 20.

Changes:

- Added a matchup-only `rolling_12_weighted_45d` form transform: 12 latest
  matches per existing home/away profile, with a 45-day recency half-life.
- Reranked against full current league profiles, not only the teams playing on
  the selected day, while leaving stored model/teamprofile values unchanged.
- Replaced same-day matchup snapshots safely after current rows are upserted;
  dashboard ranking is now contiguous among current fixtures.
- Fixed matchup CLI dry-runs to retain read access to `ullebets_v2` profiles.
- Replaced sequential Cosmos matchup writes with 100-row unordered batches and
  added the supporting league/profile index.
- Added the visible `Form 12` card marker and stabilised `npm run test` on the
  single forked worker configuration used by this machine.

Tests:

- `python -m pytest tests/v2 -q` -> `432 passed`.
- `cd frontend; npm run test` -> `14 files, 52 tests passed`.
- `cd frontend; npm run typecheck; npm run lint; npm run build` -> all passed.
- `python scripts/forward_v2/build_matchups_score.py --date 2026-08-17 --dry-run`
  -> 9 fixtures, 88 full-league profiles, 1,278 entries, all form window 12.
- Production rebuilds: `matchups_score` run
  `f739f98a6e7644c58f33987d02406d7b` and `matchups_league_avg` run
  `4cb7278827e8419d851cf1496b098243` both `succeeded`.
- Read API audit -> 40 cards: 20 OVER plus 20 UNDER, both ranked continuously
  1-20; each collection has 1,278 unique entry keys and no duplicate rows.

Insight:

The old global rank filter could hide valid current cards when deleted or
rescheduled fixtures had occupied earlier positions. The new build and read
contracts make current-day ranking self-contained. A sequential rewrite took
long enough to exceed the local operator timeout after 1,045 writes; the run
was explicitly marked failed and the batch rerun completed successfully.

Remaining:

- Real Racing Club - Villarreal is excluded because the V2 database has no
  verified Real Racing Club home profile. Do not fabricate this mapping.
- Output parity against the old repository and matchup outcome settlement over
  finished dates remain unproven.
- The current Vercel alias correctly reads the rebuilt 40-card ranking, but
  still runs the prior read adapter and therefore cannot display `Form 12`.
  Source commit `3786f64` is on `main`; the project is not Git-linked and the
  local Vercel CLI session lacks access to the hosting team, so this requires
  the existing Vercel deployment path rather than a code or database rerun.

Next:

- Repair the source/support mapping that produces the missing home profile,
  then rerun only the affected matchup acceptance audit.

### 2026-08-14 - Vercel production MongoDB configuration

Status: `VERIFIED` for the deployed read-only V2 API. This does not prove the
separate live odds, closing, CLV, or in-domain V6 forward lifecycle.

Objective: configure the existing Vercel production project with server-only
V2 database access and prove the deployed frontend API can read the production
database without accepting writes.

Changes:

- Added sensitive `Production`-only `MONGODB_URI` and `MONGODB_DB` variables
  to Vercel project `ullebets-prod-preview`; no value was committed, logged, or
  exposed to the browser.
- Corrected the URI value after the first deployment showed that outer quotes
  from the local dotenv file had been included in the Vercel secret.
- Redeployed the same source with the corrected environment as
  `dpl_9TDuhSF4VsPA12fAfpA3YEoFk6VF`.

Tests:

- `GET https://ullebets-prod-preview.vercel.app/api/v1/health`
  -> `200 {"status":"ok"}`.
- `GET https://ullebets-prod-preview.vercel.app/api/v1/dashboard?date=2026-08-14`
  -> `200`, with a valid empty fixture response for that date.
- `POST https://ullebets-prod-preview.vercel.app/api/v1/health`
  -> `405`, preserving the read-only boundary.
- Vercel runtime-errors query for the redeployment -> no runtime errors.

Insight:

Quoted dotenv values must be unquoted before being pasted into Vercel's secret
manager. A health route that reaches `read_api_database_unavailable` proves
that configuration is present but invalid; only the subsequent `200` proves
the deployed function can connect to `ullebets_v2`.

Remaining:

- Existing `vercel.app` SSO protection remains intentional until an access
  policy or custom-domain decision is made.
- Production operation, monitoring, and a full in-domain lifecycle remain
  separate readiness requirements.

Next:

- Verify only the next live checkpoint, closing, and in-domain forward windows
  when source data makes them due.

### 2026-08-13 - Vercel production adapter for the V2 read surface

Status: `PARTIAL`. The deployable source and its local gates are verified; the
public production deployment and its private MongoDB environment are the
remaining runtime gate.

Objective: host the existing Style-1 frontend without exposing MongoDB to the
browser and without replacing the existing V2 read contract.

Changes:

- Added `api/v1/[...path].py`, a Vercel Python adapter that delegates every
  read request to the existing `dispatch_get` contract and keeps one process
  scoped Mongo client.
- The adapter only accepts `GET` and `HEAD`, preserves ETags, gzip for large
  payloads, no-store error/health responses, and uses bounded edge-cache
  headers for safe read endpoints.
- Added `vercel.json` to build `frontend/`, retain `/api/v1/*` as functions,
  and route non-API SPA paths to `index.html`.
- Added a minimal Vercel runtime dependency manifest and documented the two
  required private production variables in `README.md`.

Tests:

- `python -m pytest tests/v2/test_vercel_read_api.py tests/v2/test_read_api_cache.py -q`
  -> `6 passed`.
- `cd frontend; npm run typecheck; npm run lint; npm run build` -> all passed.
- `Get-Content vercel.json -Raw | ConvertFrom-Json` -> valid JSON.
- Existing Vercel project `ullebets-prod-preview` was inspected before this
  change: it was `READY` but `/api/v1/health` returned `404`, proving it was a
  static-only deploy rather than a working product deployment.
- The first production deploy `dpl_Eoe8D4dR6bK1sFPmnL7ymCwMxaMS` was rejected
  before runtime with `unused_function`: Vercel requires a glob key under
  `functions`, not the literal dynamic route filename. The configuration now
  uses the valid `api/**/*.py` glob and must be deployed again.
- The second deploy `dpl_DVg36LZehjz2AW71HsB5f6U9REQ9` repeated the same
  build failure because the deployment upload omitted `[...path].py`: the
  PowerShell uploader treated its brackets as a wildcard. The next upload uses
  `-LiteralPath` and verifies that the function is present before deployment.
- The third deploy `dpl_4hDwUCGwXXkc8f6ibi7KSmW5fRE8` built and published the
  Python function and SPA successfully. The public SPA route returned `200`,
  but API calls returned Vercel's pre-handler `FUNCTION_INVOCATION_FAILED`.
  The adapter now defers V2 imports until request handling and searches both
  function and repository source roots; this makes the next runtime attempt
  diagnosable without exposing internal errors to clients.
- The fourth deploy `dpl_8xdsKDnPFvgrvzP3aAM6adghF2vN` proved the function
  loads and reaches its own request handler: `/api/v1/health` returned the
  V2-controlled `read_api_failure` response instead of a Vercel crash. This
  isolates the remaining failure to server configuration/database access.
  Missing `MONGODB_URI` now returns the explicit but non-sensitive `503`
  `read_api_unconfigured` response; a regression test covers that guard.
- The fifth deploy `dpl_GyLTo9WAPXvCUijm5e1L9fypZE7q` remained a V2-owned
  `read_api_failure` rather than `read_api_unconfigured`. That means the
  configured environment is not simply missing `MONGODB_URI`; the next
  adapter revision distinguishes an unsafe database target from a PyMongo
  connection failure and records only the exception class in server logs.
- The sixth deploy `dpl_D8NRsedoxnLdsZ75H2RVReW3sPxx` exposed a Python
  exception-handler scoping problem in that classification attempt and
  returned Vercel's pre-handler `FUNCTION_INVOCATION_FAILED`. The next
  revision removes that import-dependent exception branch; it classifies
  PyMongo failures from the caught exception module inside the already-proven
  generic safety handler.
- The seventh deploy `dpl_C8kJb5GsA4Tm6YUjtt9hmuDnFRJZ` uploaded the complete
  `src/ullebets_v2` package rather than a partial static dependency closure.
  Production now returns the controlled `503 {"error":"read_api_unconfigured"}`
  for `/api/v1/health`, proving that Vercel has no `MONGODB_URI`. The root SPA
  returned `200` and `POST /api/v1/health` returned `405` with
  `Allow: GET, HEAD`, so the hosting, routing, and write boundary are proven.
- Vercel project protection is `SSO all_except_custom_domains`. This is a
  deliberate access-control setting, not an application failure; the
  `vercel.app` URL therefore requires the owner's Vercel sign-in unless a
  custom domain is attached or the protection policy is changed.

New insight: static Vite hosting alone cannot work because local development
depends on the port `8787` proxy. The API must be deployed on the same public
origin; the new serverless adapter makes that boundary explicit and keeps
MongoDB credentials server-only.

Blocked: set the Vercel **Production** variables `MONGODB_URI` and
`MONGODB_DB=ullebets_v2` through an account-authorized Vercel environment
manager. This session's connected Vercel deploy tool does not expose an
environment-variable write operation, and the local Vercel CLI token is
invalid; no secret was copied to source code or the frontend.

Next justified test: after those variables are set and Vercel redeploys, call
the public health and dashboard routes and confirm current data. Decide
separately whether the existing SSO protection should remain until a custom
domain is attached.

Next justified test: deploy this exact source to `ullebets-prod-preview`, set
only the two server-side production variables, and run the public acceptance
requests.

### 2026-08-13 - Cloud/local reconciliation and read-surface contract repair

Status: `VERIFIED` for the reconciled local `style-1` branch. This does not
change independent production, live-closing, or in-domain forward-model
readiness gates.

Objective: reconcile the cloud `style-1` frontend/read-surface work with the
preserved local V2 forward-ledger and match-analytics changes without losing
either side's behavior.

Changes:

- Rebased the three preserved local commits on top of `origin/style-1`, whose
  base already contains the cloud merge into `origin/main`.
- Restored the complete read contract in the merged V2 API: cache-safe public
  dispatch, stable semantic ETags, bounded dashboard matchup reads, canonical
  Auto/Results exposure rows, and match-detail forward selections/results.
- Restored URL-driven Auto filters and server pagination, league/team/match
  navigation, and an accessible mobile dialog shell while keeping the match
  rail lazy-loaded.
- Made the new analytics view accept older V2 match-detail responses without
  profiles, and display persisted normalized market offers, settlement rows,
  and forward evidence when available.
- Corrected CLV presentation to use V2's stored percentage-point unit; for
  example, `5.5` is rendered as `+5.5 %`, not `+550 %`.
- Added a regression proving match detail returns canonical V6 selection,
  settlement, and CLV evidence from V2 collections.

Tests:

- `python -m compileall -q src; python -m pytest -q` -> `449 passed`.
- `npm test -- --run` -> `14` files / `52` tests passed.
- `npm run lint` -> passed with zero warnings.
- `npm run build` -> Vite production build passed.
- `git diff --check` -> passed.

New insight: the merge conflict was not merely visual. It exposed two
production-facing contract defects: an older API response could crash the
analytics page, and the generic fractional-percent formatter could inflate
stored V2 CLV percentage points by 100. Both are now regression-tested.

Unproven: hosted CI/deployment of this new commit, live T-30/T-10/closing
capture, closing-based CLV, and in-domain V6 forward settlement remain
separate runtime gates.

Next justified test: verify the hosted CI run after the reconciled branch is
pushed; merge to `main` only through the normal reviewed branch flow.

### 2026-08-13 - Style-1 frontend and read-only product surface

Status: `VERIFIED` for the implemented product surface on `style-1`; production deployment and the in-domain model lifecycle remain separate readiness gates.

Objective: build the complete styled Ullebets frontend against typed, read-only V2 contracts without changing model, prediction, odds-capture, settlement, database-write, or production workflow behavior.

Verified implementation sequence:

- Step 1 commit `ae75e1a`: stable read contracts, Stockholm-owned product date, entity navigation, league route, real 404, typed Auto/Results contracts, and watchlist resolution.
- Step 2 commit `ba775d7`: match, team, and league drilldowns with persisted odds, actuals, forward evidence, teamprofile contexts, league-relative deviations, rankings, and clickable history.
- Step 3 commit `4aae1ff`: shareable read-only filters, server pagination, persisted history rows, and stable pagination with previous data retained while the next page loads.
- Step 4 commit `202df85`: persisted model/policy runtime statuses and visible jobs/health/audits; observation counts are explicitly not treated as proof of forward ROI or CLV.
- Step 5 commit `37ba528`: keyboard skip link, date-only shared navigation state, mobile access to model/system tools, narrow-layout hardening, and route-shell regression coverage.

Final hosted verification on `style-1` commit `37ba528d00446e6b788d288e381609d962c29e45`:

- frontend Actions run `31648971262`: dependency audits found 0 vulnerabilities; hardcoded-preview guard passed; TypeScript passed; ESLint passed; 12 Vitest files / 45 tests passed; Vite production build passed;
- backend-isolation run `31648971290`: complete Python suite passed `434/434`;
- the frontend runtime does not contain the known preview match/card fixtures guarded by CI, and the UI does not infer proof from row counts;
- read-side additions are confined to `src/ullebets_v2/read_api/**` plus read-API tests. No model training/scoring policy, prediction write, odds acquisition, settlement, or database write path was changed by the frontend work.

Remaining truth boundary: model-specific in-domain forward ROI, model-specific in-domain CLV/beat-close evidence, live T-30/T-10/closing lifecycle proof, production deployment, and complete operational acceptance remain `UNPROVEN`, `BLOCKED`, `PARTIAL`, or `NOT STARTED` exactly as their independent evidence requires.

### 2026-08-12 - Production-database teamprofile and V6 rerun

Status: `PARTIAL`

Objective: run the two remaining V2 code paths against real current data,
then diagnose and repair any real failure before accepting them.

Production-database evidence in `ullebets_v2`:

- `build_teamprofiles` run `cd422e097d584acfa1996caf05088a66` succeeded with
  265 inserted dated profiles from 585 canonical results, 147,408 stat rows,
  1,107 incidents, and 1,105 shotmaps. Its parity, audit, and health reports
  were `matched`, `ok`, and `ok`.
- A read-only phase measurement showed `242.565 s` for canonical loading and
  `2.536 s` for profile building. The original write path then spent about 15
  minutes on 265 sequential upserts because it queried unindexed
  `profile_key`, while the collection's unique index is
  `team_key + profile_date + match_type`.
- Persistence now uses that indexed identity. The idempotent full rerun
  `62deff7b22704dc5a229ee6b39101100` succeeded with all 265 profiles and
  `0` duplicate writes; its write stage was `123.665 s`. The full local
  command including historical data loading took `407.641 s`.
- The first V6 rerun, `6b5e26b5a61c491494ef7eda8a6a5ec7`, correctly failed
  closed. The stored and rebuilt values differed only in
  `feature_values.market_anchor_lambda` by approximately `4e-16`, but its
  derived `feature_fingerprint_sha256` differed and bypassed the earlier
  tolerance rule.
- The corrected V6 rerun `33145640a5c54676b20bd6716ca74dbe` succeeded on 308
  valid prematch snapshots across five future fixtures. It reused all 105
  frozen score rows with `0` conflicts; 49 were precision-equivalent. It kept
  42 in-domain La Liga scores and excluded 63 Brazilian out-of-domain scores;
  it created zero forward bets.

Changes:

- `teamprofiles/persistence.py` now upserts through the canonical unique
  profile identity.
- `forward_scores.py` validates the feature fingerprint independently but
  compares actual feature values, not a derivative hash, for tolerant
  immutable reuse.

Tests:

- targeted teamprofile and score regression tests: `10 passed`;
- full V2 suite: `415 passed`;
- `python -m compileall -q src` and `git diff --check`: passed.

New insight: the two V2 database code paths are verified in write mode, but
the exact GitHub Actions runners still need one hosted run on the deployed
commit before the automation layer can be called fully verified.

### 2026-08-12 - Cosmos teamprofile and V6 score-idempotency repair

Status: `PARTIAL`

Changed `src/ullebets_v2/teamprofiles/service.py` and
`src/ullebets_v2/ev_model/forward_scores.py`, with regression coverage in
`tests/v2/test_teamprofiles.py` and `tests/v2/test_ev_forward_scores.py`.

Root-cause evidence from the production-read-only investigation:

- a single `match_stats_canonical` request for 579 historical `match_key`
  values timed out in Cosmos DB with `ExceededTimeLimit`;
- a stored V6 score and a rerun score had identical inputs, artifact, features,
  and policy, but differed by `5.55e-17` in probability and `1.11e-16` in EV,
  producing different exact JSON fingerprints.

The reader now sends the historical date constraint to Cosmos, projects only
needed fields, batches every dependent `match_key` query in groups of 50, and
uses an in-memory result index rather than repeatedly scanning every result.
Score persistence now reads the existing immutable row in full, validates the
derived feature fingerprint, and accepts only raw values that differ by
numeric machine precision within an absolute `1e-12` tolerance. It never
overwrites an existing score; material field changes and corrupted stored
fingerprints still fail closed.

Tests run:

- failing regression run before implementation:
  `python -m pytest -q tests/v2/test_teamprofiles.py tests/v2/test_ev_forward_scores.py`
  resulted in `3 failed, 7 passed`;
- same targeted command after implementation: `10 passed`;
- `python -m pytest -q`: `415 passed`;
- `python -m compileall -q src` and `git diff --check`: passed.

The code-level and database-read reproduction are verified. A full hosted
teamprofile build and the next scheduled V6 rerun are still required to prove
the repaired production executions.

### 2026-08-08 - Capture-triggered V6 scoring

Status: `PARTIAL`

Objective:
Remove redundant ten-minute EV recalculation and score V6 immediately after a
checkpoint actually saves new odds snapshots.

Changes:

- `v2-odds-scheduler.yml` now runs V6 only after a T-3D/T-2D/T-1D/T-2H
  checkpoint capture persists new snapshot rows.
- `run-unibet-closing.yml` now runs the same V6 command only after a T-30/T-10
  closing capture persists new snapshot rows.
- Both capture services surface the actual `market_snapshot_upserts` count in
  their CLI summary. The workflows use that persisted count, not the planned
  snapshot list, and skip the full model dependency install and V6 scorer for
  duplicates, empty windows, and manual dry-runs.
- Removed the independent ten-minute schedule from `ev-shadow-forward.yml`;
  it remains available for manual recovery only.
- Added workflow-contract regressions for the new capture-to-score chain and
  for the manual-only scorer workflow.

Tests:

```text
RED: python -m pytest tests/v2/test_automation_contract.py -q
     2 expected failures before workflow implementation
GREEN: python -m pytest tests/v2/test_automation_contract.py -q
       20 passed
python -m pytest tests/v2/test_checkpoint_capture.py tests/v2/test_closing_capture.py tests/v2/test_ev_forward_scores.py tests/v2/test_ev_forward_predictions.py tests/v2/test_automation_contract.py -q
55 passed
python -m pytest -q
413 passed
python -c "import yaml; ..."
yaml-ok
git diff --check
passed
Hosted workflow_dispatch: v2-odds-scheduler.yml, dry_run=true
run 31274563877 passed on main@4c19ea7
```

Results:

- No new V6 score job starts on an empty, duplicate, or dry-run capture.
- A successfully persisted odds snapshot starts the frozen V6 scorer in the
  same GitHub Actions job, before that job completes.
- Hosted scheduler smoke run `31274563877` passed on `main@4c19ea7`: it
  inspected nine due targets, built `744` dry-run snapshots with zero source
  errors, parsed the new persisted-upsert field safely, and correctly skipped
  V6 because a dry-run never persists snapshots.
- V6 score and forward-bet immutability remain unchanged: later snapshots add
  immutable score evidence and never rewrite an existing forward prediction.

Insight:
The scheduler frequency is now only used to discover due capture windows. It
does not imply repeated EV model execution while no new snapshot is persisted.

Remaining:

- A hosted write-mode T-3D/T-2D/T-1D/T-2H or T-30/T-10 capture must prove that
  the inline V6 scorer completes against persisted new snapshots before
  kickoff.

Next:

- Dispatch dry-run workflow smoke tests after deployment, then inspect the
  first due production checkpoint for persisted scorer evidence.

### 2026-08-08 - EV scorer and snapshot-cadence audit

Status: `PARTIAL`

Objective:
Verify whether V6 calculates and persists a score immediately after each
T-3D/T-2D/T-1D/T-2H/T-30/T-10 odds capture.

Changes:

- Updated operational documentation only; no code, workflow, or database
  write was made by this audit.

Tests:

```text
Read .github/workflows/v2-odds-scheduler.yml
Read .github/workflows/ev-shadow-forward.yml
Read scripts/forward_v2/score_ev_shadow_model.py
Read latest score_ev_shadow_model job_runs and ev_model_scores from ullebets_v2
Read current hosted EV Shadow Forward runs
```

Results:

- Capture jobs persist `market_snapshots`; they do not invoke V6 scoring.
- The V6 workflow is separately scheduled at minutes `5,15,25,35,45,55` and
  each run reads every timing-valid future snapshot available at run time.
- Latest production scorer job `c5858755ed6b403b9126446f70fa4796` succeeded at
  `2026-08-08T19:06Z`: `2,347` input snapshots, `135` canonical markets,
  `216` V6 side scores, and `24` newly persisted immutable scores.
- All current Brazilian scores were excluded from forward selection because
  Brasileirão Série A is outside V6's trained league domain.
- GitHub scheduled scorer starts were observed at `17:52Z`, `18:22Z`, and
  `19:06Z`, so the configured ten-minute cadence is not an exact runtime
  guarantee.

Insight:
Every new snapshot can be scored on the next scorer pass and score keys retain
the source snapshot key, but the system does not yet guarantee a score before
kickoff after a late T-30/T-10 capture. Forward bets are immutable: a later
snapshot produces a new score, not a mutation of an existing selection.

Remaining:

- Define and implement the production rule for fresh pre-kickoff EV: either
  score synchronously after each capture or explicitly freeze V6 selection at
  a declared earlier checkpoint.

Next:

- Decide and implement a capture-to-score contract before treating T-30/T-10
  as prediction-refresh checkpoints.

### 2026-08-08 - Closing runner import repair deployed

Status: `PARTIAL`

Objective:
Repair the production runner failure that prevented T-30/T-10 capture before
the closing command could start.

Changes:

- Added `PYTHONPATH=${{ github.workspace }}/src` to the reusable V2 Python
  runner used by lean workflows.
- Added a regression test that executes the same internal package import from
  a stripped Python process with only the V2 source path available.

Tests:

```text
python -m pytest tests/v2/test_automation_contract.py tests/v2/test_workflow_runner.py -q
python -m pytest -q
Hosted workflow_dispatch: run-unibet-closing.yml, dry_run=true
Hosted run: 31273361050
```

Results:

- Regression test first failed because the reusable workflow did not expose
  the source package.
- Targeted tests passed `21/21`; full suite passed `409/409`.
- Commit `030a401` was pushed to `main`.
- Hosted dry-run `31273361050` ran on that commit, imported
  `ullebets_v2.automation`, reached `capture_closing_snapshots.py`, and
  completed successfully with zero errors.
- It correctly reported zero due targets because the next fixture was
  Remo - Atlético Mineiro at `2026-08-08T21:30:00Z`, outside T-30/T-10.
- Dry-run made no database writes, so it is runner proof only, not closing or
  CLV evidence.

Insight:
The ordinary checkpoint scheduler works because it runs its capture script
directly. The closing workflow uses the reusable runner, so its lean profile
needed an explicit V2 source import path before command rendering.

Remaining:

- A successful scheduled production T-30/T-10 capture, closing-line
  materialization, and CLV refresh.

Next:

- Inspect the next live T-30/T-10 window after the deployed fix; do not mark
  closing or CLV complete from the manual dry-run.

### 2026-08-08 - Live checkpoint pass and closing-runner failure

Status: `PARTIAL`

Objective:
Verify the currently due Brazil odds checkpoints and determine whether the
closing chain works during a real T-30/T-10 window.

Changes:

- Updated verification documentation only; no code, workflow, or database
  write was made by this audit.

Tests:

```text
Read-only MongoDB audit of current-cycle fixtures, raw_odds_kambi,
market_snapshots, closing_lines, clv_tracking, and job_runs
gh run list --repo ulle73/ullebets-prod --workflow run-unibet-closing.yml ...
gh run view 31271905639 --repo ulle73/ullebets-prod --log-failed
```

Results:

- Valid current-cycle snapshots: T-3D `678` over 10 matches, T-2D `799` over
  10 matches, T-1D `817` over 10 matches, and T-2H `242` over three matches.
- The latest T-2H job succeeded at `2026-08-08T17:50Z`, wrote two raw Kambi
  payloads and `85` snapshots, with zero errors.
- The latest raw odds payload was stored at `2026-08-08T17:49:58Z`.
- All current-cycle snapshot rows are valid prematch rows; duplicate valid
  snapshot-key groups are `0`.
- `closing_lines = 0`; CLV remains `860` missing closing line and `3` invalid
  snapshot timing rows.
- Closing workflow run `31271905639` failed at `2026-08-08T18:26Z` with
  `ModuleNotFoundError: No module named 'ullebets_v2'`, before it could fetch
  or persist any closing odds.
- The workflow is active, but no succeeding 5-minute closing run was recorded
  through `2026-08-08T18:53:50Z`.

Insight:
The normal checkpoint pipeline is operational in production. The separate
closing workflow is blocked by a reusable-runner dependency setup defect, not
by Kambi data, timing validation, or database persistence.

Remaining:

- Repair and deploy the lean shared runner, then capture a real T-30/T-10,
  materialize closing lines, and refresh CLV.
- Observe in-domain V6 selections and untouched settlement.

Next:

- Change the reusable lean runner so `ullebets_v2` is importable without
  installing the full ML dependency profile, then run targeted workflow tests
  and verify the next real closing window.

### 2026-08-04 - Current production checkpoint audit

Status: `PARTIAL`

Objective:
Verify the latest scheduled odds state and identify exactly which production
checkpoints are proven before the 8-9 August Brazil window.

Changes:

- Updated the work log, readiness checklist, and backend verification status.
- No production code, database data, or workflow configuration changed.

Tests:

```text
Read-only MongoDB audit of fixtures_canonical, market_snapshots,
raw_odds_kambi, closing_lines, clv_tracking, and job_runs
python scripts/forward_v2/ingest_unibet_odds.py --mode fixture-db --max-days-ahead 7 --dry-run
gh run list --workflow v2-odds-scheduler.yml --limit 3 --json ...
gh run list --workflow ev-shadow-forward.yml --limit 3 --json ...
```

Results:

- 10 future canonical Brazil fixtures exist; the next is Grêmio - São Paulo
  at `2026-08-08T19:00:00Z`.
- Valid persisted snapshots: T-2D `161` rows over two matches and T-1D `244`
  rows over three matches.
- No valid T-3D, T-2H, T-30, or T-10 row exists. All `248` stored T-10 rows
  are old invalid timing rows and remain excluded.
- Latest raw odds write remains `2026-07-30T00:28:39.392Z`; this is expected
  because no current fixture was due at the latest scheduler run.
- Scheduled run `30949327663` succeeded with 10 target matches, zero due
  matches, zero fetch errors, and audit/health status `ok`.
- Current Kambi dry-run linked `10/10` matches, produced `11` raw documents
  and `607` normalized offers, and returned zero errors.
- `closing_lines` remains empty, so official closing CLV is still unavailable.

Insight:
The source, fixture linkage, and scheduler empty-window behavior are currently
healthy. T-3D is not failed: the first new fixture was still about 93.5 hours
from kickoff, outside the 60-84 hour T-3D policy window.

Remaining:

- Real persisted T-3D, T-2H, T-30, T-10, closing-line, and CLV evidence.
- In-domain V6 predictions and untouched settlements.

Next:

- Inspect the first scheduler run after `2026-08-05T07:00:00Z`; it should
  persist T-3D data for Grêmio - São Paulo when GitHub Actions executes within
  the broad 24-hour checkpoint window.

### 2026-08-01 - V6 registered forward-policy activation

Status: `PARTIAL`

Objective:
Make frozen V6 scores, rather than the legacy JS EV formula or V3, the only
source for new model-specific forward selections.

Changes:

- `ev-shadow-forward.yml` now runs only the frozen V6 artifact.
- Added immutable `forward_policy_registry_v1`, preserving V5 unchanged while
  registering the exact V6 corners + away/total policy for forward testing.
- Added a policy materialization boundary from immutable `ev_model_scores` to
  immutable `forward_bets`, with policy fingerprint, source score key, timing,
  artifact, odds, probability, EV, and feature-fingerprint provenance.
- Added policy/match dedupe and an index supporting that lookup.
- Removed the production schedule from legacy `run-unibet-backtests.yml`; it
  remains manually available as `V2 Legacy EV Parity Replay`.

Tests:

```text
python -m pytest tests/v2/test_ev_forward_predictions.py tests/v2/test_ev_score_evaluation.py tests/v2/test_automation_contract.py -q
python -m pytest tests/v2/test_ev_policy_registry.py tests/v2/test_ev_forward_predictions.py tests/v2/test_ev_score_evaluation.py tests/v2/test_automation_contract.py -q
python -m pytest -q
python scripts/forward_v2/healthcheck_v2.py
python -m compileall -q src/ullebets_v2 scripts/forward_v2
python scripts/forward_v2/bootstrap_indexes.py
python scripts/forward_v2/score_ev_shadow_model.py --repo-root . --artifact models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/ev_scope_interaction_recency45_asof_capped_v6_shadow.joblib --manifest models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/model_manifest.json --score-only --selection-policy-registry models/ev/forward_policy_registry_v1.json --selection-policy-id v6_corners_away_total_forward_v1 --dry-run
python scripts/forward_v2/score_ev_shadow_model.py --repo-root . --artifact models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/ev_scope_interaction_recency45_asof_capped_v6_shadow.joblib --manifest models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/model_manifest.json --score-only --selection-policy-registry models/ev/forward_policy_registry_v1.json --selection-policy-id v6_corners_away_total_forward_v1 --now 2026-07-30T00:30:00Z --dry-run
gh workflow run ev-shadow-forward.yml --ref main
gh run watch 30717651924 --exit-status
```

Results:

- Full suite: `408 passed`.
- Healthcheck: `overall_status=ok`, zero missing/invalid workflow contracts.
- Current real-time dry-run: zero future persisted `market_snapshots`, a valid
  empty result with the new V6 policy loaded.
- Historical prematch dry-run: `319` input snapshots, `30` canonical markets,
  `48` V6 side scores, zero future-stat observations used.
- All `48` scores were excluded because Brasileirão Série A is outside V6's
  six-league training domain; registered forward selections remained `0`.
- Both scorer runs were dry-runs and made no database writes.
- Index bootstrap applied `selection_policy_match` to `forward_bets`; all 36
  collection plans completed with `0` repaired and `0` deleted documents.
- Commit `f607338` was pushed to `main`. Hosted write-mode run `30717651924`
  succeeded and loaded only V6 with `forward_policy_registry_v1` and policy
  `v6_corners_away_total_forward_v1`; `dry_run=false`.
- The hosted run had `0` future input snapshots and therefore persisted `0`
  scores/selections. This was a valid empty run, not a scorer failure.

Insight:
V6 is now the configured production forward model, but it still fails closed
outside its fitted domain. This is an orchestration activation, not new proof
that the historical `+28.65%` survives forward testing.

Remaining:

- Observe a real prematch score and immutable selection from a V6-supported
  league, then settle it and measure model-specific ROI/CLV.

Next:

- After deployment, inspect the first hosted V6 run with an in-domain fixture;
  do not use Brazil to bypass the domain contract.

### 2026-08-01 - Current legacy-EV backtest path verification

Status: `PARTIAL`

Objective:
Verify whether the V2 replacement for the original `run-unibet-backtests`
path currently performs live Kambi discovery, normalizes every available
line, and calculates the legacy EV outputs.

Changes:

- No code, database, model, or policy changes.
- Exercised the current fixture-database path against live Kambi data in
  read-only dry-run mode.

Tests:

```text
python scripts/forward_v2/build_model_snapshots.py --mode fixture-db --snapshot-mode backtest --source-workflow current-backtest-verification-2026-08-01 --max-days-ahead 7 --dry-run
```

Results:

- The exact seven-day window contained one match, Grêmio - São Paulo.
- Event linkage succeeded `1/1`; two raw payload documents and `59` normalized
  market offers were produced in memory.
- The V2-owned legacy JS EV runtime generated `108` directed line rows with
  EV details, zero source errors, and zero model errors.
- Parity, audit, and health status were all `matched`/`ok`.
- Dry-run made no database writes. Three additional future fixtures were just
  outside the exact seven-day cutoff.

Insight:
The original-style `odds -> line sides -> legacy EV` mechanism works on a
current live market. It is not the V6 model and does not prove that the legacy
EV formulas are profitable. The existing 370 historical replay rows also
lack primary EV values and settlement, so they are not a completed historical
backtest acceptance sample.

Remaining:

- Persist a non-empty scheduled `run-unibet-backtests.yml` execution and
  settle its rows from canonical outcomes.
- Keep legacy-EV output separate from V6 forward evidence and promotion.

Next:

- Inspect the next scheduled non-empty backtest run; do not rerun the live
  dry-run unless source behavior, mappings, or model runtime changes.

### 2026-08-01 - Resilient T-2H/T-30/T-10 closing policy

Status: `PARTIAL`

Objective:
Reduce missed closing coverage under delayed GitHub Actions schedules without
misreporting an earlier price as the true closing line.

Changes:

- Added `T_MINUS_30M` with a broad 15-50 minute capture window.
- Promoted T-2H collection into the hourly production checkpoint job while
  retaining its historical research classification for model evidence.
- Reserved T-30 and T-10 exclusively for the five-minute closing workflow.
- Materialized T-30 as `t30_fallback`; a later T-10 upgrades the same closing
  row to official `t10` quality.
- Prevented T-2H/T-1D or older rows from becoming closing lines when both
  near-close checkpoints are missing.
- Propagated closing quality through CLV and forward results. T-30 CLV uses
  `tracked_fallback_t30` and is excluded from official model promotion CLV.

Tests:

```text
python -m pytest tests/v2/test_checkpoint_capture.py tests/v2/test_closing_capture.py tests/v2/test_clv_tracking.py tests/v2/test_forward_results.py tests/v2/test_ev_forward_evaluation.py tests/v2/test_ev_score_evaluation.py tests/v2/test_ev_snapshot_integrity.py tests/v2/test_automation_contract.py -q
python -m pytest -q
python scripts/forward_v2/capture_closing_snapshots.py --mode fixture-db --source-workflow near-close-production-preflight --max-days-ahead 7 --dry-run
```

Results:

- Targeted checkpoint/closing/CLV/promotion tests passed `61/61`.
- Full regression suite passed `402/402`.
- Current real-time read-only preflight completed with audit and health `ok`.
  It found zero fixtures in the next seven days, so no live capture was due.
- Hosted production write-mode run `30674861895` succeeded on commit `f6a6ea0`.
  It found zero fixtures in the source horizon, persisted parity/audit/health
  reports with zero errors, and kept the closing watcher safely disabled.
- Synthetic timing contracts prove T-30 fallback creation, T-10 upgrade,
  duplicate prevention, and exclusion of fallback CLV from promotion metrics.

Insight:
A T-30 fallback improves Actions tolerance, but it is not market close. The
quality label must remain part of every closing, CLV, and promotion report.

Remaining:

- Persist a real T-2H/T-30/T-10 lifecycle on the next fixture with Kambi
  markets. Code and dry-run evidence do not replace that live proof.

Next:

- Inspect the first scheduler activation with a real future fixture and verify
  that T-30 persists even if T-10 is delayed, then verify that a later T-10
  upgrades the closing and official CLV.

### 2026-08-01 - Production odds scheduler idempotency repair

Status: `PARTIAL`

Objective:
Ensure the deployed match-aware scheduler cannot abort regular checkpoint
capture merely because the T-10 workflow is already in the requested state.

Changes:

- Made closing-workflow enable/disable transitions idempotent by reading the
  current GitHub workflow state before applying a change.
- Added an automation contract regression for the no-op state path.
- Deployed the repair on `main@cdb83b9`.

Tests:

```text
python -m pytest tests/v2/test_automation_contract.py tests/v2/test_closing_watch.py tests/v2/test_checkpoint_capture.py tests/v2/test_closing_capture.py tests/v2/test_closing_downstream.py tests/v2/test_clv_tracking.py -q
python -m pytest -q
gh workflow run v2-odds-scheduler.yml --ref main -f lookahead_hours=2 -f days_ahead=7 -f dry_run=false
gh run watch 30673575119 --exit-status
```

Results:

- The previous scheduled run `30672553536` failed with GitHub HTTP `403`
  because it tried to disable an already disabled workflow.
- Targeted closing/checkpoint tests passed `44/44`; the full suite passed
  `394/394`.
- Hosted production write-mode run `30673575119` completed all steps.
- The current workflow state was `disabled_manually`; the new path treated it
  as a successful no-op and continued to checkpoint capture.
- With no fixture inside the current watch window, the persisted checkpoint
  job `0e4b84a64e4f44eb82412b5ba0753ed8` correctly finished `succeeded` with
  `0` due matches, `0` errors, and audit/health status `ok`.

Insight:
GitHub workflow enable/disable commands are not idempotent. State inspection
must precede mutation or an expected disabled state can suppress unrelated
checkpoint collection.

Remaining:

- The next real fixture window must still prove automatic enablement, valid
  T-10 capture, closing-line materialization, and CLV refresh.

Next:

- Inspect the first scheduler run with a fixture inside two hours, then verify
  persisted T-10, closing, and CLV evidence without simulating time.

### 2026-08-01 - Scheduled forward-scoring runtime audit

Status: `VERIFIED`

Objective:
Answer whether the current model, match-data, statistics, and odds lifecycle is
fully operational using the latest persisted and hosted-run evidence.

Changes:

- Pinned the frozen model runtime dependencies in `pyproject.toml`.
- Changed enrichment persistence to use 200-operation bulk batches.
- Updated the local ignored `.env.local` target from `app` to `ullebets_v2`.
- Fetched and stored the latest completed match dates for all seven followed
  leagues.

Tests:

```text
gh run list --limit 20 --json databaseId,name,workflowName,status,conclusion,event,createdAt,updatedAt,headSha,url
gh run view 30668128118 --log-failed
gh run watch 30672830616 --exit-status
python -m pytest -q
python scripts/forward_v2/ingest_fixtures_window.py --mode live --start-date 2026-05-16 --end-date 2026-05-24 --source-workflow production-latest-completed-2026-08-01
python scripts/forward_v2/ingest_fixtures_window.py --mode live --date 2026-07-31 --source-workflow production-latest-completed-2026-08-01
python scripts/forward_v2/backfill_match_enrichment.py --source-mode db --start-date 2026-05-18 --end-date 2026-05-24 --source-workflow production-latest-completed-rebuild-2026-08-01
```

Results:

- Latest scheduled `V2 EV Shadow Forward` run `30668128118` failed on
  `main@69e6455`.
- All four frozen scorer invocations reject the hosted runtime: manifests
  expect `numpy 2.2.2` and `pandas 2.2.3`; the unpinned install produced
  `numpy 2.5.1` and `pandas 3.0.5`.
- The shared workflow runner was inspected and its existing contract tests
  prove scheduled jobs strip command-template `--dry-run`; the earlier claim
  that production scoring was forced to dry-run was incorrect.
- Exact runtime pins now match all frozen manifests: `numpy 2.2.2`,
  `pandas 2.2.3`, `joblib 1.5.0`, and `scikit-learn 1.7.1`.
- Production fixture ingest stored 181 canonical fixtures for 16-24 May and 6
  for 31 July, with zero unmatched fixture identities.
- The first 39-match enrichment fetched every required source successfully but
  exposed one CosmosDB timeout on a single 10,085-operation canonical bulk.
- Raw statistics, incidents, shotmaps, results, and canonical results were
  preserved for all 39 affected matches. Batched canonical rebuilding then
  completed successfully from raw without refetching sources.
- Across the latest completed date per league: 41/41 matches have all four raw
  enrichment payload families, scored canonical results, and exactly 27
  corners/shots/shots-on-goal period/scope rows. There are 1,107 primary rows,
  zero duplicate primary keys, and zero missing actual values.
- Full regression suite: `394 passed`.
- Hosted run `30672830616` completed successfully in write mode on
  `main@f188c52`; V3, V4, V5, and V6 each returned `status=ok`.
- All four scorers returned zero canonical markets because no current upcoming
  model-ready markets existed. This is a valid empty production result, not a
  dry-run or source failure.

Insight:
The frozen model correctly fails closed on runtime drift. Production workflow
write mode was already correct; reproducible dependency pinning was the actual
scorer defect. Large historical enrichment batches also require bounded bulk
writes on CosmosDB even though normal daily windows are smaller.

Remaining:

- Prove one hosted scoring write before kickoff on an in-domain fixture.

Next:

- Wait for an in-domain prematch fixture, then verify the first persisted score
  and eventual untouched settlement without changing the frozen policy.

### 2026-07-31 - Match-aware GitHub Actions odds scheduling

Status: `VERIFIED`

Objective:
Retain GitHub Actions while avoiding permanent five- and ten-minute polling.

Changes:

- One hourly workflow now captures production T-3D/T-2D/T-1D checkpoints.
- The same workflow enables `run-unibet-closing.yml` only when an uncaptured
  fixture exists within two hours and disables it otherwise.
- The T-10 watcher keeps five-minute precision only during that active match
  window and still captures at most one valid T-10 snapshot per match.
- T-12H/T-2H remain available for manual research but are excluded from the
  production schedule.
- Scheduler and closing jobs use a lean `pymongo` runtime instead of installing
  the full ML dependency set on every check.

Tests:

```text
python -m pytest -q
python scripts/forward_v2/plan_closing_watch.py --lookahead-hours 2
```

Results:

- `392 passed`.
- A clean virtual environment containing only `pymongo` imported the planner,
  checkpoint, and closing CLIs successfully.
- The real read-only planner check against `ullebets_v2` returned
  `action=disable`, with zero fixtures in the next two hours.
- GitHub dry-run
  [30667410766](https://github.com/ulle73/ullebets-prod/actions/runs/30667410766)
  completed in 14 seconds with zero due targets and no workflow-state change.
- GitHub write/state run
  [30667457674](https://github.com/ulle73/ullebets-prod/actions/runs/30667457674)
  completed in 14 seconds and disabled the T-10 workflow because no fixture
  was due within two hours.
- Official runner dependencies were updated to `actions/checkout@v7`,
  `actions/setup-python@v7`, and `actions/setup-node@v7` after the first hosted
  run exposed the Node 20 deprecation warning.
- Final v7 hosted dry-run
  [30667644513](https://github.com/ulle73/ullebets-prod/actions/runs/30667644513)
  completed in 17 seconds with zero annotations. At verification time the
  match-aware scheduler was active, the T-10 workflow was disabled, and the
  manual checkpoint workflow had no cron schedule.

Insight:
GitHub Actions cannot create dynamic future cron events per fixture. Toggling a
short-interval workflow from an hourly fixture-aware planner is the closest
reliable Actions-native equivalent without wasting 288 full runs every day.

Remaining:

- The enable/capture/disable lifecycle still needs persisted proof from the
  next real fixture window.

Next:

- Inspect the next hourly planner activation and subsequent valid T-10 capture.

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
- `main` was pushed at `5aae938`; GitHub registered all 24 V2 workflows as
  active.
- Repository secrets `MONGODB_URI`, `RAPIDAPI_KEYS`, and the compatibility
  `RAPIDAPI_KEY` were configured from the ignored local environment without
  committing or printing their values.
- GitHub Actions run
  [30647673244](https://github.com/ulle73/ullebets-prod/actions/runs/30647673244)
  completed successfully on `main` in 1m45s,
  proving repository checkout, dependency installation, Mongo connectivity,
  fixture-database inspection, and the V2 healthcheck command in the hosted
  runner environment.

Insight:
The backend code already contained the capture mechanisms, but an undeployed
workflow and overlapping T-10 ownership made the live behavior unreliable.
The closing job is now the single T-10 owner and its derived outputs are part
of the same automated path.

Remaining:

- A future live fixture is still required to prove a persisted production
  T-10 snapshot, closing line, and CLV row end to end.

Next:

- Inspect the next scheduled real T-10 job run and its persisted snapshots,
  closing lines, CLV tracking, and forward results rather than running another
  manual polling loop.

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
