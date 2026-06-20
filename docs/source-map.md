# Ullebets Prod — Source Map

This file is only a source map. It is not a plan, schema, architecture, model design, or implementation instruction.

## Short prompt

```txt
Build a model that finds positive ROI plays for football stat markets.

You may inspect and take inspiration from the old repo at:
C:\dev\FRONTEND\ullebets-vecel

I have historical data, historical Unibet odds and lines, historical results/outcomes for the lines, and historical team statistics. Use docs/source-map.md only to understand where the old data sources, API fetch examples, Mongo collections and raw files are.
```

## Old repo

```txt
C:\dev\FRONTEND\ullebets-vecel
```

## Useful old files to inspect

Upcoming matches:

```txt
rapidApi/scheduled-matches.js
rapidApi/urls.js
rapidApi/http-helpers.js
```

Match statistics:

```txt
rapidApi/match-statistics.js
rapidApi/urls.js
rapidApi/http-helpers.js
```

Odds and lines:

```txt
rapidApi/odds.js
rapidApi/urls.js
rapidApi/http-helpers.js
```

Stat extraction examples:

```txt
lib/backtest/constants.js
lib/backtest/tuples.js
```

Outcome / result examples:

```txt
lib/matchupsOutcome.js
```

CLV / historical replay examples:

```txt
scripts/research_eval.js
```

## Existing MongoDB collections to inspect

```txt
teamstats
analysis-snapshots
closing-line-tracking
job_state
```

Also inspect collections related to:

```txt
matches
fixtures
odds
lines
unibet
results
outcomes
snapshots
statistics
analysis
closing
clv
```

## Raw local files

The user will manually copy this folder from the old repo:

```txt
C:\dev\FRONTEND\ullebets-vecel\data\teamstats
```

Possible new location:

```txt
./data/teamstats
```

## Environment placeholders

Environment variable names are listed separately in:

```txt
docs/env-placeholders.md
```

Real values should be added locally by the user, not committed.

## Not included here

This file intentionally does not define repo structure, dataset fields, feature design, model type, backtest method, or implementation plan.
