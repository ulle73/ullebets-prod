# Ullebets V2 EV Model Experiments

This log records every material offline model experiment, including failed
experiments. A model is not eligible for forward use merely because its
historical ROI is positive.

## Evaluation protocol

- Historical source: the normalized Offline V1 Parquet corpus.
- Primary targets: `cornerKicks`, `shotsOnGoal`, and `totalShots`.
- Odds must be strictly pre-match.
- One canonical observation per match, stat, period, and scope.
- `shotsOnGoal` and `totalShots` are over-only markets.
- Current-match outcomes and unversioned support rankings are forbidden features.
- Development model selection ends on 2026-04-30.
- May 2026 is reserved as the final chronological holdout.
- Candidate selection uses count/probability quality and calibration before ROI.
- ROI is calculated with flat one-unit stakes and exact win/push/loss rules.

## Experiment 000: Original Offline V1 Poisson

Status: invalidated by direct outcome leakage.

- Reported selections: 3,555
- Reported ROI: +20.09%
- Direct current-match feature columns: 16
- Leakage examples: current home/away corner, shots-on-goal, and shot values

The original feature selector accepted every numeric column containing
`__team_`, including the current match's `team_value`. The result cannot be used
as evidence of an edge.

## Experiment 001: Leakage-safe Offline V1 Poisson

Status: rejected.

- Input modeling rows: 14,033
- Unique matches: 1,089
- Numeric features: 276
- Categorical features: 4
- Selections: 3,494
- PnL: -341.63 units
- ROI: -9.78%

Window results:

| Test window | Bets | ROI |
| --- | ---: | ---: |
| 2026-02-19 to 2026-03-04 | 1,023 | -10.49% |
| 2026-03-05 to 2026-03-18 | 690 | -13.25% |
| 2026-03-19 to 2026-04-01 | 446 | -11.65% |
| 2026-04-02 to 2026-04-15 | 316 | -5.88% |
| 2026-04-30 to 2026-05-13 | 428 | -8.39% |
| 2026-05-14 to 2026-05-27 | 591 | -6.17% |

Conclusion: removing current-match outcomes eliminates the reported positive
signal. The old Poisson implementation remains a benchmark only.

## Experiment 002: Compact count-model candidates

Status: no general edge.

Development period ended on 2026-04-30. Five count candidates were compared
using identical chronological predictions and Poisson line probabilities.

| Model | Bets at 0% EV | ROI |
| --- | ---: | ---: |
| Market-residual HGB | 1,995 | -5.06% |
| Historical baseline | 2,049 | -10.42% |
| HGB Poisson | 1,709 | -11.11% |
| Poisson GLM | 2,633 | -11.33% |
| Unibet market anchor | 864 | -19.38% |

The market-residual model had the best count MAE (`2.110`) but its predicted
probabilities were severely overconfident. Predictions above 80% won only
51.6% of selected bets.

Full artifacts: `data/v2/ev_model/experiment_002/`.

## Experiment 003: Negative-binomial distribution

Status: no general edge; retained as the preferred count distribution.

Dispersion was estimated separately by stat, period, and scope using each
training window only. Negative binomial improved the residual model slightly:

- 0% EV gate: -4.63% ROI
- 5% EV gate: -4.69% ROI
- 10% EV gate: -4.52% ROI

The distribution fixed part of the Poisson overconfidence but did not create a
general profitable strategy.

Full artifacts: `data/v2/ev_model/experiment_003/`.

## Experiment 004: Sequential beta calibration

Status: no general edge; one segment promoted to holdout candidate.

Beta calibration was trained only on prior out-of-sample windows. It improved
Brier scores materially, but every overall strategy remained negative.

The strongest development segment was frozen as:

- Model: `hgb_poisson`
- Distribution: `negative_binomial`
- Stat: `cornerKicks`
- Period: `2ND`
- Scope: `home`
- Minimum calibrated EV: `2%`
- Development bets: `37`
- Development PnL: `+12.22` units
- Development ROI: `+33.03%`
- Window ROI: `+26.25%`, `+52.92%`, `+18.56%`
- Wins/losses: `24/13`
- Naive match bootstrap 95% interval: `+0.43%` to `+63.65%`

The interval does not correct for searching across multiple candidates. This
configuration is therefore only a pre-registered holdout hypothesis.

Full artifacts: `data/v2/ev_model/experiment_004/`.

## Frozen May holdout protocol

- Holdout dates: 2026-05-01 through 2026-05-24.
- No model, distribution, segment, direction, or threshold changes.
- The holdout is evaluated once.
- Flat one-unit staking.
- A positive result remains provisional until repeated in forward testing.

## Experiment 005/006: Frozen May holdout

Status: rejected.

The frozen `cornerKicks / 2ND / home` configuration was evaluated without
changing the model, distribution, calibration, segment, or EV threshold.

- Holdout bets: `32`
- Wins/losses: `15/17`
- Holdout PnL: `-0.61` units
- Holdout ROI: `-1.91%`
- First holdout window: `19` bets, `+0.05%` ROI
- Second holdout window: `13` bets, `-4.77%` ROI
- Naive bootstrap 95% interval: `-38.09%` to `+34.06%`

Conclusion: the development result did not replicate. The candidate must not be
promoted as a +EV production model.

Full artifacts:

- `data/v2/ev_model/experiment_005_holdout_predictions/`
- `data/v2/ev_model/experiment_006_holdout_calibration/`

## Experiment 007: Direct line classifiers

Status: promising probability model, unstable betting result.

Instead of predicting a count and imposing a count distribution, this
experiment predicted win/loss directly for every offered side. Two-sided
markets received a total sample weight of one per market.

| Model | Brier | Bets at 2% EV | ROI |
| --- | ---: | ---: | ---: |
| HGB classifier | 0.2441 | 184 | +2.68% |
| Logistic classifier | 0.2444 | 104 | -6.85% |
| Market probability | 0.2486 | 0 | 0.00% |

The HGB classifier beat the market baseline on Brier score, but its 2% EV
window results were `-5.21%`, `-2.34%`, `-3.74%`, and `+58.11%`. The aggregate
profit came entirely from the final 19-bet window and is not stable enough for
promotion.

Full artifacts: `data/v2/ev_model/experiment_007_line_classifier_dev/`.

## Experiment 008: Calibrated direct line classifier

Status: frozen secondary holdout hypothesis.

Sequential beta calibration removed the raw classifier's 2% result. The best
remaining development configuration was frozen as:

- Model: `hgb_classifier`
- Probability calibration: sequential beta calibration
- Minimum calibrated EV: `5%`
- Development bets: `77`
- Development PnL: `+3.91` units
- Development ROI: `+5.08%`
- Window ROI: `-6.53%`, `+0.28%`, `+48.57%`

The profit is again concentrated in the latest development window. This
configuration is evaluated unchanged on May and is not eligible for further
historical threshold adjustment afterward.

Full artifacts: `data/v2/ev_model/experiment_008_line_classifier_calibrated/`.

## Experiment 009/010: Frozen direct-classifier May holdout

Status: rejected.

The frozen `hgb_classifier` configuration was evaluated without changing the
model, calibration method, eligible markets, or 5% calibrated-EV threshold.

- Holdout bets: `233`
- Unique matches: `91`
- Wins/losses: `104/129`
- Holdout PnL: `-17.11` units
- Holdout ROI: `-7.34%`
- First holdout window: `52` bets, `-6.83%` ROI
- Second holdout window: `181` bets, `-7.49%` ROI
- Over bets: `70`, `-5.06%` ROI
- Under bets: `163`, `-8.33%` ROI
- Match-clustered bootstrap 95% interval: `-21.35%` to `+7.48%`

The negative result is consistent across both holdout windows and both
directions. Some small stat/period/scope slices were positive, but those slices
were inspected only after opening the holdout and are therefore exploratory,
not new evidence of an edge.

Conclusion: the direct classifier's development profit did not replicate. It
must not be promoted as a +EV production model.

Full artifacts:

- `data/v2/ev_model/experiment_009_line_classifier_holdout_predictions/`
- `data/v2/ev_model/experiment_010_line_classifier_holdout_calibrated/`

## Experiments 011-019: One-row-per-market classifiers

Status: one exploratory candidate, not independently proven.

The earlier direct classifier represented over and under as separate training
rows. The replacement predicts `P(over)` once per market and always derives
`P(under) = 1 - P(over)`. This removes incoherent two-sided probabilities.

Results through 2026-04-30:

| Experiment | Best relevant result | Decision |
| --- | --- | --- |
| 011 compact market model | Logistic Brier `0.2447`; all raw EV gates negative | Keep probability benchmark |
| 012 broad context history | Best Brier `0.2467`; all EV gates negative | Reject broad feature set |
| 013 side calibration | Logistic 5% gate: `112` bets, `+3.65%` ROI | Superseded by coherent calibration |
| 014/015 exact-line history | HGB 0% gate: `502` bets, `+2.41%`, one negative window | Reject as unstable |
| 016-019 compact full/coherent | Logistic 5% gate: `216` bets, `+5.07%` ROI | Exploratory only |

The coherent market-level calibration in experiments 018/019 preserved
complementary probabilities. It happened to select the same bets as the old
side calibration, so experiment 019 supersedes experiment 017 without changing
its ROI.

CLV cannot validate the 5% configuration: only `2/216` selected bets had a CLV
value and both values were zero.

## Experiment 020: Empirical Bayes exact-line hit rate

Status: rejected.

This experiment directly tested the proposed rule "historical hits against the
current line divided by historical matches." It used only matches before the
current kickoff, combined the team's attacking history with the opponent's
allowed history, deduplicated prior head-to-head matches, and shrank the
observed rate toward the current market probability with an eight-match prior.

- Brier: `0.2534`
- 0% EV gate: `1,798` bets, `-11.52%` ROI
- 5% EV gate: `1,207` bets, `-12.16%` ROI

Conclusion: an observed rate such as 8/10 is not a usable fair probability by
itself. Opponent, price, sample uncertainty, and non-stationarity matter.

Full artifacts: `data/v2/ev_model/experiment_020_empirical_bayes_line_dev/`.

## Experiment 021: Nested temporal calibration

Status: rejected.

Each 90-day training window was split into model-training and a final 21-day
calibration period. Both ended before the test period. Every model and EV gate
was negative; the logistic 5% gate returned `363` bets and `-8.83%` ROI.

Full artifacts: `data/v2/ev_model/experiment_021_nested_market_calibration_dev/`.

## Experiments 022-027: Window and recency robustness

Status: 45-day recency weighting retained.

| Configuration | Relevant result | Decision |
| --- | --- | --- |
| 60-day rolling window | Logistic 5% calibrated: `-10.00%` | Reject |
| 120-day rolling window | Logistic 5% raw: `+6.01%`; calibrated: `-1.40%`; only 1,044 predictions | Reject as sparse/unstable |
| 90-day window, 45-day half-life | Logistic 5% raw: `367` bets, `+6.49%` | Retain for robustness test |
| Same, sequentially calibrated | Logistic 5%: `118` bets, `-0.81%` | Do not calibrate |

The retained model uses training weights
`weight = 0.5 ** (age_days / 45)`. It was positive in three of four development
windows at a 5% EV gate. The uncalibrated logistic probabilities also had a
better development Brier score (`0.2448`) than the market (`0.2486`).

## Experiment 028: Recency model full-history replication

Status: superseded because snapshot-relative feature timing was incomplete.

The unchanged 90-day logistic model with 45-day recency weighting produced:

- 5% EV gate: `611` bets, `+37.87` units, `+6.20%` ROI
- May contribution: `244` bets, `+14.05` units, `+5.76%` ROI
- 5/6 full windows positive

A threshold robustness scan found a positive plateau around 6.5%-9.0% model
EV. A 7.5% gate was selected as a conservative midpoint:

- Bets: `360`
- Unique matches: `168`
- Wins/losses: `207/153`
- PnL: `+41.35` units
- ROI: `+11.49%`
- Positive windows: `6/6`
- May: `170` bets, `+19.03` units, `+11.19%` ROI
- Match-clustered 95% interval: `-0.55%` to `+23.29%`
- Bootstrap probability of positive ROI: `96.93%`

The result is broad across direction, primary stat, period, and scope. Removing
Serie A still leaves `250` bets at `+6.28%` ROI. Ligue 1 is negative.

This is not a clean confirmatory result. The 7.5% threshold was chosen after
multiple model and threshold comparisons, and May had already been inspected
by earlier experiments. The clustered interval also still includes zero.

Later inspection found that `12/360` selections used at least one historical
match result which occurred before the target kickoff but was not yet available
at the selected odds snapshot. There were `24` such historical observations.
This result must not be used as evidence for the shadow model.

Full artifacts: `data/v2/ev_model/experiment_028_compact_recency45_full/`.

## Experiment 029: Hierarchical segment models

Status: rejected.

Separate logistic relationships by stat and by stat/period/scope materially
overfit. The hierarchical 5% result was `1,438` bets at `-6.24%` ROI.

Full artifacts: `data/v2/ev_model/experiment_029_hierarchical_recency45_dev/`.

## Experiment 030: Frozen candidate integrity audit

Status: superseded; kickoff-relative checks passed but snapshot-relative
feature timing was not yet enforced.

- Prematch odds: `360/360`
- Odds at/after kickoff: `0`
- Missing snapshot or match start: `0`
- Snapshot source: `unibet-backtest snapshots.snapshot_fetched_at`
- Match-start source: `teamstats.kickoff_ts`
- Duplicate market/side exposures: `0/0`
- Settlement mismatches: `0`
- Forbidden model features: `0`
- Training rows at/after target match: `0`
- CLV coverage: `3/360` (`0.83%`)

Full artifacts: `data/v2/ev_model/experiment_030_frozen_candidate_audit/`.

## Experiment 031: Snapshot-as-of correction

Status: retained for shadow testing only.

Every rolling team statistic was rebuilt at the exact odds snapshot time. A
historical match becomes available only at:

`historical kickoff + 3 hours < target odds snapshot`

The correction excluded all `24` observations identified after experiment 030.
No observation at or after the target snapshot was used.

At the frozen 7.5% model EV gate:

- Bets: `363`
- Unique matches: `166`
- Wins/losses: `204/159`
- PnL: `+33.23` units
- ROI: `+9.15%`
- Positive walk-forward windows: `6/6`
- Match-clustered 95% interval: `-2.98%` to `+20.99%`
- Bootstrap probability of positive ROI: `93.08%`
- Prematch odds: `363/363`
- Settlement mismatches: `0`
- Duplicate market/side exposures: `0/0`
- Forbidden model features: `0`
- Snapshot-relative history leakage: `0`
- CLV coverage: `4/363` (`1.10%`)

The result remains materially uncertain. The interval includes zero, CLV is
almost absent, and the model/threshold were selected after many comparisons.
It permits shadow testing, not real-money promotion.

Full artifacts:

- `data/v2/ev_model/experiment_031_asof_snapshot_recency45_full/`
- `data/v2/ev_model/candidate_031_asof_snapshot/`
- `data/v2/ev_model/shadow_candidate_asof_v2/`

## Experiment 032: Extreme-edge abstention

Status: retained as the next shadow policy.

The snapshot-as-of model was stress-tested without changing its probability
estimator. Predictions above 25% model EV were treated as unsupported
extrapolation:

- 7.5%-10% EV: `161` bets, `+11.45%` ROI
- 10%-15% EV: `127` bets, `+10.28%` ROI
- 15%-25% EV: `56` bets, `+6.54%` ROI
- 25%+ EV: `19` bets, `-10.11%` ROI

The 25%+ group predicted a mean win probability of `63.71%` but won only
`42.11%`. The model is not allowed to convert this extrapolation into larger
confidence. The v3 policy therefore requires:

`7.5% < model EV < 25%`

With the upper abstention gate:

- Bets: `344`
- Unique matches: `165`
- Wins/losses: `196/148`
- PnL: `+35.15` units
- ROI: `+10.22%`
- Positive walk-forward windows: `6/6`
- Match-clustered 95% interval: `-2.51%` to `+22.40%`
- Bootstrap probability of positive ROI: `94.40%`
- Prematch odds: `344/344`
- Duplicate exposures and settlement mismatches: `0`

Additional fixed-policy stress results:

- Actual/model/market win probability: `56.98%` / `57.23%` / `48.10%`
- Model/market Brier: `0.2397` / `0.2480`
- Model/market log loss: `0.6721` / `0.6892`
- ROI after a 3% decimal-odds haircut: `+6.91%`
- ROI after a 5% decimal-odds haircut: `+4.71%`
- ROI after a 10% decimal-odds haircut: `-0.80%`
- Maximum historical drawdown: `-12.43` units
- Maximum losing streak: `10`
- ROI excluding Serie A: `+5.27%`
- Removing the five best match clusters leaves `+3.26%` ROI
- Removing the ten best match clusters leaves `-2.06%` ROI

The calibration metrics are better than the market on this selected history,
and the result survives moderate price degradation. Profit concentration is
still material: the ten best match clusters contribute `41.22` units against
total profit of `35.15` units. This is another reason not to promote before a
larger forward sample exists.

This is a risk-control improvement, not new confirmatory evidence. The cap was
introduced after inspecting the historical result, so it must be judged on
future prediction rows under a new model id:
`ev_logistic_recency45_asof_capped_v3`.

Full artifacts:

- `data/v2/ev_model/candidate_032_asof_capped/`
- `data/v2/ev_model/candidate_032_asof_capped/robustness/`
- `data/v2/ev_model/shadow_candidate_asof_capped_v3/`
- `models/ev/ev_logistic_recency45_asof_capped_v3/`

## Experiment 033: Market shrinkage and temporal policy selection

Status: challenger retained for future score-level evaluation; V3 unchanged.

The frozen experiment 031 predictions were used to test probability shrinkage
toward the market and correlated match exposure. No model was retrained and no
new outcome data was added.

Canonical-line audit:

- Model sample keys: `5,458`
- Sample keys with multiple modeled lines: `0`
- Maximum modeled lines per match/stat/period/scope: `1`

Therefore, V3 does not stack an alternate-line ladder. It can still select
different stat/period/scope segments from the same match, with up to six
historical bets on one match.

Fixed market blends use:

`p_blended = p_market + alpha * (p_model - p_market)`

Results at the unchanged 7.5%-25% EV gate:

- `alpha=1.00`, no match cap: `344` bets, `+10.22%`, `6/6` windows
- `alpha=1.00`, maximum three bets per match: `301` bets, `+7.81%`,
  `6/6` windows
- `alpha=0.75`, no match cap: `119` bets, `+4.61%`, `4/6` windows
- `alpha=0.75`, maximum three bets per match: `107` bets, `+6.31%`,
  `4/6` windows

A temporal challenger selected alpha only by Brier score on earlier OOS
windows, with two warmup windows and a maximum of three bets per match. On the
four later untouched-at-selection windows it produced:

- Bets: `93`
- Matches: `54`
- PnL: `+18.45` units
- ROI: `+19.84%`
- Positive windows: `4/4`
- Maximum drawdown: `-6.00` units
- Match-clustered 95% interval: `-2.05%` to `+40.63%`
- Bootstrap probability of positive ROI: `96.24%`

The chosen alpha was `1.00` for the first evaluation window and `0.75` for
the following three. This is promising, but 54 match clusters are insufficient
and the interval still crosses zero. A fixed 0.75 blend is not stable across
all six windows, so the nested result does not justify replacing V3.

An additional model-consensus gate requiring at least one of hierarchical
logistic, HGB, or residual HGB to show positive EV produced `275` bets,
`+10.83%` ROI, and `6/6` positive windows. Its clustered interval worsened to
`-3.67%` to `+24.67%`; consensus with historically losing models is therefore
rejected.

No segment is removed based on the displayed segment ROI. In particular,
shots-on-goal home (`19` bets, `+46.42%`) and negative segments are too small
for a defensible router. Experiment 029 already showed that separately fitted
segment models worsened generalization.

Full artifacts:

- `data/v2/ev_model/experiment_033_policy_optimization/`

## Experiment 034: Snapshot-horizon transfer audit

Status: V3 unchanged; forward capture policy expanded.

The historical V3 selections were compared with V2's production checkpoint
windows. This exposed a major forward-test mismatch:

- Historical V3 selections: `344`
- Covered by T-3D/T-2D/T-1D/T-10M: `59` (`17.15%`)
- Not covered by the original checkpoint windows: `285`
- Historical selections in the T-1D 18-36 hour window: `0`
- Historical selections 1-18 hours before kickoff: `239`

The largest historical horizon buckets were:

- 1-3 hours: `77` bets, `+0.66%` ROI
- 3-6 hours: `6` bets, `+73.17%` ROI
- 6-12 hours: `114` bets, `+11.62%` ROI
- 12-18 hours: `42` bets, `+28.24%` ROI
- 36-60 hours: `42` bets, `-13.93%` ROI

The small buckets must not be interpreted as standalone edge estimates. The
important result is coverage: a forward test that only captures the original
four checkpoints does not reproduce the historical information horizon on
which V3 selected most bets.

Two supplementary research checkpoints were added:

- `T_MINUS_12H`: 6-18 hours before kickoff
- `T_MINUS_2H`: 1-6 hours before kickoff

The original four required checkpoints remain unchanged. The expanded policy
covers `298/344` historical selection horizons (`86.63%`), an increase of
`239` rows. This changes data collection, not model probabilities or EV rules.

The first attempted real T-12H capture correctly produced zero rows because
the four apparent 18:00 fixtures had become `postponed`; the target loader
excluded them. Replay and policy tests verify the new windows until a real
playable fixture becomes due.

Full artifacts:

- `data/v2/ev_model/experiment_034_snapshot_horizons/`

## Experiment 035: Snapshot-as-of exact-line hit history

Status: rejected; V3 unchanged.

The exact-line hit-rate hypothesis from experiment 020 was rebuilt at the
exact odds snapshot. Historical statistics became eligible only after:

`historical kickoff + 3 hours < target odds snapshot`

This excluded `24` observations that a kickoff-only history would have used.
No observation at or after the target snapshot was used. Features included
attack, opponent-allowed, combined hit/push rates, sample counts, and an
Empirical-Bayes posterior shrunk toward the current market probability.

Results:

- Empirical-Bayes line model, 5% gate: `1,660` bets, `-10.34%` ROI
- Logistic model with line-history features, V3 7.5%-25% gate:
  `551` bets, `-26.97` units, `-4.89%` ROI
- Positive logistic windows: `1/6`
- Nested Brier-selected market shrinkage: `80` bets, `+8.49%` ROI,
  but only `2/4` positive windows
- Nested match-clustered 95% interval: `-12.63%` to `+29.11%`

The raw "hits divided by matches" signal is not sufficient. Adding it to the
model materially worsens probability quality and betting stability. Positive
small segments and fixed shrinkage variants are not promoted because they were
found after inspecting outcomes and do not generalize across windows.

Full artifacts:

- `data/v2/ev_model/experiment_035_asof_line_history_recency45_full/`

## Experiment 036: Snapshot-horizon-aware classifier

Status: rejected; V3 unchanged.

The compact snapshot-as-of model was extended with only two predefined timing
features: a categorical prematch horizon bucket and log-transformed hours to
kickoff. Buckets were defined from the production capture schedule before
examining the result; no profitable historical horizon was selected.

Results:

- Brier: `0.2472` versus market `0.2485`
- Raw 7.5%-25% EV policy: `625` bets, `-24.78` units, `-3.96%` ROI
- Positive raw-policy windows: `4/6`
- Nested Brier-selected shrinkage: `189` bets, `+15.28` units,
  `+8.08%` ROI and `4/4` positive later windows
- Nested match clusters: `84`
- Nested 95% interval: `-7.90%` to `+23.99%`
- Bootstrap probability of positive ROI: `83.84%`

The nested result is positive but less statistically convincing than the
existing V3 challenger: its lower bound is materially below zero and the raw
model loses money. Horizon features are therefore not promoted or added to the
production artifact.

Full artifacts:

- `data/v2/ev_model/experiment_036_asof_horizon_recency45_full/`

## Experiment 037: Nested temporal logistic regularization

Status: retained as a score-only shadow challenger; V3 unchanged.

The compact V3 feature set was retained, but logistic regularization was
selected independently inside every walk-forward window. Each outer test
window used a 90-day training history. Only the final part of that earlier
training history was used as an inner validation window to choose `C` by Brier
score; the chosen model was then refit on the complete earlier 90-day window.
No outer test outcome was used for model or policy selection.

Primary 21-day inner-validation result:

- Bets: `173`
- Match clusters: `99`
- Profit: `+23.21` units
- ROI: `+13.42%`
- Positive outer windows: `5/6`
- Maximum drawdown: `-10.48` units
- Match-clustered 95% interval: `-2.81%` to `+28.83%`
- Bootstrap probability of positive ROI: `94.712%`
- Timing, duplicate-exposure, and settlement violations: `0`

Predefined robustness variants were all historically positive and all had
`5/6` positive outer windows:

- 14-day validation: `144` bets, `+13.55%` ROI,
  95% interval `-5.09%` to `+31.50%`
- 28-day validation: `138` bets, `+13.04%` ROI,
  95% interval `-5.42%` to `+30.72%`
- 42-day validation: `97` bets, `+9.23%` ROI,
  95% interval `-11.27%` to `+29.85%`
- 21-day validation without `C=2`: `170` bets, `+14.27%` ROI,
  95% interval `-2.68%` to `+30.52%`
- 21-day strong-regularization grid: `162` bets, `+15.43%` ROI,
  95% interval `-1.14%` to `+31.39%`

The result is more stable than the rejected feature expansions, but every
confidence interval still crosses zero. The same historical November-May data
has also been inspected repeatedly. Promoting V4 or tuning stat/scope segments
from these outcomes would therefore increase overfitting rather than prove an
edge.

Full artifacts:

- `data/v2/ev_model/experiment_037_nested_regularization_full/`
- `data/v2/ev_model/experiment_037_nested_regularization_full/robustness/`

## Experiment 038: Candidate falsification and regime audit

Status: neither candidate confirmed; V3 remains primary shadow model.

This experiment did not search for another profitable subgroup. It attempted
to reject the already frozen V3 and V4 candidates using match-clustered
inference, leave-one-league-out, leave-one-test-window-out, calibration, and
recorded-price degradation. A conservative Bonferroni-style correction used
the `37` numbered experiments already inspected. That correction is not a
claim that the experiments are independent; it deliberately raises the
evidence bar.

V3:

- `344` bets, `165` matches, `+35.15` units, `+10.22%` ROI
- Match-clustered 95% interval: `-2.51%` to `+22.40%`
- One-sided centered-bootstrap null p-value: `0.0517`
- Experiment-count adjusted p-value: `1.0`
- Every leave-one-league-out result remained positive
- Minimum leave-one-league-out ROI: `+5.27%` without Serie A
- Every leave-one-window-out result remained positive
- Minimum leave-one-window-out ROI: `+8.52%`
- ROI after removing `0.10` from every winning decimal price: `+4.52%`
- Selected-bet Brier: model `0.2397`, market `0.2480`

V4:

- `173` bets, `99` matches, `+23.21` units, `+13.42%` ROI
- Match-clustered 95% interval: `-2.92%` to `+28.90%`
- One-sided centered-bootstrap null p-value: `0.0455`
- Experiment-count adjusted p-value: `1.0`
- Every leave-one-window-out result remained positive
- Removing Serie A produced `107` bets at `-0.78%` ROI
- Serie A contributed `+24.04` units versus `+23.21` total units
- ROI after removing `0.10` from every winning decimal price: `+7.64%`
- Selected-bet Brier: model `0.2421`, market `0.2515`

V3 is the stronger broad candidate because its edge survives every league and
outer-window jackknife. V4 is historically more profitable but materially
dependent on Serie A and remains a score-only challenger. Neither model meets
the predeclared confirmation gate because both clustered intervals cross zero
and neither survives the experiment-count correction.

Before any score selection had settled, the initial nine forward policies were
frozen in:

- `models/ev/score_policy_registry_v1.json`

They include the unchanged V3 primary policy plus model/stat diagnostics and
V4 corner challengers. Their registry fingerprint is persisted with every
score-policy audit. These policies do not create extra bets; they evaluate
the same immutable all-side scores and must be treated as one
multiple-comparison family.

Registry V1 was superseded before settlement by V2, which adds one
exposure-capped policy and freezes explicit promotion gates. V1 remains stored
for audit history.

Full artifacts:

- `data/v2/ev_model/experiment_038_candidate_falsification/`

## Experiment 039: Registered stat/scope policy diagnostics

Status: V4 corners away/total retained as the strongest score-only forward
hypothesis; no policy promoted.

The ten policies frozen in `score_policy_registry_v2.json` were evaluated as
one comparison family. The correction count was `47`: the previous `37`
numbered experiments plus all ten registered policies. Filters were applied
to the frozen V3/V4 historical selections; no new threshold, league, period,
or direction search was performed in this audit.

Only one policy passed the mechanical gate:

`v4_corners_away_total_challenger`

- Model: V4 nested temporal regularization
- Market: corners
- Scopes: away team and match total
- Periods: generic; `ALL`, `1ST`, and `2ND` preserved
- EV gate: strictly `7.5%` to `25%`
- Bets: `121`
- Match clusters: `77`
- Profit: `+34.53` units
- ROI: `+28.54%`
- Match-clustered 95% interval: `+8.23%` to `+47.52%`
- Family-adjusted one-sided p-value: `0.0376`
- Every leave-one-league-out result positive
- Minimum leave-one-league-out ROI: `+15.74%`
- Every leave-one-window-out result positive
- Minimum leave-one-window-out ROI: `+25.46%`
- ROI after removing `0.10` from each winning price: `+21.93%`
- Model Brier: `0.2312` versus market `0.2543`

All other registered policies failed at least one mechanical criterion. V3
all-target remains the broad primary policy at `+10.22%`, while V4 all-target
remains too dependent on Serie A. Shots-on-goal samples are small and
total-shots policies are historically negative.

The exposure-capped version keeps only the highest modeled EV per match:

- Bets/matches: `77/77`
- Profit: `+21.26` units
- ROI: `+27.61%`
- Match-clustered 95% interval: `+5.96%` to `+48.68%`
- Every leave-one-league/window result positive
- Family-adjusted p-value: `0.2021`

This proves the raw ROI is not created by duplicate or stacked match
exposure, but the smaller sample does not pass the 47-test significance gate.
It remains a separate score-only challenger.

The passing result is still not confirmatory evidence. The away/total scope
hypothesis was created after historical scope outcomes had been inspected.
Its valid role is therefore a frozen, score-only forward challenger. Its
filters, EV gate, registry fingerprint, and ten-policy comparison family were
persisted before any current forward selection settled. It must not create
additional `forward_bets`, and its policy cannot be changed after outcomes
arrive.

Registry V2 also freezes the forward promotion gate:

- At least `300` settled bets
- At least `150` independent match clusters
- At least `80%` CLV coverage
- Positive mean CLV
- Positive match-clustered 95% lower bound
- Ten-policy adjusted p-value below `0.05`
- Zero timing, outcome, duplicate, and feature-audit errors

The automated evaluator currently reports `insufficient_evidence` for all ten
policies: both model archives have audit status `ok`, but there are `0`
settled score selections and `0%` closing-line coverage.

Full artifacts:

- `data/v2/ev_model/experiment_039_registered_policy_diagnostics/`

## Experiment 040: Prior-window-only scope routing

Status: strong temporal support for away/total corners; research-only router.

A prequential router tested whether the V4 scope pattern could have been
learned without reading the current or future test window. For each outer
walk-forward window, it calculated each scope's sample and ROI from earlier
outer windows only. The router then either included or abstained from home,
away, and total for the target window.

The predefined grid contained:

- Cold start: include or abstain
- Minimum prior bets per scope: `5`, `10`, `20`, or `30`
- Minimum prior ROI: `0%`, `5%`, or `10%`
- One additional one-bet-per-match sensitivity
- Router variants: `25`
- Total corrected comparison family: `72`

Temporal integrity:

- Router decision rows using future outcomes: `0`
- Prior-window timestamps at/after target window: `0`

The central abstain rule required at least `10` earlier bets and positive
earlier ROI before enabling a scope:

- Bets: `86`
- PnL: `+30.53` units
- ROI: `+35.50%`
- Match-clustered 95% interval: `+14.22%` to `+54.80%`
- 72-test adjusted p-value: `0.0101`
- Every leave-one-league/window result positive

The result was not isolated to one router setting. Abstain variants with
minimum samples `5`, `10`, and `20`, and prior-ROI gates from `0%` to `10%`,
passed the mechanical gate. Their ROI ranged from `+31.81%` to `+38.80%`.
The strongest displayed variant used `20` prior bets and a `0%` gate:

- Bets: `71`
- ROI: `+38.80%`
- Clustered 95% interval: `+17.12%` to `+58.82%`
- 72-test adjusted p-value: `0.0029`

The one-bet-per-match sensitivity retained:

- Bets/matches: `53/53`
- ROI: `+34.11%`
- Clustered 95% interval: `+9.26%` to `+57.62%`
- Every leave-one-league/window result positive
- Adjusted p-value: `0.1526`

This substantially improves the temporal plausibility of the away/total
corner signal: after one observation window, earlier data repeatedly routes
later windows away from the losing home scope. It is still not untouched
confirmation because the router family was designed after the historical
scope pattern had been inspected. It therefore does not replace the frozen
forward registry or authorize real stakes.

Full artifacts:

- `data/v2/ev_model/experiment_040_prequential_scope_router/`

## Experiment 041: Exact scope-identity placebo

Status: scope identity not confirmed; away/total remains a forward hypothesis.

The central prequential router's result could be caused by two different
effects:

1. Away/total is a persistent profitable identity.
2. The router skips the first negative window and later V4 corner windows are
   generally profitable regardless of scope.

To separate them, home, away, and total labels were independently permuted in
every outer test window. All `6^6 = 46,656` possible scope-label sequences were
enumerated exactly. Each permutation preserved the original window's bet
counts, payouts, correlation structure, and router timing.

Results:

- Observed router: `86` bets at `+35.50%` ROI
- Null mean ROI: `+25.82%`
- Null 95% range: `+15.14%` to `+39.02%`
- Exact one-sided scope-identity p-value: `0.0790`
- 73-test adjusted p-value: `1.0`
- Delayed all-scope baseline: `106` bets at `+26.42%` ROI
- Incremental observed router improvement: `+9.08` percentage points

The router is better than simply skipping the first window and enabling every
scope, but the observed scope identity is not unusual enough at the 5% level.
Experiment 040 therefore demonstrates temporal corner-model strength and
useful abstention, but not a confirmed causal away/total segment. The static
away/total policy remains valid as a frozen forward hypothesis because it was
registered before outcomes, but its historical interpretation is explicitly
downgraded.

Full artifacts:

- `data/v2/ev_model/experiment_041_scope_identity_placebo/`

## Experiment 042: V3 versus V4 model attribution

Status: V4 probably improves selectivity; superiority not confirmed.

V3 and V4 were compared under the identical policy:

- Stat: corners
- Scopes: away and total
- Periods: all supported
- EV gate: strictly `7.5%` to `25%`

This separates the probability model from the post-model policy filter.

Results:

- V3: `228` bets, `132` matches, `+14.37%` ROI
- V4: `121` bets, `77` matches, `+28.54%` ROI
- Observed V4 minus V3 ROI: `+14.17` percentage points
- Paired match-clustered 95% difference interval:
  `-0.64` to `+28.81` points
- Bootstrap probability V4 is superior: `97.01%`
- Paired one-sided p-value: `0.0299`
- 74-test adjusted p-value: `1.0`

Selection attribution:

- Common selections: `104` at `+24.71%` ROI
- V3-only selections: `124` at `+5.69%` ROI
- V4-only selections: `17` at `+51.94%` ROI
- V3/V4 probability Brier on the shared policy universe:
  `0.247706` / `0.247544`

V4's gain is not explained only by the scope filter. Stronger regularization
makes it materially more selective, removing many low-return V3 selections
and adding a small, high-return set. However, the unique V4 sample is only
`17`, the paired interval crosses zero, and the inspected-experiment
correction removes significance. V4 remains a score-only challenger.

Full artifacts:

- `data/v2/ev_model/experiment_042_v3_v4_model_attribution/`

## Experiment 043: V4 EV-threshold sensitivity

Status: broad 5%-7.5% plateau; frozen 7.5%-25% gate retained.

The V4 corners away/total policy was rerun across `24` combinations:

- Minimum EV: `5%`, `6.5%`, `7.5%`, `9%`, `10%`, or `12.5%`
- Maximum EV: `20%`, `25%`, `30%`, or none
- Total corrected comparison family: `98`

Representative results:

| Minimum/maximum EV | Bets | ROI | Clustered 95% interval |
| --- | ---: | ---: | --- |
| 5% / 20% | 241 | +17.49% | +2.20% to +32.28% |
| 6.5% / 20% | 163 | +25.34% | +7.41% to +42.34% |
| 7.5% / 20% | 120 | +29.61% | +9.40% to +48.79% |
| 7.5% / 25% | 121 | +28.54% | +8.57% to +47.36% |
| 9% / 25% | 77 | +15.53% | -9.17% to +39.36% |
| 12.5% / 25% | 24 | -14.25% | -53.26% to +25.50% |

The profitable region is not a single lucky cutoff: minimum EV from `5%`
through `7.5%` remains positive with positive raw clustered lower bounds.
However, stricter model-EV is not better. Samples collapse above `9%`, and the
extreme `12.5%+` tail is negative. Removing the upper bound also consistently
reduces ROI.

This supports the existing abstention design and rejects extrapolation from
extreme predicted edges. No threshold was changed because every variant is
based on inspected outcomes and none passes the 98-test correction.

Full artifacts:

- `data/v2/ev_model/experiment_043_v4_policy_thresholds/`

## Experiment 044: V4 selection negative controls

Status: model selectivity supported; forward confirmation still required.

The V4 corners away/total return could still be a generic direction or market
bias rather than useful model selection. Four deterministic baselines and
three random-selection placebos were therefore tested on the same prediction
universe.

Deterministic baselines:

- V4 selected: `121` bets at `+28.54%` ROI
- Always under: `2,230` bets at `-3.10%` ROI
- Always over: `2,230` bets at `-12.50%` ROI
- Always choose market favorite: `-8.05%` ROI
- Always choose market longshot: `-7.31%` ROI

Random placebos used `100,000` iterations and a total comparison family of
`101`:

| Placebo | Null mean ROI | Null 95% range | Raw p | Adjusted p |
| --- | ---: | --- | ---: | ---: |
| Same window/scope/period/direction counts | -0.64% | -16.46% to +15.14% | 0.000160 | 0.0162 |
| Random side in the same exact market | -6.20% | -23.04% to +10.70% | 0.000070 | 0.0071 |
| Random market in the same selected match | -7.54% | -28.17% to +13.19% | 0.000380 | 0.0384 |

For the same-match test, the V4 policy was capped to one highest-EV selection
per match and retained `+27.61%` observed ROI. Therefore, neither generic
unders, broad market direction, match selection alone, nor the chosen
period/scope/direction composition explains the result. The exact model
market/side selection contains measurable historical information.

These controls strengthen the claim that V4 is identifying historically
mispriced lines. They do not make the away/total policy untouched, and the
permutation tests do not replace match-clustered forward inference. V4 remains
score-only until the frozen registry accumulates real closing lines and
settled outcomes.

Full artifacts:

- `data/v2/ev_model/experiment_044_v4_selection_placebos/`

## Experiment 045: Forward training-domain audit

Status: required safety gate; current Brazilian scores are diagnostic only.

The frozen V3 and V4 artifacts were inspected directly instead of inferring
their training support from filenames or manifests. Both fitted OneHot
encoders contain:

- Leagues: A-League Men, Bundesliga, La Liga, Ligue 1, Premier League,
  and Serie A
- Periods: 1ST, 2ND, and ALL
- Scopes: away, home, and total
- Stats: cornerKicks, shotsOnGoal, and totalShots

The first live score archive contains `96` rows across two matches:

- V3 scores: `48`
- V4 scores: `48`
- League on every row: `Brasileirão Série A`
- In-domain scores: `0`
- Out-of-domain scores: `96`

The sklearn encoder is configured with `handle_unknown="ignore"`. Without an
explicit audit, Brazilian league identity would therefore silently become an
all-zero league vector while the model still returned probabilities.

The score evaluator now extracts the fitted categorical domain from each
serialized artifact and applies it before policy selection. Out-of-domain
scores remain immutable in `ev_model_scores`, but are excluded from selection,
settlement ROI, CLV, and promotion evidence. A missing model domain also fails
closed by yielding zero eligible scores.

This does not prove that the Brazilian scores are wrong. It proves that the
existing European/Australian training data cannot validate them. Brazil needs
its own leakage-safe historical training sample, or untouched forward evidence
under a separately registered exploratory policy, before it can be considered
supported.

## Experiment 046: Stat-specific nested models

Status: corners rejected; shot models remain undersized diagnostics.

The exact V4 nested temporal procedure was trained separately for each primary
stat. No period, scope, direction, or threshold was selected from outcomes.
Shots and shots on target remained over-only because those are the available
Unibet markets.

| Stat model | Bets | ROI | Positive windows | Windows with bets |
| --- | ---: | ---: | ---: | ---: |
| cornerKicks | 199 | -0.26% | 4 | 6 |
| shotsOnGoal | 19 | +25.21% | 3 | 4 |
| totalShots | 25 | +40.80% | 2 | 2 |

The independent corner model loses the profitable global V4 behavior, showing
that cross-stat shrinkage is useful rather than harmful. The shot results are
too small and occur in too few outer windows to support separate artifacts.
They remain forward hypotheses only.

## Experiment 047: League-agnostic transfer

Status: rejected.

League identity was replaced by one constant category while every other
feature, window, nested regularization choice, and EV rule remained unchanged.
This tests whether removing league-specific coefficients creates a model that
can safely generalize to unseen competitions.

- Bets/matches: `141/96`
- ROI: `+0.94%`
- Positive windows: `3/6`
- Corners: `+2.46%`
- Shots on target: `-26.56%`

Removing league identity destroys most of the edge. It does not justify using
the existing artifact in Brazil; unseen-league predictions remain OOD.

## Experiment 048: Market-anchor feature transforms

Status: rejected; V4 feature contract unchanged.

Three predefined compact extensions were tested: logit-transformed market
probability, leakage-safe baseline-minus-market lambda gaps, and both together.

| Variant | Bets | ROI | Positive windows |
| --- | ---: | ---: | ---: |
| market logit | 175 | +10.82% | 5/6 |
| lambda gaps | 186 | +9.95% | 4/6 |
| logit + lambda gaps | 198 | +6.57% | 4/6 |

All three trail V4's unchanged `+13.42%`. The transforms add complexity
without improving generalization and were not added to production features.

## Experiment 049: Temporally local stat balancing

Status: rejected.

To test whether the larger corner sample overwhelms the two over-only targets,
training weights were partially or fully balanced by stat inside each inner
and outer training window. Counts from the target window were never used.

| Balance power | Bets | ROI | Positive windows |
| --- | ---: | ---: | ---: |
| 0.5 | 219 | +7.13% | 4/6 |
| 1.0 | 271 | +0.48% | 4/6 |

Both shot groups remained negative under the balancing policies. Reweighting
does not solve their limited information and is disabled by default.

## Experiment 050: Fixed V3/V4 probability ensemble

Status: 75% V3 / 25% V4 retained as a score-only broad challenger.

Three fixed probability averages were tested under the unchanged 7.5%-25% EV
gate. This changes model variance but does not inspect or filter a segment.

| V4 weight | Bets | Matches | ROI | Positive windows |
| ---: | ---: | ---: | ---: | ---: |
| 25% | 279 | 143 | +13.05% | 6/6 |
| 50% | 237 | 129 | +12.08% | 5/6 |
| 75% | 198 | 111 | +7.39% | 5/6 |

The 25% V4 ensemble has:

- PnL: `+36.42` units
- Match-clustered 95% interval: `-0.11%` to `+25.89%`
- Raw one-sided p-value: `0.0236`
- 116-search adjusted p-value: `1.0`
- Minimum leave-one-league ROI: `+6.94%`
- Minimum leave-one-window ROI: `+11.26%`
- ROI after removing 0.10 decimal odds from every win: `+7.25%`
- Model/market Brier on selections: `0.2380 / 0.2480`

A one-per-match cap retained `143` bets at `+9.80%`, with a `-6.69%` lower
bound. Stacked match exposure therefore contributes to precision but is not
the sole source of positive return.

Against V3, the ensemble improves ROI by `+2.84` points and full-universe
Brier by `0.000158`. The paired difference interval is `-2.75` to `+8.61`
points with only `83.42%` bootstrap probability of superiority. It is not
proven better than V3 and cannot create bets.

The frozen artifact is:

`models/ev/ev_ensemble_v3_75_v4_25_shadow/`

## Experiment 051: Ensemble consensus sensitivity

Status: no replacement; V5 weights unchanged.

Two additional deterministic consensus rules were tested:

- Conservative minimum of V3/V4 side probabilities:
  `147` bets, `+14.78%`, `5/6` positive windows
- Mean in log-odds space:
  `237` bets, `+12.08%`, `5/6` positive windows

The conservative rule raises ROI by shrinking the sample but still loses in
the first outer window and remains negative for total shots. It was inspected
after the fixed ensemble family and is not promoted. V5 keeps the simpler
75/25 arithmetic probability average.

Full reproducible artifacts:

- `data/v2/ev_model/experiment_046_stat_specific_nested/`
- `data/v2/ev_model/experiment_047_league_agnostic_nested/`
- `data/v2/ev_model/experiment_048_market_anchor_features/`
- `data/v2/ev_model/experiment_049_stat_balanced_nested/`
- `data/v2/ev_model/experiment_050_v3_v4_ensembles/`
- `data/v2/ev_model/experiment_051_v3_v4_consensus/`

## Experiment 052: Sequential V5 calibration

Status: rejected; V5 remains uncalibrated.

Beta calibration was fitted only on earlier completed outer test windows, with
at least `250` historical markets globally and `100` per stat before a
stat-specific calibrator could be used. The first outer window was never used
to calibrate itself.

- Eligible markets: `3,819`
- Raw/calibrated Brier: `0.246865 / 0.246524`
- Bets/matches: `97/64`
- PnL/ROI: `-1.70` units / `-1.75%`
- Positive windows: `2/5`
- Shots-on-goal selections: `0/5` wins

Calibration marginally improves average probability error but materially
worsens selection and ROI. It is not added to V5.

## Experiment 053: Prequential ensemble-weight selection

Status: temporal support for the fixed V5 weight not found.

For each outer test window, the ensemble weight was selected by Brier score
using completed earlier outer windows only. Candidate V4 weights were fixed at
`0`, `0.25`, `0.50`, `0.75`, and `1.0`. No current-window ROI or outcome was
used. The first window used a neutral 50/50 default.

Selected V4 weights by window:

`0.50, 0.50, 0.75, 0.50, 0.75, 0.75`

Results:

- Cold-default bets/matches: `216/123`
- Cold-default ROI: `+8.19%`
- Positive windows: `5/6`
- Cold-abstain bets/matches: `154/86`
- Cold-abstain ROI: `+12.52%`
- Total-shots ROI under the router: `-36.33%`

Earlier-window Brier does not learn the historically best fixed 25% V4
weight. The fixed V5 ensemble remains a valid pre-registered forward
hypothesis, but its exact weight is explicitly data-selected and not supported
by this temporal routing test.

## Experiment 054: Leave-one-league training transfer

Status: rejected; OOD gate confirmed as mandatory.

In every outer window, fixed-C V4 was trained on five known leagues and scored
the sixth league as an unseen OneHot category. Training remained rolling,
recency-weighted, and strictly before the target window. This directly
simulates the mechanism that would otherwise score Brazil without Brazilian
training history.

- Bets/matches: `63/44`
- PnL/ROI: `-5.20` units / `-8.25%`
- Positive windows: `2/6`
- Bundesliga: `5` bets at `-100%`
- Ligue 1: `14` bets at `-25.07%`
- Premier League: `18` bets at `-1.44%`
- Shots on goal: `5` bets at `-53.40%`

Unknown-category transfer fails even among the six competitions already
present elsewhere in the dataset. No current V3/V4/V5 score from an unseen
league may count as policy evidence.

## Experiment 055: Exact-as-of cross-stat context

Status: rejected.

Eight prior-match stat families were rebuilt at the exact odds snapshot:
possession, big chances, corners, xG, fouls, shots on goal, total shots, and
yellow cards. Home/away, for/against, all/role, and 5/10-match means produced
`128` context features in addition to the compact contract.

Leakage audit:

- Rows: `14,033`
- Historical observations excluded because unavailable at snapshot: `192`
- Observations at/after snapshot used: `0`
- Rows without context history: `0`

Results:

- Total features: `166`
- Bets/matches: `911/251`
- PnL/ROI: `-91.26` units / `-10.02%`
- Positive windows: `0/6`
- Corners: `-8.80%`
- Shots on goal: `-14.83%`
- Total shots: `-26.40%`

The expanded context is strongly harmful despite correct timing.

## Experiment 056: Reduced exact-as-of context

Status: rejected; compact target-stat features retained.

Three predefined 10-match context profiles tested whether Experiment 055
failed only because of dimensionality:

| Context profile | Extra features | Bets | ROI | Positive windows |
| --- | ---: | ---: | ---: | ---: |
| xG + big chances | 16 | 277 | +2.53% | 4/6 |
| xG + big chances + possession | 24 | 302 | +3.84% | 4/6 |
| corners + shots + shots on goal | 24 | 266 | +6.08% | 3/6 |

All reduced profiles trail the compact V3/V4/V5 models and have weaker window
stability. Cross-stat context is not added to the artifact contract.

## Experiment 057: Prequential stat partial pooling

Status: rejected.

Global V4 predictions were blended with the independently trained stat model.
For each stat and outer window, the local weight was selected by Brier score
using completed earlier outer windows only. Candidate local weights were
fixed at `0`, `0.10`, `0.25`, `0.50`, `0.75`, and `1.0`; at least `250`
prior markets were required.

- Bets/matches: `237/119`
- PnL/ROI: `+6.35` units / `+2.68%`
- Positive windows: `4/6`
- Match-clustered 95% interval: `-12.21%` to `+17.51%`
- Probability positive: `63.89%`
- Paired ROI difference versus V4: `-10.74` percentage points
- Total-shots ROI: `-10.69%`

Prequential Brier selection rapidly assigned high weight to the inferior local
corner model and did not produce a stable shot edge. Partial pooling at the
prediction layer is not retained.

Full artifacts:
`data/v2/ev_model/experiment_057_prequential_partial_pooling/`.

## Experiment 058: Regularized stat slope deviations

Status: historically positive, but rejected as a V4 replacement.

Instead of replacing the global model with small stat-specific models,
shots-on-goal and total-shots received regularized slope deviations inside
the shared nested temporal logistic model. Corners remained the reference
relationship.

| Interaction profile | Bets | ROI | Positive windows | Clustered 95% interval |
| --- | ---: | ---: | ---: | --- |
| Market deviations | 183 | +6.17% | 4/6 | -10.15% to +22.22% |
| Expected-history deviations | 198 | +10.99% | 5/6 | -4.34% to +25.76% |
| Compact core deviations | 188 | +11.49% | 5/6 | -4.91% to +27.15% |

Both history variants were positive for all three stats and survived every
leave-one-league/window exclusion. They still trailed V4, worsened paired
Brier score, and had confidence intervals crossing zero.

Full artifacts:
`data/v2/ev_model/experiment_058_regularized_stat_interactions/`.

## Experiment 059: Stat-interaction ensemble sensitivity

Status: rejected; no new artifact.

Fixed V4/interaction probability blends were evaluated at interaction weights
of `10%`, `25%`, and `50%`.

| Interaction model | Weight | Bets | ROI | Positive windows |
| --- | ---: | ---: | ---: | ---: |
| Expected history | 10% | 174 | +12.94% | 5/6 |
| Expected history | 25% | 171 | +14.04% | 5/6 |
| Expected history | 50% | 175 | +12.53% | 5/6 |
| Compact core | 10% | 174 | +12.94% | 5/6 |
| Compact core | 25% | 171 | +13.83% | 5/6 |
| Compact core | 50% | 173 | +13.64% | 5/6 |

Three-model V3/V4/interaction consensus variants were also inspected.

| Interaction model | Aggregation | Bets | ROI | Positive windows |
| --- | --- | ---: | ---: | ---: |
| Expected history | Minimum | 124 | +15.95% | 5/6 |
| Expected history | Median | 178 | +8.92% | 5/6 |
| Expected history | Mean | 204 | +11.18% | 5/6 |
| Compact core | Minimum | 117 | +14.52% | 5/6 |
| Compact core | Median | 179 | +7.41% | 4/6 |
| Compact core | Mean | 201 | +9.90% | 5/6 |

Every variant remained negative for total shots and none improved V4's window
stability. The best aggregate ROI was selected after inspection and therefore
cannot be treated as a new holdout result.

## Experiment 060: Regularized scope and period slope deviations

Status: scope candidate frozen as V6 score-only challenger; other variants
rejected.

The shared model previously allowed different category intercepts but forced
the same line, market, baseline, and history slopes across scopes and periods.
This experiment added strongly regularized reference-relative deviations.

| Variant | Bets/matches | ROI | Positive windows | Brier |
| --- | ---: | ---: | ---: | ---: |
| Scope deviations | 234/132 | +18.03% | 5/6 | 0.246351 |
| Period deviations | 280/160 | +0.81% | 3/6 | 0.245807 |
| Scope + period deviations | 354/193 | +7.54% | 5/6 | 0.246507 |

Scope-deviation details:

- PnL: `+42.18` units
- Match-clustered 95% interval: `+3.62%` to `+32.14%`
- Raw one-sided p-value: `0.00546`
- 123-search adjusted p-value: `0.672`
- Every leave-one-league and leave-one-window result remained positive
- Corners: `203` bets at `+17.77%`
- Shots on goal: `19` bets at `+12.21%`
- Total shots: `12` bets at `+31.50%`
- Away/total scope: `+27.81% / +24.82%`
- Home scope: `-0.75%`
- Removing `0.10` from every winning decimal price retained `+11.96%`
- Serie A supplied `71.1%` of net PnL, but excluding it retained `+8.29%`

The raw clustered interval is the strongest new historical result, but Brier
is worse than V4 and the experiment-count correction fails. It is frozen only
for untouched score-level forward testing.

Full artifacts:
`data/v2/ev_model/experiment_060_period_scope_interactions/`.

## Experiment 061: Scope-candidate falsification

Status: selection signal survives placebos; production promotion still fails.

The selected rows were compared with random direction and random market
selection while preserving their relevant market strata.

| Placebo | Observed ROI | Null 95% high | One-sided p |
| --- | ---: | ---: | ---: |
| Direction within selected market | +18.03% | +8.52% | 0.00011 |
| Selection within market strata | +18.03% | +7.57% | 0.00008 |
| Selection within league/market strata | +18.03% | +10.42% | 0.00042 |

Restricting exposure to one bet per match produced `132` bets at `+15.48%`,
but its clustered interval widened to `-1.25%` to `+32.01%`. Both policies
still fail the 124-search correction. The placebos support a non-random
historical selection signal; they do not create untouched confirmation.

Full artifacts:
`data/v2/ev_model/experiment_061_scope_interaction_audit/`.

## Experiment 062: Brazil legacy readiness audit

Status: insufficient for model training; OOD block retained.

The read-only `app.unibet-backtest` source contained only:

- `19` Brazilian documents representing `17` unique Unibet events
- Date range `2025-11-22` through `2025-12-04`
- `14` documents verified before kickoff
- `3` documents generated at/after kickoff
- `2` documents without a safe kickoff linkage
- `2,216` primary line rows with actual values, but only `17` independent
  match clusters
- `271` duplicate primary exposures before canonical deduplication

The many line rows are correlated observations from the same small group of
matches and cannot justify a Brazil model. Current Brazilian V3-V6 scores stay
archived for diagnostics but excluded from selection, ROI, CLV, and promotion.

Full report: `docs/brazil-model-readiness-audit.md`.

## Experiment 063: V6 scope-feature ablation

Status: scope signal survives feature removal; no simpler model replaces V6.

The V6 interaction block was retrained with predefined subsets. Thresholds,
scope filters, outer windows, and the base feature contract were unchanged.

| Scope-interaction subset | Bets | ROI | Positive windows | Clustered 95% interval |
| --- | ---: | ---: | ---: | --- |
| Market price only | 208 | +11.43% | 5/6 | crosses zero |
| History levels only | 185 | +9.65% | 5/6 | crosses zero |
| History trends only | 187 | +15.78% | 5/6 | -0.93% to +31.70% |
| Market + history levels | 201 | +15.43% | 5/6 | +0.09% to +30.32% |
| Full V6 scope block | 234 | +18.03% | 5/6 | +3.62% to +32.14% |

All reduced variants improved Brier score relative to full V6 while producing
lower ROI. That divergence is an overfit warning: V6's selection return is
not supported by better global probability calibration. The signal is not
dependent on one feature group, but no ablation is promoted.

Full artifacts:
`data/v2/ev_model/experiment_063_scope_feature_ablations/`.

## Experiment 064: V6 temporal robustness

Status: robust to recency at 90 training days; fails at 60 training days.

All variants used the same fixed test dates from `2026-02-19` through
`2026-05-24`. Only the trailing training window and recency half-life changed.

| Train days | Half-life | Bets | ROI | Positive windows |
| ---: | ---: | ---: | ---: | ---: |
| 60 | 30 | 508 | -4.94% | 3/6 |
| 60 | 45 | 475 | -4.25% | 3/6 |
| 60 | 60 | 450 | -3.32% | 3/6 |
| 90 | 30 | 278 | +13.95% | 5/6 |
| 90 | 45 | 234 | +18.03% | 5/6 |
| 90 | 60 | 223 | +16.00% | 5/6 |

The 90-day signal is stable across recency choices. Its complete reversal
under every 60-day window means the model depends on older observations and
may adapt poorly to regime changes. This is a blocking warning for production
promotion, not a reason to retune on the inspected test window.

Full artifacts:
`data/v2/ev_model/experiment_064_scope_temporal_robustness/`.

## Experiment 065: Strong-regularization control

Status: rejected; stronger shrinkage does not repair the 60-day failure.

The nested regularization grid was extended down to `C=0.001`.

- 60 training days: `229` bets at `-8.93%`, `3/6` positive windows
- 90 training days: `121` bets at `+9.97%`, `5/6` positive windows

Stronger regularization improved Brier score but did not make the short-window
model profitable. The temporal weakness is therefore not explained by a
single overly weak penalty.

Full artifacts:
`data/v2/ev_model/experiment_065_scope_strong_regularization/`.

## Experiment 066: Frozen V6 corner/scope policy audit

Status: strongest historical candidate; frozen score-only before any
in-domain forward settlement.

The existing `7.5%–25%` EV bounds were applied without change to V6 corners in
away and total scope across all periods. The comparison family includes all
`159` model, policy, and threshold variants inspected up to this audit.

- Bets/matches: `156/99`
- PnL/ROI: `+44.70` units / `+28.65%`
- Match-clustered 95% interval: `+11.33%` to `+45.27%`
- Raw one-sided p-value: `0.000130`
- 159-test adjusted p-value: `0.0207`
- Probability positive: `99.93%`
- Every leave-one-league ROI positive; minimum `+17.51%`
- Every leave-one-window ROI positive; minimum `+23.73%`
- ROI after removing `0.10` from every winning price: `+22.05%`

The neighboring threshold profile is not smooth: `5%` and `6.5%` lower bounds
produce `+14.09%` and `+15.84%`, while the fixed `7.5%` bound jumps to
`+28.65%`. That sharpness is a material selection-risk warning. The policy
passes its mechanical historical gate but remains `not_confirmed` because its
outcomes were already inspected.

Full artifacts:
`data/v2/ev_model/experiment_066_v6_corner_scope_thresholds/`.

## Experiment 067: V6 corner/scope negative controls

Status: selection beats generic controls; untouched forward proof still
required.

- Frozen candidate: `156` bets at `+28.65%`
- One highest-EV bet per match: `99` bets at `+30.02%`
- Always over: `-12.50%`
- Always under: `-3.10%`
- Market favorite: `-8.05%`
- Market longshot: `-7.31%`
- Matched-composition random adjusted p-value: `0.00324`
- Random side in the same market adjusted p-value: `0.00324`
- Random market in the same selected match adjusted p-value: `0.00972`

The exact line/side selection contains historical information beyond a
generic corner direction or market effect. These controls expand the
historical search family to `162`; they cannot turn inspected outcomes into a
holdout.

Full artifacts:
`data/v2/ev_model/experiment_067_v6_corner_scope_placebos/`.

## Experiment 068: V6 corner/scope snapshot horizons

Status: required checkpoint coverage is insufficient; research checkpoints
retained.

The exact frozen V6 corner/away+total selections were mapped to the V2
capture windows without changing predictions or selecting horizons by ROI.

- Historical candidate bets: `156`
- Covered by required T-3D/T-2D/T-1D/T-10M windows: `27` (`17.31%`)
- Covered after adding research T-12H/T-2H: `128` (`82.05%`)
- Incremental research-checkpoint coverage: `101` bets
- T-1D historical selections: `0`
- T-10M historical selections: `0`
- T-12H historical selections: `83`
- T-2H historical selections: `18`

The strongest populated buckets were 6-12 hours (`60` bets, `+39.20%`) and
12-18 hours (`23` bets, `+32.43%`). The 36-60 hour bucket lost `-17.84%` over
only `19` bets. These small bucket returns are descriptive, not independent
strategies. The decision concerns capture coverage only: T-12H and T-2H
remain required for research parity, while all original checkpoints stay
active.

The audit script previously treated already-added research checkpoints as
part of the required baseline. That reporting bug was corrected; required and
research windows are now disjoint and regression-tested.

Full artifacts:
`data/v2/ev_model/experiment_068_v6_corner_scope_horizons/`.

## Experiment 069: V6 temporal consensus

Status: rejected; frozen V6 remains unchanged.

The 90-day V6 model was combined with the previously tested 60-day,
45-day-half-life model using four predefined robustness rules. All variants
used the same dates, markets, EV bounds, and corner/away+total filter.

| Variant | Bets | ROI | Positive windows | Brier |
| --- | ---: | ---: | ---: | ---: |
| V6 90-day reference | 156 | +28.65% | 6/6 | 0.246351 |
| 75% 90-day + 25% 60-day | 163 | +21.87% | 6/6 | 0.246744 |
| 50% 90-day + 50% 60-day | 184 | +16.16% | 5/6 | 0.247220 |
| 90-day side + positive 60-day agreement | 154 | +28.81% | 6/6 | unchanged |
| Both models above 7.5% EV | 126 | +27.42% | 5/6 | unchanged |

Both probability blends worsened Brier and ROI. The weak agreement gate
removed only two bets and improved ROI by `0.16` percentage points; its paired
95% difference interval was `-1.95` to `+2.48` points. Requiring both models
above the frozen EV threshold reduced ROI and window stability.

The agreement-zero variant passes a mechanical historical gate after the
expanded 166-test family, but it is statistically indistinguishable from V6
and was created after inspecting V6 history. Extra model complexity is not
accepted without a material paired improvement.

Full artifacts:
`data/v2/ev_model/experiment_069_v6_temporal_consensus/`.

## Experiment 070: Nested count residual and V6 ensemble

Status: rejected; frozen V6 and registry V5 remain unchanged.

This experiment revisited the count-model family without repeating the
leakage and dispersion weaknesses in Experiments 000-003:

- Input was the exact `asof_market_frame.parquet` used by the later
  leakage-safe classifiers.
- Features were selected from an explicit allowlist. Outcomes, settlement,
  ids, timestamps, current-match values, and training weights were not model
  features.
- Every odds snapshot was strictly before kickoff.
- Each outer window used 90 prior days, a 45-day recency half-life, and a
  14-day test.
- The HGB model predicted a log-count residual around Unibet's
  market-implied lambda.
- Negative-binomial dispersion was estimated only from a prior 21-day
  temporal validation block, never from in-sample training residuals.
- The one test window following an empty 21-day match interval reused the
  last earlier validation profile. It did not estimate dispersion from the
  outer training fit.
- Count and V6 covered the same `8,822` side/window keys. There were zero
  missing times, post-kickoff snapshots, duplicate keys, train/test timing
  violations, or settlement mismatches.

Four fixed policies were evaluated. The robustness grid expanded the
conservative historical comparison family from `166` to `210`.

| Policy | Corner away/total bets | ROI | Positive windows | One/match ROI | Full Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen V6 reference | 156 | +28.65% | 6/6 | +30.02% | 0.246351 |
| Nested count residual NB | 1,103 | -3.31% | 1/6 | -3.24% | 0.257084 |
| 90% V6 + 10% count | 190 | +14.69% | 6/6 | +17.94% | 0.246362 |
| 75% V6 + 25% count | 345 | +2.50% | 5/6 | +0.71% | 0.246820 |
| V6 gated by positive count-side agreement | 134 | +25.85% | 6/6 | +29.90% | unchanged |

Count alone was negative in five of six windows and materially worse
calibrated than V6. Both probability blends reduced ROI and worsened Brier.
The 10% blend retained a positive `+8.79%` ROI after removing `0.10` from each
winning decimal price, but its clustered interval was `-1.52%` to `+30.34%`
and its paired ROI difference versus V6 was strictly negative:
`-22.84` to `-5.58` percentage points.

The agreement gate was the strongest count-assisted rule:

- `134` bets across `87` matches
- `+34.64` units and `+25.85%` ROI
- clustered 95% interval `+7.38%` to `+43.89%`
- all leave-one-league and leave-one-window results positive
- `+19.43%` ROI after the `0.10` absolute decimal-price stress

It still failed. Its 210-test adjusted p-value was `0.454`, and it was worse
than frozen V6 by `2.80` ROI points. The paired 95% difference interval was
`-8.37` to `+2.97` points, so count agreement did not add proven information.

Conclusion: a correctly timed and validated count distribution does not find
the historical edge. It mostly pulls V6 toward weaker and less calibrated
probabilities. No count policy, blend, segment, artifact, or registry entry is
retained. The negative result is permanent evidence against adding this model
family merely because count models look natural for football statistics.

Full artifacts:
`data/v2/ev_model/experiment_070_nested_count_ensemble/`.

## Experiment 071: Snapshot market movement

Status: rejected; frozen V6 and registry V5 remain unchanged.

The historical raw snapshot stream was used to reconstruct the balanced
canonical market independently at every saved timestamp. Movement features
were calculated only from observations no later than each modeling row's
stored odds time.

Source and timing audit:

- Raw snapshot rows: `981,400`
- Unambiguous valid price rows: `857,718`
- Canonical market observations: `93,086`
- Modeling rows with any snapshot history: `13,304/14,033`
- Modeling rows with at least two observations: `12,053`
- Rows with aligned and usable movement: `11,965` (`85.26%`)
- Future observations detected and excluded: `1,198`
- Future observations used: `0`
- V6/movement prediction-universe match: `8,822/8,822`
- Duplicate prediction keys, forbidden features, and train/test timing
  violations: `0`

The builder excluded `1,330` ambiguous duplicate line/snapshot prices. It also
left movement deltas missing when the reconstructed current canonical price
did not align with the historical model row. Count, elapsed time, line,
probability, market-lambda, and overround changes were transformed with
outcome-independent signed `log1p`, preventing a handful of raw-feed
extremes from dominating the logistic model.

The exact V6 scope-interaction architecture was retrained with the ten
movement features. Two fixed probability blends and one agreement gate were
also tested. The conservative comparison family increased from `210` to
`254`.

| Policy | Corner away/total bets | ROI | Positive windows | One/match ROI | Full Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen V6 reference | 156 | +28.65% | 6/6 | +30.02% | 0.246351 |
| V6 architecture + movement | 185 | +13.98% | 5/6 | +20.09% | 0.246631 |
| 90% V6 + 10% movement | 146 | +29.03% | 6/6 | +29.54% | 0.246293 |
| 75% V6 + 25% movement | 136 | +24.62% | 5/6 | +22.92% | 0.246241 |
| V6 gated by positive movement agreement | 141 | +25.73% | 6/6 | +29.69% | unchanged |

Movement alone worsened Brier and lost `14.67` ROI points versus V6. The 25%
blend improved Brier but reduced betting performance. The agreement rule
removed 15 V6 selections without improving the result.

The 10% blend was the only potentially useful diagnostic:

- `146` bets across `96` matches
- `+42.39` units and `+29.03%` ROI
- clustered 95% interval `+11.47%` to `+45.83%`
- every leave-one-league/window ROI positive
- `+22.39%` ROI after removing `0.10` from every winning decimal price
- full-universe Brier improvement `0.000063`

It still failed the predeclared retention gate. `142/146` selections were
already V6 selections. The observed paired ROI improvement was only `+0.38`
points with a `-5.27` to `+6.46` interval and only `54.1%` bootstrap
probability of superiority. Its 254-test adjusted p-value was `0.066`.

Conclusion: snapshot movement contains a small amount of probability
information, but this experiment does not prove that it adds betting edge
beyond V6. No movement policy or artifact is promoted. A subsequent
prequential blend-weight test may use only earlier out-of-sample windows; the
fixed 10% result cannot be relabeled as untouched evidence.

Full artifacts:
`data/v2/ev_model/experiment_071_snapshot_movement/`.

## Experiment 072: Prequential movement weight

Status: rejected; frozen V6 and registry V5 remain unchanged.

To test whether Experiment 071's fixed 10% movement weight could have been
chosen before seeing each result, a prequential blender considered movement
weights `0%`, `10%`, `25%`, `50%`, and `100%`. For every outer test window,
the weight minimized Brier over completed earlier outer windows only. The
first window used 0% movement. No current or future-window outcome entered a
decision.

Selected movement weights by test start:

| Test start | Weight | Prior markets |
| --- | ---: | ---: |
| 2026-02-19 | 0% | 0 |
| 2026-03-05 | 50% | 1,639 |
| 2026-03-19 | 10% | 2,701 |
| 2026-04-02 | 50% | 3,408 |
| 2026-04-30 | 50% | 3,838 |
| 2026-05-14 | 100% | 4,543 |

The choices were temporally valid but did not generalize:

| Policy | Markets | Brier | Corner away/total bets | ROI | Positive windows |
| --- | ---: | ---: | ---: | ---: | ---: |
| Prequential, cold reference | 5,458 | 0.246832 | 179 | +15.82% | 5/6 |
| V6 reference | 5,458 | 0.246351 | 156 | +28.65% | 6/6 |
| Prequential, first-window abstain | 3,819 | 0.248085 | 145 | +18.59% | 4/5 |
| Same-window V6 reference | 3,819 | 0.247398 | 122 | +35.53% | 5/5 |

The all-window prequential policy was `12.84` ROI points worse than V6 with a
paired 95% difference interval of `-24.79` to `-1.29`. Cold abstention was
`16.94` points worse with an interval of `-31.89` to `-2.28`. Both variants
worsened Brier. The first-window-abstain candidate had a positive standalone
cluster interval, but that is irrelevant: it was materially inferior to V6 on
the same windows and failed the 282-test correction.

Conclusion: the fixed 10% result from Experiment 071 was not a stable
prequentially selectable blend. Adaptive weighting magnified movement noise
and is permanently rejected for this dataset.

Full artifacts:
`data/v2/ev_model/experiment_072_prequential_movement_blend/`.

## Experiment 073: Alternate-line ladder consensus

Status: rejected; frozen V6 and registry V5 remain unchanged.

This experiment used every simultaneous Kambi alternate line rather than only
the canonical line. The current line was removed before calculating the
consensus, so the feature set measured independent ladder information:
other-line implied-lambda median and dispersion, neighbor probability
residual, monotonicity, line rank, span, and overround.

Coverage and leakage audit:

- Raw snapshot rows: `981,400`
- Unambiguous line points after conflict exclusion: `488,089`
- Modeling rows with a snapshot ladder: `13,304/14,033`
- Exact current line/price alignment: `13,294`
- Usable leave-current-line-out ladders: `12,445` (`88.68%`)
- Future snapshot ladders excluded/used: `1,198/0`
- V6/ladder prediction universe: `8,822/8,822`
- Duplicate prediction keys and train/test timing violations: `0`

| Policy | Corner away/total bets | ROI | Positive windows | One/match ROI | Full Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen V6 reference | 156 | +28.65% | 6/6 | +30.02% | 0.246351 |
| V6 architecture + ladder | 167 | +15.90% | 4/6 | +18.26% | 0.246333 |
| 90% V6 + 10% ladder | 148 | +31.33% | 6/6 | +30.59% | 0.246318 |
| 75% V6 + 25% ladder | 151 | +27.77% | 6/6 | +28.04% | 0.246282 |
| V6 gated by positive ladder agreement | 155 | +29.48% | 6/6 | +31.35% | unchanged |

The 10% blend passed its standalone historical gate even after increasing the
comparison family to `326`:

- `148` bets across `97` matches
- `+46.37` units and `+31.33%` ROI
- clustered 95% interval `+13.92%` to `+47.62%`
- 326-test adjusted p-value `0.0163`
- every leave-one-league/window result positive
- `+24.57%` ROI after the `0.10` decimal-price stress

It nevertheless failed the predeclared incremental gate. `147/148` bets were
already V6 bets; it added one and removed nine. Its paired improvement was
`+2.68` ROI points with a `-2.24` to `+8.13` interval and only `84.2%`
bootstrap probability of superiority. The agreement gate simply removed one
V6 loss and was not independent evidence.

Conclusion: the alternate-line ladder improves calibration and can make the
already selected V6 sample look slightly better, but the historical record
does not prove incremental edge. It is not promoted from this inspected
fixed-weight result.

Full artifacts:
`data/v2/ev_model/experiment_073_snapshot_ladder/`.

## Experiment 074: Prequential ladder weight

Status: rejected; frozen V6 and registry V5 remain unchanged.

The same prior-window-only blend selector from Experiment 072 was applied to
the ladder challenger. Selected ladder weights were:

`0%, 10%, 0%, 0%, 25%, 50%`

This sequence used zero current/future-window outcomes and improved Brier:

- All-window Brier: `0.246278` versus V6 `0.246351`
- Cold-abstain Brier: `0.247293` versus V6 `0.247398`

But the betting result did not improve:

| Policy | Bets | ROI | Positive windows | One/match ROI |
| --- | ---: | ---: | ---: | ---: |
| Prequential ladder, cold reference | 157 | +25.45% | 6/6 | +28.37% |
| V6 reference | 156 | +28.65% | 6/6 | +30.02% |
| Prequential ladder, first-window abstain | 123 | +31.39% | 5/5 | +34.57% |
| Same-window V6 reference | 122 | +35.53% | 5/5 | higher |

The all-window paired difference was `-3.20` points with a `-9.40` to `+2.94`
interval. Cold abstention was `-4.14` points with a `-12.35` to `+3.96`
interval. The latter passed a standalone 354-test gate, but it remained worse
than V6 on the exact same dates and cannot be retained as an improvement.

Conclusion: ladder information modestly improves probability calibration but
does not improve the V6 betting rule when its weight is selected using only
past data. The fixed 10% ladder result from Experiment 073 is therefore
rejected rather than frozen after inspection.

Full artifacts:
`data/v2/ev_model/experiment_074_prequential_ladder_blend/`.

## Experiment 075: Combined market microstructure

Status: rejected; frozen V6 and registry V5 remain unchanged.

Movement and alternate-line ladder features were rebuilt independently from
all `981,400` raw historical snapshot rows before the models ran. Both rebuilt
feature matrices matched their cached `14,033`-row artifacts, all four
prediction universes matched exactly at `8,822` rows, and the audit found:

- Duplicate prediction keys: `0`
- Future snapshot features used: `0`
- Train end at or after the test match: `0`

Four predeclared variants were tested:

| Policy | Bets | ROI | Positive windows | Brier |
| --- | ---: | ---: | ---: | ---: |
| Full V6 + movement + ladder feature model | 198 | +3.39% | 5/6 | 0.246923 |
| 90% V6 / 5% movement / 5% ladder | 146 | +31.97% | 6/6 | 0.246303 |
| 80% V6 / 10% movement / 10% ladder | 144 | +29.56% | 6/6 | 0.246261 |
| V6 gated by positive agreement from both | 141 | +25.73% | 6/6 | 0.246351 |

The 90/5/5 blend passed its standalone 398-test historical gate:

- Clustered 95% interval: `+14.43%` to `+48.52%`
- Multiple-comparison adjusted p-value: `0.00796`
- One bet per match: `97` bets at `+32.62%`
- 0.10 decimal price haircut: `+25.18%`
- Every leave-one-league and leave-one-window result remained positive

It did not prove incremental edge. `145/146` selections overlapped V6, and the
paired improvement was `+3.31` ROI points with a `-1.63` to `+9.01` interval.
The probability of superiority was `89.4%`, below the retention requirement.
The 80/10/10 and dual-agreement variants also had paired intervals crossing
zero. The full combined feature model materially worsened both calibration and
ROI.

Conclusion: a small symmetric microstructure blend is a useful calibration
shadow, but the inspected history cannot distinguish its betting return from
V6 selection noise. It is not added to the immutable forward registry.

Full artifacts:
`data/v2/ev_model/experiment_075_combined_microstructure/`.

## Experiment 076: Prequential combined microstructure shrinkage

Status: rejected; frozen V6 and registry V5 remain unchanged.

The Experiment 075 90/5/5 composite was treated as one challenger. For every
outer window, the blend moved `0%`, `10%`, `25%`, `50%`, or `100%` of the way
from V6 toward that composite using Brier from completed earlier windows only.
This kept the effective movement and ladder weights between `0%` and `5%`
each, rather than opening another broad historical weight search.

The first window used V6 as a cold start. Every later window selected the full
90/5/5 composite:

`0%, 100%, 100%, 100%, 100%, 100%`

Timing audit:

- Future-window outcomes used: `0`
- Prior-history end at or after the current window: `0`

Results:

| Policy | Bets | ROI | Positive windows | Brier |
| --- | ---: | ---: | ---: | ---: |
| Prequential composite, cold V6 | 147 | +30.91% | 6/6 | 0.246312 |
| V6 reference | 156 | +28.65% | 6/6 | 0.246351 |
| Prequential composite, first window omitted | 113 | +39.02% | 5/5 | 0.247342 |
| Same-window V6 reference | 122 | +35.53% | 5/5 | 0.247398 |

The all-window paired improvement was `+2.26` points with a `-2.08` to `+7.35`
interval. First-window abstention improved by `+3.48` points with a `-2.11`
to `+10.06` interval. Both standalone policies passed their historical
falsification gates after a 426-test correction, but neither proved a positive
incremental return over V6.

Conclusion: the small calibration gain persists when the weight is chosen
only from past windows, but its betting improvement remains statistically
indistinguishable from zero. This is the final historical Kambi
microstructure test; registry V5 remains unchanged.

Full artifacts:
`data/v2/ev_model/experiment_076_prequential_combined_microstructure/`.

## Experiment 077: Exact-as-of nonlinear HGB challengers

Status: rejected; frozen V6 and registry V5 remain unchanged.

The existing fixed `hgb_market` and `market_residual_hgb` implementations were
rerun on the corrected V6 feature contract. Both used:

- The exact `14,033`-row snapshot-as-of market frame
- V6's sixteen deterministic scope-deviation features
- A 90-day rolling training window
- A 45-day recency half-life
- The same six outer test windows and `8,822` side predictions as V6
- The unchanged 7.5%-25% EV policy

Audit result:

- Prediction-universe mismatches: `0`
- Duplicate prediction keys: `0`
- Forbidden outcome features used: `0`
- Missing snapshot or kickoff times: `0`
- Snapshots at or after kickoff: `0`
- Train end at or after test match: `0`

Both nonlinear models failed decisively:

| Model | Brier | Corner away/total bets | ROI | Positive windows |
| --- | ---: | ---: | ---: | ---: |
| V6 reference | 0.246351 | 156 | +28.65% | 6/6 |
| HGB classifier | 0.248933 | 424 | -8.42% | 2/6 |
| Market-residual HGB | 0.247839 | 275 | -12.20% | 1/6 |

HGB's paired ROI difference versus V6 was `-37.08` points with a `-55.27` to
`-18.61` interval. Residual HGB was `-40.85` points worse with a `-59.96` to
`-21.52` interval. Both also had negative one-bet-per-match and price-stress
results.

The only positive post-hoc primary-stat slice was total shots:

- HGB: `27` bets at `+9.59%`, only `4/5` positive windows
- Residual HGB: `28` bets at `+5.39%`, only `3/4` positive windows

Those samples are small, unstable, and were found after opening all outcomes.
They are documented as rejected diagnostics, not new total-shots policies.

Conclusion: nonlinear boosting on the final leakage-safe feature contract is
materially worse than regularized logistic V6. “More ML” does not repair the
probability or selection problem. The conservative historical comparison
family is now `454`.

Full artifacts:
`data/v2/ev_model/experiment_077_exact_asof_hgb/`.

## Current recommendation after Experiment 077

The recommended historical +EV candidate is:

`v6_scope_interaction_corners_away_total_primary_challenger`

Its immutable policy is:

- Model: `ev_scope_interaction_recency45_asof_capped_v6_shadow`
- Market: corners only
- Scope: away team or match total
- Period: ALL, 1ST, or 2ND
- Model EV: strictly above `7.5%` and below `25%`
- Training: rolling 90 days with a 45-day recency half-life
- Exposure: one side per match/stat/period/scope/line market
- Domain: only leagues present in the serialized training manifest

Historical evidence is `156` bets across `99` matches at `+28.65%` ROI, with
a match-clustered 95% interval of `+11.33%` to `+45.27%`. One bet per match
returned `+30.02%`, a 0.10 decimal price haircut retained `+22.05%`, and every
leave-one-league and leave-one-window result remained positive.

The 90/5/5 V6/movement/ladder blend is retained only as a calibration shadow.
It has slightly better Brier and higher descriptive ROI, but its paired
incremental interval crosses zero. It must not replace the exact registered
V6 policy from inspected outcomes.

This is the end of model selection on the current November-May history. Count
residuals, nonlinear HGB classifiers, temporal windows, regularization,
calibration, stat pooling, league transfer, line history, snapshot movement,
alternate-line ladders, fixed ensembles, agreement gates, and prequential
selectors have all been tested. Further filtering or weight tuning on the same
outcomes would increase selection bias without adding independent evidence.

The remaining requirement is untouched in-domain forward proof. Brazilian
scores are outside the serialized training domain and are correctly excluded.
Until new pre-kickoff predictions settle in one of the six supported leagues,
the honest status is `historically_positive_not_forward_confirmed`, not
“proven +EV”.

## Frozen shadow candidates

The primary model for forward testing remains V3:

- Probability model: regularized logistic regression
- Training history: rolling 90 days
- Recency weighting: 45-day half-life
- Probability calibration: none
- Minimum model EV: strictly greater than 7.5%
- Maximum model EV: strictly less than 25%
- Stake in evaluation: flat one unit
- Exposure: at most one side per match/stat/period/scope market
- Targets: corners, shots, and shots on target

Inputs are limited to prematch line/odds/market features, categorical
league/stat/period/scope, and shifted rolling team histories for the target
stat over 3/5/10/20 matches. Each history value must have been available before
the exact odds snapshot, using a three-hour post-kickoff availability buffer.
Current-match outcomes, current-match team values, CLV, closing prices, and
unversioned Opta data are excluded.

For half-point lines:

`EV = predicted_win_probability * decimal_odds - 1`

The candidate must run in shadow mode until it accumulates new untouched
forward bets with complete closing-line coverage. It is not approved for a
claim of proven +EV or real-money staking.

V4 reuses the exact same leakage-safe feature contract and EV policy but
selects logistic regularization through the nested temporal procedure from
Experiment 037. It is intentionally configured as `score_only`: it archives
probabilities and EV for every side but cannot create `forward_bets`. V3 and V4
can therefore be compared on the same untouched matches without duplicate
financial exposure or policy drift.

V5 is a fixed `75% V3 + 25% V4` probability ensemble. It uses the same feature,
timing, domain, and EV contracts and is also hard-restricted to `score_only`.
It remains the broad low-variance challenger.

V6 is frozen as:

`ev_scope_interaction_recency45_asof_capped_v6_shadow`

It reuses V4's exact as-of compact feature contract and nested temporal
regularization. At runtime it adds sixteen deterministic scope-interaction
features: home and away deviations for line, market probability, market
lambda, baseline lambda, 10-match role/all expected values, and role/all
trends. Total scope remains the reference relationship. V6 is `score_only`;
it cannot create `forward_bets`.

The exact V6 corner/away+total policy is frozen in
`score_policy_registry_v5.json` as the strongest historical challenger. Its
EV bounds and filters cannot change after forward outcomes arrive. V6's
60-day training failure and threshold sensitivity prevent promotion from
historical results alone.

## First immutable V2 forward freeze

On `2026-07-29T23:53:20Z`, job run
`5fe7ff76f4174ce38c492840214425b0` froze the first predictions from
`ev_logistic_recency45_asof_v2`:

- Future target matches with odds: `4`
- Canonical markets scored: `60`
- Selections above 7.5% model EV: `8`
- Matches with selections: `3`
- Target outcome rows read before prediction persistence: `0`
- Predictions created before kickoff: `8/8`
- Odds snapshots before kickoff: `8/8`
- Prediction rows containing outcomes: `0`

An immediate idempotency rerun produced `0` inserts, `8` existing rows, and
`0` conflicts. These rows are stored in `forward_bets` using immutable
prediction fingerprints. They must only be settled after canonical results and
team statistics are available.

### Timing-integrity correction

A stricter audit on `2026-07-30` compared each odds snapshot with both kickoff
and the real prediction creation time. It found that a manual production test
had previously persisted snapshots with a simulated future `--now` value.
Therefore:

- Frozen rows: `8`
- Valid rows with `odds_snapshot_time <= prediction_created_at < kickoff`: `5`
- Invalid rows with a snapshot timestamp after prediction creation: `3`
- Affected match: `sofascore:15235418`
- Valid matches represented by the five rows: `2`

The three invalid immutable predictions remain stored for auditability but are
excluded from settlement performance, ROI, CLV, and promotion evidence. Only
the five valid rows count as V2 forward evidence. The 497 derived snapshots
created by four simulated capture runs were marked
`invalid_for_model=true`; raw Kambi payloads were not changed. A repeat repair
run changed zero rows, proving idempotence. The repair also reset `444`
affected CLV rows to `missing_closing_line` instead of retaining values derived
from invalid closing observations.

Production capture and scoring jobs now reject `--now` unless `--dry-run` is
also set. Checkpoint deduplication ignores invalid snapshots, and forward
scoring requires the source snapshot to exist no later than the actual
prediction creation time.

The valid rows remain V2 evidence and are not relabeled as V3. Immutable model
identity is preserved.

## First immutable all-side score archive

V3 policy research previously depended on selected historical bets. To compare
V3 with future policy challengers on exactly the same untouched matches,
forward scoring now persists every modeled prematch side before selection in
`ev_model_scores`. `forward_bets` remains the immutable selected-bet ledger.

First live archive run on `2026-07-30`:

- Future matches scored: `2`
- Canonical markets: `30`
- Over/under side scores archived: `48`
- V3-eligible selections before match-level freeze dedupe: `6`
- New V3 bets: `0`, because both matches already had valid frozen predictions
- Target outcome rows read: `0`
- Timing violations: `0`
- Outcome mutation rows: `0`
- Duplicate score keys: `0`
- Fingerprint mismatches: `0`

The immediate rerun inserted `0`, recognized `48` existing scores, and found
`0` conflicts. This proves score persistence is idempotent. The archive does
not prove V3 is profitable; it creates the untouched evidence needed to test
V3 and the nested market-shrinkage challenger without post-selection.

## First V4 score-only archive and policy comparison

The nested-regularization artifact is frozen as:

`ev_nested_logistic_recency45_asof_capped_v4_shadow`

Its manifest hard-requires `--score-only`. A live invocation without that flag
fails before persistence. The first live run and immediate rerun produced:

- V4 scores inserted: `48`
- V4 scores on rerun: `48` existing, `0` conflicts
- V4 forward bets created: `0`
- Valid score timing: `48/48`
- Outcome, duplicate-key, and fingerprint violations: `0`

The immutable score evaluator currently sees `30` common markets:

- V3: `48` scores and `6` policy-eligible sides across `2` matches
- V4: `48` scores and `1` policy-eligible side across `1` match
- Settled selections: `0` for both models

The evaluator freezes the first score batch with an eligible side per match
and ignores later batches for policy selection. All current selections are
pending, so no forward ROI, confidence interval, or winner can yet be
reported.

## First V5 score-only archive

V5 is frozen as:

`ev_ensemble_v3_75_v4_25_shadow`

Its first write and immediate rerun produced:

- Scores inserted: `48`
- Existing scores on rerun: `48`
- Conflicts: `0`
- Forward bets created: `0`
- Valid score timing and fingerprints: `48/48`
- Outcome fields read: `0`
- In-domain scores: `0`
- OOD scores retained for diagnostics: `48`

Registry V3 contains `14` forward policies and has fingerprint
`bb90eee37081e96c236efb6c22de2ff96c6e85859cd6d1e3571d4245c6e1e4f0`.
The four V5 policies were registered before any in-domain V5 outcome. Current
Brazilian rows cannot contribute to ROI, CLV, or promotion.

## Reproduction

Rebuild the selected walk-forward experiment:

```powershell
python scripts\offline_v2\run_ev_market_classifier_experiments.py `
  --offline-v1-dir C:\dev\ullebets-prod\data\derived\offline_v1 `
  --output-dir data\v2\ev_model\experiment_031_asof_snapshot_recency45_full `
  --feature-set compact `
  --train-window-days 90 `
  --recency-half-life-days 45 `
  --evaluation-end-date 2026-05-24 `
  --as-of-snapshot-features `
  --history-availability-buffer-hours 3
```

Rebuild the frozen-candidate audit:

```powershell
python scripts\offline_v2\audit_ev_candidate.py `
  --offline-v1-dir C:\dev\ullebets-prod\data\derived\offline_v1 `
  --predictions data\v2\ev_model\experiment_031_asof_snapshot_recency45_full\predictions.parquet `
  --output-dir data\v2\ev_model\candidate_031_asof_snapshot `
  --model-name logistic_market `
  --minimum-ev 0.075 `
  --maximum-ev 0.25 `
  --history-availability-buffer-hours 3
```

Train the serialized shadow artifact:

```powershell
python scripts\offline_v2\train_ev_shadow_candidate.py `
  --offline-v1-dir C:\dev\ullebets-prod\data\derived\offline_v1 `
  --output-dir data\v2\ev_model\shadow_candidate_asof_capped_v3 `
  --candidate-audit data\v2\ev_model\candidate_032_asof_capped\candidate_audit.json `
  --robustness-audit data\v2\ev_model\candidate_032_asof_capped\robustness\robustness_audit.json `
  --history-availability-buffer-hours 3
```

Freeze new V2 predictions before kickoff:

```powershell
python scripts\forward_v2\score_ev_shadow_model.py --repo-root .
```

Archive V4 scores without creating bets:

```powershell
python scripts\forward_v2\score_ev_shadow_model.py `
  --repo-root . `
  --artifact models\ev\ev_nested_logistic_recency45_asof_capped_v4_shadow\ev_nested_logistic_recency45_asof_capped_v4_shadow.joblib `
  --manifest models\ev\ev_nested_logistic_recency45_asof_capped_v4_shadow\model_manifest.json `
  --score-only
```

Evaluate V3 and V4 from immutable scores:

```powershell
python scripts\forward_v2\evaluate_ev_score_archive.py --repo-root .
```

Rebuild the candidate falsification report:

```powershell
python scripts\offline_v2\audit_ev_candidate_falsification.py
```

Rebuild the complete registered-policy diagnostic:

```powershell
python scripts\offline_v2\audit_ev_registered_policies.py
```

Rebuild the prequential router audit:

```powershell
python scripts\offline_v2\run_ev_prequential_scope_router.py
```

Rebuild the exact scope-identity placebo:

```powershell
python scripts\offline_v2\audit_ev_scope_identity_placebo.py
```

Rebuild V3/V4 model attribution:

```powershell
python scripts\offline_v2\audit_ev_v3_v4_model_attribution.py
```

Rebuild V4 threshold sensitivity:

```powershell
python scripts\offline_v2\audit_ev_v4_policy_thresholds.py
```

Rebuild V4 selection negative controls:

```powershell
python scripts\offline_v2\audit_ev_v4_selection_placebos.py
```

Rebuild Experiments 046-054 and the V5 artifact:

```powershell
python scripts\offline_v2\run_ev_candidate_extension_experiments.py
python scripts\offline_v2\run_ev_asof_context_experiment.py
python scripts\offline_v2\build_ev_v3_v4_ensemble_candidate.py
```

Rebuild Experiments 057-061 and the V6 artifact:

```powershell
python scripts\offline_v2\run_ev_partial_pooling_experiment.py
python scripts\offline_v2\run_ev_stat_interaction_experiment.py
python scripts\offline_v2\run_ev_period_scope_interaction_experiment.py
python scripts\offline_v2\audit_ev_scope_interaction_candidate.py
python scripts\offline_v2\train_ev_scope_interaction_candidate.py
```

Rebuild Experiments 063-067:

```powershell
python scripts\offline_v2\run_ev_scope_interaction_ablation.py
python scripts\offline_v2\run_ev_scope_temporal_robustness.py
python scripts\offline_v2\run_ev_scope_strong_regularization.py
python scripts\offline_v2\audit_ev_v4_policy_thresholds.py `
  --v4-predictions data\v2\ev_model\experiment_060_period_scope_interactions\scope_deviations\predictions.parquet `
  --output-dir data\v2\ev_model\experiment_066_v6_corner_scope_thresholds `
  --prior-comparison-family 135
python scripts\offline_v2\audit_ev_v4_selection_placebos.py `
  --v4-predictions data\v2\ev_model\experiment_060_period_scope_interactions\scope_deviations\predictions.parquet `
  --v4-selections data\v2\ev_model\experiment_060_period_scope_interactions\scope_deviations\exact_policy_selections.parquet `
  --output-dir data\v2\ev_model\experiment_067_v6_corner_scope_placebos `
  --prior-comparison-family 159 `
  --candidate-label v6_scope_interaction_corners_away_total
```

Rebuild Experiments 068-069:

```powershell
python scripts\offline_v2\audit_ev_snapshot_horizons.py `
  --selections data\v2\ev_model\experiment_060_period_scope_interactions\scope_deviations\exact_policy_selections.parquet `
  --output-dir data\v2\ev_model\experiment_068_v6_corner_scope_horizons `
  --stat-key cornerKicks `
  --scope away `
  --scope total
python scripts\offline_v2\run_ev_scope_temporal_consensus.py
```

Rebuild Experiment 070:

```powershell
python scripts\offline_v2\run_ev_nested_count_ensemble.py
```

Rebuild Experiment 071:

```powershell
python scripts\offline_v2\run_ev_snapshot_movement_experiment.py
```

Rebuild Experiment 072:

```powershell
python scripts\offline_v2\run_ev_prequential_movement_blend.py
```

Rebuild Experiments 073-074:

```powershell
python scripts\offline_v2\run_ev_snapshot_ladder_experiment.py
python scripts\offline_v2\run_ev_prequential_movement_blend.py `
  --challenger-predictions data\v2\ev_model\experiment_073_snapshot_ladder\v6_scope_ladder_features\predictions.parquet `
  --challenger-label ladder `
  --experiment-id 074_prequential_ladder_blend `
  --prior-historical-family-size 326 `
  --output-dir data\v2\ev_model\experiment_074_prequential_ladder_blend
```

Rebuild Experiments 075-076:

```powershell
python scripts\offline_v2\run_ev_combined_microstructure_experiment.py
python scripts\offline_v2\run_ev_prequential_movement_blend.py `
  --challenger-predictions data\v2\ev_model\experiment_075_combined_microstructure\v6_microstructure_ensemble_90_5_5\predictions.parquet `
  --challenger-label dual_microstructure_90_5_5 `
  --experiment-id 076_prequential_combined_microstructure `
  --prior-historical-family-size 398 `
  --output-dir data\v2\ev_model\experiment_076_prequential_combined_microstructure
```

Rebuild Experiment 077:

```powershell
python scripts\offline_v2\run_ev_exact_asof_hgb_challenger.py
```

Archive V6 score-only predictions:

```powershell
python scripts\forward_v2\score_ev_shadow_model.py `
  --repo-root . `
  --artifact models\ev\ev_scope_interaction_recency45_asof_capped_v6_shadow\ev_scope_interaction_recency45_asof_capped_v6_shadow.joblib `
  --manifest models\ev\ev_scope_interaction_recency45_asof_capped_v6_shadow\model_manifest.json `
  --score-only
```

Verification:

```powershell
python -m pytest tests\v2 -q
python -m compileall -q src\ullebets_v2\ev_model scripts\offline_v2
```

Do not repeat model/threshold selection on the November-May dataset and call
the result a new holdout. That history has been inspected. The next valid
confirmatory evidence must come from new forward predictions saved before
kickoff.
