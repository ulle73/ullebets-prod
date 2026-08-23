# Ullebets app readiness checklist

Last updated: 2026-08-23

Overall status: **NOT READY FOR COMPLETE PRODUCTION USE**

Only fully evidenced behavior gets `[x]`. Implemented code, unit tests, or a
successful dry-run is not enough when the requirement needs a real live
lifecycle window.

Status details and evidence:

- [Work log](work-log.md)
- [Backend verification](v2-backend-verification-status.md)
- [Model experiments](ev-model-experiments.md)

## Critical blockers

- [ ] `UNPROVEN` Capture a real T-10 odds window before kickoff. The lean
  runner import defect is repaired and hosted smoke-tested, but no post-fix
  production capture has yet persisted.
- [ ] `UNPROVEN` Capture the new real T-30 fallback and prove that a later T-10
  upgrades it without mixing fallback CLV into official model evidence.
- [ ] `UNPROVEN` Materialize a valid closing line from that live capture.
- [ ] `UNPROVEN` Calculate CLV from a valid live closing line.
- [ ] `BLOCKED` Accumulate in-domain V6 forward predictions and settlements.
- [ ] `PARTIAL` Prove output parity for every original backend workflow.
- [ ] `PARTIAL` Remove the runtime dependency on the old repository's JS
  oracle so V2 can run independently.
- [ ] `PARTIAL` Production Vercel hosting and the server-side V2 read API are
  verified; monitoring, alerting, and full operational acceptance remain.

## 1. Database and safety

- [x] V2 has a separate `ullebets_v2` database.
- [x] `app` and `ullebets_unibet` are treated as read-only references.
- [x] Every V2 write path hard-fails when `MONGODB_DB` is not `ullebets_v2`.
- [x] Raw source documents are stored separately from canonical/derived data.
- [x] Canonical collection names are suffix-free and legacy `*_v2` names have
  cleanup mappings.
- [x] Jobs record status and metrics through `job_runs`.
- [x] Audit, parity, and health report collection families exist.
- [x] Simulated timestamps are rejected in real write mode.
- [ ] `UNPROVEN` Run and save an explicit production index audit for every
  high-volume collection.
- [ ] `NOT STARTED` Define and verify backup, restore, retention, and disaster
  recovery procedures for `ullebets_v2`.

## 2. Support data, leagues, and teams

- [x] Support sources can be synchronized.
- [x] Canonical league records are persisted.
- [x] Canonical team records and aliases are persisted.
- [x] Opta/ranking support data is persisted with auditable source metadata.
- [x] The tested support sync completed with health and audit status `ok`.
- [ ] `PARTIAL` Prove team/league alias coverage across a complete active
  season for every target league.

## 3. Fixtures and match identity

- [x] Upcoming fixtures can be fetched from the live source. After replacing
  `RAPIDAPI_KEYS` with 15 configured keys, the 2026-08-23 write-mode run
  returned the complete 19-fixture schedule and the production read API
  returned the same 19 unique canonical fixtures.
- [x] Raw fixture payloads are stored before normalization.
- [x] Canonical fixtures and source links are created idempotently.
- [x] Empty fixture dates are accepted only after every configured league
  category returns an HTTP-successful source response.
- [x] Tested fixture windows produced stable per-date canonical records.
- [x] Tested Unibet events and SofaScore fixtures linked without guessing.
- [ ] `PARTIAL` Prove canonical match identity coverage across all supported
  leagues and a complete season.
- [ ] `PARTIAL` Reduce unresolved team/league mappings to an accepted
  production threshold and report that threshold continuously.

## 4. Statistics, results, and derived sports data

- [x] Raw match statistics can be fetched and stored.
- [x] Raw incidents can be fetched and stored.
- [x] Raw shotmaps can be fetched and stored.
- [x] Raw results can be fetched and stored.
- [x] Canonical match results can be rebuilt from raw data.
- [x] Corners, total shots, and shots on goal map to canonical
  stat/period/scope rows.
- [x] Tested finished matches produced 27 canonical primary-stat rows each.
- [x] The latest completed match date for every followed league is persisted:
  41/41 matches have raw statistics, incidents, shotmaps, results, scored
  canonical results, and exactly 27 primary-stat rows each.
- [x] Teamprofiles can be rebuilt from canonical history.
- [x] Historical Unibet main-line bias is materialized as 16,528 immutable
  observations and 2,112 leakage-safe rolling profiles. The immediate rerun
  inserted zero rows and replayed all 16,528 hashes without conflict.
- [ ] `UNPROVEN` Observe the first scheduled completed-match V2 forward bias
  refresh; the historical bootstrap does not prove live refresh operation.
- [x] A full V2 database teamprofile build completed after the 2026-08-12
  Cosmos repairs: 585 matches, 147,408 stats, 1,107 incidents, 1,105
  shotmaps, 265 profiles, and `ok` audit/health reports.
- [ ] `PARTIAL` The next hosted `update-teamstats-and-teamprofiles.yml` run
  must prove the same main-branch result through GitHub Actions.
- [ ] `PARTIAL` `matchups_score` rebuilt successfully on 2026-08-14 with
  1,278 deduplicated, 12-match recency-weighted rows across 8 mapped fixtures.
  Old-output parity and the unresolved Real Racing Club home-profile mapping
  still need acceptance evidence.
- [ ] `PARTIAL` `matchups_league_avg` rebuilt successfully on 2026-08-14 with
  the same 1,278 deduplicated, 12-match recency-weighted rows. Old-output
  parity and the unresolved Real Racing Club home-profile mapping remain open.
- [ ] `PARTIAL` Prove matchup outcome settlement against old output and
  canonical actuals over a finished date range.

## 5. Unibet/Kambi odds

- [x] Unibet/Kambi events can be discovered for tested fixtures.
- [x] Full raw Kambi payloads are stored before normalization.
- [x] Event links connect source events to canonical matches.
- [x] Market offers are normalized without mutating raw payloads.
- [x] Odds rows carry source and snapshot metadata.
- [x] Odds at or after kickoff are excluded from model, ROI, and CLV.
- [x] Real T-3D capture has 678 valid prematch rows across 10 matches.
- [x] Real T-2D capture has 799 valid prematch rows across 10 matches.
- [x] Real T-1D capture has 817 valid prematch rows across 10 matches.
- [x] Real production T-2H capture has 242 valid prematch rows across three
  matches.
- [ ] `UNPROVEN` Prove a real T-30M fallback capture after the lean-runner
  import repair.
- [ ] `UNPROVEN` Prove a real T-10M capture after the lean-runner import
  repair.
- [ ] `UNPROVEN` Build closing lines from the final valid prematch snapshot.
- [ ] `UNPROVEN` Refresh CLV from valid live closing lines.

Current acceptance window:

- The 5-8 August Brazil window has persisted valid T-3D/T-2D/T-1D/T-2H data.
- At `2026-08-08T18:51Z`, Grêmio - São Paulo was eight minutes from kickoff,
  but `closing_lines` remained empty.
- Hosted closing run `31271905639` failed at startup with
  `ModuleNotFoundError: ullebets_v2`; it made no odds capture or derived write.
- Commit `030a401` repaired the reusable lean runner. Hosted dry-run
  `31273361050` completed the closing command with zero errors and zero due
  targets; it made no writes.
- No T-30/T-10, closing, or CLV checkbox may be checked until a valid
  persisted production capture exists.

## 6. Model snapshots, analysis, and predictions

- [x] Model-ready snapshots can be produced from V2 database inputs.
- [x] Auto-analysis can produce candidates and a shortlist.
- [x] Daily, combo, and user-closing prediction exports can be persisted.
- [x] Forward predictions are immutable after creation.
- [x] V6 model artifact exists and its hash matches its manifest.
- [x] Registry V5 resolves to 20 immutable policies with a stable fingerprint.
- [x] Production forward scoring is configured to use only the frozen V6
  artifact and a separate immutable V6 forward-policy registry.
- [x] Immutable score persistence preserves stored rows and accepts only
  machine-precision-equivalent raw feature values (absolute tolerance
  `1e-12`) while independently validating derived feature fingerprints;
  material changes and corrupt fingerprints still fail closed.
- [x] A production-database V6 rerun reused 105 frozen rows with zero
  conflicts, including 49 precision-equivalent rows, and created no forward
  bets.
- [ ] `PARTIAL` The next hosted V6 rerun must confirm that an equivalent
  existing production score is reused without an immutable-conflict failure.
- [ ] `PARTIAL` V6 scoring is bound to each accepted odds checkpoint and
  closing capture that persists a new snapshot. Local workflow contracts pass;
  hosted write-mode evidence from a real due checkpoint is still required.
- [x] Training-domain filtering excludes unknown leagues from evidence.
- [x] Historical experiments 000-077 are documented with negative results.
- [x] The strongest historical V6 policy has leakage-safe walk-forward evidence.
- [ ] `BLOCKED` Score upcoming matches from a V6-supported league before
  kickoff.
- [ ] `BLOCKED` Settle untouched in-domain V6 selections.
- [ ] `BLOCKED` Reach the promotion gate: at least 300 settled bets, 150 match
  clusters, 80% CLV coverage, positive mean CLV, positive clustered lower
  bound, corrected p-value below 0.05, and clean audits.

## 7. Settlement, ROI, and CLV

- [x] Over wins only when actual is greater than line.
- [x] Under wins only when actual is lower than line.
- [x] Equal actual and line settles as push with zero PnL.
- [x] Decimal-odds PnL uses win `odds - 1`, loss `-1`, and push `0`.
- [x] Duplicate snapshot exposure is deduplicated per market selection.
- [x] Invalid timing rows remain auditable but cannot receive PnL or CLV.
- [x] Operational forward rows have been settled against canonical outcomes.
- [x] Forward-results output separates open, settled, and excluded rows.
- [ ] `UNPROVEN` Produce model-specific in-domain forward ROI.
- [ ] `UNPROVEN` Produce model-specific in-domain CLV and beat-close rate.

## 8. Audits and data quality

- [x] Odds timing leakage audit exists and has excluded real violations.
- [x] Outcome mapping and push-rule audits exist.
- [x] Duplicate exposure audit exists.
- [x] Feature leakage checks enforce historical availability before kickoff.
- [x] Database safety audit exists.
- [x] Job health and stale-run reporting exist.
- [x] Fixture ingestion now fails closed on a failed or unreachable source;
  a valid HTTP-successful empty payload remains distinct from an outage.
- [ ] `PARTIAL` Source connectivity audit still reports failed endpoints and
  requires endpoint-by-endpoint triage.
- [ ] `PARTIAL` Complete raw coverage and match-mapping acceptance across a
  full active-season window.
- [ ] `PARTIAL` Complete closing/CLV coverage audits after valid live closings
  exist.

## 9. Automation and operations

- [x] Original workflow names have V2 job mappings.
- [x] Shared GitHub Actions runner enforces `ullebets_v2`.
- [x] Emergency dry-run mode exists.
- [x] A match-aware hourly Actions scheduler owns production checkpoints and
  enables the five-minute closing watcher only around uncaptured upcoming
  fixtures. Hosted write-mode run `30673575119` proved that an already-disabled
  watcher is handled idempotently and checkpoint capture still executes.
- [x] Hosted scheduler run `30949327663` on 4 August saw all 10 current future
  fixtures, correctly selected zero due checkpoints, and completed with zero
  errors plus persisted audit/health status `ok`.
- [x] T-2H is assigned to the hourly job; T-30/T-10 are exclusively assigned
  to the closing watcher, with T-30 excluded from official model CLV. Hosted
  write-mode scheduler run `30674861895` passed this deployed contract with a
  valid empty source horizon.
- [ ] `PARTIAL` Closing watcher import repair is deployed and hosted dry-run
  `31273361050` passed, but a scheduled write-mode T-30/T-10 lifecycle remains
  unproven.
- [x] EV shadow runtime versions are pinned to the frozen manifests; hosted
  production write-mode run `30672830616` passed all four scorers. It produced
  zero rows because no upcoming canonical model markets existed.
- [ ] `PARTIAL` Prove every scheduled workflow in real write mode through a
  complete prematch-to-postmatch lifecycle.
- [ ] `PARTIAL` A valid T-30/T-10 snapshot now starts V6 in the same capture
  workflow instead of waiting for an independent scorer schedule. A hosted
  write-mode closing capture remains required evidence.
- [ ] `PARTIAL` Attach persisted parity/health evidence to every workflow run.
- [ ] `NOT STARTED` Add production alerting for stale jobs, failed sources,
  missing odds, mapping failures, and missed closing windows.
- [ ] `NOT STARTED` Define operational ownership and recovery procedures for
  failed scheduled jobs.

## 10. V2 independence and original-backend parity

- [x] The old databases are not V2 write targets.
- [x] The parity matrix maps every known original workflow to a V2 job.
- [x] V2 has replacement scripts for fixtures, enrichment, support, odds,
  snapshots, settlement, analysis, exports, and training exports.
- [ ] `PARTIAL` Replace the remaining legacy JS oracle runtime dependency with
  native V2 behavior.
- [ ] `PARTIAL` Mark every workflow parity row accepted with saved count and
  quality comparisons.
- [ ] `PARTIAL` Verify `matchups_score`, `matchups_league_avg`, and matchup
  settlement output parity.
- [ ] `PARTIAL` Verify training-export sample and stat/scope/period parity.
- [ ] `PARTIAL` Demonstrate that V2 can run end-to-end with the old repository
  unavailable.

## 11. Frontend and product surface

- [x] `VERIFIED` A stable read-only API now exposes the fixture/dashboard, match, league, team, Auto, results, model, and system contracts required by the frontend without adding write behavior.
- [x] `VERIFIED` The complete `style-1` frontend is implemented across the five primary destinations plus match, team, league, model, system-status, and real not-found routes.
- [x] `VERIFIED` Today's/upcoming matches and match detail are rendered from read contracts, including available scores, market offers, actuals, checkpoints, team comparison, and forward evidence. The selected dashboard date filters on the derived Stockholm-local kickoff date rather than fixture `source_date`; the protected Vercel production API verified the `2026-08-22` contract at 19 matches, including Hull City and excluding Arsenal, and the repaired `2026-08-23` source/import/read path at the supplied 19 matches (6 Brasileirão Série A, 4 Serie A, and 3 each in Premier League, La Liga, and Ligue 1). Production deployment `dpl_DcbJPcrn5eHBH642oPpmekLStz6J` additionally proves real league, team, and match drilldowns through Vercel's one- and two-segment function routes and a browser click-through.
- [x] `VERIFIED` Team statistics are explorable by home/away context, FOR/AGAINST orientation, period, rank, and league-relative deviation; league stat rankings are also available.
- [x] `VERIFIED` Matchup cards expose available market-bias profiles as a
  compact UNDER/OVER rail with signed residual, over/non-push sample,
  confidence segments, explicit thin-data state, and accessible Swedish text.
- [x] `VERIFIED` Registered forward selections expose offered odds, model probability, expected ROI field, model/policy identities, and persisted runtime status without presenting observation counts as proof.
- [x] `VERIFIED` Settled forward-result rows can show persisted ROI/PnL, closing odds, official CLV status/value, settlement state, exclusions, and linked match/team/league entities. This verifies the product surface, not positive forward efficacy.
- [ ] `PARTIAL` Data freshness, missing-data, exclusion, health, and audit states are shown on the relevant surfaces, but uniform freshness metadata across every product section still depends on the source/read contract carrying it.
- [x] `VERIFIED` Responsive and accessibility contracts are covered by the hosted frontend gate: primary/mobile navigation, keyboard skip-link, visible focus behavior, reduced-motion handling, narrow-layout containment, route-shell smoke tests, strict TypeScript, lint, 45 frontend tests, and production build all pass on `style-1` run `31648971262`.

## 12. Release readiness

- [x] README, `.env.example`, healthcheck, smoke test, work log, and agent
  instructions exist.
- [x] Current V2 regression suite passes `449/449` in the reconciled local
  `style-1` checkout. The earlier hosted `434/434` backend-isolation run
  `31648971290` remains preserved as historical evidence.
- [x] The V2 worktree was committed and merge-verified without secrets,
  caches, or unnecessary generated data; the clean merged checkout passed
  `392/392` tests at that checkpoint.
- [x] `VERIFIED` Vercel hosts the Style-1 SPA and read-only Python API at
  `ullebets-prod-preview.vercel.app`. Sensitive Production-only
  `MONGODB_URI` and `MONGODB_DB=ullebets_v2` are configured server-side;
  production health and dashboard reads return `200`, while write requests are
  rejected with `405`. Existing Vercel SSO protection remains enabled for
  `vercel.app` URLs until a separate access-policy decision is made.
- [ ] `NOT STARTED` Run a production acceptance test over at least one complete
  in-domain match lifecycle.
- [ ] `NOT STARTED` Define release rollback, database recovery, and incident
  response.

## Definition of done

The app is complete only when every checkbox above is checked. A historically
positive model is not enough: the product must fetch, snapshot, predict,
settle, audit, display, and operate automatically on real in-domain matches
without reading the old repository or writing to the old databases.
