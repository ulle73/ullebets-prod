# Ullebets V2 Market Bias Design

Date: 2026-08-21

Status: Approved for implementation planning

## Purpose

Add an auditable market-bias signal to V2 that describes whether a team has
recently finished above or below Unibet's comparable prematch main line. The
signal is contextual information for matchup cards. It does not change matchup
ranking, the frozen V6 model, forward selection, settlement, ROI, or CLV.

The legacy `marketBias` implementation is behavioral reference only. V2 must
derive its own records from normalized prematch odds and verified canonical
outcomes.

## Current Evidence

The production V2 database currently contains:

- 15,208 `market_snapshots`, of which 14,711 are valid prematch rows.
- 147,408 canonical match-stat rows.
- 12,896 valid primary-market snapshot rows: 9,414 corners, 2,254 shots on
  target, and 1,228 total shots.
- 135 finished market contexts currently join directly between live V2
  snapshots and canonical outcomes.

The audited offline dataset can bootstrap the signal without retaining a
runtime dependency on legacy systems:

- 981,400 normalized historical snapshot rows.
- 166,816 normalized market-line rows.
- 11,917 preliminary eligible main-line contexts over 1,017 matches after
  requiring primary targets, verified outcomes, valid prematch snapshots,
  over odds between 1.70 and 2.30, and exact scope/period support.

The 11,917 figure is pre-mapping coverage, not an import acceptance target.
Every historical team and league still has to map safely to a V2 canonical
identity. Unmatched or ambiguous rows are excluded and audited.

## Non-Goals

- Do not modify V6 artifacts, features, policies, thresholds, or predictions.
- Do not use bias to reorder matchup cards in the first release.
- Do not claim that bias proves positive EV.
- Do not read `app`, `ullebets_unibet`, or the old repository during normal V2
  operation.
- Do not write market bias into canonical team-stat values.
- Do not invent bias when odds, outcome, timing, or identity is incomplete.

## Selected Approach

V2 will use a one-time audited historical bootstrap followed by an idempotent
forward refresh job.

Pure forward accumulation was rejected because current V2 coverage would leave
most teams without useful bias for months. On-demand reconstruction during
matchup reads was rejected because it would be slow, difficult to cache, and
harder to audit or reproduce.

Market bias gets its own observation and profile collections. This keeps
immutable source evidence separate from the derived rolling summary and avoids
coupling bookmaker behavior to ordinary team-stat profiles.

## Collections

### `market_bias_observations`

One immutable record represents one canonical team-context observation against
one selected prematch line.

Required identity fields:

- `observation_key`
- `match_key`
- `source_match_id`
- `league_key`
- `team_key`
- `venue_context`: `home` or `away`
- `market_scope`: `total`, `home`, or `away`
- `stat_key`
- `period`

Required market and outcome fields:

- `line_value`
- `over_odds`
- `under_odds`
- `actual_value`
- `residual_value`: `actual_value - line_value`
- `line_result`: `over`, `under`, or `push`
- `snapshot_key`
- `snapshot_label`
- `snapshot_time`
- `match_start_time`
- `minutes_to_kickoff`
- `outcome_available_at`

Required provenance fields:

- `source_kind`: `offline_v1_bootstrap` or `v2_forward`
- `source_record_key`
- `source_payload_hash`
- `line_selection_method`
- `method_version`
- `created_at`
- `run_id`

Home-scope observations belong only to the home team in its home context.
Away-scope observations belong only to the away team in its away context. A
total-market observation produces two contextual records: one for the home
team's total-market history at home and one for the away team's total-market
history away. Their distinct `team_key` values keep the observation identities
unique.

### `market_bias_profiles`

One derived record summarizes a team's recent bias for one exact context.

Identity:

- `profile_key`
- `profile_date`
- `as_of`
- `team_key`
- `league_key`
- `venue_context`
- `market_scope`
- `stat_key`
- `period`
- `method_version`

Summary:

- `direction`: `over`, `under`, `neutral`, or `insufficient`
- `strength`: `none`, `lean`, `strong`, or `very_strong`
- `sample_size`
- `non_push_sample_size`
- `effective_sample_size`
- `over_count`
- `under_count`
- `push_count`
- `raw_over_rate`
- `posterior_over_rate`
- `weighted_mean_residual`
- `shrunk_mean_residual`
- `direction_confidence`
- `latest_observation_at`
- `oldest_observation_at`
- `snapshot_quality_counts`
- `observation_keys`
- `generated_at`
- `run_id`

## Observation Selection

For each completed `match_key + stat_key + scope + period`:

1. Require a canonical fixture and exact canonical actual.
2. Require `snapshot_time < match_start_time` and
   `invalid_for_model != true`.
3. Select the latest valid prematch capture batch for that market context.
4. Within that batch, consider over lines with decimal odds from 1.70 through
   2.30.
5. Select the line whose over odds are closest to 2.00.
6. Break ties deterministically by absolute distance to 2.00, then line value,
   offer key, and snapshot key.
7. Calculate `actual - line` and classify the result. Equality is a push.

This method supports corners with both sides and shots/shot-on-target markets
where Unibet commonly exposes only over odds. A market with no qualifying
near-even over line produces no observation.

The latest stored prematch row is not silently called a true closing line.
`snapshot_label` and `minutes_to_kickoff` remain visible so consumers can
distinguish T-10/T-30 quality from an older T-1D or T-2D observation.

## Leakage And Availability Rules

An observation is eligible for a profile at cutoff `C` only when:

- `snapshot_time < match_start_time`
- `outcome_available_at < C`
- the observed match starts before `C`
- stat key, scope, period, match, team, and league mappings are exact
- the observation is not marked invalid

Forward V2 observations use the persisted canonical result availability time.
Historical bootstrap rows use a conservative availability timestamp of match
kickoff plus three hours when no trustworthy source timestamp exists. This
prevents a historical as-of profile from using a result before it could
reasonably have been known.

Profiles are materialized as of a specified cutoff. Historical rebuilds and
tests must pass that cutoff explicitly; they may not reuse a later `current`
profile.

## Rolling Bias Formula

The profile uses at most the latest 12 eligible observations for the exact
team, venue context, market scope, stat, and period.

For observation `i` at profile cutoff `C`:

`weight_i = 0.5 ** (age_days_i / 45)`

Pushes contribute residual zero and remain visible in sample counts, but they
do not count as an over or under success.

The binary component uses a neutral Beta prior equivalent to six matches:

`posterior_over_rate = (3 + weighted_over_sum) / (6 + weighted_non_push_sum)`

The residual component is shrunk toward zero with the same prior strength:

`shrunk_mean_residual = weighted_residual_sum / (6 + total_weight)`

Effective sample size is:

`effective_n = total_weight ** 2 / sum(weight_i ** 2)`

The implementation calculates an approximate posterior directional confidence
using the posterior rate and effective sample size without adding a SciPy
runtime dependency.

The result is `insufficient` unless there are at least six real observations
and effective sample size is at least four. Otherwise:

- `over` requires posterior rate above 0.50, positive shrunk residual, and at
  least 80% directional confidence.
- `under` requires posterior rate below 0.50, negative shrunk residual, and at
  least 80% directional confidence.
- Conflicting signs or lower confidence produce `neutral`.
- `lean` is 80-90% confidence, `strong` is 90-97%, and `very_strong` is at
  least 97%.

The API exposes the underlying counts and residual. The UI does not present an
opaque standalone score as if it were a model probability.

## Historical Bootstrap

The bootstrap reads only local audited derived files:

- `normalized/market_snapshots.parquet` for timestamped odds observations.
- `normalized/market_lines.parquet` for audited canonical market/outcome
  mapping.
- `normalized/matches.parquet` and V2 support data for identity resolution.

Identity resolution order:

1. Exact source team ID mapped to a V2 support team.
2. Exact normalized team name within one exact normalized league.
3. A configured unique alias within one exact normalized league.
4. Otherwise exclude as unmatched.

League aliases such as `LaLiga`/`La Liga`, `Serie A`, and A-League naming are
normalized through versioned support mappings. No fuzzy match may write an
observation.

The import is idempotent. Each accepted row stores source lineage and hash so a
repeat run can distinguish an exact replay from a source conflict. The normal
production flow never needs the local Parquet files after bootstrap.

## Forward Refresh

After match enrichment and canonical outcome creation, the forward job:

1. Loads finished fixtures not yet represented by observations.
2. Loads valid prematch market snapshots and exact actuals.
3. Selects the deterministic main line.
4. Upserts new immutable observations by `observation_key`.
5. Rebuilds affected current bias profiles.
6. Writes `job_runs`, parity, audit, and health records.
7. Triggers or precedes matchup rebuilds so cards receive the new profiles.

Rerunning the same date range must insert no duplicate observations and produce
the same profile payload except for run metadata.

## Matchup And API Integration

The matchup builder loads `market_bias_profiles` independently of
`teamprofiles`.

- Home-scope card: home team's home-context, home-market profile.
- Away-scope card: away team's away-context, away-market profile.
- Total-scope card: both the home team's home-context total profile and the
  away team's away-context total profile.

The existing `market_bias` field remains the persisted matchup field, but its
payload becomes a typed V2 summary. Missing or insufficient profiles remain
explicit rather than receiving a fabricated neutral value.

The read API returns direction, strength, shrunk residual, counts, confidence,
sample size, method, and snapshot-quality information. The frontend renders a
compact form such as:

`OVER +1.4 | 7/10 | medium confidence`

Total cards render separate home and away rows when both exist. The frontend
must not imply that bias is V6 probability or EV.

## Database Indexes

Required indexes:

- Unique `market_bias_observations.observation_key`.
- `market_bias_observations` on
  `(team_key, venue_context, market_scope, stat_key, period,
  outcome_available_at desc)`.
- `market_bias_observations` on
  `(match_key, stat_key, market_scope, period)`.
- Unique `market_bias_profiles.profile_key`.
- `market_bias_profiles` on
  `(profile_date, team_key, venue_context, market_scope, stat_key, period)`.

All writes retain the existing hard guard requiring
`MONGODB_DB=ullebets_v2`.

## Audits And Health

Each bootstrap or forward run reports:

- source rows and eligible rows
- accepted observations
- exact ID, exact-name, and configured-alias mappings
- unmatched and ambiguous teams/leagues
- missing or conflicting actuals
- missing snapshot time or kickoff
- post-start rows rejected
- invalid-for-model rows rejected
- duplicate observation identities
- source hash conflicts
- qualifying-line failures
- counts by stat, scope, period, league, and snapshot label
- profile counts by direction, strength, and sample-size bucket
- stale profile detection

Any post-start inclusion, future-outcome inclusion, duplicate observation key,
or conflicting immutable payload fails the run. Ordinary missing coverage is
reported and excluded without guessing.

## Tests

Unit tests cover:

- latest valid prematch batch selection
- rejection at or after kickoff
- near-even over-line selection and deterministic ties
- shots markets with over odds only
- corners with both sides
- push handling
- exact scope and period outcome mapping
- total-market contextual duplication
- 12-match window and 45-day weighting
- neutral prior and small-sample gating
- sign disagreement producing neutral
- historical as-of outcome availability
- identity rejection and alias uniqueness
- observation and profile idempotency
- immutable source-hash conflict failure

Integration tests cover bootstrap input, forward refresh, matchup persistence,
read API serialization, and frontend rendering. The full Python suite and
frontend test/typecheck/lint/build gates must pass before commit or deployment.

## Acceptance Criteria

- Zero included snapshots at or after kickoff.
- Zero outcomes used before `outcome_available_at`.
- Zero duplicate observation identities.
- Zero fuzzy or ambiguous identity writes.
- Every observation traces to one source snapshot and one canonical actual.
- Every profile traces to its exact observation keys and method version.
- Missing/insufficient data stays visibly missing/insufficient.
- Matchup score, sort key, rank position, and selection membership are
  unchanged for identical teamprofile input.
- V6 artifacts, features, registries, predictions, and forward selections are
  unchanged.
- Bootstrap and immediate rerun are idempotent.
- A completed forward match can produce observations, refresh profiles, and
  update matchup cards through the scheduled job chain.

## Rollout Order

1. Add schemas, collections, indexes, and pure calculation functions.
2. Add historical bootstrap with dry-run audit and mapping report.
3. Review accepted/unmatched coverage before the first database write.
4. Persist bootstrap observations and profiles, then rerun idempotency audit.
5. Add forward refresh and job automation.
6. Integrate matchup persistence and read API.
7. Add the typed frontend display.
8. Run full regression, database safety, leakage, parity, and smoke tests.
