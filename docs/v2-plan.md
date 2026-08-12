# Ullebets V2 Plan

Detta ar planen efter att originalrepot har kartlagts.
V2 ska ge samma funktionella backend-resultat som originalet, men med en betydligt starkare struktur.

## 1. Malbild

V2 ska gora samma jobb som originalsystemet:

- hamta kommande matcher
- hamta teamstats/resultat
- hamta alla relevanta Unibet/Kambi-odds
- spara raw payloads
- bygga normalized snapshots
- kora samma modell/backtest-logik pa renare data
- spara predictions fore matchstart
- skapa closing-odds och CLV
- ratta outcome och ROI efter match
- uppdatera supportdata
- kora som stabil automation

Men V2 ska inte kopiera originalets struktur.
Den ska kopiera funktionellt slutresultat.

## 2. Vad som var svagt innan

### DB-sakerhet var for svag

Originalet defaultar i stort sett overal till `app`.
Det ar inte acceptabelt i en ny pipeline.

### Raw och derived separerades inte riktigt

Originalet sparar ofta senaste användbara vy direkt i samma dokument som historiken.
Det gor rebuild, audit och felsokning onodigt svart.

### Batchjobb och app-routes var hopkopplade

Cronjobb anropar ibland interna API-routes i stallet for en ren intern service.
Det skapar onodiga lager och otydlig ansvarsfördelning.

### Samma domanlogik fanns pa flera stallen

Settlement, CLV, ranking feedback och snapshot-logik finns i flera filer med lite olika regler.
Det ar ett klassiskt satt att fa smygande regressioner.

### Matchidentity var for svag

Det finns ingen tillrackligt stark canonical relation mellan:

- fixture match
- Unibet event
- teamstats/resultat
- support-data team/league/opta

Det ar den dyraste svagheten, eftersom allt annat bygger pa den.

### Runtime byggde pa git-versionerade artifacts

Teamstats, teamprofiles och ibland modeller eller derived filer committas som en del av jobbflodet.
Det ar bekvamt men opalitligt som driftmodell.

## 3. Varfor den nya iden ar battre

Den nya iden ar inte "ny modell".
Den nya iden ar "samma produktionsoutput, men byggd som ett riktigt dataflode".

Det blir battre eftersom V2 far:

- strict DB guard: allt skriver bara till `ullebets_v2`
- raw-first ingest: varje extern payload sparas innan normalisering
- rebuildbar derived layer: normalized och snapshots kan skapas om från raw
- canonical mapping layer: match, team, league och event binds explicit
- enhetlig settlementlogik: samma regler for push, ROI, CLV och timing
- tydlig job ledger: varje jobb far run-id, status, input-span, fel och metrics
- dedupe vid skrivning: ingen tyst duplicate exposure
- auditerbar timing: all modellanvandning kan bevisas vara prematch
- mindre beroende av webapp-runtime: batchlogik flyttas till riktiga jobb

Kort sagt:
originalet optimerar for att "fa fram output".
V2 ska optimera for att outputen gar att lita pa.

## 4. Harda ramar for V2

### Databaser

- `app` = read-only referens
- `ullebets_unibet` = read-only referens
- `ullebets_v2` = enda tillatna write target

### Stoppvillkor

Alla V2-write scripts ska stoppa direkt om:

- `MONGODB_DB` saknas
- `MONGODB_DB != ullebets_v2`

### Non-goals i forsta steget

- ingen ny modelllogik
- ingen omskrivning av EV/backtest-karnan
- ingen frontend
- ingen write tillbaka till `app` eller `ullebets_unibet`

## 5. Ny V2-arkitektur

## A. Lager

### 1. Raw ingest

Append-only dokument per fetch/run.

Exempel pa collections:

- `raw_fixtures`
- `raw_teamstats`
- `raw_match_statistics`
- `raw_incidents`
- `raw_shotmaps`
- `raw_odds_kambi`
- `raw_support_opta`

Varje rad ska minst ha:

- `source`
- `source_url`
- `payload_hash`
- `fetched_at`
- `job_run_id`
- `external_ids`
- `raw_payload`

### 2. Canonical mapping

Explicit relationer mellan externa identiteter.

Exempel:

- `matches`
- `match_source_links`
- `teams`
- `team_aliases`
- `leagues`
- `league_aliases`
- `events_unibet`

Det ar har den stora risken i originalet angrips.

### 3. Normalized/derived

Rebuildbara vyer for downstream-anvandning.

Exempel:

- `fixture_snapshots`
- `teamstats_matches`
- `market_offers`
- `market_snapshots`
- `market_closing`
- `match_outcomes`
- `support_rankings`

### 4. Prediction/tracking

Detta ar det lager som maste motsvara originalets användar- och modelleffekt.

Exempel:

- `prediction_runs`
- `prediction_candidates`
- `prediction_snapshots`
- `forward_bets`
- `closing_line_audits`
- `settlement_results`

### 5. Operations/audits

- `job_runs`
- `job_events`
- `health_checks`
- `audit_reports`

## B. Jobbstruktur

Varje jobb ska ha ett ansvar.
Inga fler megascripts som gor allt samtidigt.

### Jobb 1: Support sync

Ansvar:

- synca `leagues-and-teams`
- synca `unibetLeagueUrls`
- synca Opta / league ranking

Output:

- uppdaterad support-data i V2-format
- versionsmetadata

### Jobb 2: Fixture ingest

Ansvar:

- hamta kommande matcher
- spara raw fixtures
- bygga normalized fixture snapshot

### Jobb 3: Teamstats ingest

Ansvar:

- hamta statistik/resultat/incidents/shotmap/odds efter match eller under bevakning
- spara raw payloads
- normalisera till canonical matchstats

### Jobb 4: Unibet odds ingest

Ansvar:

- hitta event i Unibet/Kambi
- spara full raw payload
- skapa normalized markets/offers
- markera `invalid_for_model` om capture ar efter start

### Jobb 5: Snapshot scheduler

Ansvar:

- avgora vilka matcher som ar due for:
  - `T_MINUS_3D`
  - `T_MINUS_2D`
  - `T_MINUS_1D`
  - `T_MINUS_10M`
- trigga odds ingest for exakt ratt fonster

### Jobb 6: Prediction run

Ansvar:

- lasa senaste giltiga prematch snapshot
- kora oforandrad modell/backtest-karnlogik
- spara prediction med immutable timestamp

### Jobb 7: Closing builder

Ansvar:

- valja sista giltiga prematch-observation som closing
- bygga CLV-jamforelse mot opening/saved odds

### Jobb 8: Settlement

Ansvar:

- lasa verifierad actual från normalized stats
- applicera samma regel for:
  - over
  - under
  - push
  - ROI
  - PnL

### Jobb 9: Audit suite

Ansvar:

- timing leakage audit
- outcome mapping audit
- duplicate exposure audit
- feature leakage audit
- match mapping audit
- raw coverage audit
- closing coverage audit
- DB safety audit

## 6. Den starkaste designprincipen

Allt som modellen eller ROI:n påstar ska ga att backtracka till:

1. exakt raw payload
2. exakt normaliseringsregel
3. exakt snapshot-val
4. exakt prediction-run
5. exakt settlement-regel

Om ett bet inte kan forklaras hela vagen bak till raw payload, sa ar systemet fortfarande for svagt.

## 7. Den dyraste antagelsen i V2 ocksa

Den dyraste antagelsen ar fortfarande matchningen mellan kallsystemen.

Mer konkret:

"Vi kan deterministiskt binda ihop fixture-match, Unibet-event, teamstats/resultat och supportdata utan att skriva fel relation."

Om det ar falskt faller hela forward-testet.

Darfor maste V2 ha:

- canonical match keys
- source link tables
- explicit confidence/quality pa mappings
- manual override registry nar automatisk mapping inte ar tillrackligt saker

Det ar battre att markera "unmatched" an att smygkoppla fel match.

## 8. Rekommenderad implementation i detta repo

Eftersom detta repo redan ar Python-first och modell/offline-V1 redan lever har, ar den battre planen:

- behall V1-modellkarnan har
- bygg V2 backend-jobben i samma repo
- lagg nya moduler under `src/ullebets_v2/`
- lagg jobb under `scripts/forward_v2/`
- anvand Node-kod i originalrepot som referens, inte som runtime-bas

Varfor detta ar battre:

- modellen och offline-logiken bor inte delas upp over två repo-runtimes om det inte maste
- batchjobb, audits och ML-delar blir lättare att testa tillsammans
- framtida frontend kan lasa fran V2-DB eller via separat API utan att batchlogiken bor i Next

Om en specifik Unibet-discovery-del visar sig for dyr att porta direkt, kan den kapslas som en separat adapter.
Men orkestreringen bor fortfarande bo i V2 och inte i gamla Next-appen.

## 9. Forelagen fil- och modulstruktur i V2

```text
src/
  ullebets_v2/
    config.py
    safety.py
    jobs/
    sources/
    raw/
    canonical/
    normalize/
    predictions/
    settlement/
    audits/
    storage/
    health/

scripts/
  forward_v2/
    bootstrap_indexes.py
    sync_support_data.py
    ingest_fixtures.py
    ingest_teamstats.py
    ingest_unibet_odds.py
    run_snapshot_scheduler.py
    run_predictions.py
    build_closing_lines.py
    settle_finished_matches.py
    run_audits.py
    smoke_test_v2.py
```

## 10. Implementation plan i verifierbara steg

### Steg 1: Safety foundation

Jag bygger:

- V2-config
- DB guard
- job-run ledger
- healthcheck
- bootstrap-index script

Varfor forst:

- utan det riskerar alla senare steg att skriva fel eller bli ospårbara

Smoke-test:

- startar config
- verifierar att `MONGODB_DB=ullebets_v2`
- skapar bas-index och `job_runs`

### Steg 2: Support-data foundation

Jag bygger:

- import av `leagues-and-teams.json`
- import av `unibetLeagueUrls.json`
- Opta/ranking sync i V2-format

Smoke-test:

- antal ligor/lag i V2 stammer mot input
- version och hash sparas

### Steg 3: Fixture raw + normalized

Jag bygger:

- raw fixture ingest
- canonical match records
- match source links

Smoke-test:

- ett datum kan hämtas, sparas raw och normaliseras
- rerun skapar inte dubletter

### Steg 4: Teamstats raw + normalized

Jag bygger:

- raw stats/incidents/shotmap/result ingest
- normalized matchstats per match
- verifierad `start_time` och status

Smoke-test:

- en känd match far komplett normalized statsrad

### Steg 5: Unibet odds raw + normalized

Jag bygger:

- event discovery
- raw Kambi payload storage
- normalized market/offer rows
- invalidation efter kickoff

Smoke-test:

- en känd match far raw payload + normalized offers
- prematch och post-start skiljs korrekt

### Steg 6: Snapshot policy

Jag bygger:

- due-match selection for `T_MINUS_3D`, `T_MINUS_2D`, `T_MINUS_1D`, `T_MINUS_10M`
- immutable snapshot rows

Smoke-test:

- en syntetisk match med given kickoff far exakt ratt due checkpoint

### Steg 7: Prediction persistence

Jag bygger:

- adapter som kor befintlig modelllogik utan omskrivning
- prediction run / candidate storage

Smoke-test:

- samma input producerar samma prediction output vid rerun
- inga predictions skrivs om efter kickoff

### Steg 8: Closing / CLV / settlement

Jag bygger:

- closing selection
- CLV metrics
- settlement mot verifierad actual

Smoke-test:

- win/loss/push testfall passerar
- after-start odds exkluderas

### Steg 9: Audits

Jag bygger:

- timing audit
- outcome mapping audit
- duplicate exposure audit
- feature leakage audit
- mapping coverage audit

Smoke-test:

- auditrapport kan koras pa ett begransat datumintervall och returnerar counts + offenders

### Steg 10: Automation

Jag bygger:

- nya Actions/cron-jobb
- smoke-test i CI
- job health summary

Smoke-test:

- varje jobb kan koras separat
- varje jobb skriver `job_runs`

## 11. Vad jag inte ska gora i fel ordning

Jag ska inte:

- bygga frontend nu
- flytta modelllogik innan dataflodet ar stabilt
- skriva till gamla databaser
- kopiera gamla collection-shapes rakt av
- anta att gammal mapping ar korrekt utan audit

## 12. Nasta beslutspunkt

Efter detta ska jag inte hoppa direkt till allt pa en gang.
Ratt nasta steg ar att implementera Steg 1 och Steg 2 forst:

- safety/config/index/job ledger
- support-data foundation

Det ar den minsta starten som faktiskt minskar risk i stallet for att bara producera ny kod.
