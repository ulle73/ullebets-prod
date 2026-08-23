# Ullebets V2 Backend Verification Status

Last updated: 2026-08-23
Branch: `main`
Database: `ullebets_v2`

This file is the frozen backend verification snapshot for the current V2 state.
Use it to avoid rerunning full end-to-end checks unless one of the remaining unverified windows is actually due, or a relevant subsystem changes.

## Self-Healing Post-Match Recovery On 2026-08-23

Eleven completed V6 checkpoint-journal exposures from 22 August remained open
because their canonical actuals had never been ingested. The defect was not a
settlement-rule failure. Daily enrichment run `32620243134` was cancelled by
the repository-wide concurrency group, and enrichment selected mutable source
dates rather than `fixture_date_stockholm`; the 7 affected Stockholm-date
fixtures carried source dates of 23 or 30 August.

The permanent contract now has two independent recovery paths. Daily
enrichment has its own concurrency group and uses the product date. The hourly
post-match workflow first discovers every sufficiently old, started forward
exposure whose latest settlement is `pending_result` or `missing_actual`,
enriches those exact immutable match keys, and only then runs settlement, CLV,
forward-result refresh, and audits. Both paths remain fail-closed on
`MONGODB_DB=ullebets_v2` and share the canonical settlement timing contract.

Current evidence:

- targeted regression suite: 32 passed;
- full V2 suite: 528 passed;
- guarded production dry-run and write run: 7/7 affected matches, 7 raw result
  payloads, 7 canonical results, 1,821 canonical stat rows, zero source errors,
  matched parity, and `ok` audit;
- exact affected exposures: 11/11 settled, 5 wins, 6 losses, and 0 missing
  actuals;
- complete current forward surface: 55 canonical exposures, 15 settled and 40
  legitimately open for current/future fixtures;
- production read API exposes the repaired outcomes, and V2 health is `ok`.

Status: `VERIFIED` for implementation, regression coverage, production data
recovery, settlement, and the read contract. It remains `PARTIAL` until the
new workflow definition has run from the merged `main` SHA and the final
deployment/source boundary is verified separately.

## V6 Full-Domain Checkpoint Journal On 2026-08-23

The new immutable `forward_policy_registry_v2` leaves frozen V1 evidence
untouched and registers `v6_full_domain_checkpoint_journal_v2`. Each eligible
positive-EV score is a separate 1u evaluation at its captured checkpoint. The
same policy/match/stat/scope/period/direction/line is grouped only by the read
API, where the highest observed EV is shown and all underlying stake, PnL,
ROI, and official CLV observations remain aggregated.

Supported model domain is explicit and fail-closed:

- `cornerKicks`: over and under;
- `shotsOnGoal` and `totalShots`: over only;
- scopes `home`, `away`, `total`;
- periods `1ST`, `2ND`, `ALL`.

Unsupported offer dimensions return `model_missing`; shots under is not
invented. Checkpoint provenance now survives forward bet, settlement, CLV,
and forward result documents. `/auto` and `/results` filter by checkpoint,
policy, model, stat, scope, period, direction, and league before presentation
grouping.

Current evidence:

- 103 backend feature/contract tests and the full 522-test V2 suite passed;
- 57 frontend tests, strict TypeScript, ESLint, and production build passed;
- real read-only scoring dry-run: 1,391 snapshots, 249 canonical markets, 402
  scores, 306 in-domain scores, 96 Brazil OOD scores excluded, 44 registered
  V2 selections across 17 target matches, and zero persistence attempts;
- automation contracts prove all scoring workflows use registry V2 and the
  settlement workflow orders settlement before CLV and result refresh;
- feature commit `1243355` is on `origin/main`, and Vercel production
  deployment `dpl_7yabEkwkhqdA2dkcQkeEph1DFUFa` is `Ready` with both
  read-only Python route depths and the production alias.

Status is `VERIFIED` for local implementation, read contract, dry-run scoring,
workflow configuration, Git delivery, and production deployment. It remains
`UNPROVEN` for the first hosted write-mode V2 journal row and a complete
future official-CLV settlement.

## Market Bias Bootstrap And Matchup Attachment On 2026-08-21

V2 now stores an independent, presentation-only measure of team performance
against comparable Unibet prematch main lines. It uses exact
team/league/stat/scope/period contexts, latest 12 observations, 45-day
recency weighting, Beta shrinkage, residual shrinkage, and strict prematch and
outcome-availability cutoffs. It does not alter matchup rankings, V6,
selection, ROI, or CLV.

The real write acceptance uncovered and fixed N+1 Cosmos reads plus two
nondeterministic legacy duplicate paths. The final adapter was run twice over
the full source before persistence and produced identical 16,528 observation
keys, source hashes, and prices. Production database evidence:

- first accepted run `6821fc78adbf42ff9e26bb994f527853`: 16,528 inserts,
  2,112 profile upserts, and zero mapping/timing/duplicate/hash failures;
- immediate rerun `6267c0b6141b41669ee400fcaf0f986a`: zero inserts,
  16,528 immutable replays, zero profile upserts, and zero conflicts;
- collections: 16,528 observations and 2,112 profiles with unique and context
  indexes; zero running refresh jobs;
- 2026-08-22 matchup rebuilds: 3,222 rows per output, including 1,080
  primary-stat rows and 520 exact bias attachments per output;
- fresh read API smoke: HTTP 200, 26 matches, 40 top cards, and typed camelCase
  summaries without private lineage fields;
- tests: 475 backend tests and 54 frontend tests passed; compileall, TypeScript,
  lint, production build, and diff check passed.

Status: `VERIFIED` for historical bootstrap, immutable replay, matchup/API/UI
attachment, and no ranking/model side effects. `UNPROVEN` for the first
scheduled completed-match `v2_forward` refresh. Missing exact contexts render
no bias rather than falling back or guessing.

## Matchup Form And Current-Fixture Ranking On 2026-08-14

Matchup cards now use a dedicated presentation-only form layer. It selects the
latest 12 valid home or away matches from each existing teamprofile history,
weights newer matches with a 45-day half-life, recalculates league ranks across
the full participating league, and leaves the model/training teamprofile values
unchanged. Each output records `rolling_12_weighted_45d`, window `12`, and the
45-day half-life. The frontend exposes this as `Form 12` on each card.

Two persistence defects were also repaired:

- date rebuilds now remove only stale entries after all current entries have
  been upserted, so an obsolete fixture cannot occupy a ranking place;
- dashboard reads rank current fixtures locally by score, so stale historical
  rank numbers cannot create missing positions in an otherwise valid response.

The first sequential write run was intentionally marked failed after the local
operator timeout interrupted it at 1,045/1,278 rows. Matchup persistence now
uses ordered-false Mongo bulk batches of 100 writes. The subsequent production
database rebuilds both succeeded:

- `matchups_score`: run `f739f98a6e7644c58f33987d02406d7b`, 1,278 unique rows;
- `matchups_league_avg`: run `4cb7278827e8419d851cf1496b098243`, 1,278 unique
  rows and 162 stale rows removed.

The read API returned exactly 20 OVER and 20 UNDER cards, each continuously
ranked 1-20. All 2,556 rebuilt rows carry the new form metadata. One of nine
fixtures, Real Racing Club - Villarreal, remains excluded because it lacks a
verified Real Racing Club home profile. This is correct fail-closed behavior,
not a ranking fallback.

The current Vercel alias was also queried directly after the database rebuild.
It returns the same 40 correctly ranked persisted cards, but its older deployed
read adapter does not yet serialize the new form fields, so the `Form 12` UI
tag is not live. Source commit `3786f64` is pushed to `main`; the Vercel
project has no Git connection and the local CLI account has no access to its
team scope, so publishing the new frontend adapter requires the existing Vercel
project deployment path rather than another database run.

Status: `PARTIAL`. V2 build, deduplication, current-fixture ranking, and form
metadata are database-verified. Old-repository output parity and the missing
home-profile mapping remain unproven. The Vercel `Form 12` presentation update
is also pending deployment.

## Vercel Read API Production Acceptance On 2026-08-14

The existing Vercel project `ullebets-prod-preview` now has sensitive,
Production-only `MONGODB_URI` and `MONGODB_DB=ullebets_v2` configuration. The
first deployment after configuration returned `503 read_api_database_unavailable`
because outer dotenv quotes were included in the URI. The secret was corrected
without changing source code, then redeployed as
`dpl_9TDuhSF4VsPA12fAfpA3YEoFk6VF`.

Verification against the production alias:

- `GET /api/v1/health` -> `200 {"status":"ok"}`
- `GET /api/v1/dashboard?date=2026-08-14` -> `200` with a valid empty response
  for the selected date
- `POST /api/v1/health` -> `405`
- Vercel reported no runtime errors for the redeployment

Status: `VERIFIED` for the deployed server-side, read-only V2 API connection.
This does not change the separate `UNPROVEN` live closing, CLV, and in-domain
V6 forward-result requirements.

## Production-Database Teamprofile And V6 Rerun On 2026-08-12

The two newly repaired paths were tested in write mode against `ullebets_v2`.
They are database-verified; hosted GitHub Actions evidence remains separate.

### Teamprofiles

The first complete run `cd422e097d584acfa1996caf05088a66` succeeded with:

- 585 canonical results
- 147,408 canonical stats
- 1,107 raw incidents
- 1,105 raw shotmaps
- 265 dated teamprofiles
- matched parity and `ok` audit/health reports

A read-only timing probe isolated the historical reader at `242.565 s` and
profile construction at `2.536 s`. The original upsert predicate used
unindexed `profile_key`, even though `teamprofiles` has the unique index
`team_key + profile_date + match_type`. That caused the first full write run
to take about 15 minutes.

Persistence now uses the indexed unique identity. The complete idempotent
rerun `62deff7b22704dc5a229ee6b39101100` succeeded with all 265 profiles and
no duplicate inserts. Its post-read write stage took `123.665 s`; the full
local command took `407.641 s`, dominated by the large historical read.

### V6 Score Archive

The first exact production scorer command failed closed on run
`6b5e26b5a61c491494ef7eda8a6a5ec7`. The conflicting stored/rebuilt score had
the same raw inputs, artifact, policy, and semantic feature values; only
`market_anchor_lambda` differed by about `4e-16`. Its derived feature
fingerprint consequently changed and the earlier equivalence check rejected
the row.

The repair validates each row's feature fingerprint but excludes that derived
hash from semantic equality. It compares actual nested feature values with an
absolute `1e-12` tolerance, never overwrites the frozen document, and still
fails for a material feature change or corrupted fingerprint.

Rerun `33145640a5c54676b20bd6716ca74dbe` then succeeded:

- valid prematch snapshots read: `308`
- canonical market rows: `60`
- frozen V6 score rows: `105`
- inserted/existing/conflicts: `0 / 105 / 0`
- precision-equivalent existing scores: `49`
- in-domain/out-of-domain scores: `42 / 63`
- registered forward bets created: `0`

The 63 Brazilian rows remain archived diagnostics and are excluded from
selection. The 42 La Liga rows are in-domain scores, but V6 remains
score-only and produced no forward bets.

Status: `PARTIAL`. V2 database behavior is proven in write mode. A hosted
`main` run of the two relevant GitHub Actions jobs is still required to prove
workflow environment and automation parity.

## Cosmos Teamprofile And V6 Score-Idempotency Repair On 2026-08-12

Two production defects were reproduced and repaired without changing model
features, artifact, policy, or any frozen document:

- the profile build previously sent all 579 historical `match_key` values in
  one `match_stats_canonical` `$in` query; the real read-only Cosmos query
  failed with `ExceededTimeLimit`;
- a V6 rerun encountered a stored immutable score whose probability differed
  by `5.55e-17` and EV by `1.11e-16`, despite identical inputs, features,
  artifact, and policy. Exact JSON fingerprinting treated that harmless
  machine precision variation as a conflict.

The repaired reader applies `source_date < profile_date` in Cosmos, projects
only the fields needed by teamprofiles, batches stats/incidents/shotmaps in
50-match requests, and indexes results in memory. V6 persistence validates
the derived feature fingerprint, then accepts only raw feature values with
numeric variation no greater than `1e-12`; it increments
`precision_equivalent_existing`, never updates the stored score, and still
fails closed for material differences or a corrupted stored fingerprint.

Verification:

- regression tests failed before implementation: `3 failed, 7 passed`;
- teamprofile and forward-score regression suite: `10/10` passed;
- full V2 suite: `415/415` passed;
- `python -m compileall -q src` and `git diff --check` passed.

Status: `PARTIAL`. The failure modes are code- and database-read-reproduced,
but the next full hosted teamprofile build and the next scheduled V6 rerun
must confirm the repaired production executions.

## Capture-Triggered V6 Scoring On 2026-08-08

V6 scoring is now part of the two production capture workflows, not an
independent ten-minute schedule. `v2-odds-scheduler.yml` parses the finished
checkpoint capture JSON and runs the frozen V6 command only when the actual
persisted count `market_snapshot_upserts > 0`; it owns T-3D, T-2D, T-1D, and
T-2H. The same guarded V6 command runs in `run-unibet-closing.yml` after a
T-30/T-10 capture. Empty windows, duplicate/retry writes, and manual dry-runs
skip the model dependency install and scorer.

`ev-shadow-forward.yml` is now a manual recovery workflow only. This removes
the former scheduled cadence of minutes `5,15,25,35,45,55`, which was neither
an exact runtime guarantee nor necessary when no new odds existed.

The implementation does not change the V6 artifact, features, domain filter,
selection policy, or immutable score/forward-bet contract. A later snapshot
can add a new immutable score but cannot rewrite an existing prediction.

Local verification:

- capture-to-score contract test was observed failing before implementation
  and passing after it;
- automation contract suite: `20/20` passed;
- checkpoint, closing, score, prediction, and automation subset: `53/53`
  passed;
- persistence summaries expose actual snapshot upserts: `2/2` passed;
- checkpoint, closing, score, prediction, and automation subset after the
  persistence guard: `55/55` passed;
- full V2 suite: `413/413` passed;
- all three changed workflows parsed as YAML and `git diff --check` passed.
- hosted scheduler smoke
  [`31274563877`](https://github.com/ulle73/ullebets-prod/actions/runs/31274563877)
  passed on `main@4c19ea7`, built `744` dry-run snapshot rows for nine due
  targets with zero source errors, and correctly skipped V6 without writes.

This is `PARTIAL`, not live proof. The next hosted write-mode due checkpoint
must show a successful capture followed by a successful V6 score job before
kickoff. Until then, the real T-30/T-10 closing and CLV lifecycle remains
unproven.

## Closing Runner Repair On 2026-08-08

The closing runner defect identified earlier on 8 August was repaired in
`main@030a401`. The reusable `v2-python-job.yml` runner now exports the
repository `src/` directory through `PYTHONPATH` before rendering any command.
This keeps the lean dependency profile while making its own V2 package
available.

Verification evidence:

- targeted workflow tests: `21/21` passed
- full V2 suite: `409/409` passed
- hosted smoke run
  [`31273361050`](https://github.com/ulle73/ullebets-prod/actions/runs/31273361050)
  completed successfully on `main@030a401`
- the hosted run reached `capture_closing_snapshots.py`, reported zero errors,
  and showed the deployed `PYTHONPATH` value in its environment

The smoke run intentionally used `dry_run=true`. It ran at
`2026-08-08T19:01Z`, after Grêmio - São Paulo kickoff; the next fixture was
at `21:30Z` and not yet in a T-30/T-10 window, so it correctly returned zero
due targets and made no writes. The repair proves the runner is no longer
blocking capture; it does not prove T-30, T-10, closing lines, or CLV.

## Live Checkpoint And Closing Audit On 2026-08-08

A read-only audit at `2026-08-08T18:51:10Z` confirmed that the ordinary
production checkpoint chain is now live and writing valid prematch data:

- T-3D: `678` valid rows across 10 matches, first/last capture
  `2026-08-05T10:00:18Z` / `2026-08-06T12:22:00Z`
- T-2D: `799` valid rows across 10 matches, first/last capture
  `2026-08-06T07:06:52Z` / `2026-08-07T11:11:14Z`
- T-1D: `817` valid rows across 10 matches, first/last capture
  `2026-08-07T07:47:04Z` / `2026-08-08T10:54:33Z`
- T-2H: `242` valid rows across three matches, first/last capture
  `2026-08-08T13:16:09Z` / `2026-08-08T17:49:58Z`

The latest successful T-2H run was `f78ab0b86429406e998a9eb4226e7247` at
`2026-08-08T17:50Z`: one due match, two raw Kambi documents, 85 snapshots,
and zero errors. The current-cycle valid snapshot-key duplicate audit returned
zero groups. The latest raw Kambi payload is timestamped
`2026-08-08T17:49:58Z`.

The separate closing path is currently failed. The hosted active workflow run
[`31271905639`](https://github.com/ulle73/ullebets-prod/actions/runs/31271905639)
started at `2026-08-08T18:25Z` during the first fixture's T-30 window, but
exited before the capture command with:

```text
ModuleNotFoundError: No module named 'ullebets_v2'
```

`v2-python-job.yml` installs only `pymongo` for its `lean` profile, then
imports `ullebets_v2.automation` to render the command. It neither installs
the project package nor exposes `src` on `PYTHONPATH`. The bug is therefore
in reusable runner setup, not the Kambi source, the odds normalizer, or
prematch timing validation.

At the audit point, eight minutes before Grêmio - São Paulo kickoff,
`closing_lines = 0`; CLV consisted of `860` `missing_closing_line` rows and
three `invalid_snapshot_timing` rows. No T-30/T-10, valid closing line, or
closing-based CLV claim is accepted until the runner is repaired and a future
live window persists it.

## Current Checkpoint Evidence On 2026-08-04

A read-only production audit at `2026-08-04T21:33:37Z` found 10 future
canonical Brasileirão Série A fixtures for 8-9 August. The next fixture is
Grêmio - São Paulo at `2026-08-08T19:00:00Z`.

Persisted checkpoint evidence is:

- T-2D: `161` valid prematch rows across two matches
- T-1D: `244` valid prematch rows across three matches
- T-3D: no persisted row
- T-2H: no persisted row
- T-30: no persisted row
- T-10: no valid persisted row; all `248` historical rows are marked invalid

The latest raw odds write is still `2026-07-30T00:28:39.392Z`. This is not a
current failure: at the latest scheduled checkpoint job all 10 fixtures were
outside every due checkpoint window. Job run
`5869cacebf294545bbf16b9dc5dde5a0`, corresponding to hosted Actions run
`30949327663`, completed `succeeded` with 10 target matches, zero due matches,
zero source errors, and audit/health status `ok`.

A current source dry-run independently linked all `10/10` fixtures to Kambi,
returned `11` raw payload documents and `607` normalized offers, and reported
zero source or mapping errors. The source and match linkage are therefore
currently healthy.

The first new T-3D opportunity opens at `2026-08-05T07:00:00Z`, when the first
fixture enters the configured 60-84 hour window. Closing lines remain at zero,
so T-3D, T-2H, T-30, T-10, closing-line materialization, and official CLV must
remain unproven until their real scheduled windows persist valid evidence.

## Production Runtime And Latest-Match Ingest On 2026-08-01

The latest scheduled `V2 EV Shadow Forward` GitHub Actions run
`30668128118` failed on `main@69e6455` before any scoring completed.

- Frozen manifests require `numpy 2.2.2` and `pandas 2.2.3`.
- The full dependency profile installed `numpy 2.5.1` and `pandas 3.0.5`
  because the project dependency bounds do not pin those packages.
- Runtime validation correctly rejected all four scorer invocations.
- `pyproject.toml` now pins the exact manifest-compatible versions and a
  regression contract prevents drift.
- The shared workflow runner removes command-template `--dry-run` flags when
  scheduled execution uses its default false input. Production was not forced
  to dry-run; manual dry-run remains intentionally available.

The local full suite passes `394/394`. The fix was deployed on `main@f188c52`;
hosted production write-mode run `30672830616` passed V3, V4, V5, and V6 with
`status=ok`. All four returned zero canonical markets because no current
upcoming model-ready markets existed. That is a valid empty production result,
not a dry-run or source failure.

The next scheduled odds run exposed a separate orchestration defect: GitHub
returned HTTP `403` when the scheduler tried to disable an already-disabled
closing workflow, aborting before checkpoint capture. `main@cdb83b9` now reads
the workflow state before mutation. Hosted production write-mode run
`30673575119` treated `disabled_manually` as a successful no-op, reached the
checkpoint job, and persisted succeeded job run
`0e4b84a64e4f44eb82412b5ba0753ed8`. There were zero due matches and zero
errors because no fixture was inside the current window. Automatic enablement,
T-10 capture, closing-line materialization, and CLV still require the next real
fixture window.

Production checkpoint policy was then hardened for GitHub Actions timing.
The hourly scheduler now captures T-2H in addition to T-3D/T-2D/T-1D. The
five-minute closing workflow owns both a broad T-30 fallback window (15-50
minutes before kickoff) and the existing T-10 window (5-15 minutes). T-30
closing rows are labeled `t30_fallback`; only T-10 is official closing CLV and
eligible for model promotion metrics. A later T-10 replaces T-30 as the latest
canonical closing observation. Older T-2H/T-1D rows cannot be promoted to a
closing line when both near-close captures are absent. Targeted tests pass
`61/61`, the full suite passes `402/402`, and the current database preflight
returned a valid empty result because no future fixture existed in the source
horizon. Hosted production write-mode scheduler run `30674861895` also
succeeded with parity/audit/health reports, zero errors, and zero due targets;
the closing watcher remained safely disabled. The first real
T-2H/T-30/T-10 lifecycle remains unproven.

The latest completed match dates for all followed leagues were then fetched in
production write mode. Fixture ingest stored 181 canonical matches for 16-24
May and 6 for 31 July, with zero unmatched identities. Latest-date enrichment
coverage is:

- A-League Men: 1 match on 23 May
- Bundesliga: 1 match on source date 22 May
- Ligue 1: 8 matches on source date 18 May
- Premier League: 10 matches on 24 May
- La Liga: 10 matches on 24 May
- Serie A: 9 matches on 24 May
- Brasileirão Série A: 2 matches on 31 July

All 41 matches have raw statistics, incidents, shotmaps, results, canonical
results with scores, and exactly 27 primary stat rows. The 1,107 primary rows
have zero duplicate keys and zero missing actual values.

A current read-only verification of the original-style backtest replacement
then processed Grêmio - São Paulo from the live fixture database. Kambi event
linkage succeeded `1/1`, `59` normalized offers produced `108` directed legacy
EV line rows, and source/model errors were both zero. Parity, audit, and health
were `matched`/`ok`. This proves the current `odds -> line sides -> legacy EV`
mechanism, not profitability and not V6 behavior. The next non-empty scheduled
write run and canonical settlement remain unproven.

The first 39-match write exposed a CosmosDB timeout because 10,085 canonical
stat upserts were sent as one bulk command. Raw payloads and canonical results
had already persisted. Enrichment persistence now uses 200-operation batches,
and job `b0d64776e3704278a0754fa1511cc1b0` rebuilt the canonical stats from raw
and finished `succeeded`. A redundant retry was terminated after the primary
job succeeded and its job row was explicitly marked failed for auditability.

## V6 Forward Policy Activation On 2026-08-01

The production scorer is now configured to run only the frozen V6 artifact.
V3 no longer creates the authoritative forward rows, and V4/V5 are no longer
rescored by the production forward workflow. The old JS EV snapshot builder
has been removed from its daily schedule and retained only as a manual parity
replay.

V5's frozen score-policy registry was not changed. A separate immutable
`forward_policy_registry_v1` registers the exact historically selected V6
policy: corners only, away/total scopes, EV strictly above `7.5%` and below
`25%`. In-domain qualifying scores are materialized to `forward_bets` with a
stable policy id/fingerprint and direct source-score provenance. Existing
policy/match selections are excluded on rerun.

Verification evidence:

- full suite: `408/408` passed
- V2 healthcheck: `overall_status=ok`
- historical prematch replay: `319` snapshots, `30` canonical markets and
  `48` V6 side scores
- domain audit: `48/48` Brazil scores correctly excluded and `0` selections
- current real-time run: valid empty result because no future persisted market
  snapshots were available at execution time
- index bootstrap: all 36 collection plans applied; the new
  `selection_policy_match` index exists with zero repaired/deleted documents

No model score or prediction write was made during these checks; only index
metadata changed. A real immutable V6 selection from A-League Men, Bundesliga,
La Liga, Ligue 1, Premier League, or Serie A remains unproven until one of
those leagues has a qualifying prematch market.

Deployment is now verified on `main@f607338`. Hosted write-mode run
`30717651924` succeeded with `dry_run=false`, loaded only V6,
`forward_policy_registry_v1`, and `v6_corners_away_total_forward_v1`. It read
zero future snapshots and wrote zero scores/selections, so the deployment and
empty-path behavior are proven while a non-empty in-domain production path
remains unproven.

## Critical Timing Correction On 2026-07-30

A stricter forward audit found four production capture job runs that had used
simulated future timestamps. The repair:

- detected `497` affected derived `market_snapshots`
- marked all `497` as `invalid_for_model`
- changed `0` raw Kambi payloads
- removed `251` stale closing rows that had no valid prematch source left
- reset `444` affected CLV rows to `missing_closing_line`
- changed `0` rows on an immediate second repair run
- reduced the first EV model freeze from `8` stored rows to `5` valid forward
  evidence rows; `3` immutable rows remain stored but are excluded

A real T-1D capture then succeeded for two future matches:

- `2/2` events linked
- `158` market snapshots stored
- `0` post-start rows
- `0` fetch errors

Production writes now reject simulated `--now` values, invalid snapshots do not
block future checkpoint capture, and model scoring requires
`snapshot_time <= prediction_created_at < match_start_time`.

## Live Post-Match Verification On 2026-07-30

Only the remaining post-match chain was rerun for the current Brazil window.
The full prematch chain was not repeated.

### Finished-match enrichment

Four matches that had passed kickoff were refreshed from the live source:

- Mirassol - Remo: `2-1`
- Internacional - Flamengo: `1-1`
- Vitoria - Palmeiras: `0-4`
- Fluminense - Bahia: `0-0`

For every match:

- raw statistics present
- raw incidents present
- raw shotmap present
- raw result present
- canonical result present
- `27` canonical primary stat rows present:
  - corners, total shots, and shots on goal
  - ALL, 1ST, and 2ND
  - home, away, and total

The first live attempt exposed an uncaught network `TimeoutError` that aborted
the whole enrichment date. The transport now normalizes that timeout into the
existing source fallback path. The regression test and the repeated live ingest
both pass.

### Forward timing and settlement correction

The first settlement run incorrectly graded three immutable EV rows whose odds
snapshot was created after the prediction freeze:

- odds snapshot: `2026-07-30T00:25:00Z`
- prediction freeze: `2026-07-29T23:53:20.776Z`
- kickoff: `2026-07-30T00:30:00Z`

The shared forward timing contract now enforces:

`odds_snapshot_time <= prediction_created_at < match_start_time`

Settlement, CLV, and forward results all use the same contract. Invalid source
rows remain immutable for audit, while derived outputs set:

- settlement status `invalid_timing`
- forward result status `excluded`
- no win/loss
- no PnL or ROI
- no CLV

Repeated live result:

- forward rows: `67`
- valid settled rows: `33`
- open rows: `31`
- timing-excluded rows: `3`
- valid settled outcomes: `22` wins and `11` losses

The `33` settled rows include ordinary daily/combo/user exports and repeated
operational selections. Their aggregate ROI is not model evidence and must not
be reported as the EV model's forward ROI.

EV shadow model only:

- stored forward rows: `8`
- valid but still open: `5`
- timing-excluded: `3`
- valid settled: `0`
- proven forward ROI: none yet

### T-10 and CLV status

No real T-10 closing capture is proven for the finished matches. The `248`
stored T-10 snapshots for those matches were produced by earlier
future-timestamp simulations and are correctly marked `invalid_for_model`.
There are currently `0` valid closing lines for the current six-match Brazil
set, so CLV remains unavailable.

The current live acceptance baseline was refreshed at
`2026-07-30T12:34:10Z`:

- six future Brazil fixtures are present
- four kick off at `18:00Z`, one at `22:30Z`, and one at `00:30Z`
- target fixtures have `319` valid T-2D/T-1D snapshots
- target fixtures have `31` forward bets
- target fixtures have `0` closing lines
- target fixtures have `31` CLV rows with status `missing_closing_line`
- a real-time dry-run before the window selected `0` due matches, as expected

The closing and CLV dry-run paths now read current V2 history without writing,
and the targeted checkpoint/closing/CLV/safety suite passes `27/27`.

The automation gap was concrete: `run-unibet-closing.yml`, which materializes
`closing_lines`, had no deployed schedule during this window. The deployed
replacement is match-aware: an hourly scheduler captures T-3D/T-2D/T-1D and
enables the five-minute T-10 watcher only while an uncaptured fixture is within
two hours. The next real T-10 window must prove:

- a live due target is selected
- raw Kambi data is fetched
- valid prematch market snapshots are stored
- closing lines are materialized
- CLV can be refreshed from those lines

Runtime correction at `2026-07-30T23:39Z`: five of the six listed fixture
windows had passed with `0` valid T-10 snapshots and `0` closing lines. The
heartbeat was changed to five-minute polling for the final fixture,
`sofascore:15235409`, whose kickoff is `2026-07-31T00:30Z`.

Final correction at `2026-07-31T05:48Z`: the final heartbeat was also
delivered after kickoff. The current window ended with:

- `0` valid T-10 snapshots
- `0` closing lines
- `0` tracked CLV rows
- `0` duplicate snapshot-key groups
- `64` CLV rows missing a closing line
- `3` CLV rows excluded for invalid snapshot timing

The post-match path was completed:

- `Coritiba 0-1 Cruzeiro`
- raw statistics, incidents, shotmap, and result present
- canonical result present
- `252` canonical stats, including `27` primary-stat period/scope rows
- `9/9` match forward rows settled: 4 wins and 5 losses
- all current forward rows: `64` settled and `3` timing-excluded
- settled outcomes: `26` wins and `38` losses

The five timing-valid EV shadow rows are now settled at 2 wins, 3 losses, and
`-1.17` units (`-23.40%`). These are Brazilian out-of-domain diagnostics and
must not be reported as V6 model evidence.

The operational cause of the missing closing data is now explicit: the
five-minute workflow schedule existed only in the dirty local branch, while
the thread heartbeat arrived after the narrow live windows. The next
acceptance attempt requires a deployed scheduler before selecting a target.

## Goal

Document exactly:

- what has already been tested
- what currently works
- what does not work yet
- what is not actually failing, but cannot be fully proven yet because the time window has not arrived
- which jobs should be rerun next, and only when

## Verified On 2026-07-28

The following was tested against the real `ullebets_v2` database in write mode.

### Foundation / Safety

- `MONGODB_DB` resolved to `ullebets_v2`
- `.codegraph/` exists in the repo
- V2 is isolated from `app` and `ullebets_unibet`
- healthcheck confirmed distinct DB roles and no collection-name drift

### Support Data

Command area:

- `sync_support_data.py`

Latest verified result:

- `support_sources = 4`
- `support_leagues = 7`
- `support_teams = 128`
- `support_rankings = 6`
- audit `ok`
- health `ok`

### Live Fixtures

Command area:

- `ingest_fixtures_window.py --mode live --start-date 2026-07-25 --end-date 2026-07-30`

Latest verified result:

- processed dates: `2026-07-25` through `2026-07-30`
- `raw_docs = 48`
- `canonical_docs = 34`
- `source_link_docs = 34`
- no missing dates

Observed per-date canonical coverage:

- `2026-07-25`: `3`
- `2026-07-26`: `10`
- `2026-07-27`: `7`
- `2026-07-28`: `0`
- `2026-07-29`: `4`
- `2026-07-30`: `10`

Note:

- `2026-07-28` returned zero fixtures in that run. That is not treated as a system failure by itself.

### Live Match Enrichment

Command area:

- `ingest_match_enrichment.py --mode live --fixture-source db --start-date 2026-07-25 --end-date 2026-07-27`

Latest verified result:

- `target_matches = 10`
- `matched_targets = 10`
- `raw_match_statistics = 10`
- `raw_incidents = 10`
- `raw_shotmaps = 10`
- `raw_results = 10`
- `match_results_canonical = 10`
- `match_stats_canonical = 2478`
- audit `ok`

Interpretation:

- live result/statistics/incidents/shotmap ingestion worked for the tested finished-match window

### Teamprofiles

Command area:

- `build_teamprofiles.py --profile-date 2026-07-28`

Latest verified result:

- `teamprofiles = 264`
- `match_results = 530`
- `match_stats = 134276`
- audit `ok`
- health `ok`

### Upcoming Odds / Prematch Modeling Chain

Target window tested:

- `2026-07-29`
- `2026-07-30`

Selection summary:

- `available_target_match_count = 6`
- `selected_target_match_count = 6`
- next fixture start at test time: `2026-07-29T22:30:00Z`

#### Odds Ingest

- `ingest_unibet_odds.py --mode fixture-db`
- `matched_events = 6 / 6`
- `raw_docs = 7`
- `event_links = 6`
- `market_offers = 499`
- errors: `0`
- audit `ok`

#### Model Snapshots

- `build_model_snapshots.py --mode fixture-db --snapshot-mode forward`
- `matched_events = 6 / 6`
- `model_snapshots = 855`
- `oracle_error_count = 0`
- `invalid_for_model_count = 0`
- `model_read_source = v2_database`
- audit `ok`

#### Auto Analysis

- `run_auto_analysis.py --mode fixture-db --snapshot-source db`
- `model_snapshots = 865`
- `analysis_candidates = 865`
- `qualifying_candidates = 33`
- `analysis_shortlist = 4`
- `oracle_error_count = 0`
- audit `ok`

Note:

- `build_ai_bet_exports` was hardened so it only reuses DB analysis if the stored analysis actually covers the requested target match set. This prevents stale/incomplete reuse during concurrent writes.

#### Prediction Exports / Forward Bets

`user-daily`

- `analysis_source = db`
- `analysis_candidates = 865`
- `source_candidates = 4`
- `prediction_exports = 4`
- `forward_bets = 4`

`combos`

- `analysis_source = db`
- `analysis_candidates = 865`
- `source_candidates = 33`
- `prediction_exports = 20`
- `forward_bets = 40`

`user-closing`

- `analysis_source = db`
- `analysis_candidates = 865`
- `source_candidates = 4`
- `prediction_exports = 4`
- `forward_bets = 4`

Interpretation:

- the prematch V2 chain works end-to-end now:
  - fixtures
  - odds ingest
  - normalized offers
  - model snapshots
  - auto analysis
  - immutable forward bet creation

### Post-Match / Tracking Jobs

The jobs below were executed successfully at the process level, but the currently tested rows are still open and therefore not fully settled yet.

#### Forward Bet Settlement

- `settle_forward_bets.py`
- `forward_bets = 59`
- `settled_bets = 59`
- status bucket: `pending_result = 59`
- audit `ok`

Interpretation:

- the settlement job runs
- the currently selected bets are still pending
- this does not prove win/loss/push correctness yet

#### CLV Tracking

- `refresh_clv_tracking.py`
- `tracked_bets = 59`
- `closing_lines = 251`
- `tracked = 20`
- `missing_closing_line = 39`
- audit `ok`

Interpretation:

- the CLV refresh job runs
- some bets already have enough line history to track
- many do not yet have closing lines, which is expected before the closing window has actually been captured

#### Forward Results

- `refresh_forward_results.py`
- `forward_results = 59`
- status bucket: `open = 59`
- timing bucket: `prematch_valid = 59`
- settlement bucket: `pending_result = 59`
- audit `warn`

Why the audit is `warn`:

- no bets are settled yet
- many rows still lack closing lines

This is not a backend crash. It is an expected lifecycle state for open bets.

## What Works Right Now

These areas are already verified and do not need full retesting unless the relevant code changes:

- DB safety guard
- support-data sync
- live fixture ingest
- live match enrichment
- teamprofile rebuild
- Unibet/Kambi odds ingest
- normalized market offers
- model snapshot generation
- DB-backed auto analysis
- immutable prediction export creation
- immutable forward bet creation
- post-match maintenance jobs can run without failing

## What Is Not Proven Yet

These are not currently broken; they are time-window dependent and were not yet due in the last acceptance run.

### Odds Checkpoints

Latest result:

- `due_matches = 0`
- `market_snapshots = 0`
- audit finding: `no_due_targets_in_requested_window`

Interpretation:

- no checkpoint rows were due at the exact time of test
- this is not evidence of a defect

### Closing Capture

Latest result:

- `due_matches = 0`
- `closing_lines = 0`
- audit finding: `no_due_closing_targets`

Interpretation:

- the closing job did not fail
- the time window simply had not opened yet

### Real Settlement / ROI / Win-Loss-Push

Not fully proven yet because:

- current forward bets were still pre-match or not yet fully enriched with finished results
- `settled_count = 0` in the latest forward-results audit

## Known Weak Area

### Source Connectivity Audit

Latest audit:

- `status = warn`
- `endpoint_count = 58`
- `success_count = 17`
- `empty_count = 2`
- `failure_count = 39`

Findings:

- `empty_payloads_detected`
- `failed_endpoint_requests`

Important nuance:

- this audit is weaker than it should be
- despite that, the actual live jobs for fixtures, enrichment and odds succeeded in the verified windows above
- so the remaining risk is source stability/coverage, not total backend non-function

## Do Not Retest These Unless Something Changed

Skip full reruns of these unless:

- code in the relevant subsystem changed
- env vars or source credentials changed
- source mappings changed
- a parity/audit regression appears in later runs

Safe to skip for now:

- `sync_support_data.py`
- `ingest_fixtures_window.py` for the same already-tested date window
- `ingest_match_enrichment.py` for `2026-07-26` and `2026-07-27`
- `build_teamprofiles.py`
- `ingest_unibet_odds.py` for `2026-07-29` and `2026-07-30`
- `build_model_snapshots.py` for that same prematch window
- `run_auto_analysis.py` for that same prematch window
- `build_ai_bet_exports.py` for the already-tested `user-daily`, `combos` and `user-closing` runs

## What To Test Next, And Only When

### 1. Checkpoint Capture

Rerun only when a checkpoint window is actually due for the next fixtures.

Focus:

- `capture_odds_checkpoints.py`

Reason:

- last run had zero due matches

### 2. Closing Capture

Rerun only when the first match enters the `T_MINUS_10M` window.

Focus:

- `capture_closing_snapshots.py`

Reason:

- last run had zero due matches

### 3. Finished-Match Settlement

Rerun only after the current forward-bet matches are finished and match results/statistics have been ingested.

Focus:

- `ingest_match_enrichment.py` for the finished match date
- `settle_forward_bets.py`
- `refresh_clv_tracking.py`
- `refresh_forward_results.py`

Reason:

- latest forward results are still open and pending

### 4. Connectivity Audit Triage

Rerun and diagnose only if:

- source failures start affecting fixture/enrichment/odds jobs
- or if the endpoint matrix is explicitly being hardened

Focus:

- `audit_source_connectivity.py`

## Current Collection Snapshot

Read from `ullebets_v2` after the latest acceptance run:

- `support_sources = 5`
- `support_leagues = 7`
- `support_teams = 128`
- `support_rankings = 6`
- `raw_fixtures = 245`
- `fixtures_canonical = 600`
- `raw_match_statistics = 1041`
- `raw_incidents = 1046`
- `raw_shotmaps = 1050`
- `raw_results = 1038`
- `match_stats_canonical = 134276`
- `match_results_canonical = 530`
- `teamprofiles = 1849`
- `raw_odds_kambi = 395`
- `unibet_event_links = 246`
- `market_offers = 23314`
- `market_snapshots = 744`
- `model_snapshots = 1235`
- `analysis_runs = 4`
- `analysis_candidates = 2099`
- `prediction_exports = 36`
- `forward_bets = 59`
- `closing_lines = 251`
- `clv_tracking = 855`
- `settled_bets = 867`
- `forward_results = 59`

## Stored Snapshot

Machine-readable snapshot saved here:

- [backend-verification-status-2026-07-28.json](C:/Users/ryd/.config/superpowers/worktrees/ullebets-prod/feature-ullebets-v2-backend/data/v2/reports/backend-verification-status-2026-07-28.json)

## EV Timing Repair And Score Archive Update

Verified on `2026-07-30` after the snapshot-timing repair:

- `market_snapshots = 902`
- invalid simulated derived snapshots = `497`
- valid snapshots = `405`
- `closing_lines = 0` after removing closings derived from simulated time
- affected CLV rows reset to `missing_closing_line = 444`
- V2 frozen predictions = `8`, of which `5` are valid and `3` are excluded
- V3 forward bets = `0`
- V3 immutable all-side scores = `48`
- V4 immutable all-side scores = `48`
- V4 forward bets = `0` by enforced score-only policy

Both V3 and V4 score archives contain `48/48` valid rows with:

- `0` missing or invalid timing rows
- `0` outcome fields
- `0` duplicate score keys
- `0` fingerprint mismatches
- `0` rows invalid for policy evaluation

The first live scorer run inserted all `48` scores. The immediate rerun
inserted `0`, recognized `48` existing rows, and produced `0` conflicts.
No new V3 bet was created because both scored matches already had a valid
frozen prediction under the earlier immutable model identity.

The V4 manifest rejects write-mode scoring unless `--score-only` is supplied.
Its first live run inserted `48` scores and the immediate rerun found all `48`
as existing with `0` conflicts. The shared policy evaluator reports `30`
common scored markets, `6` pending V3 selections, and `1` pending V4
selection. No model has settled forward score evidence yet, so forward ROI
remains unavailable.

An artifact-derived domain audit subsequently found that all `96` score rows
belong to `Brasileirão Série A`, while both fitted models only support
A-League Men, Bundesliga, La Liga, Ligue 1, Premier League, and Serie A.
Because the encoder otherwise ignores unknown categories, the evaluator now
fails closed:

- archived scores retained = `96`
- in-domain scores = `0`
- out-of-domain scores excluded = `96`
- selections eligible for ROI/CLV/promotion = `0`

The earlier `6` V3 and `1` V4 values remain a record of the raw frozen policy
output, not valid promotion evidence. Brazilian predictions require Brazilian
historical training coverage or a separately registered exploratory domain.

The forward score-policy registry was frozen before settlement with:

- registry id = `score_policy_registry_v2`
- policies = `10`
- registry fingerprint =
  `c37bcd332b2d33db51a0595e23819514309fdad40efce9dfdb8f2e0c52c7b818`
- V3 primary pending selections = `6`
- V3 corners pending selections = `5`
- V3 shots-on-goal pending selections = `1`
- V3 total-shots pending selections = `0`
- V4 all-target/corners pending selections = `1`

The historical falsification audit leaves both candidates
`not_confirmed`. V3 remains positive after removing every individual league
or test window. V4 falls to `-0.78%` ROI when Serie A is removed. No policy
promotion is permitted from these inspected outcomes.

The registered-policy historical diagnostic tested all ten policies as one
family. The only policy passing its mechanical historical gate was:

- policy = `v4_corners_away_total_challenger`
- bets/matches = `121/77`
- ROI = `+28.54%`
- clustered 95% interval = `+8.23%` to `+47.52%`
- 47-test adjusted p-value = `0.0376`
- every leave-one-league/window result positive = `true`

The separately frozen one-bet-per-match policy retained `77` bets at
`+27.61%` ROI with a positive `+5.96%` clustered lower bound. Its corrected
p-value was `0.2021`, so it remains diagnostic despite proving that stacked
match exposure is not the source of the observed return.

This remains `score_only_exploratory`. The scope filter came from inspected
history, so the result is hypothesis-generating and cannot authorize real
stakes or model promotion. Its current forward selection is still pending.

Promotion-gate automation is active for all ten policies:

- source model audit status = `ok` for V3 and V4
- settled policy selections = `0`
- CLV coverage = `0%` because no valid closing lines currently exist
- promotion status = `insufficient_evidence`
- registry fingerprint covers policies, exposure cap, and promotion gates

The evaluator will not mark a policy eligible until all frozen sample,
clustered inference, CLV, multiple-comparison, and audit requirements pass.

The prequential scope-router audit also completed:

- variants = `25`
- total comparison family = `72`
- future rows used = `0`
- window-order violations = `0`
- central 10-bet/positive-prior-ROI rule = `86` bets, `+35.50%` ROI
- clustered 95% interval = `+14.22%` to `+54.80%`
- adjusted p-value = `0.0101`
- one-bet-per-match sensitivity = `53` bets, `+34.11%` ROI

This is temporal robustness evidence only. The router is not allowed to
rewrite the frozen forward policy registry from historical outcomes.

The exact scope-identity placebo then enumerated all `46,656` label sequences:

- observed router ROI = `+35.50%`
- null mean ROI = `+25.82%`
- null 95% range = `+15.14%` to `+39.02%`
- exact one-sided p-value = `0.0790`
- 73-test adjusted p-value = `1.0`
- delayed all-scope baseline = `106` bets at `+26.42%` ROI

Conclusion: later-window V4 corner strength is real historical behavior, but
away/total scope identity is not statistically isolated. The scope policy
remains forward-only evidence.

The same-policy V3/V4 attribution reports:

- V3 = `228` bets at `+14.37%` ROI
- V4 = `121` bets at `+28.54%` ROI
- paired V4 minus V3 = `+14.17` percentage points
- paired 95% interval = `-0.64` to `+28.81` points
- probability V4 superior = `97.01%`
- 74-test adjusted p-value = `1.0`
- V4-only selections = `17` at `+51.94%` ROI

V4 is probably more selective, but its incremental sample and corrected
evidence remain insufficient for promotion.

V4 threshold sensitivity covered `24` variants and a `98`-test total family:

- 5%-20% gate = `241` bets at `+17.49%`
- 6.5%-20% gate = `163` bets at `+25.34%`
- frozen 7.5%-25% gate = `121` bets at `+28.54%`
- 9%-25% gate = `77` bets at `+15.53%`, interval crosses zero
- 12.5%-25% gate = `24` bets at `-14.25%`

The frozen lower/upper EV bounds remain unchanged. Extreme model EV is treated
as extrapolation risk, not stronger evidence.

V4 selection negative controls used a `101`-test total family:

- always under = `2,230` bets at `-3.10%`
- always over = `2,230` bets at `-12.50%`
- market favorite/longshot = `-8.05%` / `-7.31%`
- matched-composition random adjusted p = `0.0162`
- random side in same market adjusted p = `0.0071`
- random market in same selected match adjusted p = `0.0384`

The exact V4 line/side selection adds historical information beyond generic
direction, match, and composition effects. This is still not a substitute for
untouched forward settlement.

## V5 Fixed Ensemble Update

Experiments 046-051 tested stat-specific models, league removal, market-anchor
features, stat balancing, fixed V3/V4 ensembles, and conservative consensus.
Negative results were retained:

- stat-specific corners = `199` bets at `-0.26%`
- league-agnostic nested model = `+0.94%`, only `3/6` positive windows
- market-anchor feature variants = `+6.57%` to `+10.82%`
- stat-balanced variants = `+0.48%` to `+7.13%`

The retained V5 score-only challenger uses fixed `75% V3 / 25% V4`
probabilities:

- historical bets/matches = `279/143`
- historical ROI = `+13.05%`
- positive outer windows = `6/6`
- clustered 95% interval = `-0.11%` to `+25.89%`
- 0.10 decimal price haircut ROI = `+7.25%`
- paired improvement over V3 = `+2.84` ROI points
- paired improvement interval = `-2.75` to `+8.61`

V5 is not statistically superior to V3 and remains `score_only`. Its first
database write inserted `48` immutable scores; the rerun returned
`0 inserted / 48 existing / 0 conflicts`. All `48` are valid by timing and
fingerprint, contain no outcomes, and created zero bets.

Registry V3 now contains `14` policies with fingerprint
`bb90eee37081e96c236efb6c22de2ff96c6e85859cd6d1e3571d4245c6e1e4f0`.
Across V3, V4, and V5 the archive contains `144` scores. All are currently
Brazilian OOD diagnostics, so the policy evaluator correctly reports `0`
in-domain scores and no ROI/CLV/promotion evidence.

## V6 Scope-Interaction Update

Experiments 057-061 tested prequential stat partial pooling, regularized stat
slopes, fixed interaction ensembles, scope/period slopes, and selection
placebos. The retained score-only challenger is:

`ev_scope_interaction_recency45_asof_capped_v6_shadow`

Historical scope-deviation result:

- bets/matches = `234/132`
- PnL/ROI = `+42.18` units / `+18.03%`
- positive outer windows = `5/6`
- clustered 95% interval = `+3.62%` to `+32.14%`
- every leave-one-league/window ROI remained positive
- 0.10 decimal price haircut ROI = `+11.96%`
- raw one-sided p-value = `0.00546`
- 123-search adjusted p-value = `0.672`

Three selection placebos produced one-sided p-values from `0.00008` to
`0.00042`, but one-bet-per-match widened the clustered interval across zero.
V6 therefore remains exploratory and cannot create `forward_bets`.

V6 artifact serialization passed. Its first real database score run inserted
`48` rows; the immediate rerun returned
`0 inserted / 48 existing / 0 conflicts`. The archive audit reports:

- valid scores = `48/48`
- timing violations = `0`
- outcome mutation rows = `0`
- duplicate score keys = `0`
- fingerprint mismatches = `0`
- in-domain scores = `0`

All V6 scores are Brazilian OOD diagnostics and created zero bets. Registry V4
resolves to `19` policies with fingerprint
`49337d918609c451cdbd71726ef76d3c13c6185f55f66a7f95614a2fba2447c6`.
Across V3-V6 the current archive contains `192` diagnostic scores.

## V6 Robustness And Primary Challenger Freeze

Experiments 063-067 completed before any in-domain V6 settlement.

Feature-group ablations remained historically positive at `+9.65%` to
`+15.78%`, so the scope result does not depend on one interaction group.
However, every simpler variant had better Brier score than full V6. This
conflict between probability calibration and selected-bet ROI is retained as
an overfit warning.

Temporal robustness is mixed:

- 90-day training with 30/45/60-day half-lives = `+13.95%`, `+18.03%`,
  and `+16.00%`
- 60-day training with the same half-lives = `-4.94%`, `-4.25%`, and
  `-3.32%`
- Extending regularization to `C=0.001` did not repair the 60-day failure

The strongest exact historical policy is now frozen as:

`v6_scope_interaction_corners_away_total_primary_challenger`

- Filters = corners, away/total, all periods, EV strictly between `7.5%`
  and `25%`
- Bets/matches = `156/99`
- PnL/ROI = `+44.70` units / `+28.65%`
- Clustered 95% interval = `+11.33%` to `+45.27%`
- 159-test adjusted p-value = `0.0207`
- Every leave-one-league/window result positive
- 0.10 decimal price haircut ROI = `+22.05%`
- One highest-EV bet per match = `99` bets at `+30.02%`

Always-over, always-under, favorite, and longshot controls were all negative.
Three matched random-selection controls retained adjusted p-values from
`0.00324` to `0.00972` after expanding the historical family to `162`.

The result is still `not_confirmed`: the outcomes were inspected, the
7.5%-threshold neighborhood is sharp, and the shorter training window loses.
No historical result can promote this policy.

Registry V5 was written before new in-domain outcomes:

- registry id = `score_policy_registry_v5`
- policies = `20`
- historical search family = `162`
- fingerprint =
  `5b8a699fc874d9f967aaaab81b68ff85f61c28dbf5fb634860f768b04889794d`

The real database evaluator resolved all 20 policies and read 48 V6 scores.
The V6 corner/away+total policy saw 24 relevant score rows, but all were
Brasileirão Série A OOD rows. It therefore selected zero bets and contributed
zero ROI, CLV, or promotion evidence, as required.

## V6 Horizon And Temporal-Consensus Audits

The exact frozen V6 policy has materially different historical timing from
the four required production checkpoints:

- Required T-3D/T-2D/T-1D/T-10M coverage = `27/156` (`17.31%`)
- Coverage with supplementary T-12H/T-2H = `128/156` (`82.05%`)
- T-1D/T-10M historical selections = `0/0`
- T-12H/T-2H historical selections = `83/18`

T-12H and T-2H remain research checkpoints so the forward archive can observe
the horizons that generated most historical V6 selections. The original four
checkpoints remain mandatory. No horizon is promoted or removed from its
descriptive ROI.

The horizon audit previously included T-12H/T-2H in both the baseline and the
expanded policy because those checkpoints had already moved into the shared
policy list. The script now separates required and research key sets, and a
regression test verifies they remain disjoint.

A fixed 90/60-day temporal-consensus experiment then tested four variants:

- 25% short-window blend = `163` bets at `+21.87%`
- 50% short-window blend = `184` bets at `+16.16%`
- Positive short-window side agreement = `154` bets at `+28.81%`
- Both models above 7.5% EV = `126` bets at `+27.42%`

Both blends worsened Brier and ROI relative to frozen V6. The weak agreement
gate was only two bets different from V6; its paired ROI improvement was
`+0.16` points with a `-1.95` to `+2.48` interval. The strict gate reduced ROI
and positive-window count. All consensus variants are rejected, the
historical comparison family is now `166`, and registry V5 remains unchanged.

## Nested Count/Residual Audit

Experiment 070 rebuilt the count-model path with exact snapshot-as-of
features, 90-day outer training, 21-day temporal validation, 45-day recency
weights, and negative-binomial dispersion estimated only from prior
out-of-sample validation predictions.

- Count and V6 prediction universes matched exactly: `8,822/8,822` sides
- Timing, forbidden-feature, duplicate-key, and settlement mismatches: `0`
- Count-only corner away/total: `1,103` bets at `-3.31%` ROI
- 90% V6 / 10% count: `190` bets at `+14.69%` ROI
- 75% V6 / 25% count: `345` bets at `+2.50%` ROI
- V6 plus positive count-side agreement: `134` bets at `+25.85%` ROI
- Frozen V6 reference: `156` bets at `+28.65%` ROI

Every count-assisted policy failed the retention gate. Count alone and both
blends worsened full-universe Brier score; the agreement rule was `2.80` ROI
points worse than V6 with a paired 95% difference interval of `-8.37` to
`+2.97`. The conservative historical comparison family is now `210`.
Registry V5 was not mutated.

## Snapshot Movement Audit

Experiment 071 reconstructed historical canonical markets from `981,400`
raw snapshot rows and built opening-to-current movement features strictly as
of each saved model odds time.

- Rows with usable aligned movement: `11,965/14,033` (`85.26%`)
- Future market observations excluded/used: `1,198/0`
- V6/movement prediction universe: `8,822/8,822`
- Forbidden feature, duplicate-key, and train/test timing violations: `0`

The movement-only V6 architecture fell to `+13.98%` corner away/total ROI.
A fixed 90% V6 / 10% movement blend improved full Brier by `0.000063` and
returned `+29.03%`, but `142/146` bets overlapped V6. Its paired improvement
was only `+0.38` ROI points with a `-5.27` to `+6.46` interval, and its
254-test adjusted p-value was `0.066`. Every movement policy failed the
predeclared retention gate; registry V5 remains unchanged.

## Prequential Movement-Weight Audit

Experiment 072 selected a V6/movement weight separately for every outer
window using Brier from completed earlier windows only. The selected movement
weights were `0%`, `50%`, `10%`, `50%`, `50%`, and `100%`.

- Future-window outcomes used: `0`
- All-window Brier: `0.246832` versus V6 `0.246351`
- All-window corner away/total: `179` bets at `+15.82%`
- Cold-abstain corner away/total: `145` bets at `+18.59%`
- Paired ROI difference versus V6: `-12.84` points
- Paired 95% interval: `-24.79` to `-1.29`

The fixed 10% movement blend was therefore not prequentially stable. Both
adaptive variants failed, the conservative comparison family is now `282`,
and registry V5 remains unchanged.

## Alternate-Line Ladder Audits

Experiment 073 reconstructed `488,089` unambiguous simultaneous Kambi line
points. `12,445/14,033` model rows had at least two other lines available
after excluding the current line; future ladders excluded/used were
`1,198/0`.

The fixed 90% V6 / 10% ladder blend produced `148` corner away/total bets at
`+31.33%` ROI, a `+13.92%` clustered lower bound, `+24.57%` under the
0.10 price stress, and a 326-test adjusted p-value of `0.0163`. It still
failed the incremental gate: `147/148` bets overlapped V6 and its paired
improvement interval was `-2.24` to `+8.13`.

Experiment 074 selected ladder weight from completed prior outer windows only:
`0%`, `10%`, `0%`, `0%`, `25%`, and `50%`. Brier improved, but corner
away/total ROI fell to `+25.45%`. First-window abstention returned `+31.39%`
versus V6's `+35.53%` on the same dates. Both paired intervals crossed zero
on the negative side.

The conservative comparison family is now `354`. Ladder information is
retained as a documented calibration finding, not a promoted betting model;
registry V5 remains unchanged.

## Combined Market Microstructure Audits

Experiment 075 rebuilt movement and alternate-line ladder features directly
from `981,400` raw snapshot rows. The rebuilt features matched both cached
`14,033`-row matrices, and V6, movement, ladder, and combined models shared an
exact `8,822`-row prediction universe with zero duplicate keys or timing
violations.

The full combined feature model failed at `+3.39%` corner away/total ROI and
worsened Brier. The best fixed blend used 90% V6, 5% movement, and 5% ladder:

- `146` bets at `+31.97%` ROI
- `6/6` positive windows
- clustered 95% interval `+14.43%` to `+48.52%`
- `+25.18%` ROI after a 0.10 decimal price haircut
- Brier `0.246303` versus V6 `0.246351`

It still failed the incremental gate. `145/146` bets overlapped V6 and its
paired improvement was `+3.31` ROI points with a `-1.63` to `+9.01` interval.

Experiment 076 then chose how far to move from V6 toward the 90/5/5 composite
using completed prior-window Brier only. It selected no movement in the cold
start and the full composite in all five later windows. The all-window result
was `147` bets at `+30.91%`, but paired improvement remained unproven:
`+2.26` points with a `-2.08` to `+7.35` interval.

The conservative comparison family is now `426`. The microstructure composite
is retained as a calibration shadow only. Frozen V6 and registry V5 remain
unchanged; further selection on the same outcomes would be data mining rather
than new model evidence.

## Exact-As-Of Nonlinear HGB Audit

Experiment 077 reran both existing nonlinear model families on the final V6
snapshot-as-of contract. V6, HGB, and residual HGB had the same `8,822`
prediction rows, with zero duplicate keys, forbidden outcome features, timing
violations, or prediction-universe mismatches.

The results were materially worse than V6:

- HGB classifier: `424` corner away/total bets at `-8.42%`
- Market-residual HGB: `275` bets at `-12.20%`
- Positive windows: `2/6` and `1/6`
- Brier: `0.248933` and `0.247839`, versus V6 `0.246351`
- Paired ROI intervals versus V6 were fully negative

Small positive total-shots slices contained only `27-28` bets and failed
window stability. They remain rejected post-hoc diagnostics. The conservative
comparison family is now `454`; registry V5 remains unchanged.
