# Ullebets Original Backend Map

Detta dokument beskriver vad `C:\dev\frontend\ullebets-vecel` faktiskt gor i dag pa backend/data-sidan.
Målet ar inte att forsvara strukturen. Målet ar att frysa nulaget innan V2 byggs om.

## 1. Kort sammanfattning

Originalsystemet ar egentligen inte ett enhetligt backend-system. Det ar en blandning av:

- GitHub Actions
- Node-scripts
- Next API-routes som batchjobben anropar internt
- lokala JSON-filer som versioneras i git
- Mongo-collections med blandade raw- och derived-ansvar

Det funktionella slutresultatet ar att systemet:

- hamtar kommande matcher
- hamtar teamstats/matchstats/resultat
- hamtar Unibet/Kambi-odds
- bygger snapshots i `unibet-backtest`
- bygger matchups/rankings/AI-bets
- rattar utfall och CLV dar det gar
- tranar ML-modeller pa historik

Det som ar svagt ar att samma jobb ofta finns i flera varianter, samma data finns i filer och DB samtidigt, och "sakerhetsbroms" mot fel databas i princip saknas.

## 2. Viktigaste externa kallor

### Matcher, statistik, resultat

- RapidAPI scheduled matches
- RapidAPI match statistics
- RapidAPI incidents
- RapidAPI shotmap
- RapidAPI odds
- SofaScore public API som fallback i vissa steg

### Odds

- Unibet listView via `UNIBET_EVENT_BASE_URL`
- Kambi event-odds via `https://eu1.offering-api.kambicdn.com/offering/v2018/ubse/betoffer/event/{eventId}.json`

### Support-data

- `data/leagues-and-teams.json`
- `data/unibetLeagueUrls.json`
- `data/league_ranking.json`
- Opta rankings JSON via `https://dataviz.theanalyst.com/opta-power-rankings/pr-reference.json`
- extern fallback for `league_ranking.json` via remote URL i `lib/backtest/data.js`

## 3. Primara Mongo-collections i nulaget

### Core ingest / derived

- `match-for-date`
- `teamstats`
- `teamprofiles`
- `unibet-backtest`
- `matchups-score`
- `matchups-league-avg`
- `job_state`

### Prediction / tracking / analytics

- `ai-generated-bets`
- `analysis-snapshots`
- `auto-analysis-runs`
- `auto-analysis-bets`
- `result-loop-bets`
- `closing-line-tracking`
- `watchlist-items`

### Support-data och inkonsistenser

- `leagues-and-teams`
- `leages-and-teams`

Den sista punkten ar ett reellt problem. Originalrepot anvander bade korrekt och felstavad collection, beroende pa fil.

## 4. Overgripande dataflode

### A. Fixtures

1. `scripts/fetch-and-import-fixtures.js`
2. laster ligor/category-plan fran `data/leagues-and-teams.json`
3. hamtar matcher via RapidAPI
4. skriver `matches-for-date/fixtures-YYYY-MM-DD.json`
5. pushar in samma payload i `match-for-date.full[]`

### B. Teamstats / resultat

1. `scripts/update-teams-v2.js`
2. hamtar statistik, incidents, shotmap, odds och resultat
3. skriver lokala `data/teamstats/*.json` och `public/teamstats/*.json`
4. syncar filer till `teamstats`
5. uppdaterar scores inne i `match-for-date`
6. sparar `job_state.update-teams-v2.lastRun`

### C. Teamprofiles

1. `scripts/import-teamstats.js` upsertar teamstats fran fil till DB
2. `scripts/generate-teamprofiles.js`
3. bygger derived teamprofiler fran `teamstats` + `data/leagues-and-teams.json`
4. skriver lokala profiler i `data/teamprofiles/...`
5. upsertar `teamprofiles`
6. kor `scripts/scew.js --save-profiles` som enrichar profilerna vidare

### D. Matchups

1. `scripts/dump-matchups.js`
2. `scripts/dump-matchups-league-avg.js`
3. laser fixtures + teamprofiles
4. bygger ranked matchup-underlag
5. skriver lokala JSON-filer under `data/matchups/...`
6. upsertar `matchups-score` och `matchups-league-avg`
7. `scripts/enrich-matchups-results.js` enrichar samma dokument med utfall via `teamstats` eller RapidAPI fallback

### E. Unibet snapshots

1. `scripts/run-unibet-backtests.js`
2. `scripts/run-unibet-forward-backtests.js`
3. `scripts/run-unibet-closing.js`
4. `scripts/run-unibet-odds-checkpoints.js`
5. dessa använder `lib/runners/backtest-runner.js`
6. runnern:
   - laser fixtures fran `match-for-date`
   - matchar event i Unibet listView
   - hamtar Kambi event-payload
   - mappar marknader via `unibetOddsMapper`
   - raknar EV via `ev-engine`
   - skriver snapshots i `unibet-backtest`

### F. Settlement / correction

1. `scripts/correct-unibet-backtest.js`
2. laser `unibet-backtest`
3. laser `teamstats`
4. satter `actual` och `win` pa varje line i `unibet-backtest`

### G. Auto-analysis / shortlist / CLV / result loop

1. `scripts/run-auto-analysis-checkpoints.js`
2. laser fixtures
3. hamtar Unibet-odds live
4. raknar EV pa shortlist-kandidater
5. skriver:
   - `auto-analysis-runs`
   - `auto-analysis-bets`
   - `analysis-snapshots`
6. `app/api/closing-lines` laser `analysis-snapshots` + `result-loop-bets`, hamtar aktuell marknadsodds och bygger `closing-line-tracking`
7. `app/api/result-loop` sparar forward-bets i `result-loop-bets`, bygger price history i `closing-line-tracking`, och rattar open/settled/CLV i GET
8. `lib/autoAnalysis/rankingFeedback.js` bygger ranking-adjustments fran historiska `analysis-snapshots` + `teamstats`

### H. AI user / AI daily

1. `scripts/generate-daily-bets.js`
2. `scripts/generate-ai-user-combos.js`
3. `app/api/ai/generate-user`
4. dessa laser `matchups-score`, fixtures, Unibet-odds och EV-berakningar
5. sparar snapshots eller dokument i `ai-generated-bets`
6. `app/api/ai/history` läser tillbaka dessa och försöker gradera dem

### I. ML training

1. `scripts/correct-unibet-backtest.js`
2. `machinelearning/data/extract/extractTrainingData.js`
3. Python-traning av tier1/tier2
4. laser i praktiken:
   - `unibet-backtest`
   - `teamstats`
   - `teamprofiles`
   - `leages-and-teams`
5. skriver modeller till repo-filer

## 5. GitHub Actions: vad som kor i dag

## Core workflows

| Workflow | Trigger | Kommando | Huvudansvar |
| --- | --- | --- | --- |
| `import-fixtures-rolling.yml` | var 4:e timme | `node scripts/fetch-and-import-fixtures.js "${START}-${END}"` | bygger `match-for-date` for rullande datumintervall |
| `import-fixtures-dplus7.yml` | dagligen 05:00 UTC | `node scripts/fetch-and-import-fixtures.js "$TARGET"` | bygger D+7 fixtures |
| `update-teamstats-and-teamprofiles.yml` | dagligen 05:00 UTC + manuell | `update-teams-v2` -> `import-teamstats` -> `generate-teamprofiles` | uppdaterar teamstats och profiler |
| `dump-matchups.yml` | dagligen 07:00 UTC | `dump-matchups` + `dump-matchups-league-avg` | bygger matchup-tabeller |
| `enrich-matchups-results.yml` | dagligen 07:00 UTC | `enrich-matchups-results` | lagger till outcomes i matchup-tabeller |
| `run-unibet-backtests.yml` | dagligen 05:30 UTC | `run-unibet-backtests.js` | tar historiska/backtest-snapshots |
| `run-unibet-odds-checkpoints.yml` | var 10:e minut | `run-unibet-odds-checkpoints.js` | checkpointad prematch capture |
| `run-auto-analysis-checkpoints.yml` | dagligen 05:45 UTC | `run-auto-analysis-checkpoints.js` | schemalagd shortlist/auto-analysis |
| `correct-backtests-daily.yml` | dagligen 08:00 UTC | `correct-unibet-backtest.js` | rattar `unibet-backtest` |
| `train-ml-models.yml` | dagligen 05:00 UTC | correction + extract + Python train | producerar ML-modeller |

## AI / user-facing workflows

| Workflow | Trigger | Kommando | Huvudansvar |
| --- | --- | --- | --- |
| `ai-bets-daily.yml` | dagligen 10:00 UTC | `generate-daily-bets.js` | bygger dagliga AI-bets |
| `ai-user-combos.yml` | dagligen 10:00 UTC | `generate-ai-user-combos.js` | bygger user-combos |
| `ai-user-daily.yml` | dagligen 11:00 UTC | inline Node som anropar `/api/ai/generate-user` eller `/api/ai/history` | driver AI user-flodet via HTTP |
| `ai-user-closing.yml` | flera intraday-kronfonstren | re-use av `ai-user-daily.yml` | closing-fonster for AI user |
| `run-unibet-closing.yml` | manuell | `run-unibet-closing.js` | explicit closing capture |
| `run-unibet-forward.yml` | manuell | `run-unibet-forward-backtests.js --date=...` | manuell forward capture |

## Ops / support workflows

| Workflow | Trigger | Kommando | Huvudansvar |
| --- | --- | --- | --- |
| `update-opta.yml` | dagligen 08:00 UTC | `update-opta-id.js` | uppdaterar supportdata med Opta IDs/ranks |
| `backfill-teamstats-from-date.yml` | manuell | reset `job_state` + `update-teams-v2 --yesterday` | backfill |
| `verify-teamstats-db.yml` | manuell | inline Mongo-check | verifierar `teamstats` och `job_state` |
| `debug-rapidapi-endpoints.yml` | manuell | `debug-rapidapi-endpoints.js` | endpoint-diagnostik |

## 6. Viktiga scripts och deras verkliga I/O

### `scripts/fetch-and-import-fixtures.js`

- källor:
  - RapidAPI scheduled matches
  - `data/leagues-and-teams.json`
- laser:
  - env: `MONGODB_URI`, `MONGODB_DB`, `RAPIDAPI_KEYS`, `RAPIDAPI_KEY`
- skriver:
  - fil: `matches-for-date/fixtures-YYYY-MM-DD.json`
  - DB: `match-for-date`
- struktur:
  - upsert pa `_id = date`
  - pushar varje ny import till `full[]`
- risk:
  - inte append-only raw per källa
  - blandar file snapshot och DB update i samma script

### `scripts/update-teams-v2.js`

- källor:
  - RapidAPI statistics, incidents, shotmap, odds, results
  - lokala supportfiler
- laser:
  - `job_state`
  - `match-for-date`
- skriver:
  - `data/teamstats/*.json`
  - `public/teamstats/*.json`
  - `teamstats`
  - `job_state`
  - score-falt i `match-for-date`
- risk:
  - ett mycket stort monolitscript med flera ansvar
  - lokal fil-IO och DB-sync i samma exekvering
  - historiskt kansligt for retries och partiella writes

### `scripts/import-teamstats.js`

- källor:
  - `data/teamstats/*.json`
- skriver:
  - `teamstats`
- modell:
  - ett dokument per fil / team-roll, inte ett dokument per match
- risk:
  - denormaliserad match-sokning
  - match-identitet maste rekonstrueras i efterhand

### `scripts/generate-teamprofiles.js`

- källor:
  - `teamstats`
  - `data/leagues-and-teams.json`
- skriver:
  - `data/teamprofiles/...`
  - `teamprofiles`
- extra:
  - kor `scew.js --save-profiles`
- risk:
  - derived data skrivs bade till filer och DB
  - kaskadjobb utan tydlig run-ledger

### `scripts/dump-matchups.js` och `dump-matchups-league-avg.js`

- källor:
  - `match-for-date`
  - `teamprofiles`
- skriver:
  - `data/matchups/...`
  - `matchups-score`
  - `matchups-league-avg`
- risk:
  - outputs ar already derived ranking-lager, men saknar stabil rå-separation

### `scripts/enrich-matchups-results.js`

- källor:
  - `matchups-score`
  - `matchups-league-avg`
  - `teamstats`
  - RapidAPI fallback
- skriver:
  - updaterade `matchups-score`
  - updaterade `matchups-league-avg`
  - lokala matchups-filer
- risk:
  - rettning sker in-place i already derived dokument

### `lib/runners/backtest-runner.js`

- källor:
  - fixtures via `getMatchesForDateFiltered`
  - Unibet discovery via `getUnibetOddsForMatch`
  - EV via `calculateEvForBet`
- skriver:
  - `writeSnapshot(...)` till default `unibet-backtest`
- snapshotmodell:
  - latest lines pa root
  - snapshots-array i samma dokument
- risk:
  - raw Kambi payload sparas inte separat
  - normalized lines och snapshot history blandas i samma dokument

### `scripts/correct-unibet-backtest.js`

- källor:
  - `unibet-backtest`
  - `teamstats`
- skriver:
  - uppdaterade `lines.actual` och `lines.win` i `unibet-backtest`
- risk:
  - push/void hanteras inte lika tydligt som i nyare routes
  - settlementlogik finns pa flera stallen i systemet

### `scripts/run-auto-analysis-checkpoints.js`

- källor:
  - fixtures
  - `leages-and-teams`
  - Unibet/Kambi
  - teamprofiles/teamstats via EV layer
- skriver:
  - `auto-analysis-runs`
  - `auto-analysis-bets`
  - `analysis-snapshots`
- risk:
  - buildRankingFeedback anvander samma snapshots historiskt, men utan separat data warehouse-lager

### `app/api/result-loop`

- POST skriver:
  - `result-loop-bets`
  - opening price history i `closing-line-tracking`
- GET laser:
  - `result-loop-bets`
  - `teamstats`
  - `closing-line-tracking`
- GET beraknar:
  - status
  - settlement
  - CLV
  - beat closing line
- risk:
  - batchlogik ligger i en Next-route
  - state och analytics uppdateras i request/response-flode

### `app/api/closing-lines`

- laser:
  - `analysis-snapshots`
  - `result-loop-bets`
  - `teamstats`
  - Unibet live odds
- skriver:
  - `closing-line-tracking`
- risk:
  - polling/logik/audit ar kopplat till en route i stallet for ett dedikerat jobb

### `scripts/generate-daily-bets.js`, `scripts/generate-ai-user-combos.js`, `app/api/ai/generate-user`

- källor:
  - `matchups-score`
  - fixtures
  - Unibet odds
  - EV engines
- skriver:
  - `ai-generated-bets`
- risk:
  - tre olika vägar till i princip samma typ av output
  - vissa floden anropar `/api/backtest` internt via HTTP i stallet for en intern service

## 7. API-routes som fungerar som intern backend

Flera routes ar inte bara frontend-API. De ar faktiska batch-komponenter.

### Viktigaste

- `app/api/backtest/route.js`
  - batch EV
  - auto-unibet-odds
  - teamstats fetch
  - leagues fetch
- `app/api/closing-lines/route.js`
  - CLV/closing tracking
- `app/api/result-loop/route.js`
  - forward result tracking + settlementvisning
- `app/api/auto-analysis-runs/route.js`
  - triggar och lagrar auto-analysis
- `app/api/auto-analysis-bets/route.js`
  - visar enriched auto-analysis performance
- `app/api/analysis-snapshots/route.js`
  - skriver/laser shortlist snapshots
- `app/api/ai/generate-user/route.js`
  - bygger AI-user snapshots och sparar i `ai-generated-bets`

Detta ar funktionellt men arkitekturellt svagt. Cron-jobb och interna HTTP-anrop blandas med applikations-API.

## 8. Miljovariabler som faktiskt driver flodet

### Overgripande

- `MONGODB_URI`
- `MONGODB_DB`
- `BASE_URL`

### RapidAPI / SofaScore

- `RAPIDAPI_KEY`
- `RAPIDAPI_KEYS`
- `RAPIDAPI_SPORTAPI7_BASE_URL`
- `RAPIDAPI_SOFASCORE_BASE_URL`
- `RAPIDAPI_SPORT_API_REAL_TIME_BASE_URL`
- `RAPIDAPI_SOFASCORE_SPORT_API_BASE_URL`
- `RAPIDAPI_SOFASPORT_BASE_URL`
- `SOFASCORE_PUBLIC_API_BASE_URL`

### Lokala paths / support

- `TEAMSTATS_DIR`
- `PUBLIC_TEAMSTATS_DIR`
- `ULLEBETS_OLD_REPO_ROOT`
- `LEAGUE_RANKING_URL`
- `BACKEND_BASE_URL`

## 9. Storsta strukturella svagheter i originalsystemet

### 1. Ingen riktig DB-sakerhet

Nastan allt defaultar till:

- `process.env.MONGODB_DB || "app"`

Det betyder att fel `.env` i praktiken kan skriva rakt in i gamla databasen.

### 2. Raw och derived ar hopblandade

Exempel:

- `unibet-backtest` innehaller både senaste normalized lines och snapshots
- `match-for-date` innehaller importer packade i `full[]`
- `teamstats` ar importerad filstruktur, inte canonical matchstruktur

### 3. Samma ansvar finns pa flera stallen

Exempel:

- closing capture finns bade som manuell `run-unibet-closing.js` och via checkpoint-runner
- settlementlogik finns i `correct-unibet-backtest.js`, `result-loop`, `auto-analysis-bets`, `rankingFeedback`
- AI-user-output genereras pa flera olika satt

### 4. Filer i git ar del av runtime

Workflows committar:

- `data/teamstats/*.json`
- `public/teamstats/*.json`
- ibland modeller och andra derived outputs

Det gor reruns, recovery och diffar onodigt brusiga.

### 5. Svag match- och support-normalisering

- `leages-and-teams` vs `leagues-and-teams`
- teamstats ar fil-centriskt lagrat
- matchval till settlement sker via heuristiskt snapshotval

### 6. Batchjobb kor via Next-routes

Det fungerar, men gor batchflodet mindre testbart, mindre explicit och mer beroende av webapp-kontext.

### 7. Ingen tydlig raw Kambi-arkivering

Systemet skriver normalized lines i `unibet-backtest`, men sparar inte full append-only råpayloads som primarkalla for senare ombyggnad och audit.

## 10. Den dyraste dolda antagelsen

Den dyraste antagelsen i originalsystemet ar inte att modellerna ar bra.
Den dyraste antagelsen ar att samma match kan mappas korrekt och konsekvent mellan:

- fixtures
- Unibet/Kambi event
- teamstats/resultat
- support-data for league/team/opta

utan att systemet sparar en riktigt stark canonical relation mellan dessa varianter.

Om den antagelsen ar fel far du:

- fel odds pa ratt match
- ratt odds pa fel match
- settlement pa fel statistikblock
- CLV pa fel event
- dubletter mellan snapshots

Det ar precis dar V2 maste vara skoningslos.
