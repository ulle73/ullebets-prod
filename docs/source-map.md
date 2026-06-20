# Ullebets Prod Source Map

Target new repository: `ulle73/ullebets-prod`

This document is the source contract for a full rebuild of the Ullebets football stat-market engine.

The old repository is **not** the architecture to continue. It is only a reference for providers, endpoints, payload shapes, existing MongoDB collections, stat extraction examples, settlement examples, and CLV/backtest data flow.

Production code in the new repository must be rewritten from scratch.

---

## 0. Rebuild rules

These rules are intentionally strict. Their purpose is to stop the new project from inheriting the unstable parts of the old repository.

### Old code usage

Old files may be copied into:

```txt
/reference/old-ullebets/
```

They are **read-only reference material**.

Production code must live under:

```txt
/src/
/scripts/
```

Production code must **not** import from `/reference`.

### Forbidden

Do not copy the old architecture.

Do not copy old scripts directly into production.

Do not copy any hardcoded API keys.

Do not use `C:/Users/ryd`, OneDrive paths, or any local machine path.

Do not commit raw data dumps into Git.

Do not mutate existing source MongoDB collections.

Do not build UI first.

Do not optimize for all markets before the first target works.

Do not trust old stat mappings blindly.

Do not assume old odds market IDs are correct for stat markets.

### Required

All credentials must come from environment variables.

All generated datasets must have `datasetVersion`.

All feature sets must have `featureVersion`.

All model outputs must have `modelVersion`.

All backtests must have `backtestRunId`.

All features must be built only from matches before the current match kickoff.

Every market mapping must be audited before model results are trusted.

Every settlement rule must be tested before ROI is trusted.

---

## 1. Project goal

Build a stable, reproducible engine for football count-stat markets.

The first target market family:

```txt
shots
shots_on_target
corners
```

The first required scopes:

```txt
match_total_ft
home_team_ft
away_team_ft
home_team_1h
away_team_1h
home_team_2h
away_team_2h
```

This creates 21 initial stat targets:

```txt
3 stats × 7 scopes = 21 targets
```

The system must be config-driven so more count stats can be added later.

Examples of future stats:

```txt
fouls
offsides
yellow_cards
saves
tackles
passes
```

---

## 2. First milestone

Do **not** build all markets first.

First milestone:

```txt
shots.home_team.ft
```

For this one target, build a complete reproducible pipeline:

```txt
source data inspection
market mapping
actionable odds rows
actual stat outcome
pre-match features
walk-forward backtest
ROI/CLV report
```

The first report must include:

```txt
bets
turnover
profit
ROI
ROI ex largest win
hit rate
average odds
average edge
CLV
beat closing percentage
max drawdown
profit by league
profit by odds bucket
profit by line bucket
```

Only after this works should the system expand to all 21 stat targets.

---

## 3. Required new repository layout

Recommended layout:

```txt
ullebets-prod/
  .env.example
  package.json
  README.md

  docs/
    source-map.md
    data-contract.md
    market-definition-audit.md
    methodology.md
    rebuild-rules.md

  reference/
    old-ullebets/
      README.md
      rapidApi/
        scheduled-matches.js
        match-statistics.js
        odds.js
        urls.js
        http-helpers.js
      stats/
        constants.js
        tuples.js
        matchupsOutcome.js
      research/
        research_eval.js

  src/
    config/
      statTargets.ts
      statPatterns.ts
      providers.ts
      markets.ts

    providers/
      rapidapiClient.ts
      sofascoreClient.ts

    ingestion/
      fetchUpcomingMatches.ts
      fetchMatchStatistics.ts
      fetchMatchOdds.ts
      fetchFinishedResults.ts
      importOldTeamstats.ts

    normalize/
      normalizeMatch.ts
      normalizeStatistics.ts
      normalizeOdds.ts
      normalizeMarket.ts

    stats/
      extractStatTuple.ts
      resolveOutcome.ts
      periods.ts

    dataset/
      buildMarketDataset.ts
      buildFeatureRows.ts
      validateDataset.ts

    models/
      bookmakerBaseline.ts
      countModel.ts
      mlModel.ts
      calibrate.ts

    backtest/
      walkForward.ts
      settle.ts
      clv.ts
      metrics.ts

    reports/
      writeBacktestReport.ts

  scripts/
    inspect-old-sources.ts
    ingest-upcoming.ts
    ingest-historical-stats.ts
    ingest-odds.ts
    build-dataset.ts
    run-backtest.ts
    train-model.ts
    score-today.ts

  data/
    README.md
    .gitkeep
```

---

## 4. Environment variables and placeholders

No real secrets should ever be committed.

Create `.env.example` with placeholders.

```env
# Runtime
NODE_ENV=development
LOG_LEVEL=info
TZ=UTC

# MongoDB
MONGODB_URI=__PASTE_MONGODB_URI_HERE__
SOURCE_DB=app
RESEARCH_DB=ullebets_stat_research

# RapidAPI keys
# Use comma-separated keys. Never commit real keys.
RAPIDAPI_KEYS=__PASTE_RAPIDAPI_KEY_1_HERE__,__PASTE_RAPIDAPI_KEY_2_HERE__,__PASTE_RAPIDAPI_KEY_3_HERE__

# Optional individual aliases if implementation wants named keys
RAPIDAPI_KEY_PRIMARY=__PASTE_PRIMARY_RAPIDAPI_KEY_HERE__
RAPIDAPI_KEY_SECONDARY=__PASTE_SECONDARY_RAPIDAPI_KEY_HERE__
RAPIDAPI_KEY_TERTIARY=__PASTE_TERTIARY_RAPIDAPI_KEY_HERE__

# RapidAPI provider base URLs
RAPIDAPI_SPORTAPI7_BASE_URL=https://sportapi7.p.rapidapi.com
RAPIDAPI_SOFASCORE_BASE_URL=https://sofascore.p.rapidapi.com
RAPIDAPI_SPORT_API_REAL_TIME_BASE_URL=https://sport-api-real-time.p.rapidapi.com
RAPIDAPI_SOFASCORE_SPORT_API_BASE_URL=https://sofascore-sport-api.p.rapidapi.com
RAPIDAPI_SOFASPORT_BASE_URL=https://sofasport.p.rapidapi.com

# Public fallback
SOFASCORE_PUBLIC_API_BASE_URL=https://www.sofascore.com/api/v1

# Optional rate limits and retry config
API_TIMEOUT_MS=15000
API_RETRY_COUNT=3
API_RETRY_BACKOFF_MS=1000
API_MAX_CONCURRENCY=3

# Dataset versions
DATASET_VERSION=stat_dataset_v1
FEATURE_VERSION=features_v1
MODEL_VERSION=baseline_v1
```

The implementation may rename env vars only if `.env.example`, docs, and validation code are updated together.

---

## 5. Reference files from old repo

Copy only the following files from the old repo into `/reference/old-ullebets/`.

Do **not** copy the entire old repo.

### 5.1 Upcoming matches reference

Old files:

```txt
rapidApi/scheduled-matches.js
rapidApi/urls.js
rapidApi/http-helpers.js
```

Purpose:

Understand how the old repo fetched upcoming football matches.

The old file `scheduled-matches.js` showed a multi-provider discovery strategy for scheduled football events.

Known endpoint patterns:

```txt
sportapi7:
  /api/v1/sport/football/scheduled-events/{date}

sofascore RapidAPI:
  /tournaments/get-scheduled-events

sport-api-real-time RapidAPI:
  /tournaments/scheduled-events

sofascore-sport-api RapidAPI:
  /api/sport/football/scheduled-events/{date}

SofaScore public fallback:
  /sport/football/scheduled-events/{date}
```

Important old behavior to understand:

```txt
- date-based match discovery
- categoryId filtering
- includeGlobalEndpoint flag
- RapidAPI provider fallback
- public SofaScore fallback
```

New implementation requirement:

Build a provider abstraction that returns normalized upcoming matches.

Do not let provider-specific payloads leak into the rest of the system.

Normalized upcoming match shape:

```ts
export type NormalizedMatch = {
  matchId: string;
  provider: string;
  providerMatchId: string;
  leagueId?: string;
  leagueName?: string;
  season?: string;
  homeTeamId: string;
  homeTeamName: string;
  awayTeamId: string;
  awayTeamName: string;
  kickoffTime: string;
  status?: string;
  rawRef?: {
    collection?: string;
    documentId?: string;
    file?: string;
  };
};
```

---

### 5.2 Match statistics reference

Old files:

```txt
rapidApi/match-statistics.js
rapidApi/urls.js
rapidApi/http-helpers.js
```

Purpose:

Understand how match statistics were fetched from RapidAPI providers and SofaScore fallback.

Known endpoint patterns:

```txt
sportapi7:
  /api/v1/event/{matchId}/statistics

sofascore RapidAPI:
  /matches/get-statistics

sport-api-real-time RapidAPI:
  /matches/statistics

sofascore-sport-api RapidAPI:
  /api/event/{matchId}/statistics

sofasport RapidAPI:
  /v1/events/statistics

SofaScore public fallback:
  /event/{matchId}/statistics
```

Important old behavior to understand:

```txt
- try multiple providers
- treat 404/empty payloads as recoverable
- support multiple payload shapes
- extract statistics groups and statisticsItems
- normalize home/away values
```

New implementation requirement:

Build a statistics ingestion layer that stores raw payloads and emits normalized stat tuples.

Raw payloads should be stored separately from normalized records.

Normalized stat tuple shape:

```ts
export type NormalizedStatTuple = {
  matchId: string;
  provider: string;
  stat: "shots" | "shots_on_target" | "corners" | string;
  period: "FT" | "H1" | "H2";
  home: number | null;
  away: number | null;
  total: number | null;
  sourceField?: string;
  confidence: "high" | "medium" | "low";
  rawRef?: {
    collection?: string;
    documentId?: string;
    file?: string;
  };
};
```

---

### 5.3 Odds reference

Old files:

```txt
rapidApi/odds.js
rapidApi/urls.js
rapidApi/http-helpers.js
```

Purpose:

Understand how odds were fetched and how market endpoints were discovered.

Known endpoint patterns:

```txt
sportapi7:
  /api/v1/event/{matchId}/odds/{market}/all

sofascore RapidAPI:
  /matches/get-all-odds

sport-api-real-time RapidAPI:
  /matches/all-odds

sofascore-sport-api RapidAPI:
  /api/event/{matchId}/odds/{market}/all

sofasport RapidAPI:
  /v1/events/odds/all
```

Old repo historically tried these market IDs:

```txt
1
5
226
317
100
```

Critical warning:

Do **not** assume those market IDs are correct for shots, shots on target, or corners.

The new repo must perform market discovery and market audit.

Market discovery must inspect market names, group names, line names, selection names, provider IDs, and odds payloads to map them to stat targets.

Normalized odds row shape:

```ts
export type NormalizedOddsRow = {
  matchId: string;
  provider: string;
  bookmaker?: string;
  marketId?: string;
  marketName?: string;
  targetId?: string;
  stat?: string;
  scope?: "match_total" | "home_team" | "away_team";
  period?: "FT" | "H1" | "H2";
  line: number;
  side: "over" | "under";
  odds: number;
  capturedAt: string;
  isClosing?: boolean;
  mappingConfidence: "high" | "medium" | "low";
  rawRef?: {
    collection?: string;
    documentId?: string;
    file?: string;
  };
};
```

---

### 5.4 Base URLs and provider env reference

Old file:

```txt
rapidApi/urls.js
```

Purpose:

Understand provider base URLs and expected env vars.

Known old env vars:

```txt
RAPIDAPI_SPORTAPI7_BASE_URL
RAPIDAPI_SOFASCORE_BASE_URL
RAPIDAPI_SPORT_API_REAL_TIME_BASE_URL
RAPIDAPI_SOFASCORE_SPORT_API_BASE_URL
RAPIDAPI_SOFASPORT_BASE_URL
SOFASCORE_PUBLIC_API_BASE_URL
```

New implementation requirement:

Centralize provider config in:

```txt
src/config/providers.ts
```

Validate env vars at startup.

Fail fast if required env vars are missing.

Never silently fall back to a developer machine path or a secret in code.

---

### 5.5 HTTP fallback and key rotation reference

Old file:

```txt
rapidApi/http-helpers.js
```

Purpose:

Understand old fallback behavior.

The old helper handled concepts like:

```txt
multiple providers
multiple RapidAPI keys
x-rapidapi-key
x-rapidapi-host
query params
timeouts
404 fallback
empty payload fallback
public SofaScore fallback
```

New implementation requirement:

Rewrite as a typed provider client.

Expected behaviors:

```txt
- timeout per request
- retry with exponential backoff
- key rotation on rate-limit/auth errors where appropriate
- provider result metadata
- structured errors
- no swallowed failures without logs
- no hidden browser dependency unless explicitly configured
```

Provider response metadata shape:

```ts
export type ProviderResult<T> = {
  ok: boolean;
  provider: string;
  endpoint: string;
  status?: number;
  data?: T;
  error?: string;
  attemptedAt: string;
  durationMs: number;
};
```

---

### 5.6 Stat extraction reference

Old files:

```txt
lib/backtest/constants.js
lib/backtest/tuples.js
```

Purpose:

Understand how the old repo identified and extracted stats from SofaScore/RapidAPI statistics payloads.

Old useful concept:

```txt
extract home/away/total values from statistics groups/items
support multiple period groups
normalize item keys and names
```

Critical warning:

Old `STAT_PATTERNS` must not be copied blindly.

The old `totalShots` mapping looked suspicious because it could mix total shots with shots on target. The new implementation must verify all mappings.

Required initial stat mapping:

```ts
export const STAT_PATTERNS = {
  shots: {
    canonical: "shots",
    candidateKeys: ["totalshots", "shots"],
    candidateNames: ["total shots", "shots"],
    mustNotMatch: ["shots on target", "shots on goal", "total shots on goal"],
  },
  shots_on_target: {
    canonical: "shots_on_target",
    candidateKeys: ["shotsongoal", "shotson goal", "shotsontarget", "shots on target"],
    candidateNames: ["shots on goal", "shots on target"],
  },
  corners: {
    canonical: "corners",
    candidateKeys: ["cornerkicks", "corners"],
    candidateNames: ["corner kicks", "corners"],
  },
};
```

The implementation must include tests with representative payloads.

---

### 5.7 Outcome and settlement reference

Old file:

```txt
lib/matchupsOutcome.js
```

Purpose:

Understand how old repo resolved actual stat outcomes using:

```txt
statKey
period
scope
```

New implementation requirement:

Rewrite this as:

```txt
src/stats/resolveOutcome.ts
src/backtest/settle.ts
```

Expected API:

```ts
export type StatTarget = {
  id: string;
  stat: string;
  scope: "match_total" | "home_team" | "away_team";
  period: "FT" | "H1" | "H2";
};

export type OutcomeResolution = {
  matchId: string;
  targetId: string;
  actualValue: number | null;
  homeValue?: number | null;
  awayValue?: number | null;
  confidence: "high" | "medium" | "low";
  reason?: string;
};
```

Settlement must be deterministic:

```ts
export function settleOverUnder(params: {
  side: "over" | "under";
  line: number;
  actualValue: number;
}): "win" | "loss" | "push";
```

For half-lines like `4.5`, push is impossible.

For integer lines, settlement rules must match bookmaker rules.

---

### 5.8 CLV and historical backtest data-flow reference

Old file:

```txt
scripts/research_eval.js
```

Purpose:

Understand old data flow for:

```txt
analysis-snapshots
teamstats
closing-line-tracking
actual outcome lookup
ROI
CLV
```

Important old collections:

```txt
analysis-snapshots
teamstats
closing-line-tracking
```

New implementation requirement:

Do not copy old ranking logic.

Do not copy old policy mutation logic.

Only use this file to understand how existing data may be linked.

New CLV shape:

```ts
export type ClvResult = {
  oddsTaken: number;
  closingOdds: number | null;
  clvDecimal?: number | null;
  beatClosing?: boolean | null;
};
```

Suggested decimal CLV approximation:

```txt
clvDecimal = oddsTaken / closingOdds - 1
```

Only calculate this when both odds are valid decimal odds for the same side and line.

---

## 6. Existing MongoDB source collections

Existing MongoDB is source data and must be treated as read-only.

Inspect these collections:

```txt
teamstats
analysis-snapshots
closing-line-tracking
job_state
```

Also inspect any collections matching:

```txt
matches
fixtures
odds
results
events
snapshots
teamprofiles
```

Do not assume collection schemas.

The first script should inspect and summarize available schemas:

```txt
scripts/inspect-old-sources.ts
```

It should output:

```txt
collection name
estimated document count
sample document keys
date fields found
match id fields found
team id fields found
odds fields found
stat payload fields found
```

---

## 7. New derived MongoDB collections

Create new collections in the research database.

Recommended database:

```txt
RESEARCH_DB=ullebets_stat_research
```

Recommended collections:

```txt
raw_provider_payloads
normalized_matches
normalized_match_stats
normalized_odds
stat_market_dataset
stat_feature_rows
stat_backtest_runs
stat_backtest_trades
stat_model_registry
stat_data_quality_reports
market_mapping_audit
```

### 7.1 raw_provider_payloads

Purpose:

Store raw API responses or old raw payload imports.

Suggested fields:

```ts
{
  provider: string;
  endpoint: string;
  params: Record<string, unknown>;
  capturedAt: string;
  payloadHash: string;
  payload: unknown;
  source: "api" | "old_mongo" | "old_file";
}
```

### 7.2 normalized_matches

Purpose:

One normalized match record per match.

Suggested indexes:

```txt
matchId unique
kickoffTime
homeTeamId
awayTeamId
leagueId
```

### 7.3 normalized_match_stats

Purpose:

One stat tuple per match/stat/period.

Suggested unique key:

```txt
matchId + stat + period
```

### 7.4 normalized_odds

Purpose:

One odds row per match/target/line/side/bookmaker/capturedAt.

Suggested indexes:

```txt
matchId
targetId
capturedAt
bookmaker
marketId
```

### 7.5 stat_market_dataset

Purpose:

Training/backtest rows.

One row per:

```txt
match + stat target + line + side + odds snapshot
```

Suggested shape:

```ts
export type StatMarketDatasetRow = {
  datasetVersion: string;
  featureVersion: string;
  matchId: string;
  kickoffTime: string;
  leagueId?: string;
  leagueName?: string;
  homeTeamId: string;
  homeTeamName: string;
  awayTeamId: string;
  awayTeamName: string;
  targetId: string;
  stat: string;
  scope: "match_total" | "home_team" | "away_team";
  period: "FT" | "H1" | "H2";
  line: number;
  side: "over" | "under";
  odds: number;
  capturedAt: string;
  closingOdds?: number | null;
  actualValue?: number | null;
  result?: "win" | "loss" | "push" | "unsettled";
  featuresJson?: Record<string, number | string | boolean | null>;
  mappingConfidence: "high" | "medium" | "low";
  outcomeConfidence: "high" | "medium" | "low";
  createdAt: string;
};
```

---

## 8. Stat target config

All stat targets must be generated from config, not hardcoded throughout the codebase.

Initial config:

```ts
export const STAT_TARGETS = [
  { id: "shots.match_total.ft", stat: "shots", scope: "match_total", period: "FT" },
  { id: "shots.home_team.ft", stat: "shots", scope: "home_team", period: "FT" },
  { id: "shots.away_team.ft", stat: "shots", scope: "away_team", period: "FT" },
  { id: "shots.home_team.h1", stat: "shots", scope: "home_team", period: "H1" },
  { id: "shots.away_team.h1", stat: "shots", scope: "away_team", period: "H1" },
  { id: "shots.home_team.h2", stat: "shots", scope: "home_team", period: "H2" },
  { id: "shots.away_team.h2", stat: "shots", scope: "away_team", period: "H2" },

  { id: "shots_on_target.match_total.ft", stat: "shots_on_target", scope: "match_total", period: "FT" },
  { id: "shots_on_target.home_team.ft", stat: "shots_on_target", scope: "home_team", period: "FT" },
  { id: "shots_on_target.away_team.ft", stat: "shots_on_target", scope: "away_team", period: "FT" },
  { id: "shots_on_target.home_team.h1", stat: "shots_on_target", scope: "home_team", period: "H1" },
  { id: "shots_on_target.away_team.h1", stat: "shots_on_target", scope: "away_team", period: "H1" },
  { id: "shots_on_target.home_team.h2", stat: "shots_on_target", scope: "home_team", period: "H2" },
  { id: "shots_on_target.away_team.h2", stat: "shots_on_target", scope: "away_team", period: "H2" },

  { id: "corners.match_total.ft", stat: "corners", scope: "match_total", period: "FT" },
  { id: "corners.home_team.ft", stat: "corners", scope: "home_team", period: "FT" },
  { id: "corners.away_team.ft", stat: "corners", scope: "away_team", period: "FT" },
  { id: "corners.home_team.h1", stat: "corners", scope: "home_team", period: "H1" },
  { id: "corners.away_team.h1", stat: "corners", scope: "away_team", period: "H1" },
  { id: "corners.home_team.h2", stat: "corners", scope: "home_team", period: "H2" },
  { id: "corners.away_team.h2", stat: "corners", scope: "away_team", period: "H2" },
] as const;
```

No model code should need to know whether the target is shots or corners.

Model code should operate on generic count targets.

---

## 9. Market mapping audit

This is the most important risk area.

The expensive assumption is that odds markets, stat fields, and settlement outcomes refer to the exact same thing.

Before any ROI result is trusted, prove:

```txt
1. odds market maps to the correct stat target
2. outcome value is extracted from the same definition
3. closing odds are linked to the same side and line
4. features are built only from pre-match data
```

Create:

```txt
docs/market-definition-audit.md
```

For every market mapping, record:

```txt
targetId
provider
bookmaker
marketId
marketName
selectionName
lineFormat
period
scope
stat
sampleMatchIds
mappedOutcomeField
confidence
knownRisks
```

Example:

```md
## shots.home_team.ft

Provider: TBD
Bookmaker: TBD
Market ID: TBD
Market names observed:
- TBD

Selection names observed:
- Over 12.5
- Under 12.5

Outcome source:
- normalized_match_stats.stat = shots
- normalized_match_stats.period = FT
- scope = home_team

Definition confidence: TBD

Risks:
- Need to verify whether provider stat includes blocked shots.
- Need to verify whether bookmaker definition matches provider stat.
```

Important practical note:

If historical settlement matches the same provider stat consistently, the blocked-shot debate is secondary.

The core question is not philosophical.

The core question is:

```txt
Does the bookmaker market settle against the same count that our outcome extractor returns?
```

If yes, the target is usable.

If no, ROI is invalid.

---

## 10. Feature generation rules

Features must be generated only from data available before kickoff.

Mandatory rule:

```txt
previousMatch.kickoffTime < currentMatch.kickoffTime
```

Never use:

```txt
current match stats
future matches
closing odds as a pre-match feature unless modeling at close and timestamp allows it
final result
post-match status
```

Initial feature set:

```txt
home_stat_for_l3
home_stat_for_l5
home_stat_for_l10
home_stat_against_l3
home_stat_against_l5
home_stat_against_l10

away_stat_for_l3
away_stat_for_l5
away_stat_for_l10
away_stat_against_l3
away_stat_against_l5
away_stat_against_l10

home_home_stat_for_l5
home_home_stat_against_l5
away_away_stat_for_l5
away_away_stat_against_l5

league_stat_avg
combined_expected_count
line
odds
vig_free_implied_probability
```

For H1/H2 targets, include period-specific historical features:

```txt
home_h1_stat_for_l5
home_h1_stat_against_l5
away_h1_stat_for_l5
away_h1_stat_against_l5
home_h2_stat_for_l5
home_h2_stat_against_l5
away_h2_stat_for_l5
away_h2_stat_against_l5
```

---

## 11. Modeling rules

Do not train a model to predict ROI directly.

Train models to estimate either:

```txt
expected count
P(over line)
P(under line)
```

Then calculate:

```txt
fair_odds = 1 / probability
EV = probability * odds - 1
```

Initial baselines:

```txt
1. bookmaker vig-free implied probability
2. simple count model
3. Poisson or Negative Binomial count model
```

Only after the dataset is proven correct should ML be added.

Suggested later models:

```txt
logistic regression
LightGBM/XGBoost/CatBoost
calibrated ensemble
```

The bookmaker baseline is mandatory.

If the model cannot beat vig-free market probability and closing line over time, it has no proven edge.

---

## 12. Backtest requirements

Use walk-forward validation.

Do not use random train/test split.

Recommended procedure:

```txt
For each month in validation period:
  train on all data before month
  predict that month
  settle bets
  store trades
  move to next month
```

Mandatory report metrics:

```txt
bets
turnover
profit
ROI
ROI ex largest win
hit rate
average odds
average edge
CLV
beat closing percentage
max drawdown
profit by league
profit by odds bucket
profit by line bucket
profit by target
profit by period
profit by scope
```

Minimum promotion gates before any model can be considered useful:

```txt
min 500 bets per stat family
min 100 bets per target
ROI ex largest win > 0
CLV > 0
beat closing percentage > 52%
no single league contributes more than 30% of total profit
all leakage tests pass
all settlement tests pass
all high-volume market mappings have medium/high confidence
```

These thresholds can be tuned later, but no model should be trusted with tiny samples.

---

## 13. Betting rule for initial backtests

Do not bet every positive EV row.

Initial filters:

```txt
edge >= 0.04
odds >= 1.60
odds <= 2.60
mappingConfidence != low
outcomeConfidence != low
closingOdds exists for CLV reports
max 1 bet per match + target + side
max 3 bets per match total
```

Test thresholds:

```txt
edge >= 0.02
edge >= 0.04
edge >= 0.06
edge >= 0.08
edge >= 0.10
```

Report each threshold separately.

---

## 14. Tests required

Create tests before trusting any result.

Required tests:

```txt
stat extraction from representative statistics payloads
period mapping FT/H1/H2
home/away/total tuple extraction
market parsing from odds payloads
market target mapping
settlement over/under
integer-line push handling
closing odds linkage
feature no-leakage rule
walk-forward split
ROI calculation
ROI ex largest win calculation
CLV calculation
```

Golden tests should use small fixture datasets where expected outputs are known exactly.

---

## 15. Raw teamstats folder

The user will manually copy the old `teamstats` folder into the new repo or local workspace.

Important:

Do not commit large raw data dumps to Git unless explicitly requested.

Recommended local path:

```txt
data/raw/teamstats/
```

Recommended import script:

```txt
scripts/import-old-teamstats.ts
```

The import script should:

```txt
read raw files
hash payloads
store raw payload refs
normalize matches
normalize match stats
write data quality report
be idempotent
never duplicate matches
never mutate old source collections
```

If raw teamstats are too large for Git, use local disk or object storage and document the path.

---

## 16. Docs to create before heavy coding

Before building models, create:

```txt
docs/data-contract.md
docs/market-definition-audit.md
docs/methodology.md
docs/rebuild-rules.md
```

### data-contract.md

Must define:

```txt
NormalizedMatch
NormalizedStatTuple
NormalizedOddsRow
StatMarketDatasetRow
FeatureRow
PredictionRow
BacktestRun
BacktestTrade
```

### market-definition-audit.md

Must document every odds-to-outcome mapping.

### methodology.md

Must explain:

```txt
why counts are predicted instead of ROI
why walk-forward is used
how CLV is calculated
how ROI ex largest win is calculated
how leakage is prevented
how model promotion works
```

### rebuild-rules.md

Must repeat:

```txt
/reference is read-only
/src is production
no hardcoded keys
no local paths
no production imports from old files
existing MongoDB is source only
```

---

## 17. Codex implementation instruction

Use this exact instruction when starting the new build:

```txt
Build a completely new repo from scratch.

Do not continue the old architecture.

Use docs/source-map.md as the source contract.

Old files under /reference/old-ullebets/ are read-only examples. They exist only to understand endpoints, payload shapes, Mongo collections, stat extraction and settlement. Do not import from them in production code.

Rewrite everything under /src.

First task:
1. Read docs/source-map.md.
2. Inspect the reference files.
3. Create docs/data-contract.md, docs/market-definition-audit.md and docs/methodology.md.
4. Build the first pipeline for shots.home_team.ft:
   - inspect source data
   - normalize stats
   - map odds market
   - resolve actual outcome
   - build dataset rows
   - build pre-match features
   - run walk-forward backtest
   - report ROI, ROI ex largest win and CLV

Do not build UI.
Do not build live betting.
Do not optimize for all markets yet.
Do not mutate old Mongo collections.
Do not copy old scripts into production.
```

---

## 18. Final warning

The hardest part is not writing a model.

The hardest part is proving the rows are real.

No ROI result is valid until these are true:

```txt
odds market = correct stat target
outcome = same count definition
closing odds = same side and line
features = only pre-match data
backtest = walk-forward
sample size = large enough
```

A weak model on clean data is useful.

A strong model on dirty mappings is worthless.
