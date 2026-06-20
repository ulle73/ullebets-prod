# Ullebets Prod — Source Map

This file exists so the new repo can be driven by a very short prompt.

## Short prompt to use

```txt
Build a model that finds positive ROI bets for football stat markets.

You may inspect and take inspiration from the old repo at:
C:\dev\FRONTEND\ullebets-vecel

I have historical data, historical Unibet odds and lines, historical results/outcomes for the lines, and historical team statistics. Use the sources in docs/source-map.md to understand where the data comes from and how it was fetched.

Rewrite the implementation in this repo. Do not copy the old architecture blindly.
```

## Real goal

Find +ROI opportunities on football count/stat markets:

- total shots in match
- home team shots FT
- away team shots FT
- home team shots 1H
- away team shots 1H
- home team shots 2H
- away team shots 2H

Repeat the same structure for:

- shots on target
- corners

The system should be easy to extend later to more stats.

## Old repo reference

Old repo local path:

```txt
C:\dev\FRONTEND\ullebets-vecel
```

Old repo should be used as a **source/reference**, not as architecture to copy.

The agent may inspect the old repo to understand:

- how upcoming matches were fetched
- how match statistics were fetched
- how odds and lines were fetched
- how historical stats were stored
- how outcomes were resolved
- how CLV/closing odds were tracked
- which MongoDB collections already exist

The agent should not blindly copy:

- old ranking logic
- old research/autoloop logic
- old frontend logic
- old GitHub Actions
- hardcoded API keys
- local Windows/OneDrive paths
- old scripts that mix fetch, import, DB writes and research logic

## Most useful old files to inspect

### Upcoming matches

```txt
rapidApi/scheduled-matches.js
rapidApi/urls.js
rapidApi/http-helpers.js
```

Purpose:

- shows how upcoming football matches were fetched
- shows provider fallback behavior
- shows date-based scheduled match discovery

Known endpoint patterns:

```txt
/api/v1/sport/football/scheduled-events/{date}
/tournaments/get-scheduled-events
/tournaments/scheduled-events
/api/sport/football/scheduled-events/{date}
/sport/football/scheduled-events/{date}
```

### Match statistics

```txt
rapidApi/match-statistics.js
rapidApi/urls.js
rapidApi/http-helpers.js
```

Purpose:

- shows how historical/final match statistics were fetched
- shows the payload shapes used to extract shots, shots on target and corners
- shows RapidAPI + SofaScore fallback strategy

Known endpoint patterns:

```txt
/api/v1/event/{matchId}/statistics
/matches/get-statistics
/matches/statistics
/api/event/{matchId}/statistics
/v1/events/statistics
/event/{matchId}/statistics
```

### Odds and lines

```txt
rapidApi/odds.js
rapidApi/urls.js
rapidApi/http-helpers.js
```

Purpose:

- shows how odds were fetched
- shows how old repo queried multiple odds market IDs
- useful for understanding where Unibet odds/lines came from if stored in DB/snapshots

Known endpoint patterns:

```txt
/api/v1/event/{matchId}/odds/{market}/all
/matches/get-all-odds
/matches/all-odds
/api/event/{matchId}/odds/{market}/all
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

Important:

Do not assume these IDs are correct for every stat market. Inspect historical odds/line payloads and map markets by actual market names, lines, sides and outcomes.

### Stat extraction

```txt
lib/backtest/constants.js
lib/backtest/tuples.js
```

Purpose:

- shows how old repo extracted stat tuples from match statistics
- relevant for shots, shots on target and corners
- shows how periods and home/away values were handled

Important:

Verify the old stat mappings. Do not blindly trust them. In particular, make sure shots and shots on target are not mixed.

### Outcome / settlement

```txt
lib/matchupsOutcome.js
```

Purpose:

- shows how old repo resolved actual outcome values from:
  - stat key
  - period
  - scope
  - match/team stats

This is important because the model is worthless if the odds market and outcome stat do not refer to the same thing.

### CLV / backtest reference

```txt
scripts/research_eval.js
```

Purpose:

- shows old flow for:
  - reading historical analysis snapshots
  - reading teamstats
  - reading closing-line-tracking
  - resolving actual outcomes
  - calculating ROI
  - calculating CLV

Use it to understand available data and collection names. Do not copy old ranking strategy.

## Existing data sources to inspect

Existing MongoDB should be treated as historical source data.

Inspect these collections if present:

```txt
teamstats
analysis-snapshots
closing-line-tracking
job_state
```

Also inspect any collections with names related to:

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
teamstats
```

The key question is whether the DB contains, for each historical bettable market:

```txt
match id
kickoff time
home team
away team
market name
stat type
period
scope
line
side
odds
bookmaker
captured time
closing odds / closing line if available
actual result / outcome
```

## Raw files to copy manually

The user will manually copy raw historical teamstats into the new repo or local data folder.

Expected source folder from old repo:

```txt
data/teamstats
```

This folder is raw/historical API data and is useful for rebuilding features and outcomes.

Do not require it to be committed to Git. It can live locally.

## Environment variables needed

Do not commit real secrets.

Create local `.env` manually from these names:

```txt
MONGODB_URI
SOURCE_DB
RESEARCH_DB

RAPIDAPI_KEYS
RAPIDAPI_KEY_PRIMARY
RAPIDAPI_KEY_SECONDARY
RAPIDAPI_KEY_TERTIARY

RAPIDAPI_SPORTAPI7_BASE_URL
RAPIDAPI_SOFASCORE_BASE_URL
RAPIDAPI_SPORT_API_REAL_TIME_BASE_URL
RAPIDAPI_SOFASCORE_SPORT_API_BASE_URL
RAPIDAPI_SOFASPORT_BASE_URL

SOFASCORE_PUBLIC_API_BASE_URL

API_TIMEOUT_MS
API_RETRY_COUNT
API_RETRY_BACKOFF_MS
API_MAX_CONCURRENCY

DATASET_VERSION
FEATURE_VERSION
MODEL_VERSION
```

Suggested non-secret defaults:

```txt
SOURCE_DB=app
RESEARCH_DB=ullebets_stat_research

RAPIDAPI_SPORTAPI7_BASE_URL=https://sportapi7.p.rapidapi.com
RAPIDAPI_SOFASCORE_BASE_URL=https://sofascore.p.rapidapi.com
RAPIDAPI_SPORT_API_REAL_TIME_BASE_URL=https://sport-api-real-time.p.rapidapi.com
RAPIDAPI_SOFASCORE_SPORT_API_BASE_URL=https://sofascore-sport-api.p.rapidapi.com
RAPIDAPI_SOFASPORT_BASE_URL=https://sofasport.p.rapidapi.com

SOFASCORE_PUBLIC_API_BASE_URL=https://www.sofascore.com/api/v1

API_TIMEOUT_MS=15000
API_RETRY_COUNT=3
API_RETRY_BACKOFF_MS=1000
API_MAX_CONCURRENCY=3

DATASET_VERSION=stat_dataset_v1
FEATURE_VERSION=features_v1
MODEL_VERSION=baseline_v1
```

## Data the model should build

The new implementation should build a clean dataset where each row represents one historical bettable stat line.

Required row fields:

```txt
matchId
kickoffTime
league
homeTeam
awayTeam
bookmaker
marketName
targetId
stat
scope
period
line
side
odds
capturedAt
closingOdds
actualValue
result
features
datasetVersion
featureVersion
```

Target examples:

```txt
shots.match_total.ft
shots.home_team.ft
shots.away_team.ft
shots.home_team.h1
shots.away_team.h1
shots.home_team.h2
shots.away_team.h2

shots_on_target.match_total.ft
corners.home_team.ft
corners.away_team.h1
```

## Model expectation

Do not train directly on ROI first.

The model should estimate:

```txt
P(over line)
P(under line)
```

or expected count, then convert that to probability and EV.

Required comparisons:

```txt
model probability vs odds implied probability
EV
ROI
CLV
ROI excluding largest win
profit by target
profit by league
profit by odds bucket
profit by line bucket
```

## Critical validation

Before trusting any +ROI result, prove:

```txt
1. The odds market maps to the same stat as the outcome.
2. The line and side are parsed correctly.
3. Closing odds/CLV belong to the same market and line.
4. Features use only matches before the current kickoff.
5. Shots, shots on target and corners are not mixed.
6. FT, 1H and 2H are not mixed.
7. Home team, away team and match total are not mixed.
```

If any of those fail, ROI is not valid.

## One-sentence instruction for the agent

Historical data is valuable; old architecture is not.
