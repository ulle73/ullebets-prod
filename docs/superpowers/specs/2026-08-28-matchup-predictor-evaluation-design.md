# Matchup predictor evaluation design

Date: 2026-08-28

Status: Approved in chat; written specification awaiting user review

## Decision

Ullebets will evaluate matchup rankings through two separate contracts:

1. **Predictor evaluation** measures whether a frozen matchup direction
   correctly anticipated the realized statistic relative to a frozen league
   baseline. It applies to every resolved matchup context with valid canonical
   actuals.
2. **Market evaluation** measures win/loss/push, flat-stake return, odds
   movement, and CLV only when the frozen predictor can be joined to one exact
   immutable Unibet offer.

The two contracts must never share a denominator or be collapsed into one
headline accuracy number. Missing odds are a coverage state, not a predictor
loss. A matchup score such as `93.4` remains a relative ranking score and must
not be rendered or evaluated as a 93.4% probability.

## Current evidence and problem

The 2026-08-28 read-only audit found:

- 15,876 persisted `matchups_score` rows;
- 5,544 resolved rows with canonical actual values;
- 805/5,544 resolved rows with an exact prematch market context and a price
  for the ranked direction;
- 623/5,544 resolved rows with such a price inside 1.80-2.20;
- 641/5,544 resolved rows with accepted T-30/T-10 closing-price coverage, all
  T-30 in the resolved sample;
- no current exact odds coverage for fouls, free kicks, throw-ins, or tackles;
- 8,640 rows still marked `pending_result`, 72 `missing_actual`, and 1,620
  rows without an outcome status.

Current matchup settlement stores actual values but does not derive a
predictor or market verdict. The dashboard read model omits those actuals. All
persisted score rows lack a row-level immutable creation timestamp, and 9,270
rows lack the current `rolling_12_weighted_45d` method identity. Existing
history can therefore be descriptive evidence, but it cannot prove a
leakage-safe forward predictor.

## Constraints

- `app` and `ullebets_unibet` remain read-only references. All new state is
  stored independently in `ullebets_v2`.
- Every V2 write continues to hard-fail unless `MONGODB_DB=ullebets_v2`.
- Raw source payloads, canonical actuals, frozen scores, and first-capture
  market evidence are immutable.
- Predictor results, market results, ROI, and CLV use exact match, stat,
  period, scope, direction, and policy identities.
- T-1D is the primary and only forward-evaluation anchor in version 1. A
  fixture discovered after T-1D may be displayed but is not silently mixed
  into the forward evaluation sample.
- Market eligibility requires direction odds from 1.80 through 2.20,
  inclusive. This interval selects comparable offers; it is not a correctness
  threshold.
- T-10 is the preferred accepted closing and T-30 is the accepted fallback.
- A provider name must not appear in public URLs.
- Existing model, backtest, V6 selection, ROI, CLV, and promotion policies are
  not changed by this feature.

## Evaluation identities

### Predictor context

One predictor context is:

```text
match_key + stat_key + period + scope
```

The current builder emits complementary OVER and UNDER rows for each context.
The forward evaluation direction is the side with the higher frozen score.
An exact tie at 50.0 has no selected direction and is excluded from aggregate
predictor and market denominators while remaining visible for audit.

Both directional rows may receive actual values for transparency. Aggregate
metrics count the selected context once so complementary rows cannot create
two nominally independent observations.

### Observation identity

The immutable observation key is:

```text
matchup-eval-v1|match_key|stat_key|period|scope|T_MINUS_1D
```

The observation stores the selected direction rather than including direction
in its identity. Replaying the same source inputs must reuse the first exact
observation. A differing replay is an immutable conflict and fails closed.

### Result identity

One derived result exists per observation key. It can move from open to a
terminal status as canonical match data arrives, but terminal actual values
and verdicts cannot be rewritten. Source corrections require an explicit
versioned correction record; they do not mutate frozen evidence silently.

## Immutable forward capture

A new `matchup_observations` collection owns first-capture predictor evidence.
At the accepted T-1D checkpoint the capture service:

1. loads the canonical fixture and verifies kickoff timing;
2. builds or reads the current matchup candidate universe;
3. chooses one selected direction per predictor context;
4. freezes score, daily rank, league baseline, and method identity;
5. attempts an exact market join and deterministic comparable-offer selection;
6. inserts or idempotently replays the immutable observation;
7. records an audit and health result for the complete due fixture set.

Each observation stores at least:

- `observation_key` and `policy_version = matchup-eval-v1`;
- fixture date, match key, league, teams, and kickoff;
- `prediction_created_at`, T-1D snapshot time, minutes before kickoff, and
  timing validity;
- stat, period, scope, selected direction, score, rank, and daily universe
  size;
- ranking method, window matches, recency half-life, and source/input
  fingerprints;
- frozen league baseline;
- exact market eligibility state and rejection reason;
- selected snapshot key, offer key, line, direction odds, opposite odds,
  overround, and observed time when eligible.

The existing `matchups_score` collection can continue to power replaceable
upcoming rankings. It is not the performance journal.

## Comparable market selection

Market selection is deterministic and only considers valid prematch T-1D
snapshots matching the exact predictor context.

For the selected direction:

1. discard offers without a numeric line and both usable direction prices;
2. discard invalid or at/post-kickoff snapshots;
3. retain offers whose selected-direction price is in `[1.80, 2.20]`;
4. sort by absolute distance from 2.00;
5. break ties by snapshot time, numeric line, and lexical offer key;
6. freeze the first offer.

This produces one auditable, main-line-like market test without selecting a
favorable line after the result is known. Offers outside the interval can be
shown as market availability but cannot enter market hit rate or ROI.

## Settlement semantics

A new derived `matchup_results` collection is populated from immutable
observations and canonical actuals.

### Lifecycle states

- `open`: kickoff has not passed.
- `pending_result`: match has started or finished but no canonical final
  result is available.
- `missing_actual`: final match exists but the exact stat/period/scope actual
  cannot be resolved.
- `resolved_predictor_only`: predictor result exists but no eligible frozen
  market offer exists.
- `resolved_market`: predictor and market results both exist.
- `excluded_timing`: the observation was not captured under the T-1D timing
  contract.
- `excluded_mapping`: an exact canonical identity could not be established.

### Predictor verdict

For an OVER selection:

```text
signed_residual = actual_value - frozen_league_baseline
```

For an UNDER selection:

```text
signed_residual = frozen_league_baseline - actual_value
```

The predictor verdict is `hit` when the signed residual is positive, `miss`
when negative, and `push` when zero. The UI calls this `Prediktorträff`, not a
won or lost bet.

### Market verdict and return

The exact frozen line determines `win`, `loss`, or `push` in the selected
direction. An eligible observation carries one virtual unit:

- win: `pnl_units = selected_odds - 1`;
- loss: `pnl_units = -1`;
- push: `pnl_units = 0`;
- ROI: aggregate PnL divided by aggregate eligible stake.

No market offer means null stake, PnL, ROI, and CLV. Predictor-only rows never
enter betting denominators.

## Closing, movement, and CLV

Closing lookup uses the same match, stat, period, scope, line, and direction as
the frozen T-1D offer. T-10 is preferred and T-30 is the accepted fallback.
The result stores actual closing checkpoint, observation time, age, odds, and
quality.

Price CLV is calculated only when the exact frozen line exists at accepted
closing. A different closing line is useful line-movement evidence but is not
substituted into price CLV. This prevents unlike markets from producing a
misleading percentage.

The movement series contains every valid prematch observation for the exact
frozen line, in chronological order. A parallel line-movement summary may
show that the main line changed, but it remains separate from same-line price
CLV.

## Predictor-quality metrics

The aggregate predictor service operates on one selected direction per exact
context and reports:

- resolved, pending, missing, and excluded coverage;
- hit/loss/push counts and non-push hit rate against frozen league baseline;
- mean and median signed residual;
- score bands 50-59.9, 60-69.9, 70-79.9, 80-89.9, and 90-100;
- top-20 daily lift versus the remaining selected daily universe;
- Spearman rank correlation between frozen score and signed residual;
- 95% confidence intervals clustered by `match_key` because multiple
  statistics from one match are correlated;
- breakdowns by stat, period, scope, league, ranking method, and date window.

The score is not probabilistic, so Brier score, calibration error, and labels
such as `93.4% chans` are prohibited until a separately versioned probability
calibration model exists.

Metrics are always accompanied by sample and coverage counts. Samples under
30 selected contexts show `För tunt`. Descriptive reporting starts at 30.
The product may call the ranking a supported predictor only after at least 300
resolved selected contexts across at least 100 matches and 30 fixture dates,
with the lower clustered 95% confidence bound for top-20 lift above zero.

## Market-quality metrics

Market aggregates are strictly limited to `resolved_market` rows and report:

- eligible-offer coverage among resolved predictor observations;
- win/loss/push and non-push hit rate;
- flat one-unit PnL and ROI at frozen T-1D odds;
- accepted closing coverage split by T-10 and T-30;
- mean and median same-line CLV;
- beat/match/miss-closing counts;
- breakdowns by stat, period, scope, league, and date window.

No green efficacy claim is allowed before 300 resolved market observations.
Predictor support does not imply positive ROI or CLV, and market performance
does not rewrite predictor metrics.

## Read API

Dashboard and match-detail matchup summaries add a nested contract:

```text
evaluation.predictor
evaluation.market
evaluation.closing
evaluation.provenance
```

`predictor` contains status, actual, frozen league baseline, signed residual,
verdict, and sample eligibility. `market` contains eligibility/reason, frozen
line, selected odds, settlement verdict, virtual stake, and PnL. `closing`
contains accepted checkpoint, same-line closing odds, CLV, beat-close state,
and exact-line movement history. `provenance` contains policy, timing, method,
and legacy/forward evidence labels.

A separate aggregate endpoint returns predictor and market metrics with exact
denominators. The frontend must not derive ROI, confidence intervals, or
coverage by combining paginated card data.

## Frontend

Upcoming cards retain score, rank, form method, league baseline, and available
market context. Finished cards add two explicit rows:

```text
Prediktor: TRÄFF · Utfall 14 mot ligasnitt 11.7 · +2.3
Marknad: VUNNEN · Över 10.5 @ 1.94
```

When no eligible market exists:

```text
Prediktor rättad · Ingen jämförbar spelmarknad
```

This state is neither a loss nor an error. Pending and missing actuals are
named explicitly.

Hover, keyboard focus, and touch activation open the same exact-market panel.
It shows the T-1D frozen offer, chronological odds movement, T-30/T-10 close,
line movement, and whether same-line CLV was computable. The information is
never hover-only.

The overview adds summary cards for:

- corrected predictor contexts and coverage;
- predictor hit rate and top-20 lift;
- market eligibility coverage;
- market ROI;
- accepted mean CLV and beat-close rate.

Predictor and market summaries are visually separated and include their own
denominators. Filters cover date window, evidence class, league, stat, period,
scope, ranking method, and outcome state.

## Legacy migration and recovery

Existing `matchups_score` rows are backfilled with canonical actuals wherever
possible. They are labelled `legacy_descriptive` because their row-level
creation time is absent. Existing prematch odds can be linked for descriptive
coverage, but those rows cannot enter forward predictor, ROI, or CLV proof.

The recovery job independently audits every old `pending_result`,
`missing_actual`, and null-status row against canonical fixture lifecycle and
actual-stat availability. It distinguishes genuinely unfinished/rescheduled
fixtures from missed enrichment or settlement. It does not mark a row failed
merely because the source has no applicable stat.

Historical score rows are not rewritten to the new ranking method. New
forward observations start a clean versioned evidence series.

## Error handling and audits

The implementation must distinguish:

- valid no-market coverage;
- market source or mapping failure;
- late or invalid predictor capture;
- missing canonical final result;
- missing exact actual statistic;
- immutable observation replay;
- immutable observation conflict;
- accepted T-30 closing with missed T-10;
- missing same-line close despite available different-line movement.

Each capture and settlement run writes due, captured, replayed, conflicted,
resolved, pending, missing, market-eligible, closing-covered, and excluded
counts. Audit rows include exact affected match keys without secrets.

An immutable conflict, timing violation, or attempted non-V2 write fails the
job. Valid no-market and predictor-only results are successful domain states.

## Testing and acceptance

Implementation is test-driven and must cover:

- complementary OVER/UNDER deduplication into one selected context;
- exact 50.0 ties excluded from aggregate denominators;
- T-1D timing boundaries and late-fixture exclusion;
- deterministic nearest-2.00 market selection and all tie-breakers;
- inclusive 1.80 and 2.20 boundaries;
- immutable insert, exact replay, and conflicting replay;
- actual resolution for total, home, and away scopes in all periods;
- predictor hit, miss, and push residuals;
- market win, loss, push, PnL, and ROI;
- exact-line T-10 preference and T-30 fallback;
- different-line movement not becoming price CLV;
- clustered aggregates and daily top-20 comparison;
- legacy rows excluded from forward proof;
- pending/missing recovery and idempotent rerun;
- read API nullability, denominators, evidence class, and movement history;
- frontend predictor-only, market-resolved, pending, legacy, keyboard, hover,
  and touch states;
- no effects on V6 selection, forward bets, model ROI, or model CLV.

Local completion requires targeted backend tests, the full V2 suite, frontend
tests, TypeScript, ESLint, production build, workflow contract tests, and
`git diff --check`.

Production remains `PARTIAL` until untouched future fixtures prove:

```text
T-1D immutable matchup capture
-> canonical post-match actual
-> predictor verdict
-> exact market verdict when eligible
-> T-10 or T-30 same-line close
-> API and UI rendering
-> idempotent replay
```

Historical backfill cannot satisfy this forward acceptance gate.

## Non-goals

- No probability reinterpretation of the matchup score.
- No fabricated odds or league-average proxy odds for unavailable markets.
- No cross-line price CLV.
- No automatic betting selection or change to V6 policy.
- No mutation of legacy databases, raw source evidence, settled outcomes, or
  existing model journals.
- No claim that descriptive historical accuracy proves future profitability.
