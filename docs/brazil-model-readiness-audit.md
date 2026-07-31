# Brazil Model Readiness Audit

## Decision

Brazil is not ready for a trained EV model. V3, V4, V5, and V6 must continue
to classify `Brasileirão Série A` as outside their fitted training domain.

## Read-Only Sources

- Database: `app`
- Odds/lines/outcomes: `unibet-backtest`
- Kickoff and team statistics: `teamstats`
- Diagnostic references: `analysis-snapshots`, `result-loop-bets`, and
  `closing-line-tracking`
- Database: `ullebets_unibet`
- Diagnostic raw snapshots only; it did not contain a usable historical
  Brazilian training corpus

No legacy collection was mutated.

## Coverage

| Measure | Result |
| --- | ---: |
| Brazilian backtest documents | 19 |
| Unique Unibet events | 17 |
| Date range | 2025-11-22 to 2025-12-04 |
| Documents linked to teamstats/kickoff | 17 |
| Verified prematch documents | 14 |
| Documents at/after kickoff | 3 |
| Documents without safe kickoff linkage | 2 |
| All market line rows | 2,805 |
| Primary target line rows | 2,216 |
| Primary rows with actual | 2,216 |
| Primary rows missing actual | 0 |
| Primary rows with actual zero | 45 |
| Duplicate primary exposures | 271 |

Primary target rows consisted of `1,794` corner lines, `244` total-shot lines,
and `178` shots-on-goal lines. Period and scope coverage existed, but it came
from only seventeen independent events.

## Timing Failure

Three documents were generated after their linked kickoff:

- Bahia vs Vasco da Gama, 2025-11-23
- São Paulo vs Juventude, 2025-11-23
- Sport Recife vs Vitória, 2025-11-23

They are leakage-risk rows and cannot enter ROI, training, or validation.
Two additional documents could not be safely linked to kickoff and must also
be excluded.

## Statistical Limitation

The effective independent sample is the number of match clusters, not the
number of offered lines. Thousands of correlated thresholds from seventeen
events do not provide enough league regimes, teams, dates, or independent
outcomes for walk-forward training.

A Brazil candidate requires newly archived prematch scores and outcomes over
multiple windows. Until then, Brazilian scores may be retained only for
pipeline diagnostics and must remain excluded by the training-domain audit.
