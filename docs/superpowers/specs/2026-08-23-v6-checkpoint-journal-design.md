# V6 Full-Domain Checkpoint Journal Design

## Objective

Build an automatic shadow-bet journal that records every supported positive-EV
V6 observation at each captured pre-match odds checkpoint, settles every
observation for one unit, measures CLV against the official T-10 close, and
groups repeated observations of the same market into one simple UI row.

The journal is forward evidence only. It must not rewrite the frozen V1 policy,
reclassify old rows, or present descriptive ROI as proven future edge.

## Supported model contract

The frozen `ev_scope_interaction_recency45_asof_capped_v6_shadow` artifact
supports these categorical values:

- stat keys: `cornerKicks`, `shotsOnGoal`, `totalShots`
- scopes: `home`, `away`, `total`
- periods: `1ST`, `2ND`, `ALL`
- leagues: the six leagues embedded in the artifact training domain

The checkpoint journal records:

- `cornerKicks`: `over` and `under`
- `shotsOnGoal`: `over` only
- `totalShots`: `over` only

The shot-stat direction restriction is deliberately conservative because the
historical Unibet corpus used for the frozen model contained over-only offers
for those stat keys. Other Unibet stat keys remain visible as
`model_missing`; they do not receive invented probabilities or EV values.

## Policy and evidence boundaries

`forward_policy_registry_v1` is immutable after its first forward settlement.
It remains untouched. A new registry and policy are timestamped before their
first eligible future observation:

- registry: `forward_policy_registry_v2`
- policy: `v6_full_domain_checkpoint_journal_v2`
- status: `forward_test_exploratory`
- stake: `1.0` unit per checkpoint observation
- EV gate: strictly greater than `0.0`
- upper EV gate: none; extreme positive observations remain auditable instead
  of being silently deleted
- selection granularity: `checkpoint_observation`

V1 and V2 must always be filterable by policy. Their results must never be
silently pooled into promotion evidence.

## Immutable observation model

Every normalized market snapshot is scored once per model side. The existing
score key already contains the snapshot key and direction. The V2 prediction
key contains policy ID plus score key, so the same market at T-3D and T-2H is
two immutable prediction records.

Checkpoint rows carry `snapshot_label`, `snapshot_type`, and
`selection_granularity`. The canonical evaluation key includes the snapshot
identity only for `checkpoint_observation` rows. Legacy rows and V1 retain the
existing one-exposure canonicalization behavior.

Repeated execution is idempotent. It may observe an existing immutable row,
but it may not update its odds, probability, EV, timing, feature fingerprint,
or policy provenance.

## Grouping and performance semantics

The storage, settlement, CLV, and result layers retain every checkpoint
observation. Grouping happens only in the read layer.

The group identity is:

`policy + match + stat_key + scope + period + direction + line`

The group representative is the observation with the highest recorded EV;
ties use the earliest valid observation and then the immutable prediction key.
The UI shows that representative price and EV plus:

- observation count
- checkpoint labels represented
- aggregate stake and PnL
- group ROI (`sum(PnL) / sum(stake)`)
- official CLV observation count
- number and rate that beat the official close
- mean official CLV

This does not pretend the best historical checkpoint was known in advance.
Checkpoint filters calculate separate T-3D, T-2D, T-1D, T-2H, T-30 and T-10
portfolios from the observations actually available at each horizon.

## Automatic lifecycle

After each successful checkpoint or closing odds capture, V6 scoring runs with
the V2 registry. New positive-EV observations are persisted.

The hourly post-match workflow executes, in order:

1. settle forward bets against canonical match statistics;
2. refresh CLV from materialized closing lines;
3. refresh the forward result read collection.

All three operations are idempotent. Missing results, stats, or official T-10
closing lines remain explicit lifecycle statuses rather than fabricated
outcomes.

## Read API and UI

`/api/v1/auto` and `/api/v1/results` accept existing stat, scope, period,
direction, league, model, and policy filters plus a new `checkpoint` filter.
They paginate grouped rows while summaries count underlying 1u observations.

Auto and Resultatloop show filters for stat key, scope, period, direction, and
checkpoint. Auto keeps V6 and legacy provenance visibly separate. Match odds
show whether each market is supported by V6, partially supported by direction,
or missing a trained model.

## Failure boundary and expensive unknown

The strongest failure mode is silently mixing repeated checkpoint observations
with one-exposure V1 evidence, which would inflate sample counts and corrupt
ROI/CLV interpretation. Granularity-aware canonical keys and explicit policy
filters prevent that.

The most expensive unvalidated assumption remains that V6's historical signal
survives new in-domain matches with sufficient official T-10 closing coverage.
This implementation measures that assumption; it does not claim it is true.

