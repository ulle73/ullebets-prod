# Ullebets work log

Last updated: 2026-09-03

This is the mandatory first-read project log. It records what has already been
tested, what currently works, what failed, the strongest insights, and what is
still worth testing. Detailed evidence remains in the linked reports.

## Status vocabulary

- `VERIFIED`: current evidence proves the claim.
- `PARTIAL`: the path works, but required coverage is incomplete.
- `FAILED`: a reproducible defect exists.
- `UNPROVEN`: the required event, source payload, or lifecycle window has not
  happened yet.
- `BLOCKED`: progress requires new external data or another state change.
- `REJECTED`: a tested experiment failed its predefined retention gate.
- `NOT STARTED`: a required product area has no completed implementation yet.

Valid empty source responses are not failures when no matches or markets exist.

### 2026-09-03 - Cosmos session cleanup and bounded matchup repair

Status: `VERIFIED` locally and against the production database; `PARTIAL` until
the final commit completes in a hosted GitHub Actions run.

Objective:
Diagnose the current failed and timed-out GitHub Actions runs, remove the
Cosmos DB session-exhaustion path, recover the exact missed formula journal
scope, and stop the daily matchup repair from rewriting terminal history.

Changes:

- Formula journal materialization now reuses one explicit Mongo session for
  snapshot, fixture, model-data, score, immutable-replay, and persistence
  operations.
- Formula journal and frozen-model scorer CLIs close their Mongo clients in a
  `finally` block. The shared Mongo client factory also registers process-exit
  cleanup so normal CLI completion sends server-side session cleanup for all
  workflows.
- Historical matchup repair now reads and persists only rows whose outcome is
  not already `resolved`; terminal rows are left untouched.
- Repaired the nine exact match keys captured by failed run `33767926969`.

Tests:

```text
$env:PYTHONPATH = (Resolve-Path 'src').Path
python -m pytest tests/v2/test_formula_journal_materialize.py tests/v2/test_formula_journal_observations.py tests/v2/test_matchup_settlement.py tests/v2/test_mongo_client_lifecycle.py tests/v2/test_automation_contract.py tests/v2/test_registered_shadow_model_runner.py tests/v2/test_ev_shadow_candidate.py -q
python scripts/forward_v2/materialize_formula_journal.py --repo-root . --registry models/ev/shadow_formula_registry_v1.json --match-key sofascore:15235456 --match-key sofascore:15235457 --match-key sofascore:16310945 --match-key sofascore:16363262 --match-key sofascore:16416320 --match-key sofascore:16416321 --match-key sofascore:16416324 --match-key sofascore:16416340 --match-key sofascore:16434028
git diff --check
```

Results:

- GitHub run `33767926969` captured `303` market snapshots and persisted `480`
  frozen-model scores, then failed in formula-observation persistence with
  Cosmos error `TooManyLogicalSessions` (`code 261`). Earlier scheduler runs
  `33715988601` and `33741488402` reached the 60-minute job limit after opening
  the same database path.
- Run `33752059496` completed live enrichment but timed out at 45 minutes in
  the 45-day matchup repair. Already resolved dates were being settled and
  rewritten again; the new unresolved-only contract removes that work.
- Targeted regression coverage passed `48/48`, including explicit session
  propagation, process-exit client cleanup, immutable replay, scorer runner,
  automation order, and terminal matchup-row exclusion.
- An initial test command named the nonexistent
  `tests/v2/test_ev_shadow_scoring.py` and ran no tests; the corrected command
  above passed. A one-off Python import also exposed a stale editable install
  pointing at an older worktree, so validation explicitly used this checkout's
  `src` directory.
- The production repair completed with `19,013` candidate observations:
  `11,154` inserted, `7,859` immutable existing rows reused, `0` conflicts,
  `0` oracle errors, and `0` domain-unverified scores.
  The saved report is
  `data/v2/reports/formula-journal-0f093592888b42c3ac526037c6433ebd.json`.

Insight:
The visible failure was not a model error. Multiple short-lived CLI clients
left server-side logical-session cleanup to garbage collection, while the
largest journal job opened many implicit sessions. The separate enrichment
timeout came from repeatedly processing terminal matchup rows over the whole
45-day repair window.

Remaining:

- The code has production-database evidence but still needs one hosted run on
  the final commit before the GitHub Actions repair is fully `VERIFIED`.
- The readiness checklist does not change; this repair adds operational
  reliability but no new model-performance or complete-lifecycle evidence.

Next:

- Push the final commit, run the match-aware scheduler in hosted write mode,
  and verify terminal success plus a later scheduled enrichment run without
  repeating already resolved matchup rows.

### 2026-08-30 - Högre laggrafer med lutade statetiketter

Status: `VERIFIED` lokalt för komponentkontrakt, typkontroll, lint och
produktionsbygge; `PARTIAL` för browser-renderad referensjämförelse.

Objective:
Efterlikna referensens läsbara 30-kolumnslayout genom att visa statnyckel och
period lutande under varje kolumn samt göra diagrammen och staplarna högre.

Changes:

- Höjde varje FÖR/MOT-plot från `300 px` till `420 px`, inklusive Recharts
  responsiva mätcontainer och initialdimension.
- Samlade statnamn och period i en gemensam axeletikett per kombination och
  roterade den `-50deg` med kolumnens mittpunkt som ankare.
- Gav etikettraden ett eget `112 px` högt utrymme så de lutade etiketterna får
  plats utan att trycka ihop eller flytta staplarnas träffytor.
- Behöll faktisk statnivå horisontellt ovanför respektive lutad etikett.
- Utökade regressionstestet till att kräva `420 px` plotthöjd och exakt 30
  axeletiketter i både FÖR och MOT.

Tests:

```text
npm test -- --run src/app/step2-drilldowns.test.tsx
npm run typecheck
npm run lint
npm run build
git diff --check
```

Results:

- Regressionstestet föll först på den gamla `300 px`-höjden och passerade
  efter ändringen (`3/3`).
- TypeScript, ESLint och Vite-produktionsbygget passerade.
- `git diff --check` passerade.

Insight:
Referensens läsbarhet kommer inte bara från större bredd. Den skapar vertikalt
utrymme åt både längre staplar och diagonala kategorietiketter; att endast göra
horisontell text mindre gör 30 kombinationer svårare att koppla till rätt data.

Remaining:

- Ingen godkänd browser-renderad efterbild eller hoverkontroll finns i denna
  session. Exakt typografi, överlapp och visuell referensmatchning är därför
  fortsatt `BLOCKED` i `design-qa.md`.

Next:

- Fånga samma lagsida i desktopläge och jämför etikettvinkel, stapelhöjd och
  första/mitten/sista hover mot referensen.

### 2026-08-30 - Responsiv laggraf och korrekt hoverposition

Status: `VERIFIED` lokalt för regressionskontrakt, typkontroll, lint och
produktionsbygge; `PARTIAL` för browser-renderad hover- och referenskontroll.

Objective:
Låta FÖR/MOT-graferna använda hela lagsidans tillgängliga bredd utan att
statetiketterna sticker ut och utan att hoverns träffyta förskjuts till en annan
stapel.

Changes:

- Ersatte den fasta `1100 px`-bredden i Recharts med `ResponsiveContainer`, så
  diagrammets synliga bredd och interna pekarkoordinater alltid mäts från samma
  verkliga container.
- Tog bort CSS-regeln som visuellt sträckte en redan fixerad Recharts-wrapper
  samt de hårda minbredderna som skapade horisontellt överhäng.
- Lät lagsidan och båda diagramkorten fylla tillgänglig bredd och justerade den
  30-delade värderaden till samma fasta vänster/högermarginaler som diagrammets
  ritområde.
- Lade till regressionstest som kräver en responsiv container i både FÖR- och
  MOT-grafen.

Tests:

```text
npm test -- --run src/app/step2-drilldowns.test.tsx
npm run typecheck
npm run lint
npm run build
git diff --check
```

Results:

- Regressionstestet föll först eftersom båda diagrammen saknade
  `.recharts-responsive-container`, och passerade efter ändringen (`3/3`).
- TypeScript, ESLint och Vite-produktionsbygget passerade.
- `git diff --check` passerade.

Insight:
Grundfelet var inte sorteringen av statnycklar. En `1100 px` bred Recharts-yta
skalades visuellt till `100%` av CSS, men bibliotekets interna hoverkoordinater
fortsatte använda den fasta bredden. Därför hamnade markeringen flera staplar
från pekaren.

Remaining:

- Sessionen saknar en styrbar in-app-browser. Faktisk hover i renderad browser,
  console och pixeljämförelse mot användarens skärmbild är därför fortsatt
  `BLOCKED` i `design-qa.md`; ingen browserverifiering hävdas.

Next:

- När styrbar browser finns: kontrollera första, mittersta och sista stapelns
  hover vid samma desktopbredd och fånga post-fix-bilden för visuell jämförelse.

### 2026-08-30 - Alla periodkombinationer i sorterade laggrafer

Status: `VERIFIED` lokalt för datakontrakt, frontendbeteende och
produktionsbygge; `PARTIAL` för slutlig renderad referensjämförelse.

Objective:
Samla totalt, första halvlek och andra halvlek för samtliga tio spelbara
statnycklar i samma FÖR-graf respektive MOT-graf och alltid sortera staplarna
från högsta till lägsta procentavvikelse mot ligasnittet.

Changes:

- Varje graf bygger nu alltid 30 unika kombinationer (`10 stats x 3 perioder`)
  i stället för tio rader för en vald period.
- Sorteringen använder liga-relativ procentavvikelse fallande. Alla jämförbara
  positiva och negativa värden behåller en gemensam ordning; kombinationer
  utan ligasnitt ligger sist och visas som saknade i stället för att döljas.
- Tog bort periodväljaren från lagsidan. Hemma/borta är fortsatt det enda
  profilfiltret, medan varje stapel visar statnamn, period och faktiskt värde.
- Minskade stapel- och etikettstorleken så alla kombinationer ryms i samma
  grafyta med bibehållen nollinje och separata FÖR/MOT-paneler.

Tests:

```text
npm --prefix frontend test -- --run src/domain/team-stats.test.ts src/app/step2-drilldowns.test.tsx
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
git diff --check
```

Results:

- `4/4` riktade tester passerade.
- Det nya domäntestet bevisar exakt 30 unika stat/period-identiteter, fallande
  sortering på procentavvikelse och att saknade jämförelser hamnar sist.
- Sidtestet bevisar 30 staplar i både FÖR och MOT, tre instanser vardera av
  insparkar/inkast och att periodknapparna inte längre finns.
- TypeScript, ESLint, Vite-produktionsbygge och `git diff --check` passerade.

Insight:
Grundfelet var att perioden modellerades som ett sidfilter och därför togs
bort ur grafens radidentitet. Den hållbara lösningen är att period ingår i den
unika visualiseringsnyckeln och sorteras tillsammans med statnyckeln.

Remaining:

- En ny browser-renderad implementationbild kunde inte fångas i sessionen;
  post-fix pixeljämförelse mot referensen är därför fortsatt `BLOCKED` i
  `design-qa.md` och ingen exakt visuell matchning hävdas.

Next:

- När styrbar browser finns: fånga den hostade lagsidan i samma desktopbredd,
  jämför mot referensen och rätta endast eventuella kvarvarande P0-P2-fel.

### 2026-08-30 - Liga-relativa FÖR/MOT-grafer för lagprofil

Status: `VERIFIED` lokalt för datakontrakt, beteendetester och produktionsbygge;
`PARTIAL` för visuell referensjämförelse och verklig marknadstäckning.

Objective:
Visa samma tio spelbara lagstatistiknycklar i två tydliga liga-relativa grafer
för FÖR och MOT, med hemma/borta samt hela/första/andra halvlek, och utan att
positiva staplar fortsätter under nollinjen.

Changes:

- Ersatte den växlade FOR/AGAINST-tabellen på lagsidan med två samtidiga
  Recharts-grafer för FÖR och MOT, symmetrisk nollinje, grön/gul/röd avvikelse,
  faktiska värden under grafen och explicita saknade värden.
- Låste grafordningen till skott på mål, skott, hörnor, gula kort, frisparkar,
  fouls, tacklingar, offsides, insparkar och inkast.
- Lade till insparkar (`goalKicks`) och inkast (`throwIns`) i frontendetiketter,
  filter, matchupstatlista, Unibet-normalisering och settlement-registret.
- Båda nya nycklarna är settlement-stödda men inte felaktigt markerade som
  modellstödda.

Tests:

```text
python -m pytest tests/v2/test_odds_ingest.py tests/v2/test_stat_registry.py tests/v2/test_teamprofiles.py -q
npm --prefix frontend test -- --run src/app/step2-drilldowns.test.tsx
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
git diff --check
```

Results:

- Backend: `23/23` tester passerade, inklusive normalisering av insparkar och
  inkast samt settlement-stöd utan modellflagga.
- Frontend: `3/3` riktade tester passerade och bevisar tio statnycklar i både
  FÖR och MOT samt nollinje som staplarnas ursprung.
- TypeScript, ESLint, Vite-produktionsbygge och `git diff --check` passerade.
- In-app-browserns kontrollverktyg var inte tillgängligt i sessionen. Därför
  saknas den obligatoriska renderade jämförelsebilden mot användarens referens;
  `design-qa.md` är korrekt markerad `blocked` och ingen pixelperfekt matchning
  hävdas.

Insight:
Lagprofilens datakontrakt hade redan `throwIns` och konfiguration för
`goalKicks`, men oddsnormalisering och settlement-register saknade båda. Det
var en kedjelucka, inte bara en presentationsmiss.

Remaining:

- Verkliga provideretiketter och faktisk oddstäckning för insparkar/inkast är
  `UNPROVEN` tills sådana marknader observeras i råa payloads.
- Visuell jämförelse i samma viewport är `BLOCKED` i denna session eftersom
  ingen styrbar in-app-browser kunde väljas.

Next:

- När en styrbar browser finns: rendera en riktig lagprofil i desktopviewport,
  jämför den sida vid sida med referensen och rätta eventuella P0-P2-avvikelser.

### 2026-08-30 - Pedagogisk matchupöversikt och rankingdiagnostik

Status: `VERIFIED` lokalt för API-kontrakt, frontendbeteende och produktionsbygge;
`PARTIAL` tills den pushade versionen är separat verifierad på hostingen.

Objective:
Göra matchupöversikten snabb att tolka utan att blanda ihop rankingpoäng,
predictorträff och spelmarknadsresultat, samt ersätta synliga statusord med
tillgängliga ikoner.

Changes:

- Bytte `Score` till `Rankingpoäng`, markerade att värdet inte är en
  sannolikhet och visar placeringen som `#x av y` inom den filtrerade
  riktningslistan.
- Ersatte synliga träff/miss- och vinst/förlustord med gröna bockar, röda
  kryss, push-/väntarikoner, svenska `aria-label`-värden och tooltips.
- Delade kortet i en kompakt resultatnivå och en tangentbordsöppningsbar detalj
  med predictortröskel, faktiskt utfall, signerat avstånd, exakt marknad,
  oddsrörelse, closing och CLV.
- Delade sammanfattningen i `Prediktor` och `Spelbara marknader` med separata
  nämnare. Lade till medianavstånd, jämförelse mot bästa konstanta riktning på
  samma observationer och fasta rankingintervall med egna stickprovsstorlekar.
- Ersatte otydliga streck med precisa saknasorsaker och flyttade filter samt
  rankingdiagnostik till expanderbara paneler.

Tests:

```text
python -m pytest tests/v2/test_matchup_evaluation_metrics.py tests/v2/test_read_api_contracts.py -q
npm test --prefix frontend -- --run src/app/matchup-evaluation.test.tsx
npm run typecheck --prefix frontend
npm run lint --prefix frontend
npm run build --prefix frontend
git diff --check
```

Results:

- Backendens metric- och API-kontrakt passerade `21/21`.
- Frontendens riktade beteendetest passerade `2/2`, inklusive tillgängliga
  gröna bockar och röda kryss utan synliga statusord.
- TypeScript, ESLint och Vites produktionsbygge passerade utan fel.
- Rankingintervall med noll icke-push-observationer returnerar `null`, inte en
  missvisande träffprocent på noll.
- Ingen readiness-ruta ändrades; arbetet förbättrar presentation och
  deskriptiv diagnostik men tillför inte nytt forwardbevis.

Insight:
En rättvis enkel baseline kan härledas utan ett nytt modellantagande genom att
jämföra prediktorn med alltid OVER respektive alltid UNDER på exakt samma
rättade observationer. Den bästa konstanta riktningen är fortfarande endast en
deskriptiv referens och inte bevis för framtida edge.

Remaining:

- Hosted deployment och den faktiska responsiva renderingen är ännu inte
  verifierade på den pushade committen.
- Den dyraste oprövade premissen är fortsatt om rankingstyrkan överlever fler
  nya in-domain forwardmatcher; historiska eller små score buckets får inte
  beskrivas som bevisad ROI.

Next:

- Leverera till `main`, verifiera `origin/main`, och kontrollera därefter bara
  den nya hostade översikten när deploymenten är klar. Låt nya automatiska
  forwardresultat bygga stickprovet i stället för att återköra historiska
  experiment.

### 2026-08-30 - Historical matchup result recovery and terminal journal isolation

Status: `VERIFIED` for the 2026-08-22 production cards and local regression
coverage; `PARTIAL` for the next hosted automatic run on the final commit.

Objective:
Determine why visible 2026-08-22 matchup cards remained `VÄNTAR` despite
available source statistics, repair that date, and prevent the daily recovery
workflow from either timing out on broad refetches or rewriting frozen legacy
evidence.

Changes:

- Ran the production workflow for exactly 2026-08-22. It populated missing
  canonical results and 258-282 canonical stat rows for each of the four
  visible example fixtures, then bulk-settled the historical matchup outputs.
- Added bounded recovery of up to 10 old `matchups_score` fixtures whose
  outcome is still `pending_result`, including pre-journal rows that have no
  immutable matchup observation.
- Reduced the normal live enrichment window from eight days to yesterday;
  the 45-day ranking/settlement repair remains and now combines with the
  bounded unresolved queue.
- Excluded terminal `legacy_descriptive` observations from the generic result
  refresh. Their dedicated legacy materializer remains the only writer, so the
  immutable conflict gate stays fail-closed.

Verification:

```text
Read-only production dashboard before repair: 40 cards = 14 resolved, 26 pending_result
GitHub Actions run 33295677436 on f2ed2d970c07e255d513b3f914235f9b4a79fd7c, target_date=2026-08-22
Read-only production dashboard after settlement: 40 cards = 40 resolved; 28 hit, 12 miss
python -m pytest tests/v2/test_matchup_evaluation_results.py tests/v2/test_matchup_evaluation_legacy.py tests/v2/test_match_enrichment.py tests/v2/test_automation_contract.py -q
python scripts/forward_v2/refresh_matchup_results.py --date-from 2026-08-22 --date-to 2026-08-22 --dry-run
```

Results:

- All 40 visible top cards for 2026-08-22 are now corrected; no visible card
  remains `VÄNTAR`.
- The production settlement resolved 5,760 combined score/league rows. It
  retained 648 `pending_result` rows for Olympique de Marseille - RC Strasbourg
  and Real Betis - Real Sociedad because neither V2 canonical storage nor the
  read-only legacy `teamstats` source currently contains a finished result or
  stats for those two fixtures. Udinese - Como retains 36 combined
  `missing_actual` rows for stat contexts absent from its otherwise complete
  261-row canonical payload.
- The run then correctly exposed a terminal conflict after inserting 1,380
  legacy observations/results: generic refresh classified those descriptive
  rows as excluded. The final code fixes the writer boundary rather than
  weakening conflict detection.
- Related regression coverage passes `41/41`. The exact-date dry refresh now
  selects zero legacy observations and returns zero conflicts.

Remaining:

- Hosted run 33295677436 is `FAILED` only at the now-fixed final refresh step;
  its enrichment, settlement, legacy materialization, and live dashboard
  publication completed. A later scheduled run must prove terminal hosted
  success on the final commit.
- The two fixtures with no finished canonical or legacy source payload remain
  unresolved by design; the bounded daily recovery queue will retry them
  without blocking new match days.

Next:

- Push the final recovery/journal-boundary commit and use the next scheduled
  run as hosted acceptance evidence; do not repeat the already-successful
  2026-08-22 provider fetch solely for verification.

### 2026-08-29 - Automatic historical matchup repair and immutable evaluation

Status: `VERIFIED` locally and for the bounded ranking/settlement production
backfill; `PARTIAL` for hosted automation and legacy-evaluation publication.

Objective:
Repair missing historical matchup dates, correct every resolvable matchup
predictor independently of odds coverage, and automate immutable T-1D market,
closing, and CLV evaluation without relying on mutable ranking rows.

Changes:

- Added independent `matchup_observations` and `matchup_results` collections,
  immutable T-1D observation identity/fingerprints, exact 1.80-2.20 offer
  selection, terminal result conflict checks, and separate predictor/market
  metrics.
- Added bounded legacy-descriptive backfill and historical ranking repair. The
  daily workflow repairs 45 days from stored V2 data, limits normal live
  enrichment to yesterday, and selectively retries a bounded unresolved queue.
- Wired T-1D materialization before model scoring, post-match result refresh,
  exact-line T-10/T-30 CLV, API/card presentation, and accessible odds movement.
- Replaced serial matchup-settlement writes with bounded 100-row bulk upserts.

Verification:

```text
python -m pytest tests/v2/test_matchup_evaluation_observations.py tests/v2/test_matchup_evaluation_results.py tests/v2/test_matchup_evaluation_legacy.py tests/v2/test_matchup_evaluation_metrics.py tests/v2/test_matchup_settlement.py tests/v2/test_read_api.py tests/v2/test_read_api_contracts.py tests/v2/test_match_enrichment.py tests/v2/test_automation_contract.py tests/v2/test_parity_framework.py -q
python -m pytest tests/v2 -q
python -m pytest tests/v2/test_read_api_cache.py tests/v2/test_read_api.py tests/v2/test_read_api_contracts.py -q
npm test -- --run src/app/matchup-evaluation.test.tsx src/app/App.test.tsx src/app/spel-resultat-clv.test.tsx
npm run typecheck
npm run lint
npm run build
python scripts/forward_v2/repair_matchup_history.py --start-date 2026-08-22 --end-date 2026-08-28 --source-workflow manual-matchup-history-bulk-repair-2026-08-29
```

Results:

- Targeted backend coverage passed `92/92`; the full V2 run reached `567/568`
  before exposing one missing-optional-collection cache regression, and the
  corrected read/cache subset then passed `39/39`.
- Frontend targeted tests passed `7/7`; TypeScript, ESLint, and production
  build passed.
- Production repaired six previously absent ranking dates over 22-28 August.
  The terminal run settled `12,780` score/league rows. Dates 25-27 had complete
  profile coverage; 23, 24, and 28 retained explicit missing-profile coverage
  of 3, 1, and 2 fixtures instead of inventing rankings.
- The interrupted serial write job was marked failed explicitly and superseded
  by the successful bounded bulk run.

Remaining:

- Git delivery and hosted Vercel/workflow evidence are not yet recorded in this
  entry. The bounded legacy evaluation backfill must populate the new
  collections before historical aggregate cards are called published.
- Historical rows remain `legacy_descriptive`; only new immutable T-1D rows can
  contribute to forward predictor evidence.

Next:

- Push `main`, dispatch the bounded evaluation workflow, then verify the live
  dashboard/API separately without rerunning unrelated model experiments.

### 2026-08-28 - Matchup settlement and market-coverage design audit

Status: `PARTIAL`

Objective:
Determine how matchup rankings can be evaluated honestly as predictors, and
whether every matchup has an exact odds market suitable for win/loss, ROI, and
CLV reporting. Convert the approved product contract into a test-driven
implementation plan without changing product code or runtime state.

Changes:

- Added the approved design specification at
  `docs/superpowers/specs/2026-08-28-matchup-predictor-evaluation-design.md`.
- Added the implementation plan at
  `docs/superpowers/plans/2026-08-28-matchup-predictor-evaluation.md`.
- No database, runtime, workflow, model, API, or frontend state was mutated.

Tests:

```text
Read src/ullebets_v2/matchups/service.py,
src/ullebets_v2/matchups_settlement/service.py,
src/ullebets_v2/read_api/service.py, and the current frontend matchup types/card.
Queried ullebets_v2.matchups_score and ullebets_v2.market_snapshots with
read-only projections; joined exact match/stat/period/scope identities and
excluded invalid or post-kickoff snapshots.
Ran CodeGraph status/current-index inspection and mapped the storage,
checkpoint, settlement, read-API, workflow, and frontend call paths.
Ran plan placeholder scans, Markdown fence-count validation, and
git diff --check.
```

Results:

- `matchups_score` contains 15,876 rows: 5,544 `resolved`, 8,640
  `pending_result`, 72 `missing_actual`, and 1,620 without outcome status.
- Current settlement persists canonical actual values but does not define a
  matchup win/loss against a frozen baseline or market line. The read API does
  not expose those stored actual fields on matchup cards.
- Only 805/5,544 resolved rows (14.5%) have an exact prematch market context
  with odds for the ranked direction; 623/5,544 (11.2%) have any such odds in
  the 1.80-2.20 interval. Only 641/5,544 (11.6%) have T-30/T-10 closing-price
  coverage, all currently T-30 in the resolved sample.
- Resolved exact-price coverage is concentrated in corner kicks (450 rows),
  followed by yellow cards (148), shots on goal (75), total shots (75), and
  offsides (57). Fouls, free kicks, throw-ins, and tackles have zero exact odds
  coverage in current snapshots.
- The 2026-08-22 visible top-20 sets contain 40 rows; only 4 have exact
  direction odds and only 1 has odds inside 1.80-2.20.
- A matchup score is a normalized relative rank, not a calibrated probability.
  Existing rows also lack a row-level immutable creation timestamp; 9,270 of
  15,876 lack the current `rolling_12_weighted_45d` method identity.
- The approved plan has nine implementation tasks, balanced Markdown fences,
  no unresolved placeholder markers, and no whitespace errors.

Insight:
A single odds-based win/loss denominator would discard roughly 85% of resolved
matchup evidence and overrepresent the few offered stat markets. Predictor
quality and market/betting quality must therefore be separate contracts. The
1.80-2.20 interval is suitable for deterministic comparable-market selection,
not as the definition of whether a predictor was correct.

Remaining:

- The hybrid product definition and immutable T-1D capture contract are
  approved and planned, but implementation has not started.
- Existing historical rows can be shown as descriptive legacy evidence but do
  not prove leakage-safe forward predictor quality without a frozen timestamp.
- Old pending/missing matchup outcomes and exact fixture lifecycle state still
  require a dedicated settlement audit before history can be called complete.

Next:

- The written specification was approved. Execute the test-driven plan in
  `docs/superpowers/plans/2026-08-28-matchup-predictor-evaluation.md` using the
  selected execution workflow, then record local and hosted evidence
  separately.

## Current project state

### Repository and data boundaries

- `VERIFIED`: V2 is preserved on `feature/ullebets-v2-backend`, merged to
  `main`, and deployed through active GitHub Actions workflows.
- `VERIFIED`: V2 writes target only `ullebets_v2`.
- `VERIFIED`: `app` and `ullebets_unibet` are read-only reference sources.
- `VERIFIED`: raw and canonical/derived data are separated.
- `VERIFIED`: V2 collection names are suffix-free; old `*_v2` names are legacy
  cleanup aliases only.
- `VERIFIED`: the full V2 Python test suite currently passes, `555/555` in
  the all-formula production-hardening checkout.

### Backend

- `VERIFIED`: support sync, fixture ingest, finished-match enrichment,
  teamprofiles, Kambi event linking, raw odds, normalized offers, model
  snapshots, analysis, prediction exports, forward rows, settlement jobs, and
  audit jobs run against `ullebets_v2`.
- `VERIFIED`: four finished Brazil matches were enriched with raw statistics,
  incidents, shotmaps, results, canonical results, and 27 canonical primary
  stat rows per match.
- `VERIFIED`: settlement, CLV, and forward results share the timing contract
  `odds_snapshot_time <= prediction_created_at < match_start_time`.
- `VERIFIED`: three rows violating prediction-freeze timing are retained for
  audit but excluded from outcomes, PnL, ROI, and CLV.
- `VERIFIED`: simulated write-time snapshots were invalidated without changing
  raw Kambi payloads or immutable predictions.
- `VERIFIED`: production now contains valid T-30 fallback and official T-10
  closing materialization. The current read-only audit found `5,203`
  `closing_lines`, including `976` official T-10 rows over `13` matches.
- `FAILED`: official CLV coverage still does not intersect the current forward
  sample. Across `230` canonical tracked bets, CLV status is `69`
  `tracked_fallback_t30`, `161` `missing_closing_line`, and `0` official T-10;
  the official T-10 matches currently have no forward bets.
- `VERIFIED`: the final Brazil match was enriched with statistics, incidents,
  shotmap, result, canonical result, and 27 canonical primary-stat rows.
- `VERIFIED`: post-match settlement now contains 64 valid settled operational
  rows and 3 timing-excluded rows; forward results match those counts.
- `FAILED`: the scheduled fixture source returned no successful category batch
  on 2026-08-23, while the workflow still reported success and persisted zero
  canonical records. Enrichment and odds evidence does not establish current
  fixture-schedule coverage.
- `VERIFIED`: scheduled `V2 EV Shadow Forward` runtime drift exposed by run
  `30668128118` is fixed. Production write-mode run `30672830616` passed all
  four frozen scorers on the manifest-compatible runtime.
- `VERIFIED`: scheduled workflows are write-mode by default. Their command
  templates include `--dry-run`, but the shared runner removes that flag when
  the workflow input is false. Manual dry-run remains available as a safety
  control.
- `VERIFIED`: the latest completed match date for every followed league is now
  stored in V2. Across 41 matches, raw statistics, incidents, shotmaps,
  results, canonical results, and all 1,107 primary stat rows are complete.
- `VERIFIED`: live T-2D capture has 161 valid prematch rows across two
  matches, and live T-1D capture has 244 valid rows across three matches.
- `VERIFIED`: the hourly production scheduler is active. Hosted run
  `30949327663` succeeded, saw all 10 upcoming Brazil fixtures, correctly
  found zero due checkpoints, and persisted audit/health status `ok`.
- `VERIFIED`: a current read-only Kambi dry-run linked 10/10 upcoming
  fixtures, returned 11 raw payload documents and 607 normalized offers, with
  zero source or mapping errors.
- `PARTIAL`: a bounded runner-owned closing watcher now polls from its own
  clock, persists lease/heartbeat state, retries transient failures, accepts
  T-30 for product CLV, and upgrades to T-10 when available. The code and
  current read-only database path are verified, but this branch has not yet
  produced a hosted watch session or a new overlapping T-10 selection close.
- `VERIFIED`: the 5-8 August production window persisted valid T-3D `678`,
  T-2D `799`, T-1D `817`, and T-2H `242` odds rows. All rows are before
  kickoff, and the current-cycle duplicate-snapshot-key audit found `0` groups.
- `FAILED`: hosted closing workflow run `31271905639` failed before its capture
  command. Its lean runner installs only `pymongo`, but then imports
  `ullebets_v2.automation`; the source package is neither installed nor on
  `PYTHONPATH`. At `2026-08-08T18:51Z`, eight minutes before Grêmio - São
  Paulo, no T-30/T-10 row or closing line had been stored.
- `VERIFIED`: commit `030a401` adds the repository's `src/` directory to the
  shared runner `PYTHONPATH`. Hosted dry-run `31273361050` completed the
  formerly failing import and closing command with zero errors. It had zero
  due targets because the next fixture was still outside its closing window.
- `PARTIAL`: V6 scoring is now downstream of each production checkpoint or
  closing capture that persists at least one new snapshot. The separate
  ten-minute scoring schedule is removed; a hosted write-mode due window must
  still prove the complete chain.
- `VERIFIED`: V2 rebuilt the full dated teamprofile snapshot in the production
  database: 585 matches, 147,408 canonical stat rows, 1,107 incidents, 1,105
  shotmaps, and 265 teamprofiles. The completed job recorded matched parity
  plus `ok` audit and health reports.
- `VERIFIED`: teamprofile persistence now uses the database's existing unique
  identity (`team_key`, `profile_date`, `match_type`) rather than an
  unindexed `profile_key`. The immediate full idempotent rebuild succeeded;
  its write stage completed in 123.7 seconds after the historical read/build.
- `VERIFIED`: V6 score persistence now compares raw feature values with an
  absolute `1e-12` tolerance and independently validates their derived feature
  fingerprint. A production-database rerun reused 105 frozen scores with zero
  conflicts; 49 were precision-equivalent rows. It created zero forward bets.
- `VERIFIED`: post-match recovery now selects by the canonical Stockholm
  fixture date and independently discovers every started forward exposure
  whose actual is unresolved. The production repair enriched all 7 affected
  22 August matches and settled all 11 V6 journal exposures: 5 wins, 6 losses,
  and 0 missing actuals.
- `VERIFIED`: every registered active EV formula now writes an immutable,
  first-capture shadow observation for each exact odds snapshot. Positive EV is
  a virtual 1u evaluation; non-positive scores remain stake-free calibration
  evidence. This journal is separate from the real V6 forward-selection
  policy.
- `VERIFIED`: production replay run `32796556700` reused all 9,358 active
  observations with zero inserts and zero immutable conflicts. Settlement run
  `32796715652` created 9,358 formula-result rows; all remain legitimately
  pending because the four underlying matches had not finished.
- `VERIFIED`: the live formula-performance API and `/modell` UI expose formula,
  statkey, scope, period, direction, league, checkpoint, status, and all-score
  versus +EV filters. Open virtual bets are excluded from stake, PnL, and ROI,
  so the current 2,913 open +EV observations render ROI as unavailable rather
  than as a false 0% result.
- `UNPROVEN`: all-formula forward ROI, official CLV, and comparative model
  efficacy require completed matches and future official T-10 closings.

Detailed backend state:
[v2-backend-verification-status.md](v2-backend-verification-status.md).

Overall product readiness:
[app-readiness-checklist.md](app-readiness-checklist.md).

### Recommended EV model

- `VERIFIED`: the serialized V6 artifact exists and its SHA-256 matches its
  manifest.
- `VERIFIED`: registry V5 resolves to 20 immutable policies with fingerprint
  `5b8a699fc874d9f967aaaab81b68ff85f61c28dbf5fb634860f768b04889794d`.
- `VERIFIED`: the strongest historical policy is
  `v6_scope_interaction_corners_away_total_primary_challenger`.
- `VERIFIED`: policy definition is corners, away or total scope, ALL/1ST/2ND,
  model EV strictly above 7.5% and below 25%, rolling 90-day training, and a
  45-day recency half-life.
- `VERIFIED`: historical result is 156 bets over 99 matches, +44.70 units,
  +28.65% ROI, and a match-clustered 95% interval of +11.33% to +45.27%.
- `VERIFIED`: one bet per match returned +30.02%; a 0.10 decimal price haircut
  retained +22.05%; every leave-one-league/window result remained positive.
- `PARTIAL`: the result is historically positive but not forward-confirmed.
- `BLOCKED`: the latest direct V2 score-archive audit found 48 V6 score rows,
  all from Brasileirão Série A and all outside the fitted training domain.
  There are 0 in-domain V6 scores, selections, settlements, ROI rows, or CLV
  rows.
- `VERIFIED`: the broader all-formula journal is evaluation infrastructure,
  not a promotion of the JS heuristics or older ML artifacts. Only the frozen
  V6 registry remains attached to real production selection; all other
  registered formulas are shadow-only.

Supported V6 leagues are A-League Men, Bundesliga, La Liga, Ligue 1, Premier
League, and Italian Serie A. Brazilian scores must remain diagnostic only.

Detailed model history:
[ev-model-experiments.md](ev-model-experiments.md).

### Model-search conclusion

- `VERIFIED`: experiments 000-077 are documented.
- `REJECTED`: count residuals and count/V6 ensembles did not improve V6.
- `REJECTED`: movement and alternate-line ladder features slightly improved
  calibration but did not prove incremental ROI over V6.
- `REJECTED`: the 90/5/5 V6/movement/ladder blend returned +31.97%
  descriptively, but its paired improvement interval crossed zero.
- `REJECTED`: prequential microstructure weighting also failed the paired
  retention gate.
- `REJECTED`: exact-as-of HGB returned -8.42% on the V6 corner policy.
- `REJECTED`: exact-as-of market-residual HGB returned -12.20%.
- `REJECTED`: small positive total-shots HGB slices had only 27-28 bets and
  failed window stability.
- `VERIFIED`: the conservative historical comparison family is now 454.
- `BLOCKED`: further filtering or weighting on the same November-May outcomes
  is data mining, not new evidence. The next justified model test is untouched
  in-domain forward settlement.

## Do not rerun without a changed reason

- Do not rerun experiments 000-077 on the same inputs merely to search for a
  higher historical ROI.
- Do not alter registry V5 from inspected history.
- Do not use current Brazilian OOD scores as model ROI or promotion evidence.
- Do not rerun already accepted support, fixture, enrichment, odds, analysis,
  and export windows unless related code, credentials, mappings, or source
  behavior changed.
- Do not simulate future timestamps in write mode.
- Do not treat missing T-10/closing evidence as a code failure before a real
  due window exists.

## Next justified tests

1. Verify the next hosted `update-teamstats-and-teamprofiles.yml` run executes
   the repaired teamprofile persistence on `main`.
2. Verify the next hosted V6 checkpoint/scorer rerun records no immutable
   conflict on `main`.
3. Merge and push the durable watcher branch, then verify the first hosted
   lease/heartbeat session from the merged `main` SHA.
4. Prove a new T-30 capture and preferred T-10 upgrade for the same immutable
   forward selection in a real hosted lifecycle.
5. Deploy the unified `Spel & resultat` read/UI contract and repeat the
   protected production browser/API checks separately from Git delivery.
6. Refresh promotion-eligible T-10 CLV for the next overlapping forward-bet
   lifecycle.
7. Evaluate forward ROI and CLV only after sufficient untouched observations
   exist.

## Chronological entries

### 2026-08-28 - Calendar date propagation and scheduled-job failure repair

Status: `VERIFIED` - both production defects are reproduced and repaired; the
current main SHA, Vercel deployment, live date endpoints, and hosted dry-run
workflow paths are verified.

Objective:

Make the shared date picker control both the match rail and `Spel & resultat`,
remove the datatunga dashboard timeout, and repair the two currently failed
scheduled workflows.

Root causes and changes:

- production `/api/v1/dashboard?date=2026-08-29` and `2026-08-30` both returned
  `504` after roughly 30 seconds, while 31 August returned `200`; dashboard
  fallback performed one full teamprofile read per home/away context;
- current profiles are now loaded in one indexable `$or` batch on exact
  `team_key`/`profile_date=current`/`match_type` identities. The real 30 August
  read fell from more than 30 seconds to `2.09s`, returning 22 matches and 40
  computed matchup rows;
- the shared `date` query is now forwarded to `/auto`, whose backend resolves
  match identities by indexed `fixtures_canonical.fixture_date_stockholm` and
  returns only selections from that Stockholm fixture day;
- scheduled teamstats run `33193180143` failed because market-bias ingestion
  passed unsupported `shotsPerTenMinutes` rows into a three-stat domain that
  intentionally accepts only corners, shots on goal, and total shots. The
  loader now excludes and audits unsupported rows instead of aborting the job;
- scheduled settlement run `33200657415` failed when Cosmos timed out the
  combined `$in` read over `ev_model_scores` after 121 seconds. The archive
  evaluator now issues one indexable equality read per model;
- teamprofile CLI logging no longer prints `profile_docs`; the failed hosted
  run emitted about 181 MB of logs although those documents are already
  represented by compact counts.

Evidence:

- `python -m pytest -q tests/v2/test_read_api.py tests/v2/test_market_bias_forward.py tests/v2/test_ev_score_archive_cli.py tests/v2/test_teamprofile_cli.py`
  -> `23 passed`;
- `npm test -- --run src/app/step1-navigation.test.tsx` -> `8 passed`;
- `npm run typecheck` -> passed;
- direct read-only production-database `read_dashboard(...,
  source_date='2026-08-30')` -> `2.09s`, 22 matches, 40 matchups,
  `computed_read_only`;
- `refresh_market_bias.py` production-data dry-run for 27 August -> exit 0,
  9 accepted observations, 239 explicitly audited unsupported rows, zero
  duplicate observation keys;
- `evaluate_ev_score_archive.py --dry-run` against current production data ->
  exit 0 after the formerly timing-out score load.
- commit `6f74034` is pushed to `origin/main`; Vercel status for that SHA is
  `success`, deployment `3xVR6Utzr9VYRxLVgZH9b2mojF3J`;
- the formerly failing live 30 August dashboard now returns `200`, 22 matches,
  40 matchup rows, and `computed_read_only` (cold request `23.22s`; warm
  production-data read `2.09s`);
- live `/auto` date filtering returned 61 groups for 29 August and correctly
  zero for 30/31 August, proving that the selected calendar date now reaches
  both read contracts;
- hosted teamstats dry-run `33206458108` on `6f74034` completed `success` in
  1m13s through the formerly failing market-bias step;
- hosted settlement dry-run `33206458437` on `6f74034` completed `success` in
  10m39s through the formerly timing-out score-archive evaluation.

What remains unproven:

- the next natural schedule occurrence in write mode has not happened yet.
  Hosted dry-runs prove the repaired failure paths without adding duplicate
  production writes; the next justified operational check is that natural
  scheduled occurrence, not another manual rerun.

### 2026-08-28 - Open-selection exact-market odds history repair

Status: `VERIFIED` - root cause, regression coverage, current read-only V2
data, Git delivery, and the exact production API row are verified.

Objective:

Show the stored odds movement for open selections instead of claiming that no
history exists before settlement.

Root cause and change:

- `read_auto` previously sourced `oddsHistory` only from
  `forward_results.price_history`; open selections have no result document yet;
- the read contract now loads immutable `market_snapshots` only for the exact
  `match_key`/`offer_key` pairs on the requested page, retaining the existing
  compound-index prefix and excluding invalid model snapshots;
- result/closing history is merged and deduplicated by the existing read model;
- the selected point is identified by exact `snapshot_key` when older forward
  rows lack `snapshot_label`.

Evidence:

- the production API reproduced the defect for RC Strasbourg-RC Lens, away
  corners, full match, under 5.5: selected odds `1.74`, `oddsHistory=[]`;
- read-only V2 inspection found three valid rows for the exact offer key:
  T-3D `1.74`, T-2D `1.77`, and T-1D `1.80`;
- the new open-selection contract test first failed with an empty list and then
  passed after the source fix;
- the focused open and settled history contracts pass `2/2`;
- the repaired read contract against the current V2 database returns the three
  prices in time order and marks T-3D `1.74` as the selected point.
- commit `1b375e4` was pushed to `origin/main`; production deployment
  `dpl_ACL3W5WhHy5z9TpqQc22eygCeMtg` reached `READY` and the permanent live API
  returned the same three points with T-3D `1.74` selected.

Files changed:

- `src/ullebets_v2/read_api/service.py`
- `tests/v2/test_read_api_contracts.py`

Remaining:

No repair remains for this defect. Later T-2H/T-30/T-10 points will appear only
after their immutable snapshots have actually been captured.

### 2026-08-28 - Durable closing watcher and unified CLV results implementation

Status: `PARTIAL` - implementation, regression coverage, current V2 data,
local browser behavior, Git delivery, and production deployment are verified;
the first hosted watcher session and next real closing lifecycle remain
unproven.

Objective:

Remove the narrow T-10 schedule dependency without paid or trial services,
accept T-30 as truthful product closing while retaining T-10 as the stronger
promotion checkpoint, and replace duplicate Auto/Resultatloop surfaces with
one `Spel & resultat` view.

Changes:

- preserved exact checkpoint provenance through the forward adapter;
- versioned closing policy `accepted_t30_t10_v2` now records separate
  `accepted_for_product_clv` and `eligible_for_promotion_clv` decisions;
- added atomic `closing_watch_sessions` lease, heartbeat, expiry takeover,
  terminal/missed states, runner-clock planning, and downstream retries;
- replaced five-minute precision scheduling and dynamic workflow enablement
  with a 15-minute seed schedule that starts a bounded 320-minute watcher,
  polling once per minute inside the runner;
- exposed accepted CLV totals, T-30/T-10 counts, beat-close distance, global
  family-aware result/ROI summaries, and exact-market odds history from the
  Auto read contract;
- reduced primary navigation to four destinations, renamed Auto to
  `Spel & resultat`, redirected legacy `/resultatloop` links to the settled
  filter, and added an accessible hover/focus/click/touch odds-movement panel.

Commands and scenarios verified:

```text
python -m pytest tests/v2/test_closing_watch_session.py tests/v2/test_closing_watch.py tests/v2/test_closing_downstream.py tests/v2/test_closing_capture.py tests/v2/test_forward_exposures.py tests/v2/test_workflow_runner.py tests/v2/test_automation_contract.py tests/v2/test_read_api_contracts.py -q
npm test -- --run
npm run lint
npm run build
python scripts/forward_v2/watch_closing_window.py --repo-root C:\dev\ullebets-prod --lookahead-hours 4 --dry-run
codegraph sync
git push origin main
git ls-remote origin refs/heads/main
vercel inspect https://ullebets-prod-preview-2x7oqj366-ryds-projects-4371adb0.vercel.app --json
```

The database scenario called `read_auto(database, status='settled', limit=1)`
directly against the guarded `ullebets_v2` connection and printed only its
count and summary fields.

Browser scenarios used the current V2 database through the local read API at
desktop and 390px widths. The settled filter, accepted CLV card, positive,
negative, and matched-close rows, desktop hover, mobile click/touch layout,
focus behavior, outside close, and Escape close were exercised. The supplied
screenshots were used as the visual reference.

Exact results:

- closing/read/automation subset: `77/77` passed;
- complete frontend suite through the VM-isolated single-thread pool: `61/61`
  passed;
- strict TypeScript production build and ESLint: passed;
- the configured Vitest fork pool was stopped after repeatedly replacing a
  Windows worker without producing a result. The project test command now uses
  one VM-isolated thread with a five-second async UI bound; all 19 files retain
  isolation and pass;
- current settled read contract: `100` observations in `61` groups, `40`
  wins, `60` losses, `-21.48%` descriptive ROI, `69` accepted T-30 CLV
  comparisons, `18/69` beating close, mean accepted CLV `-0.2072%`, and `0`
  T-10 comparisons;
- current primary V6 family: `96` observations in `57` groups, `39` wins,
  `57` losses, `-20.46875%` descriptive ROI, and the same `69` accepted T-30
  comparisons;
- the current watcher dry-run was read-only, found no fixture in the next
  four hours, attempted no capture, and returned `status=dry_run` with zero
  errors;
- local browser console noise was limited to the separately hosted SiteChat
  widget/CORS and favicon path; the unified read/UI requests returned data.
- `origin/main` resolved to implementation SHA `eb69ac8`, production deployment
  `dpl_BLiTd5NDqyxhXEEXiCm5c2VdebMh` was `READY`, and its permanent production
  alias returned HTTP 200 for `/auto?status=settled`;
- the live settled Auto API returned `126` observations in `70` groups, `69`
  accepted T-30 comparisons, `18` beating close, `0` T-10 comparisons, and the
  new family-aware summary. These live counts are time-specific and supersede
  the earlier local data snapshot above for current product display only.

Insight:

The missing-CLV complaint was a read-contract defect, not absence of odds.
T-30 comparisons already existed, but the old UI counted only official T-10.
The new product contract reports accepted T-30 honestly while model promotion
continues to require the stricter T-10 evidence. A second defect found during
browser verification was page-scoped result/ROI cards; summaries are now
computed before pagination and split by V6 versus legacy family.

Remaining:

- commits `bce4888` through `1716d53` are integrated on `main`; Git delivery
  and the production page/API are verified separately as described above;
- no hosted watcher has yet demonstrated lease recovery or a real T-30/T-10
  capture from the merged workflow;
- the current forward sample still has `0` promotion-eligible T-10 CLV rows,
  so model-quality CLV remains failed/unproven despite accepted product T-30.

Next:

Observe the first hosted bounded session, then verify the next real overlapping
T-30/T-10 close as a separate lifecycle gate.

### 2026-08-27 - Durable free closing watcher and unified results design

Status: `VERIFIED` for user-approved design; implementation and live lifecycle
remain `NOT STARTED` in this entry.

Objective:

Lock a zero-cost, no-trial production design that removes exact T-10 timing
from GitHub scheduled events, accepts T-30 as product closing, preserves T-10
quality, and consolidates Auto/Resultatloop into one truthful product surface.

Files changed:

- `docs/plans/2026-08-27-durable-closing-and-unified-results-design.md`;
- `docs/work-log.md`.

Commands or scenarios verified:

- `gh repo view ulle73/ullebets-prod --json nameWithOwner,visibility,isPrivate,defaultBranchRef,url` proved the repository is public;
- current `run-unibet-closing.yml`, `v2-odds-scheduler.yml`, closing watch
  planner, CLV/closing persistence, read contracts, routes, and frontend CLV
  rendering were inspected against the approved design;
- GitHub's current public documentation was checked for public-runner cost,
  scheduled-event delay/drop behavior, and the six-hour hosted-job limit.

Exact result and new insight:

- Standard hosted runners are available without Actions-minute charges for
  this public repository, but GitHub scheduled events are explicitly not a
  reliable precision clock. The approved design starts a bounded watcher
  several hours early and makes MongoDB lease/heartbeat state recoverable.
- T-30 becomes accepted product CLV under a versioned policy while T-10 remains
  preferred and the existing T-10-only model-promotion evidence is not changed
  retroactively.
- The design also covers the adapter provenance defect, a single server read
  contract, one `Spel & resultat` route, signed beat/miss distance, and an
  accessible exact-market odds timeline.

Unproven and next justified test:

- No implementation or live runtime state is claimed by this design entry.
- Next create the test-driven implementation plan, then prove the watcher and
  contracts locally before any hosted write-mode acceptance window.

### 2026-08-27 - CLV presentation and closing-coverage root-cause audit

Status: `VERIFIED` for persisted T-30/T-10 closing capability and the current
read-only counts; `FAILED` for official CLV coverage on tracked bets and honest
fallback presentation; `PARTIAL` for the scheduled near-close lifecycle.

Objective:

Explain why Auto and Resultatloop report missing CLV despite multiple captured
odds checkpoints, and define the smallest maintainable product/backend scope
before implementation is locked.

Files or subsystems inspected:

- `frontend/src/pages/AutoPage.tsx`, `ResultsLoopPage.tsx`,
  `components/ForwardResultTable.tsx`, `components/TopNav.tsx`, and the forward
  read types;
- `src/ullebets_v2/read_api/service.py`, closing/CLV services, checkpoint
  policy, V2 forward adapter, score persistence, and forward prediction path;
- production read-only collections `market_snapshots`, `closing_lines`,
  `forward_bets`, `forward_results`, `clv_tracking`, and `ev_model_scores`;
- current `run-unibet-closing.yml` workflow configuration and hosted run
  timing.

Commands or scenarios tested:

- `git status --short --branch`;
- `python scripts/forward_v2/refresh_clv_tracking.py --mode paths-or-db --dry-run`;
- read-only joins from each canonical forward bet to its source score,
  `market_snapshots`, same-market closing rows, CLV row, and settlement state;
- read-only closing-quality aggregation by match and forward-bet overlap;
- `gh run list --repo ulle73/ullebets-prod --workflow run-unibet-closing.yml`
  plus individual `gh run view` timing/log inspection for the T-30/T-10
  production windows.

Exact results:

- The canonical audit reduced `293` raw tracked rows to `230` bets after `46`
  combo exclusions, `8` shadow exclusions, and `9` duplicate collapses.
- CLV status is `69` `tracked_fallback_t30`, `161`
  `missing_closing_line`, and `0` official; the health, audit, and parity gates
  remained `ok` in dry-run.
- Of the `100` settled rows currently shown by the product, `69` have a valid
  T-30 fallback comparison and `31` lack a matching close; none has an
  official T-10 close.
- Production contains `5,203` closing rows. `976` are official T-10 rows over
  `13` matches, but those matches have `0` forward bets and therefore cannot
  create official selection CLV.
- A hosted window proved the code path: run `32783401333` persisted `73` T-30
  rows and run `32786170511` later persisted `73` official T-10 rows. Other
  tracked-match windows jumped from T-30 to after kickoff or outside the
  5-14-minute T-10 acceptance window.
- Resultatloop converts every non-official CLV row to `CLV saknas`, so all `69`
  valid fallback comparisons are hidden even though their signed CLV values
  exist.
- The V2 forward adapter omits `snapshot_label` and `snapshot_type`. Current
  forward rows therefore show `bäst saknas` even when their source
  `market_snapshots` row is labelled, for example, `T_MINUS_3D`.
- Closing and CLV documents retain exact-market `price_history`, but neither
  the Auto nor results read contract exposes that timeline to the frontend.

New technical/data insight:

Multiple T-3D/T-2D/T-1D/T-2H observations prove price history, not closing.
Official CLV intentionally requires a T-10 closing row; T-30 remains useful
preliminary evidence and must neither be hidden as missing nor promoted to
official CLV. The dominant operational defect is relying on delayed GitHub
scheduled events for a ten-minute acceptance window. Separately, the frontend
has two overlapping result surfaces and drops already persisted fallback and
movement detail at the read/presentation boundary.

Unproven or blocked:

- No immutable forward bet currently overlaps an official T-10 closing row,
  so official mean CLV and beat-close rate remain `UNPROVEN`.
- No product change was made in this audit; unified navigation, truthful CLV
  states, odds-history interaction, provenance repair, and a durable watcher
  remain proposed work.

Next justified test:

After approval, first regression-test and repair snapshot provenance and the
unified read contract. Then replace the narrow-window scheduler dependency and
prove one untouched forward bet through T-30, T-10, settlement, official CLV,
and the final product row without relabelling fallback evidence.

### 2026-08-25 - Immutable all-formula EV journal and comparison UI

Status: `VERIFIED` for implementation, immutable replay, hosted automation,
live read API, and responsive UI; `UNPROVEN` for settled comparative efficacy
and official CLV.

Objective:
Score every registered active formula at every exact odds capture, retain each
score as leakage-safe forward evidence, treat every valid positive-EV signal as
a virtual 1u evaluation, settle it from canonical post-match data, attach only
official closing evidence, and make the comparison understandable and
filterable without changing the real V6 selection policy.

Permanent contract:

- `models/ev/shadow_formula_registry_v1.json` freezes 16 JS formulas and the
  five existing frozen ML artifacts. Registry identity, source or artifact
  fingerprint, formula version, exact odds-snapshot identity, inputs,
  probability, EV, domain status, checkpoint, and capture time are immutable.
- `formula_observations` owns first-capture evidence. A replay validates the
  stored formula fingerprint and reuses the row; it never recomputes mutable
  support/team context into the identity of an already captured price. Direct
  conflicting writes still fail closed.
- Active JS evidence uses schema `js-v3`, canonical numeric precision, and a
  line-ending-independent runtime hash
  `e1168ea08c0efda1034343397d89525097654130495312269490180dbfd67cd5`.
  Earlier unversioned and `js-v2` rows are retained for audit with 0u and are
  excluded from active result refresh.
- `formula_results` shares the canonical settlement and closing-line
  contracts. Valid positive-EV observations use 1u; non-positive observations
  use 0u but can contribute calibration after settlement. Out-of-domain rows
  never enter ROI, CLV, calibration, or promotion evidence.
- The read API aggregates only after filtering and reports observation count,
  virtual bets, settled bets, unique matches, flat-stake PnL/ROI, official CLV,
  beat-close rate, Brier score, and log loss. Groups are ordered by evidence
  volume, not inspected ROI.
- `/modell` keeps the broad shadow comparison visibly separate from the real
  registered V6 forward proof. Its summary, explanations, evidence labels,
  filters, query-string state, all-score view, and comparison table use the
  same read contract.

Files and subsystems changed:

- formula registry, immutable observation/materialization/result services,
  settlement integration, storage collections/indexes, read API, CLI runners,
  checkpoint/closing/settlement workflows, model page, query state, filters,
  comparison table, responsive styles, and backend/frontend contract tests;
- design and execution records in
  `docs/specs/2026-08-25-all-model-shadow-journal.md` and
  `docs/plans/2026-08-25-all-model-shadow-journal.md`.

Exact verification:

- `python -m pytest -q`: 555 passed in 32.12 seconds after the final hosted
  cold-start guard was added;
- `npm --prefix frontend test -- --run`: 18 files and 59 tests passed;
- `npm --prefix frontend run lint`: passed;
- `npm --prefix frontend run build`: passed, 2,347 modules transformed and a
  production bundle built in 7.82 seconds;
- hosted replay run `32796556700`: 9,358 candidates, 8,896 JS plus 462 ML
  observations, 2,913 positive-EV virtual bets, 0 inserts, 9,358 immutable
  replays, 0 conflicts, 0 oracle errors, and 0 domain-unverified rows;
- hosted settlement run `32796715652`: 9,358 result documents inserted, 9,358
  pending, 0 settled, 0 excluded, and 0 official CLV observations;
- Vercel production deployment `dpl_7XCf1Hmv5sFcGQvdwRq6Rj8YPWmk` was `Ready`
  on the production aliases. The live positive-EV API returned 2,913 open
  virtual bets over 4 matches, 0 settled, 0 stake units, and null ROI. The
  combined `cornerKicks` + `away` + `ALL` + `T_MINUS_3D` filter returned 109
  observations over 3 matches;
- real-browser desktop and 390px mobile checks of `/modell` confirmed the
  summary, null ROI/CLV states, filter URL state, comparison table, and
  responsive layout. Switching that combined slice to `all_scores` showed 480
  scores while preserving 109 virtual +EV bets.
- the first cold protected API request reproduced Vercel's former 10-second
  function timeout, while the warm request completed in roughly 2-3 seconds.
  The read-only Python function budget is now 30 seconds, retaining edge cache
  and stale-while-revalidate behavior; a regression test freezes that minimum.
  The first protected request to the new deployment then completed successfully
  with the same 2,913/0/null-ROI contract in 9.96 seconds end to end through
  Vercel CLI.

Failures that produced permanent safeguards:

- run `32793933250` exposed capture-time instability; JS prediction time is
  now the immutable odds-snapshot time;
- run `32794550081` exposed floating-point replay drift; active evidence now
  uses canonical precision and schema-versioned formula identities;
- run `32796005030` exposed mutable support-data recomputation on replay;
  materialization now treats the earliest captured evidence as authoritative.
- the live cold-read timeout exposed an unsafe serverless duration margin;
  `vercel.json` now allows 30 seconds for the existing filtered aggregation
  instead of failing a legitimate cold database connection at 10 seconds.

New technical and data insight:
Idempotency is not merely rebuilding the same formula today. Forward evidence
must preserve what the formula knew when the price was captured. Mutable
support features may be used on the first capture, but cannot later be
recomputed into the same immutable observation identity.

What remains unproven:

- none of the current 9,358 rows had a finished-match outcome at verification
  time, so no all-formula win/loss, ROI, calibration, or comparative ranking is
  yet evidence;
- no current row has an official T-10 closing line, so CLV and beat-close rate
  remain unavailable;
- the current surface covers only the statkeys and contexts present in the four
  safe forward fixtures. Coverage expands from future odds captures; it is not
  fabricated for unsupported markets.

Next justified test:
Allow the scheduled post-match workflow to run after these four fixtures have
finished, then verify exact canonical actuals, win/loss/push settlement,
idempotent result replay, stake/PnL/ROI, and any genuinely official closing
coverage without changing formulas, thresholds, or stored observations.

### 2026-08-25 - Ullebets chatbot tenant binding repair

Status: `VERIFIED` for the deployed loader and the exact-origin SiteChat chat
contract; a manual visual click-through in a user browser remains unobserved.

Objective:
Repair the hosted Ullebets widget's tenant binding after its generic chat error
was traced to the Golfkuponger site ID being embedded on the Ullebets origin.

Changes:

- `frontend/index.html` now loads the Coastworks SiteChat widget with Ullebets
  site ID `56e53c18828b`; it no longer identifies the Ullebets origin as
  Golfkuponger (`dc0db006c4de`).
- `frontend/src/app/chatbot-loader.test.ts` now locks the Ullebets ID.

Tests:

```text
cd frontend && npm test -- --run src/app/chatbot-loader.test.ts
cd frontend && npm run build
PowerShell source/built-template/assertion check for data-site-id="56e53c18828b"
```

Results:

- The isolated Vitest command started but did not reach test execution or
  produce a pass/fail result; its local process was stopped after it hung.
- The production build passed: TypeScript completed and Vite built 2,347
  modules in 6.99 seconds.
- The exact Ullebets ID is present in the source template, built `dist` HTML,
  and the regression assertion.
- Vercel production deployment `dpl_DEYhRR5cSMAWMCqJaPLLN9VRiBo9` is `Ready`
  and its `ullebets-prod-preview.vercel.app` alias serves
  `data-site-id="56e53c18828b"` with HTTP `200`.
- A production `POST /api/chat` with Origin
  `https://ullebets-prod-preview.vercel.app`, the Ullebets site ID, and a
  valid session ID returned HTTP `200`, that exact CORS origin, a 183-character
  answer, and 3 sources.

Insight:

The crawler and the SiteChat index were not the cause of this particular chat
failure. The widget was requesting the Golfkuponger tenant from the Ullebets
browser origin, so SiteChat's tenant/origin boundary rejected the browser
request and the widget rendered its generic fallback.

Remaining:

- `UNPROVEN`: a manual visual click-through of the hosted widget in a user
  browser has not been recorded. Its deployed loader, browser-origin CORS, and
  chat response contract are verified.

Next:

- Refresh the Ullebets page and send a normal widget message; it should now
  receive the verified Ullebets response rather than the generic error.

### 2026-08-23 - Self-healing post-match enrichment and settlement recovery

Status: `PARTIAL`

Objective:
Diagnose why completed 22 August V6 journal exposures remained open in
`/auto`, repair the underlying automation and date contract, backfill the
missing production outcomes, and prove that future missed runs recover
automatically.

Root cause:

- GitHub Actions run `32620243134` for the daily teamstats/enrichment workflow
  was queued behind ML training run `32620200522` and then cancelled when
  fixture run `32620592959` became the single pending member of the shared
  `ullebets-v2-backend` concurrency group. Recent daily runs had therefore not
  fetched completed results.
- Finished-match enrichment selected mutable source dates instead of the
  product contract `fixture_date_stockholm`. The 7 affected fixtures belonged
  to 22 August in Stockholm but carried source dates of 23 or 30 August.
- The hourly settlement workflow reran correctly, but canonical actuals did
  not exist, so all 11 affected exposures remained `pending_result`.

Changes:

- Finished-match selection, persisted enrichment dates, and enrichment audits
  now consistently use `fixture_date_stockholm` with source date only as a
  compatibility fallback.
- Enrichment can now include exact match keys from started forward exposures
  in `pending_result` or `missing_actual`, guarded by the shared settlement
  timing contract and a configurable minimum match age.
- The hourly post-match workflow now owns recovery enrichment before
  settlement, CLV, result refresh, and audits. It has a dedicated concurrency
  group; the daily teamstats workflow has its own group and also runs the
  unresolved-forward recovery path.
- Automation verification now rejects the former global concurrency group and
  requires the recovery command, minimum-age guard, and job order.
- The negative workflow-contract test now removes its target line through
  `splitlines(keepends=True)` and byte-preserving rewrite, so the same gate
  executes under both LF and CRLF checkouts.

Verification:

- Regression tests were observed failing before implementation and passing
  afterward; targeted result: `32 passed in 2.53s`.
- The first merged-main run exposed the LF-only test mutation on Windows:
  `1 failed, 527 passed`. After the newline-neutral test repair, the exact
  regression passed `1/1` and the full merged-main suite passed
  `528 passed in 44.14s`.
- Production recovery dry-run selected 7 exact affected matches and produced
  7/7 raw statistics, incidents, shotmaps, results, and canonical results,
  1,821 canonical stat rows, matched parity, zero source errors, and `ok`
  audit status.
- The equivalent guarded write run persisted those 7 match outcomes. The
  settlement/result chain then produced 55 canonical forward exposures: 15
  settled and 40 legitimately open for current or future matches.
- Exact 22 August audit: 11/11 V6 journal exposures are `settled`, with 5
  wins, 6 losses, and 0 missing actuals. The protected production
  `/api/v1/auto` response exposes the same statuses and actual values.
- `MONGODB_DB=ullebets_v2 python scripts/forward_v2/healthcheck_v2.py`
  returned `overall_status=ok`.

Insight:
Settlement cannot repair missing upstream actuals. Durable recovery must be
driven by unresolved immutable forward identities, not only by a calendar
schedule that can be cancelled or by a provider's mutable date label.

Remaining:
The code and data repair are production-database verified. Merge/push, hosted
execution of the new workflow definition, and final Vercel source/deployment
verification remain separate delivery gates.

Next justified test: run the post-match workflow from the merged `main` SHA,
verify its complete hosted chain, and then confirm the protected production
read API still returns all 11 affected rows as settled.

### 2026-08-23 - V6 full-domain checkpoint journal

Status: `PARTIAL`

Objective:
Implement the forward-only journal that records every supported positive-EV
V6 checkpoint observation as a separate 1u play, settles each observation,
tracks CLV by horizon, and groups only the read presentation.

Changes:

- Added immutable registry `forward_policy_registry_v2` and policy
  `v6_full_domain_checkpoint_journal_v2`; frozen V1 was not modified.
- Registered the honest V6 domain: corners over/under and shots on goal/total
  shots over-only, for home/away/total and 1ST/2ND/ALL.
- Made forward identity granularity-aware so checkpoint observations remain
  separate through persistence, settlement, CLV, and forward results.
- Added read-only grouping by policy, match, stat, scope, period, direction,
  and line. Best observed EV is the representative row; stake, PnL, ROI, and
  official CLV counts are aggregated over every underlying observation.
- Added stat/scope/period/direction/checkpoint filters, model-support status on
  match offers, grouped Auto/Resultat UI, and automatic score -> settle -> CLV
  -> forward-result workflow wiring.
- Fast-forward merged the verified feature branch to `main`, pushed commit
  `1243355` to `origin/main`, and removed only the clean owned feature
  worktree/branch. The unrelated `.playwright-cli/` directory was preserved.
- Deployed the same product commit explicitly to Vercel Production because the
  project is not Git-linked. Deployment `dpl_7yabEkwkhqdA2dkcQkeEph1DFUFa`
  reached `Ready` and received the production alias
  `https://ullebets-prod-preview.vercel.app`.

Tests:

```text
python -u -m pytest tests/v2/test_ev_policy_registry.py tests/v2/test_ev_score_evaluation.py tests/v2/test_ev_forward_predictions.py tests/v2/test_forward_exposures.py tests/v2/test_settlement.py tests/v2/test_clv_tracking.py tests/v2/test_forward_results.py tests/v2/test_read_api.py tests/v2/test_read_api_contracts.py tests/v2/test_automation_contract.py -q
python -u -m pytest tests -q
npm test -- --run
npm run typecheck
npm run lint
npm run build
python -u scripts/forward_v2/score_ev_shadow_model.py --repo-root C:\dev\ullebets-prod --artifact <worktree>/models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/ev_scope_interaction_recency45_asof_capped_v6_shadow.joblib --manifest <worktree>/models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/model_manifest.json --score-only --selection-policy-registry <worktree>/models/ev/forward_policy_registry_v2.json --selection-policy-id v6_full_domain_checkpoint_journal_v2 --dry-run
git push origin main
vercel deploy . --prod -y --scope ryds-projects-4371adb0
vercel inspect dpl_7yabEkwkhqdA2dkcQkeEph1DFUFa --scope ryds-projects-4371adb0
```

Results:

- Backend feature/contract gate: `103 passed`; the subsequent full V2 suite
  and the post-merge `main` suite both passed `522/522`.
- Frontend gate under Node 24.19: `57 passed`; TypeScript, ESLint, and
  production build all exited `0` before and after the merge.
- One deliberately parallel pre-merge backend/frontend gate produced a
  frontend cold-import timeout in the Auto route plus two Vitest worker-start
  timeouts while the backend suite and an unrelated package installation were
  consuming the machine. No production code was changed for that run. The
  isolated rerun passed all `57/57`, and the sequential merged-main gates then
  passed `522/522` backend and `57/57` frontend tests.
- The first unscoped post-merge `python -m pytest -q` process also ended with
  exit `1` near completion without a pytest failure report during the same
  resource contention. The explicit repository collection found exactly 522
  tests, and `python -m pytest tests -q` passed all `522/522` in `35.42s`.
- Real database dry-run read `1,391` snapshot rows, built `249` canonical
  markets and `402` scores across 17 matches, excluded 96 Brazil OOD scores,
  and produced 44 registered V2 checkpoint-journal selections.
- Dry-run persistence was exactly zero inserts, existing rows, and conflicts.
- Registry fingerprint:
  `7d3c1a2fe659a86a8b8078a22d1af1e93bd57316138b8d5ca0ac76aa5a0b805e`.
- GitHub `origin/main` resolved to `1243355`; Vercel built 2,343 frontend
  modules plus both read-only Python route depths and reported production
  deployment `dpl_7yabEkwkhqdA2dkcQkeEph1DFUFa` as `Ready`.

Insight:
The same market can be one display group without becoming one evaluation
unit. Horizon ROI and CLV remain honest only when every captured checkpoint
keeps its own prediction key, 1u stake, price, settlement, and CLV row.

Remaining:

- `UNPROVEN`: no V2 journal row has yet been persisted by a hosted write-mode
  checkpoint run.
- `UNPROVEN`: no complete future in-domain journal observation has yet passed
  through official T-10 CLV and untouched settlement.
- Historical or dry-run selections are not forward model ROI evidence.

Next:
Verify the next due hosted checkpoint writes the V2 policy observations, then
audit the later scheduled settlement, official CLV refresh, and grouped read
result without changing the policy or model.

### 2026-08-23 - Vercel-routing för liga-, lag- och matchdetaljer

Status: `VERIFIED`

Objective:
Reproduce and permanently repair the production defect where the dashboard
loaded but every clicked league, team, and match rendered an API error.

Changes:

- Replaced the incompatible Vercel Python catch-all entrypoint with the two
  filesystem route depths Vercel supports: `api/v1/[resource]` and
  `api/v1/[resource]/[resource_id]`.
- Moved the complete HTTP adapter (V2-only database guard, JSON responses,
  ETags, compression, cache policy, and write rejection) to the single shared
  module `ullebets_v2.read_api.vercel_adapter`. The two Vercel files only
  declare route entrypoints; they do not duplicate API behavior.
- Added regression coverage that starts both entrypoints and verifies that a
  single-segment path reaches the read dispatcher and an unknown league detail
  receives V2 JSON `league_not_found`, rather than a Vercel filesystem page.

Tests:

```text
python -m pytest -q tests/v2/test_vercel_read_api.py -k detail_function
python -m pytest -q tests/v2/test_vercel_read_api.py -k single_segment
python -m pytest -q tests/v2/test_vercel_read_api.py
python -m compileall -q api src/ullebets_v2/read_api
npm --prefix frontend run lint
npm --prefix frontend run build
vercel deploy --yes
vercel deploy --prod --yes --scope ryds-projects-4371adb0
vercel inspect dpl_DcbJPcrn5eHBH642oPpmekLStz6J --scope ryds-projects-4371adb0
```

Results:

- The two new tests each failed first because the required Vercel dynamic
  entrypoint did not exist. The final focused backend suite passed `6/6`.
- Compile and whitespace checks, frontend ESLint (zero warnings), and the
  TypeScript/Vite production build passed.
- A local `vercel build` first exposed the unsupported catch-all/dynamic-route
  collision. After the route-depth change it reached dependency installation
  and stopped only because this workstation has no local `uv`; Vercel's remote
  build supplies `uv` and completed successfully.
- Preview deployment `dpl_8ZMAkBm8gLQngtFujRswKW3cMBxp` and production
  deployment `dpl_DcbJPcrn5eHBH642oPpmekLStz6J` are `Ready`. Each contains
  exactly `api/v1/[resource]` and `api/v1/[resource]/[resource_id]` Python
  functions at `14.8 MB`. Production alias:
  `https://ullebets-prod-preview.vercel.app`.
- Authenticated production reads returned V2 JSON for
  `/api/v1/leagues/brasileirao-serie-a` (`league, teams, ranking, matches`),
  `/api/v1/teams/brasileirao-serie-a%3A1954`
  (`team, league, contexts, matches`), and
  `/api/v1/matches/sofascore%3A15235438` (complete match-detail payload).
- A real-browser Playwright check clicked the same league, Cruzeiro, and
  Cruzeiro - Flamengo links. The loaded headings were Brasileirão Série A,
  Cruzeiro, and Cruzeiro mot Flamengo; none rendered the former read error.

Insight:

The previous Python catch-all looked correct in local proxy tests but Vercel
never invoked it for two-segment filesystem paths. Declaring supported route
depths while sharing one adapter makes the deployment contract explicit and
prevents local mocks from masking a routing failure.

Remaining:

- The browser reported pre-existing CORS failures from the independent
  Coastworks chatbot widget. They do not affect the verified Ullebets API or
  the three drilldown routes and were not changed in this repair.

Next:

- Treat the drilldown routing as complete; only re-run the focused route test
  and production smoke when the Vercel function layout or read API contract
  changes.

### 2026-08-23 - Coastworks SiteChat widget endpoint update

Status: `VERIFIED`

Objective:
Update the embedded chatbot widget in the frontend HTML shell to point to the
Coastworks SiteChat production endpoint (`https://coastworks-sitechat.vercel.app`).

Changes:
- Replaced the local development chatbot script loader in `frontend/index.html`
  with the production Coastworks SiteChat widget script tag (`data-site-id="dc0db006c4de"`, `data-api-url="https://coastworks-sitechat.vercel.app"`).
- Updated `frontend/src/app/chatbot-loader.test.ts` to assert against the new
  Coastworks SiteChat widget attributes.

Tests:
```text
cd frontend && npm test -- --run src/app/chatbot-loader.test.ts
cd frontend && npm test -- --run
cd frontend && npm run typecheck
cd frontend && npm run lint
cd frontend && npm run build
git diff --check
python -m pytest tests/v2 -q
```

Results:
- Frontend isolated test `chatbot-loader.test.ts` passed 1/1.
- Full frontend test suite passed 17 files / 57 tests.
- TypeScript check, ESLint (0 warnings), and Vite production build passed.
- `git diff --check` passed with 0 whitespace issues.
- Backend regression passed 480/480.

Insight:
The chatbot widget is now loaded directly from the hosted Coastworks SiteChat
production service rather than the local development server.

Remaining:
- Live browser interaction with the hosted chatbot widget in production.

Next:
- Observe chatbot appearance and responsiveness in live frontend sessions.

### 2026-08-23 - Fail-closed fixture ingestion after current-day coverage loss

Status: `VERIFIED`

Objective:
Reproduce why the 23 August dashboard shows four fixtures although the supplied
day schedules show 19, then prevent an upstream outage from being recorded as a
successful empty import.

Changes:

- `fixtures/live.py` now rejects a live date when any supported league category
  has no HTTP-successful scheduled-fixture source; an HTTP-successful empty
  response remains a valid empty category.
- `fixtures/service.py` creates the V2-safe job run before live retrieval and
  records it as `failed` if source retrieval aborts. No raw, canonical, link,
  parity, or audit documents are written for a failed date.
- Updated fixture regression tests and the readiness checklist to distinguish
  complete empty days from a provider outage.

Tests:

```text
vercel curl '/api/v1/dashboard?date=2026-08-23' --scope ryds-projects-4371adb0
gh run view 32629154864 --log
python -m pytest tests/v2/test_fixture_live.py::test_live_fixture_ingest_fails_closed_when_a_category_has_no_reachable_source -q
python -m pytest tests/v2/test_fixture_live.py -q
python -m pytest tests/v2 -q
python -m compileall -q src scripts
git diff --check
vercel deploy --prod --yes --scope ryds-projects-4371adb0
gh workflow run import-fixtures-rolling.yml -f start_date=2026-08-23 -f end_date=2026-08-23 -f dry_run=false
gh run watch 32631232032 --exit-status
gh workflow run import-fixtures-rolling.yml -f start_date=2026-08-23 -f end_date=2026-08-23 -f dry_run=false
gh run watch 32634363672 --exit-status
```

Results:

- The protected production API and the V2 canonical query both returned exactly
  four fixtures for `2026-08-23`: Cruzeiro - Flamengo, Brighton - Aston Villa,
  Manchester City - Bournemouth, and Angers - Lille.
- The latest scheduled Actions run `32629154864` was marked `success` although
  it reported `processed_dates=8`, `raw_docs=8`, `canonical_docs=0`, and
  `source_link_docs=0`.
- Direct diagnostics found all 12 configured RapidAPI keys returned 429 or 403
  across the scheduled-fixture endpoints; the public fallback returned 403.
  The configured SofaSport provider does not expose a scheduled-events endpoint
  (its responses were HTTP 404). No missing fixtures exist in V2 under another
  timestamp or date field.
- New fixture regression coverage passed: `16 passed in 0.32s`; the complete
  V2 suite passed `482` tests in `17.18s`. Compile and whitespace checks
  passed. The red tests first reproduced both the old false-success behavior
  and the HTTP-200 error-payload gap.
- Vercel production deployment `dpl_JDRoSvYcrSw6bdJpnNk3tE9LDwJd` is `Ready`
  with the `api/v1/[...path]` function at `14.79 MB`.
- A write-mode, one-date production verification run
  `32631232032` failed in `52s` exactly as intended. Its V2 job run
  `41f8eca2a72e4c9c91e9141a49b270ca` has `status=failed`,
  `processed_dates=0`, and `FixtureSourceUnavailableError` listing the
  RapidAPI `429/403` responses plus public fallback `403`; it did not create
  a new canonical fixture batch.
- The local `.env.local` now contains `15` `RAPIDAPI_KEYS`. The same secret
  was replaced in GitHub Actions and in Vercel Production as a sensitive
  server-side environment variable; neither platform exposed the value during
  verification.
- The subsequent one-date, write-mode GitHub Actions run `32634363672`
  succeeded. It processed `1` date and reported `8` raw documents, `38`
  canonical upsert operations, and `38` source-link operations. A direct V2
  read then confirmed exactly `19` canonical documents, `19` unique identity
  keys, and no duplicate identities for `2026-08-23`.
- The protected production dashboard now returns exactly `19` matches for
  `2026-08-23`: Brasileirão Série A `6`, Serie A `4`, Premier League `3`,
  La Liga `3`, and Ligue 1 `3`.

Insight:

The initial fault was a live-source entitlement/capacity outage, compounded by
a workflow bug that treated zero successful source batches as a valid empty
day. New active credentials restore the schedule; the fail-closed behavior
remains necessary for the next provider outage.

Remaining:

- `UNPROVEN`: the new credential pool's sustained capacity for the rolling
  D0-D7 schedule is not yet proven; only the repaired D0 import has current
  runtime evidence.

Next:

- Observe the next scheduled rolling D0-D7 import and require nonzero source
  coverage plus canonical counts before accepting sustained provider capacity.

### 2026-08-23 - Stockholm-baserat fixture-datum för matchlistan

Status: `VERIFIED`

Objective:
Åtgärda den reproducerade datumblandningen i dashboarden utan att förvanska
källproveniens eller historiska rådata.

Changes:

- Lade till det härledda canonical-fältet `fixture_date_stockholm`, beräknat
  från `start_time` i `Europe/Stockholm`; `source_date` bevaras oförändrat som
  den externa källans inläsningsetikett.
- Uppdaterade dashboarden samt date-bundna matchup- och league-average-läsningar
  till att använda produktdatumet och lade till ett sammansatt index för
  `fixture_date_stockholm` och `start_time`.
- Lade till en V2-säker, idempotent backfill som endast skriver det härledda
  fältet. Den produktionsanslutna körningen uppdaterade `755/755` canonical
  fixtures; en efterföljande dry-run krävde `0` ändringar.
- Lade till regressionstester för tidszonsgräns, 21/22/23-augusti-kontraktet,
  indexet och backfillens idempotens.
- Lade till root-förankrade Vercel-exkluderingar så att lokala historik- och
  offlinefiler inte blir deployade. Funktionens runtime använder enbart
  `requirements.txt`; det lokala `pyproject.toml` med ML-beroenden bevaras för
  offline-jobben men skickas inte till Vercel.

Tests:

```text
python scripts/forward_v2/backfill_fixture_date_stockholm.py --dry-run
python scripts/forward_v2/backfill_fixture_date_stockholm.py --batch-size 100
python scripts/forward_v2/backfill_fixture_date_stockholm.py --dry-run
python -m pytest tests/v2 -q
cd frontend && npm test -- --run
cd frontend && npm run typecheck
cd frontend && npm run lint
cd frontend && npm run build
python -m compileall -q src scripts
git diff --check
vercel deploy --prod --yes --scope ryds-projects-4371adb0 --no-wait
vercel inspect dpl_AYky64hNFyiPfThuZSPMEsd2SiX1 --logs --scope ryds-projects-4371adb0
vercel curl '/api/v1/dashboard?date=2026-08-22' --deployment dpl_AYky64hNFyiPfThuZSPMEsd2SiX1
```

Results:

- Första dry-run: `scanned=755`, `eligible=755`, `would_update=755`.
  Skrivkörningen uppdaterade exakt `755`; andra dry-run rapporterade
  `already_correct=755` och `would_update=0`.
- Det nya indexet finns i den anslutna `fixtures_canonical`-kollektionen.
- Det aktuella dashboard-kontraktet för `2026-08-22` returnerar `19` matcher:
  Arsenal - Coventry City (`2026-08-21` Stockholm) utesluts och Hull City -
  Manchester United (`2026-08-22 13:30` Stockholm) inkluderas. Den bevarade
  källbatchen innehåller fortfarande fördelningen `3/19/4` över 21/22/23.
- Backend: `480 passed in 23.98s`. Frontend: `17` filer och `57` tester.
  TypeScript, lint, produktionsbygge (`2,343` moduler), compileall och
  whitespace-kontroll passerade.
- Vercel-produktion `dpl_AYky64hNFyiPfThuZSPMEsd2SiX1` är `Ready`. Bygget
  passerade på `15s` och den read-only Python-funktionen är `14.79 MB`.
  Den skyddade, autentiserade produktionskontrollen returnerade
  `selectedDate=2026-08-22` och `19` matcher, med Hull City men utan Arsenal.
  Oautentiserade direkta HTTP-anrop går avsiktligt till Vercel SSO (HTTP 302)
  innan appen, inte till en felaktig API- eller frontend-fallback.

Insight:

En lyckad inläsning av en källdag betyder inte att alla matcher startar samma
lokala kalenderdag. Produktens datumfilter måste baseras på den canoniska
avsparkstiden, medan `source_date` endast ska användas för spårbarhet.

Remaining:

- Ingen öppen brist i datumkontraktet. Vercel-skyddet innebär att framtida
  automatiserade HTTP-prober måste använda auktoriserad bypass eller köras av
  en inloggad användare.

Next:

- Observera nästa vanliga fixture-inläsning och dess dashboarddatum som
  rutinmässig livscykeluppföljning; ingen historisk datakörning är motiverad.

### 2026-08-23 - Dashboardens datumfilter blandar avsparksdagar

Status: `FAILED`

Objective:
Verifiera varför den valda matchdagen `2026-08-22` visar matcher från andra
Stockholm-datum i den produktionsanslutna skrivskyddade V2-vyn.

Changes:

- Ingen produktkod, databasdata eller konfiguration ändrades.
- Dokumenterade den reproducerade read-kontraktsdefekten och sänkte endast den
  berörda frontend-readiness-raden till `PARTIAL`.

Tests:

```text
Read-only audit: fixtures_canonical.find({"source_date": "2026-08-22"})
Read-only contract call: read_dashboard(db, source_date="2026-08-22")
```

Results:

- Båda läsningarna returnerade 26 matcher för `source_date=2026-08-22`.
- Avsparksdatum i `Europe/Stockholm` var 3 matcher den 21:a, 19 den 22:a och
  4 den 23:e. Arsenal - Coventry City startar `2026-08-21T21:00:00+02:00`;
  Hull City - Manchester United startar `2026-08-22T13:30:00+02:00`.
- `read_dashboard()` filtrerar `fixtures_canonical` på den externa
  inläsningsetiketten `source_date`. Fixture-normaliseringen kopierar i sin
  tur payloadens/frågans datum till samma fält även när händelsens
  `start_time` tillhör en annan lokal kalenderdag.

Insight:

`source_date` är källproveniens, inte ett säkert användarvalt speldatum.
Datumvyn måste filtrera på ett separat, härlett datum från `start_time` i
`Europe/Stockholm`; rått källdatum ska bevaras oförändrat för spårbarhet.

Remaining:

- `FAILED`: den produktionsanslutna matchlistan kan blanda dagar när
  datuminläsningen innehåller evenemang utanför den begärda kalenderdagen.
- Ingen regression täcker skillnaden mellan `source_date` och lokalt
  avsparksdatum.

Next:

- Implementera ett separat, indexerat Stockholm-baserat fixture-datum,
  migrera/rebygg bara det härledda fältet från befintliga `start_time`-värden,
  och lägg till en regression med 21/22/23-augusti-fixtures.

### 2026-08-22 - Stable lazy-route frontend gate

Status: `VERIFIED`

Objective:
Make the complete frontend route-surface gate deterministic when its first
lazy-loaded page is transformed from a cold test process.

Changes:

- Made the Auto route's existing asynchronous heading assertion wait up to five
  seconds instead of relying on Testing Library's one-second default. No
  production route, API, or lazy-loading behavior changed.

Tests:

```text
cd frontend && npm test -- --run src/app/remaining-routes.test.tsx
cd frontend && npm test -- --run
```

Results:

- The isolated route-surface test passed 5/5.
- The complete frontend suite passed 17 files and 57 tests after the
  cold-load timing failure was reproduced only in the original merge gate.
- The merged `main` backend regression passed 476/476; frontend lint and the
  TypeScript/Vite production build passed, and `git diff --check` reported no
  whitespace errors.

Insight:

`AutoPage` is the first lazy module exercised by this route test. Its module
load can exceed the generic one-second async-query timeout in a cold serial
Vitest process; that is test timing, not an Auto API or rendering failure.

Remaining:

- The verified local `main` commit still needs to be pushed and compared with
  `origin/main`; this does not itself prove a Vercel deployment.

Next:

- Push the green merged `main` branch and verify the remote ref.

### 2026-08-22 - Neutral public match URLs and preview API diagnosis

Status: `PARTIAL`

Objective:
Ensure public match URLs never expose the internal source provider, preserve
legacy links, and identify why the active preview cannot load match details.

Changes:

- Added `frontend/src/domain/match-route.ts`. Internal keys such as
  `sofascore:16283044` now generate the neutral public URL
  `/matcher/match-16283044`.
- Centralized match-link generation through that route helper, including the
  generic entity links, Auto page, active match rail, and legacy source-key
  redirects.
- Updated the read API to resolve a `match-<source-id>` URL identifier to one
  canonical fixture only, while retaining the internal `match_key` for every
  downstream database lookup.

Tests:

```text
RED: cd frontend && npm test -- --run src/domain/match-route.test.ts
RED: python -m pytest tests/v2/test_read_api.py -q
RED: cd frontend && npm test -- --run src/pages/match-detail/MatchAnalytics.test.tsx
GREEN: python -m pytest tests/v2 -q
GREEN: cd frontend && npm test -- --run
cd frontend && npm run lint
cd frontend && npm run build
git diff --check
codegraph sync
```

Results:

- The source-contract tests failed first because the neutral route helper and
  public-ID resolver did not exist; the legacy-route UI test also reproduced
  the same failed match state shown in the preview.
- Direct public request to
  `/api/v1/matches/sofascore%3A16283044` returned Vercel `404 NOT_FOUND`,
  before the V2 handler could run. The deployed preview is therefore a
  static-only deployment despite the checked-out repository containing the
  tested `api/v1/[...path].py` read function.
- Backend: `476 passed in 59.68s`. Frontend: `17` files / `57` tests passed
  in `95.94s`. Lint, production build (`2,343` modules), diff check, and
  CodeGraph sync passed.

Insight:

The displayed fallback was correct client behavior for a missing API, not a
missing match or a frontend rendering defect. A rewritten URL alone would not
fix the preview until the serverless read function is deployed with the app.

Remaining:

- `BLOCKED`: the live preview still returns Vercel's infrastructure `404` for
  every `/api/v1/*` request. The deployment must include the repository root,
  `vercel.json`, and `api/v1/[...path].py`; runtime health remains unverified.

Next:

- Deploy the verified repository-root Vercel configuration, then check
  `/api/v1/health` and a neutral `/matcher/match-16283044` URL.

### 2026-08-22 - Local chatbot widget loader

Status: `PARTIAL`

Objective:
Load the supplied chatbot widget from the shared frontend document head without
changing application, API, model, or data behavior.

Changes:

- Added the asynchronous widget loader to `frontend/index.html` with site ID
  `dc0db006c4de` and the supplied local widget/API endpoints.
- Added `frontend/src/app/chatbot-loader.test.ts` to lock the required loader
  URL, async flag, dataset values, and head insertion contract.

Tests:

```text
RED: cd frontend && npm test -- --run src/app/chatbot-loader.test.ts
GREEN: cd frontend && npm test -- --run src/app/chatbot-loader.test.ts
cd frontend && npm run lint
cd frontend && npm run build
git diff --check
```

Results:

- RED failed as expected with `1 failed`: the loader URL was absent from the
  page template.
- GREEN passed with `1 passed` after adding the loader.
- Lint passed with zero warnings; the production build transformed `2,342`
  modules and completed successfully; `git diff --check` passed.

Insight:

`127.0.0.1:8000` resolves in each visitor's browser, so the widget can load
only where that local chatbot service is running.

Remaining:

- `UNPROVEN`: live widget startup and interaction against that local service;
  no service or runtime behavior was changed in this session.

Next:

- Start the local widget service and open the frontend only when live widget
  behavior needs verification.

### 2026-08-21 - V2 market bias production bootstrap and matchup UI

Status: `VERIFIED` for the historical bootstrap, immutable replay, persisted
matchup attachment, read API, and frontend contract. `UNPROVEN` for the first
scheduled completed-match forward refresh.

Objective:
Build an auditable, presentation-only indicator of how each team has performed
against comparable Unibet prematch main lines without changing matchup ranks,
V6, selections, ROI, or CLV.

Changes and findings:
- Added immutable `market_bias_observations`, reproducible rolling
  `market_bias_profiles`, database indexes, audits, health rows, offline
  bootstrap, and V2-only completed-match refresh automation.
- The real bootstrap exposed and fixed three production defects before final
  acceptance: N+1 Cosmos existence reads, nondeterministic duplicate legacy
  line selection, and a final join that could reintroduce a non-selected price.
- Full bootstrap now chooses one deterministic latest authoritative line and
  one direction price nearest even odds before calculating the observation.
  Two independent full source builds produced identical 16,528 keys, hashes,
  and odds with `diff_count=0`.
- Failed partial bootstrap rows were deleted only after proving they were
  rebuildable `offline_v1_bootstrap` derivatives, contained no forward data,
  had produced no profiles, and had no accepted successful lifecycle.

Persisted evidence:
- Successful bootstrap run `6821fc78adbf42ff9e26bb994f527853` inserted
  16,528 observations and 2,112 profiles with zero mapping, timing, duplicate,
  missing-actual, or source-hash failures.
- Immediate rerun `6267c0b6141b41669ee400fcaf0f986a` inserted zero
  observations, replayed all 16,528 immutable rows, and inserted zero profiles.
- Final collections contain 16,528 observations and 2,112 profiles with the
  intended unique/context indexes and zero running refresh jobs.
- The 367 qualifying-line rejections are markets without an OVER price in the
  configured 1.70-2.30 main-line window, not identity or timing failures.
- Rebuilt 2026-08-22 outputs contain 3,222 rows in each matchup collection.
  Each has 1,080 primary-stat rows; 520 have an exact team/stat/scope/period
  bias profile. Missing contexts remain explicit rather than guessed.
- Fresh read API smoke on isolated port 8790 returned HTTP 200 with 26 matches,
  40 top matchup cards, typed camelCase bias summaries, and no secret lineage
  fields. The old local process on port 8787 was deliberately left untouched.

Verification:
```text
python -m pytest tests/v2 -q
python -m compileall -q src scripts
git diff --check
cd frontend && npm test -- --run
cd frontend && npm run typecheck
cd frontend && npm run lint
cd frontend && npm run build
```

Results:
- Backend: `475 passed in 30.81s`; compileall and diff check passed.
- Frontend: `54 passed in 119.05s`; typecheck, lint, and production build
  passed.

Remaining:
- `UNPROVEN`: the first scheduled `v2_forward` market-bias refresh after a
  newly completed match. Historical bootstrap success is not live evidence.
- `PARTIAL`: 560/1,080 primary matchup rows for the tested date lack an exact
  profile context and correctly render no bias; season-wide coverage remains
  to be measured as new observations accumulate.

Next:
Inspect the next completed-match workflow's `refresh_market_bias` job metrics
and require immutable inserts/replays plus zero timing and mapping failures.

### 2026-08-21 - V2 market-bias Tasks 6-8 integration

Status: `PARTIAL`

Objective:
Attach the independent market-bias profile context to matchup reads, expose a
typed read contract, and render it on matchup cards without changing ranking,
V6, selection, ROI, or CLV behavior.

Results:
- Task 6 matchup regression passed `9/9`: entry keys, scores, sort keys,
  rank positions, and membership remain invariant with bias profiles present.
- Task 7 API contract regression passed `22/22`: only typed camelCase
  summaries are exposed, total profiles are home/away ordered, and absent
  profiles are `null`.
- Task 8 component and app regression passed `5/5`; full frontend suite
  passed `54/54` in `111.28s`; typecheck, lint, and production build passed.

Insight:
Market bias is loaded from `market_bias_profiles` independently of
teamprofiles and only when its `as_of` is strictly before fixture kickoff.

Remaining:
- `UNPROVEN`: a live completed forward market-bias lifecycle.

Next:
Observe a completed-match forward refresh before treating the feature as
operationally proven.

### 2026-08-21 - V2 market-bias Tasks 4-5 adapters

Status: `PARTIAL`

Objective:
Add the read-only offline bootstrap adapter and V2-only forward refresh
foundation without bootstrap writes, matchup changes, or model changes.

Results:
- Historical dry-run command completed read-only with `16,386` accepted,
  `0` unmatched, `0` ambiguous, `0` timing-invalid, `0` missing actuals,
  `0` duplicate keys, and `438` qualifying-line rejections. It created no
  observations or profiles because `--write` was not supplied.
- Exact source IDs resolved `25,286` team identities; no name fallback or
  configured alias was needed. The compact local audit records the accepted distributions and
  bounded metrics without embedding observation/profile documents.
- Focused adapter suites passed `43/43` in `5.97s`; full V2 suite passed `464/464` in
  `61.97s`; `python -m compileall -q src scripts`, `git diff --check`, and
  `codegraph sync` passed.
- Observation persistence now batch-fetches immutable evidence by
  `observation_key` in bounded `$in` queries before bulk insert; it no longer
  performs one Cosmos `find_one` per candidate. The focused market-bias suites
  passed `23/23` in `2.88s`; the full V2 suite passed `470/470` in `22.01s`;
  `python -m compileall -q src` and `git diff --check` passed.

Insight:
The source adapter must select an exact `match_id + bet_key` outcome for the
chosen OVER price, not a match-level row. Its line-independent context grouping
now chooses only one main line per market context.
Existing observation replay is bounded to `100` exact-context clauses per
Cosmos `$or` query, verified with a `101`-context service regression test.
An empty `market_bias_observations` collection now exits after one projected
`find_one` instead of issuing context queries; interrupted write-mode refreshes
mark their `job_run` as failed before re-raising.
For nonempty collections, persistence resolves all candidate keys in bounded
Cosmos-safe `$in` batches, compares immutable fingerprints locally, then sends
only absent documents to unordered bulk writes. Existing or concurrent
duplicate-key errors remain failures rather than silently accepting a possible
hash conflict.

Remaining:
- `UNPROVEN`: a deliberate bootstrap write and its immutable persistence
  lifecycle; this batch was explicitly read-only.
- `UNPROVEN`: live scheduled forward refresh against a completed match.

Next:
Review the compact bootstrap audit and authorize a separately audited write
only if the historical import is needed; otherwise observe a completed-match
forward refresh.

### 2026-08-21 - V2 market-bias Tasks 1-3 foundation

Status: `PARTIAL`

Objective:
Implement only the V2 market-bias storage contracts, pure domain calculation,
and immutable refresh-service foundation. Matchup ranking, V6, model, ROI,
CLV, API, and frontend were intentionally unchanged.

Changes:
- Added suffix-free `market_bias_observations` and `market_bias_profiles`
  collection contracts plus unique and context lookup indexes.
- Added deterministic prematch main-line selection, exact outcome/context
  observations, leakage-safe rolling profiles, immutable persistence, audit /
  health rows, and `job_runs` lifecycle orchestration.

Tests:
```text
python -m pytest tests/v2 -q
python -m compileall -q src
git diff --check
```

Results:
- Full V2 regression: `452 passed in 23.73s`; `compileall` passed and
  `git diff --check 44c6d50..HEAD` reported no errors.

Insight:
The initial foundation is database-adapter-neutral and fails closed on source
evidence changes, duplicate observation keys, post-kickoff snapshots, and
outcomes unavailable at the explicit profile cutoff.

Remaining:
- `UNPROVEN`: audited Parquet bootstrap mapping/coverage, V2 forward candidate
  adapter, production database index application, scheduled orchestration,
  matchup/read-API integration, and frontend rendering.
- No database write or live market-bias result occurred in this task group.

Next:
Implement the audited bootstrap adapter with dry-run identity/mapping report
before permitting the first V2 market-bias database write.

### 2026-08-21 - V2 market-bias production design

Status: `NOT STARTED` for implementation. The architecture and acceptance
contract are approved and documented; no production code, database data,
matchup ranking, or V6 behavior changed in this session.

Objective: replace the empty legacy-compatible `market_bias` field with an
auditable team tendency against comparable Unibet prematch lines.

Evidence and decisions:

- Current V2 contains 15,208 market snapshots, including 14,711 valid
  prematch rows, but only 135 finished primary-market contexts currently join
  directly to canonical actuals.
- The audited offline corpus contains 11,917 preliminary eligible main-line
  contexts over 1,017 matches before canonical V2 team/league mapping.
- The selected architecture uses a one-time audited Parquet bootstrap followed
  by idempotent forward refreshes from V2-only collections.
- Bias uses the latest valid prematch capture, an over line nearest 2.00 within
  1.70-2.30, exact stat/scope/period outcomes, a rolling 12-match window,
  45-day recency half-life, and neutral small-sample shrinkage.
- Bias remains matchup context only. Matchup ranking and frozen V6 model,
  prediction, selection, ROI, and CLV paths remain unchanged.

Design:

- [2026-08-21-market-bias-v2-design.md](superpowers/specs/2026-08-21-market-bias-v2-design.md)

Remaining:

- Execute the reviewed implementation plan.
- Audit exact historical team/league mapping before any bootstrap write.
- Implement, verify, and deploy the observation, profile, automation, API, and
  frontend layers.

Next:

- Execute the implementation plan task by task with TDD and stop the bootstrap
  before its first write if the mapping/leakage acceptance gate fails.

Implementation plan:

- [2026-08-21-market-bias-v2-implementation.md](superpowers/plans/2026-08-21-market-bias-v2-implementation.md)

### 2026-08-14 - Matchup ranking form, day replacement, and Cosmos persistence

Status: `PARTIAL`. The V2 matchup presentation layer is verified against the
production V2 database. It does not change V6, backtest features, artifacts,
or frozen forward predictions.

Objective: rank today's matchups from each team's recent, scope-correct form
without stale fixture rows distorting the visible top 20.

Changes:

- Added a matchup-only `rolling_12_weighted_45d` form transform: 12 latest
  matches per existing home/away profile, with a 45-day recency half-life.
- Reranked against full current league profiles, not only the teams playing on
  the selected day, while leaving stored model/teamprofile values unchanged.
- Replaced same-day matchup snapshots safely after current rows are upserted;
  dashboard ranking is now contiguous among current fixtures.
- Fixed matchup CLI dry-runs to retain read access to `ullebets_v2` profiles.
- Replaced sequential Cosmos matchup writes with 100-row unordered batches and
  added the supporting league/profile index.
- Added the visible `Form 12` card marker and stabilised `npm run test` on the
  single forked worker configuration used by this machine.

Tests:

- `python -m pytest tests/v2 -q` -> `432 passed`.
- `cd frontend; npm run test` -> `14 files, 52 tests passed`.
- `cd frontend; npm run typecheck; npm run lint; npm run build` -> all passed.
- `python scripts/forward_v2/build_matchups_score.py --date 2026-08-17 --dry-run`
  -> 9 fixtures, 88 full-league profiles, 1,278 entries, all form window 12.
- Production rebuilds: `matchups_score` run
  `f739f98a6e7644c58f33987d02406d7b` and `matchups_league_avg` run
  `4cb7278827e8419d851cf1496b098243` both `succeeded`.
- Read API audit -> 40 cards: 20 OVER plus 20 UNDER, both ranked continuously
  1-20; each collection has 1,278 unique entry keys and no duplicate rows.

Insight:

The old global rank filter could hide valid current cards when deleted or
rescheduled fixtures had occupied earlier positions. The new build and read
contracts make current-day ranking self-contained. A sequential rewrite took
long enough to exceed the local operator timeout after 1,045 writes; the run
was explicitly marked failed and the batch rerun completed successfully.

Remaining:

- Real Racing Club - Villarreal is excluded because the V2 database has no
  verified Real Racing Club home profile. Do not fabricate this mapping.
- Output parity against the old repository and matchup outcome settlement over
  finished dates remain unproven.
- The current Vercel alias correctly reads the rebuilt 40-card ranking, but
  still runs the prior read adapter and therefore cannot display `Form 12`.
  Source commit `3786f64` is on `main`; the project is not Git-linked and the
  local Vercel CLI session lacks access to the hosting team, so this requires
  the existing Vercel deployment path rather than a code or database rerun.

Next:

- Repair the source/support mapping that produces the missing home profile,
  then rerun only the affected matchup acceptance audit.

### 2026-08-14 - Vercel production MongoDB configuration

Status: `VERIFIED` for the deployed read-only V2 API. This does not prove the
separate live odds, closing, CLV, or in-domain V6 forward lifecycle.

Objective: configure the existing Vercel production project with server-only
V2 database access and prove the deployed frontend API can read the production
database without accepting writes.

Changes:

- Added sensitive `Production`-only `MONGODB_URI` and `MONGODB_DB` variables
  to Vercel project `ullebets-prod-preview`; no value was committed, logged, or
  exposed to the browser.
- Corrected the URI value after the first deployment showed that outer quotes
  from the local dotenv file had been included in the Vercel secret.
- Redeployed the same source with the corrected environment as
  `dpl_9TDuhSF4VsPA12fAfpA3YEoFk6VF`.

Tests:

- `GET https://ullebets-prod-preview.vercel.app/api/v1/health`
  -> `200 {"status":"ok"}`.
- `GET https://ullebets-prod-preview.vercel.app/api/v1/dashboard?date=2026-08-14`
  -> `200`, with a valid empty fixture response for that date.
- `POST https://ullebets-prod-preview.vercel.app/api/v1/health`
  -> `405`, preserving the read-only boundary.
- Vercel runtime-errors query for the redeployment -> no runtime errors.

Insight:

Quoted dotenv values must be unquoted before being pasted into Vercel's secret
manager. A health route that reaches `read_api_database_unavailable` proves
that configuration is present but invalid; only the subsequent `200` proves
the deployed function can connect to `ullebets_v2`.

Remaining:

- Existing `vercel.app` SSO protection remains intentional until an access
  policy or custom-domain decision is made.
- Production operation, monitoring, and a full in-domain lifecycle remain
  separate readiness requirements.

Next:

- Verify only the next live checkpoint, closing, and in-domain forward windows
  when source data makes them due.

### 2026-08-13 - Vercel production adapter for the V2 read surface

Status: `PARTIAL`. The deployable source and its local gates are verified; the
public production deployment and its private MongoDB environment are the
remaining runtime gate.

Objective: host the existing Style-1 frontend without exposing MongoDB to the
browser and without replacing the existing V2 read contract.

Changes:

- Added `api/v1/[...path].py`, a Vercel Python adapter that delegates every
  read request to the existing `dispatch_get` contract and keeps one process
  scoped Mongo client.
- The adapter only accepts `GET` and `HEAD`, preserves ETags, gzip for large
  payloads, no-store error/health responses, and uses bounded edge-cache
  headers for safe read endpoints.
- Added `vercel.json` to build `frontend/`, retain `/api/v1/*` as functions,
  and route non-API SPA paths to `index.html`.
- Added a minimal Vercel runtime dependency manifest and documented the two
  required private production variables in `README.md`.

Tests:

- `python -m pytest tests/v2/test_vercel_read_api.py tests/v2/test_read_api_cache.py -q`
  -> `6 passed`.
- `cd frontend; npm run typecheck; npm run lint; npm run build` -> all passed.
- `Get-Content vercel.json -Raw | ConvertFrom-Json` -> valid JSON.
- Existing Vercel project `ullebets-prod-preview` was inspected before this
  change: it was `READY` but `/api/v1/health` returned `404`, proving it was a
  static-only deploy rather than a working product deployment.
- The first production deploy `dpl_Eoe8D4dR6bK1sFPmnL7ymCwMxaMS` was rejected
  before runtime with `unused_function`: Vercel requires a glob key under
  `functions`, not the literal dynamic route filename. The configuration now
  uses the valid `api/**/*.py` glob and must be deployed again.
- The second deploy `dpl_DVg36LZehjz2AW71HsB5f6U9REQ9` repeated the same
  build failure because the deployment upload omitted `[...path].py`: the
  PowerShell uploader treated its brackets as a wildcard. The next upload uses
  `-LiteralPath` and verifies that the function is present before deployment.
- The third deploy `dpl_4hDwUCGwXXkc8f6ibi7KSmW5fRE8` built and published the
  Python function and SPA successfully. The public SPA route returned `200`,
  but API calls returned Vercel's pre-handler `FUNCTION_INVOCATION_FAILED`.
  The adapter now defers V2 imports until request handling and searches both
  function and repository source roots; this makes the next runtime attempt
  diagnosable without exposing internal errors to clients.
- The fourth deploy `dpl_8xdsKDnPFvgrvzP3aAM6adghF2vN` proved the function
  loads and reaches its own request handler: `/api/v1/health` returned the
  V2-controlled `read_api_failure` response instead of a Vercel crash. This
  isolates the remaining failure to server configuration/database access.
  Missing `MONGODB_URI` now returns the explicit but non-sensitive `503`
  `read_api_unconfigured` response; a regression test covers that guard.
- The fifth deploy `dpl_GyLTo9WAPXvCUijm5e1L9fypZE7q` remained a V2-owned
  `read_api_failure` rather than `read_api_unconfigured`. That means the
  configured environment is not simply missing `MONGODB_URI`; the next
  adapter revision distinguishes an unsafe database target from a PyMongo
  connection failure and records only the exception class in server logs.
- The sixth deploy `dpl_D8NRsedoxnLdsZ75H2RVReW3sPxx` exposed a Python
  exception-handler scoping problem in that classification attempt and
  returned Vercel's pre-handler `FUNCTION_INVOCATION_FAILED`. The next
  revision removes that import-dependent exception branch; it classifies
  PyMongo failures from the caught exception module inside the already-proven
  generic safety handler.
- The seventh deploy `dpl_C8kJb5GsA4Tm6YUjtt9hmuDnFRJZ` uploaded the complete
  `src/ullebets_v2` package rather than a partial static dependency closure.
  Production now returns the controlled `503 {"error":"read_api_unconfigured"}`
  for `/api/v1/health`, proving that Vercel has no `MONGODB_URI`. The root SPA
  returned `200` and `POST /api/v1/health` returned `405` with
  `Allow: GET, HEAD`, so the hosting, routing, and write boundary are proven.
- Vercel project protection is `SSO all_except_custom_domains`. This is a
  deliberate access-control setting, not an application failure; the
  `vercel.app` URL therefore requires the owner's Vercel sign-in unless a
  custom domain is attached or the protection policy is changed.

New insight: static Vite hosting alone cannot work because local development
depends on the port `8787` proxy. The API must be deployed on the same public
origin; the new serverless adapter makes that boundary explicit and keeps
MongoDB credentials server-only.

Blocked: set the Vercel **Production** variables `MONGODB_URI` and
`MONGODB_DB=ullebets_v2` through an account-authorized Vercel environment
manager. This session's connected Vercel deploy tool does not expose an
environment-variable write operation, and the local Vercel CLI token is
invalid; no secret was copied to source code or the frontend.

Next justified test: after those variables are set and Vercel redeploys, call
the public health and dashboard routes and confirm current data. Decide
separately whether the existing SSO protection should remain until a custom
domain is attached.

Next justified test: deploy this exact source to `ullebets-prod-preview`, set
only the two server-side production variables, and run the public acceptance
requests.

### 2026-08-13 - Cloud/local reconciliation and read-surface contract repair

Status: `VERIFIED` for the reconciled local `style-1` branch. This does not
change independent production, live-closing, or in-domain forward-model
readiness gates.

Objective: reconcile the cloud `style-1` frontend/read-surface work with the
preserved local V2 forward-ledger and match-analytics changes without losing
either side's behavior.

Changes:

- Rebased the three preserved local commits on top of `origin/style-1`, whose
  base already contains the cloud merge into `origin/main`.
- Restored the complete read contract in the merged V2 API: cache-safe public
  dispatch, stable semantic ETags, bounded dashboard matchup reads, canonical
  Auto/Results exposure rows, and match-detail forward selections/results.
- Restored URL-driven Auto filters and server pagination, league/team/match
  navigation, and an accessible mobile dialog shell while keeping the match
  rail lazy-loaded.
- Made the new analytics view accept older V2 match-detail responses without
  profiles, and display persisted normalized market offers, settlement rows,
  and forward evidence when available.
- Corrected CLV presentation to use V2's stored percentage-point unit; for
  example, `5.5` is rendered as `+5.5 %`, not `+550 %`.
- Added a regression proving match detail returns canonical V6 selection,
  settlement, and CLV evidence from V2 collections.

Tests:

- `python -m compileall -q src; python -m pytest -q` -> `449 passed`.
- `npm test -- --run` -> `14` files / `52` tests passed.
- `npm run lint` -> passed with zero warnings.
- `npm run build` -> Vite production build passed.
- `git diff --check` -> passed.

New insight: the merge conflict was not merely visual. It exposed two
production-facing contract defects: an older API response could crash the
analytics page, and the generic fractional-percent formatter could inflate
stored V2 CLV percentage points by 100. Both are now regression-tested.

Unproven: hosted CI/deployment of this new commit, live T-30/T-10/closing
capture, closing-based CLV, and in-domain V6 forward settlement remain
separate runtime gates.

Next justified test: verify the hosted CI run after the reconciled branch is
pushed; merge to `main` only through the normal reviewed branch flow.

### 2026-08-13 - Style-1 frontend and read-only product surface

Status: `VERIFIED` for the implemented product surface on `style-1`; production deployment and the in-domain model lifecycle remain separate readiness gates.

Objective: build the complete styled Ullebets frontend against typed, read-only V2 contracts without changing model, prediction, odds-capture, settlement, database-write, or production workflow behavior.

Verified implementation sequence:

- Step 1 commit `ae75e1a`: stable read contracts, Stockholm-owned product date, entity navigation, league route, real 404, typed Auto/Results contracts, and watchlist resolution.
- Step 2 commit `ba775d7`: match, team, and league drilldowns with persisted odds, actuals, forward evidence, teamprofile contexts, league-relative deviations, rankings, and clickable history.
- Step 3 commit `4aae1ff`: shareable read-only filters, server pagination, persisted history rows, and stable pagination with previous data retained while the next page loads.
- Step 4 commit `202df85`: persisted model/policy runtime statuses and visible jobs/health/audits; observation counts are explicitly not treated as proof of forward ROI or CLV.
- Step 5 commit `37ba528`: keyboard skip link, date-only shared navigation state, mobile access to model/system tools, narrow-layout hardening, and route-shell regression coverage.

Final hosted verification on `style-1` commit `37ba528d00446e6b788d288e381609d962c29e45`:

- frontend Actions run `31648971262`: dependency audits found 0 vulnerabilities; hardcoded-preview guard passed; TypeScript passed; ESLint passed; 12 Vitest files / 45 tests passed; Vite production build passed;
- backend-isolation run `31648971290`: complete Python suite passed `434/434`;
- the frontend runtime does not contain the known preview match/card fixtures guarded by CI, and the UI does not infer proof from row counts;
- read-side additions are confined to `src/ullebets_v2/read_api/**` plus read-API tests. No model training/scoring policy, prediction write, odds acquisition, settlement, or database write path was changed by the frontend work.

Remaining truth boundary: model-specific in-domain forward ROI, model-specific in-domain CLV/beat-close evidence, live T-30/T-10/closing lifecycle proof, production deployment, and complete operational acceptance remain `UNPROVEN`, `BLOCKED`, `PARTIAL`, or `NOT STARTED` exactly as their independent evidence requires.

### 2026-08-12 - Production-database teamprofile and V6 rerun

Status: `PARTIAL`

Objective: run the two remaining V2 code paths against real current data,
then diagnose and repair any real failure before accepting them.

Production-database evidence in `ullebets_v2`:

- `build_teamprofiles` run `cd422e097d584acfa1996caf05088a66` succeeded with
  265 inserted dated profiles from 585 canonical results, 147,408 stat rows,
  1,107 incidents, and 1,105 shotmaps. Its parity, audit, and health reports
  were `matched`, `ok`, and `ok`.
- A read-only phase measurement showed `242.565 s` for canonical loading and
  `2.536 s` for profile building. The original write path then spent about 15
  minutes on 265 sequential upserts because it queried unindexed
  `profile_key`, while the collection's unique index is
  `team_key + profile_date + match_type`.
- Persistence now uses that indexed identity. The idempotent full rerun
  `62deff7b22704dc5a229ee6b39101100` succeeded with all 265 profiles and
  `0` duplicate writes; its write stage was `123.665 s`. The full local
  command including historical data loading took `407.641 s`.
- The first V6 rerun, `6b5e26b5a61c491494ef7eda8a6a5ec7`, correctly failed
  closed. The stored and rebuilt values differed only in
  `feature_values.market_anchor_lambda` by approximately `4e-16`, but its
  derived `feature_fingerprint_sha256` differed and bypassed the earlier
  tolerance rule.
- The corrected V6 rerun `33145640a5c54676b20bd6716ca74dbe` succeeded on 308
  valid prematch snapshots across five future fixtures. It reused all 105
  frozen score rows with `0` conflicts; 49 were precision-equivalent. It kept
  42 in-domain La Liga scores and excluded 63 Brazilian out-of-domain scores;
  it created zero forward bets.

Changes:

- `teamprofiles/persistence.py` now upserts through the canonical unique
  profile identity.
- `forward_scores.py` validates the feature fingerprint independently but
  compares actual feature values, not a derivative hash, for tolerant
  immutable reuse.

Tests:

- targeted teamprofile and score regression tests: `10 passed`;
- full V2 suite: `415 passed`;
- `python -m compileall -q src` and `git diff --check`: passed.

New insight: the two V2 database code paths are verified in write mode, but
the exact GitHub Actions runners still need one hosted run on the deployed
commit before the automation layer can be called fully verified.

### 2026-08-12 - Cosmos teamprofile and V6 score-idempotency repair

Status: `PARTIAL`

Changed `src/ullebets_v2/teamprofiles/service.py` and
`src/ullebets_v2/ev_model/forward_scores.py`, with regression coverage in
`tests/v2/test_teamprofiles.py` and `tests/v2/test_ev_forward_scores.py`.

Root-cause evidence from the production-read-only investigation:

- a single `match_stats_canonical` request for 579 historical `match_key`
  values timed out in Cosmos DB with `ExceededTimeLimit`;
- a stored V6 score and a rerun score had identical inputs, artifact, features,
  and policy, but differed by `5.55e-17` in probability and `1.11e-16` in EV,
  producing different exact JSON fingerprints.

The reader now sends the historical date constraint to Cosmos, projects only
needed fields, batches every dependent `match_key` query in groups of 50, and
uses an in-memory result index rather than repeatedly scanning every result.
Score persistence now reads the existing immutable row in full, validates the
derived feature fingerprint, and accepts only raw values that differ by
numeric machine precision within an absolute `1e-12` tolerance. It never
overwrites an existing score; material field changes and corrupted stored
fingerprints still fail closed.

Tests run:

- failing regression run before implementation:
  `python -m pytest -q tests/v2/test_teamprofiles.py tests/v2/test_ev_forward_scores.py`
  resulted in `3 failed, 7 passed`;
- same targeted command after implementation: `10 passed`;
- `python -m pytest -q`: `415 passed`;
- `python -m compileall -q src` and `git diff --check`: passed.

The code-level and database-read reproduction are verified. A full hosted
teamprofile build and the next scheduled V6 rerun are still required to prove
the repaired production executions.

### 2026-08-08 - Capture-triggered V6 scoring

Status: `PARTIAL`

Objective:
Remove redundant ten-minute EV recalculation and score V6 immediately after a
checkpoint actually saves new odds snapshots.

Changes:

- `v2-odds-scheduler.yml` now runs V6 only after a T-3D/T-2D/T-1D/T-2H
  checkpoint capture persists new snapshot rows.
- `run-unibet-closing.yml` now runs the same V6 command only after a T-30/T-10
  closing capture persists new snapshot rows.
- Both capture services surface the actual `market_snapshot_upserts` count in
  their CLI summary. The workflows use that persisted count, not the planned
  snapshot list, and skip the full model dependency install and V6 scorer for
  duplicates, empty windows, and manual dry-runs.
- Removed the independent ten-minute schedule from `ev-shadow-forward.yml`;
  it remains available for manual recovery only.
- Added workflow-contract regressions for the new capture-to-score chain and
  for the manual-only scorer workflow.

Tests:

```text
RED: python -m pytest tests/v2/test_automation_contract.py -q
     2 expected failures before workflow implementation
GREEN: python -m pytest tests/v2/test_automation_contract.py -q
       20 passed
python -m pytest tests/v2/test_checkpoint_capture.py tests/v2/test_closing_capture.py tests/v2/test_ev_forward_scores.py tests/v2/test_ev_forward_predictions.py tests/v2/test_automation_contract.py -q
55 passed
python -m pytest -q
413 passed
python -c "import yaml; ..."
yaml-ok
git diff --check
passed
Hosted workflow_dispatch: v2-odds-scheduler.yml, dry_run=true
run 31274563877 passed on main@4c19ea7
```

Results:

- No new V6 score job starts on an empty, duplicate, or dry-run capture.
- A successfully persisted odds snapshot starts the frozen V6 scorer in the
  same GitHub Actions job, before that job completes.
- Hosted scheduler smoke run `31274563877` passed on `main@4c19ea7`: it
  inspected nine due targets, built `744` dry-run snapshots with zero source
  errors, parsed the new persisted-upsert field safely, and correctly skipped
  V6 because a dry-run never persists snapshots.
- V6 score and forward-bet immutability remain unchanged: later snapshots add
  immutable score evidence and never rewrite an existing forward prediction.

Insight:
The scheduler frequency is now only used to discover due capture windows. It
does not imply repeated EV model execution while no new snapshot is persisted.

Remaining:

- A hosted write-mode T-3D/T-2D/T-1D/T-2H or T-30/T-10 capture must prove that
  the inline V6 scorer completes against persisted new snapshots before
  kickoff.

Next:

- Dispatch dry-run workflow smoke tests after deployment, then inspect the
  first due production checkpoint for persisted scorer evidence.

### 2026-08-08 - EV scorer and snapshot-cadence audit

Status: `PARTIAL`

Objective:
Verify whether V6 calculates and persists a score immediately after each
T-3D/T-2D/T-1D/T-2H/T-30/T-10 odds capture.

Changes:

- Updated operational documentation only; no code, workflow, or database
  write was made by this audit.

Tests:

```text
Read .github/workflows/v2-odds-scheduler.yml
Read .github/workflows/ev-shadow-forward.yml
Read scripts/forward_v2/score_ev_shadow_model.py
Read latest score_ev_shadow_model job_runs and ev_model_scores from ullebets_v2
Read current hosted EV Shadow Forward runs
```

Results:

- Capture jobs persist `market_snapshots`; they do not invoke V6 scoring.
- The V6 workflow is separately scheduled at minutes `5,15,25,35,45,55` and
  each run reads every timing-valid future snapshot available at run time.
- Latest production scorer job `c5858755ed6b403b9126446f70fa4796` succeeded at
  `2026-08-08T19:06Z`: `2,347` input snapshots, `135` canonical markets,
  `216` V6 side scores, and `24` newly persisted immutable scores.
- All current Brazilian scores were excluded from forward selection because
  Brasileirão Série A is outside V6's trained league domain.
- GitHub scheduled scorer starts were observed at `17:52Z`, `18:22Z`, and
  `19:06Z`, so the configured ten-minute cadence is not an exact runtime
  guarantee.

Insight:
Every new snapshot can be scored on the next scorer pass and score keys retain
the source snapshot key, but the system does not yet guarantee a score before
kickoff after a late T-30/T-10 capture. Forward bets are immutable: a later
snapshot produces a new score, not a mutation of an existing selection.

Remaining:

- Define and implement the production rule for fresh pre-kickoff EV: either
  score synchronously after each capture or explicitly freeze V6 selection at
  a declared earlier checkpoint.

Next:

- Decide and implement a capture-to-score contract before treating T-30/T-10
  as prediction-refresh checkpoints.

### 2026-08-08 - Closing runner import repair deployed

Status: `PARTIAL`

Objective:
Repair the production runner failure that prevented T-30/T-10 capture before
the closing command could start.

Changes:

- Added `PYTHONPATH=${{ github.workspace }}/src` to the reusable V2 Python
  runner used by lean workflows.
- Added a regression test that executes the same internal package import from
  a stripped Python process with only the V2 source path available.

Tests:

```text
python -m pytest tests/v2/test_automation_contract.py tests/v2/test_workflow_runner.py -q
python -m pytest -q
Hosted workflow_dispatch: run-unibet-closing.yml, dry_run=true
Hosted run: 31273361050
```

Results:

- Regression test first failed because the reusable workflow did not expose
  the source package.
- Targeted tests passed `21/21`; full suite passed `409/409`.
- Commit `030a401` was pushed to `main`.
- Hosted dry-run `31273361050` ran on that commit, imported
  `ullebets_v2.automation`, reached `capture_closing_snapshots.py`, and
  completed successfully with zero errors.
- It correctly reported zero due targets because the next fixture was
  Remo - Atlético Mineiro at `2026-08-08T21:30:00Z`, outside T-30/T-10.
- Dry-run made no database writes, so it is runner proof only, not closing or
  CLV evidence.

Insight:
The ordinary checkpoint scheduler works because it runs its capture script
directly. The closing workflow uses the reusable runner, so its lean profile
needed an explicit V2 source import path before command rendering.

Remaining:

- A successful scheduled production T-30/T-10 capture, closing-line
  materialization, and CLV refresh.

Next:

- Inspect the next live T-30/T-10 window after the deployed fix; do not mark
  closing or CLV complete from the manual dry-run.

### 2026-08-08 - Live checkpoint pass and closing-runner failure

Status: `PARTIAL`

Objective:
Verify the currently due Brazil odds checkpoints and determine whether the
closing chain works during a real T-30/T-10 window.

Changes:

- Updated verification documentation only; no code, workflow, or database
  write was made by this audit.

Tests:

```text
Read-only MongoDB audit of current-cycle fixtures, raw_odds_kambi,
market_snapshots, closing_lines, clv_tracking, and job_runs
gh run list --repo ulle73/ullebets-prod --workflow run-unibet-closing.yml ...
gh run view 31271905639 --repo ulle73/ullebets-prod --log-failed
```

Results:

- Valid current-cycle snapshots: T-3D `678` over 10 matches, T-2D `799` over
  10 matches, T-1D `817` over 10 matches, and T-2H `242` over three matches.
- The latest T-2H job succeeded at `2026-08-08T17:50Z`, wrote two raw Kambi
  payloads and `85` snapshots, with zero errors.
- The latest raw odds payload was stored at `2026-08-08T17:49:58Z`.
- All current-cycle snapshot rows are valid prematch rows; duplicate valid
  snapshot-key groups are `0`.
- `closing_lines = 0`; CLV remains `860` missing closing line and `3` invalid
  snapshot timing rows.
- Closing workflow run `31271905639` failed at `2026-08-08T18:26Z` with
  `ModuleNotFoundError: No module named 'ullebets_v2'`, before it could fetch
  or persist any closing odds.
- The workflow is active, but no succeeding 5-minute closing run was recorded
  through `2026-08-08T18:53:50Z`.

Insight:
The normal checkpoint pipeline is operational in production. The separate
closing workflow is blocked by a reusable-runner dependency setup defect, not
by Kambi data, timing validation, or database persistence.

Remaining:

- Repair and deploy the lean shared runner, then capture a real T-30/T-10,
  materialize closing lines, and refresh CLV.
- Observe in-domain V6 selections and untouched settlement.

Next:

- Change the reusable lean runner so `ullebets_v2` is importable without
  installing the full ML dependency profile, then run targeted workflow tests
  and verify the next real closing window.

### 2026-08-04 - Current production checkpoint audit

Status: `PARTIAL`

Objective:
Verify the latest scheduled odds state and identify exactly which production
checkpoints are proven before the 8-9 August Brazil window.

Changes:

- Updated the work log, readiness checklist, and backend verification status.
- No production code, database data, or workflow configuration changed.

Tests:

```text
Read-only MongoDB audit of fixtures_canonical, market_snapshots,
raw_odds_kambi, closing_lines, clv_tracking, and job_runs
python scripts/forward_v2/ingest_unibet_odds.py --mode fixture-db --max-days-ahead 7 --dry-run
gh run list --workflow v2-odds-scheduler.yml --limit 3 --json ...
gh run list --workflow ev-shadow-forward.yml --limit 3 --json ...
```

Results:

- 10 future canonical Brazil fixtures exist; the next is Grêmio - São Paulo
  at `2026-08-08T19:00:00Z`.
- Valid persisted snapshots: T-2D `161` rows over two matches and T-1D `244`
  rows over three matches.
- No valid T-3D, T-2H, T-30, or T-10 row exists. All `248` stored T-10 rows
  are old invalid timing rows and remain excluded.
- Latest raw odds write remains `2026-07-30T00:28:39.392Z`; this is expected
  because no current fixture was due at the latest scheduler run.
- Scheduled run `30949327663` succeeded with 10 target matches, zero due
  matches, zero fetch errors, and audit/health status `ok`.
- Current Kambi dry-run linked `10/10` matches, produced `11` raw documents
  and `607` normalized offers, and returned zero errors.
- `closing_lines` remains empty, so official closing CLV is still unavailable.

Insight:
The source, fixture linkage, and scheduler empty-window behavior are currently
healthy. T-3D is not failed: the first new fixture was still about 93.5 hours
from kickoff, outside the 60-84 hour T-3D policy window.

Remaining:

- Real persisted T-3D, T-2H, T-30, T-10, closing-line, and CLV evidence.
- In-domain V6 predictions and untouched settlements.

Next:

- Inspect the first scheduler run after `2026-08-05T07:00:00Z`; it should
  persist T-3D data for Grêmio - São Paulo when GitHub Actions executes within
  the broad 24-hour checkpoint window.

### 2026-08-01 - V6 registered forward-policy activation

Status: `PARTIAL`

Objective:
Make frozen V6 scores, rather than the legacy JS EV formula or V3, the only
source for new model-specific forward selections.

Changes:

- `ev-shadow-forward.yml` now runs only the frozen V6 artifact.
- Added immutable `forward_policy_registry_v1`, preserving V5 unchanged while
  registering the exact V6 corners + away/total policy for forward testing.
- Added a policy materialization boundary from immutable `ev_model_scores` to
  immutable `forward_bets`, with policy fingerprint, source score key, timing,
  artifact, odds, probability, EV, and feature-fingerprint provenance.
- Added policy/match dedupe and an index supporting that lookup.
- Removed the production schedule from legacy `run-unibet-backtests.yml`; it
  remains manually available as `V2 Legacy EV Parity Replay`.

Tests:

```text
python -m pytest tests/v2/test_ev_forward_predictions.py tests/v2/test_ev_score_evaluation.py tests/v2/test_automation_contract.py -q
python -m pytest tests/v2/test_ev_policy_registry.py tests/v2/test_ev_forward_predictions.py tests/v2/test_ev_score_evaluation.py tests/v2/test_automation_contract.py -q
python -m pytest -q
python scripts/forward_v2/healthcheck_v2.py
python -m compileall -q src/ullebets_v2 scripts/forward_v2
python scripts/forward_v2/bootstrap_indexes.py
python scripts/forward_v2/score_ev_shadow_model.py --repo-root . --artifact models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/ev_scope_interaction_recency45_asof_capped_v6_shadow.joblib --manifest models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/model_manifest.json --score-only --selection-policy-registry models/ev/forward_policy_registry_v1.json --selection-policy-id v6_corners_away_total_forward_v1 --dry-run
python scripts/forward_v2/score_ev_shadow_model.py --repo-root . --artifact models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/ev_scope_interaction_recency45_asof_capped_v6_shadow.joblib --manifest models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/model_manifest.json --score-only --selection-policy-registry models/ev/forward_policy_registry_v1.json --selection-policy-id v6_corners_away_total_forward_v1 --now 2026-07-30T00:30:00Z --dry-run
gh workflow run ev-shadow-forward.yml --ref main
gh run watch 30717651924 --exit-status
```

Results:

- Full suite: `408 passed`.
- Healthcheck: `overall_status=ok`, zero missing/invalid workflow contracts.
- Current real-time dry-run: zero future persisted `market_snapshots`, a valid
  empty result with the new V6 policy loaded.
- Historical prematch dry-run: `319` input snapshots, `30` canonical markets,
  `48` V6 side scores, zero future-stat observations used.
- All `48` scores were excluded because Brasileirão Série A is outside V6's
  six-league training domain; registered forward selections remained `0`.
- Both scorer runs were dry-runs and made no database writes.
- Index bootstrap applied `selection_policy_match` to `forward_bets`; all 36
  collection plans completed with `0` repaired and `0` deleted documents.
- Commit `f607338` was pushed to `main`. Hosted write-mode run `30717651924`
  succeeded and loaded only V6 with `forward_policy_registry_v1` and policy
  `v6_corners_away_total_forward_v1`; `dry_run=false`.
- The hosted run had `0` future input snapshots and therefore persisted `0`
  scores/selections. This was a valid empty run, not a scorer failure.

Insight:
V6 is now the configured production forward model, but it still fails closed
outside its fitted domain. This is an orchestration activation, not new proof
that the historical `+28.65%` survives forward testing.

Remaining:

- Observe a real prematch score and immutable selection from a V6-supported
  league, then settle it and measure model-specific ROI/CLV.

Next:

- After deployment, inspect the first hosted V6 run with an in-domain fixture;
  do not use Brazil to bypass the domain contract.

### 2026-08-01 - Current legacy-EV backtest path verification

Status: `PARTIAL`

Objective:
Verify whether the V2 replacement for the original `run-unibet-backtests`
path currently performs live Kambi discovery, normalizes every available
line, and calculates the legacy EV outputs.

Changes:

- No code, database, model, or policy changes.
- Exercised the current fixture-database path against live Kambi data in
  read-only dry-run mode.

Tests:

```text
python scripts/forward_v2/build_model_snapshots.py --mode fixture-db --snapshot-mode backtest --source-workflow current-backtest-verification-2026-08-01 --max-days-ahead 7 --dry-run
```

Results:

- The exact seven-day window contained one match, Grêmio - São Paulo.
- Event linkage succeeded `1/1`; two raw payload documents and `59` normalized
  market offers were produced in memory.
- The V2-owned legacy JS EV runtime generated `108` directed line rows with
  EV details, zero source errors, and zero model errors.
- Parity, audit, and health status were all `matched`/`ok`.
- Dry-run made no database writes. Three additional future fixtures were just
  outside the exact seven-day cutoff.

Insight:
The original-style `odds -> line sides -> legacy EV` mechanism works on a
current live market. It is not the V6 model and does not prove that the legacy
EV formulas are profitable. The existing 370 historical replay rows also
lack primary EV values and settlement, so they are not a completed historical
backtest acceptance sample.

Remaining:

- Persist a non-empty scheduled `run-unibet-backtests.yml` execution and
  settle its rows from canonical outcomes.
- Keep legacy-EV output separate from V6 forward evidence and promotion.

Next:

- Inspect the next scheduled non-empty backtest run; do not rerun the live
  dry-run unless source behavior, mappings, or model runtime changes.

### 2026-08-01 - Resilient T-2H/T-30/T-10 closing policy

Status: `PARTIAL`

Objective:
Reduce missed closing coverage under delayed GitHub Actions schedules without
misreporting an earlier price as the true closing line.

Changes:

- Added `T_MINUS_30M` with a broad 15-50 minute capture window.
- Promoted T-2H collection into the hourly production checkpoint job while
  retaining its historical research classification for model evidence.
- Reserved T-30 and T-10 exclusively for the five-minute closing workflow.
- Materialized T-30 as `t30_fallback`; a later T-10 upgrades the same closing
  row to official `t10` quality.
- Prevented T-2H/T-1D or older rows from becoming closing lines when both
  near-close checkpoints are missing.
- Propagated closing quality through CLV and forward results. T-30 CLV uses
  `tracked_fallback_t30` and is excluded from official model promotion CLV.

Tests:

```text
python -m pytest tests/v2/test_checkpoint_capture.py tests/v2/test_closing_capture.py tests/v2/test_clv_tracking.py tests/v2/test_forward_results.py tests/v2/test_ev_forward_evaluation.py tests/v2/test_ev_score_evaluation.py tests/v2/test_ev_snapshot_integrity.py tests/v2/test_automation_contract.py -q
python -m pytest -q
python scripts/forward_v2/capture_closing_snapshots.py --mode fixture-db --source-workflow near-close-production-preflight --max-days-ahead 7 --dry-run
```

Results:

- Targeted checkpoint/closing/CLV/promotion tests passed `61/61`.
- Full regression suite passed `402/402`.
- Current real-time read-only preflight completed with audit and health `ok`.
  It found zero fixtures in the next seven days, so no live capture was due.
- Hosted production write-mode run `30674861895` succeeded on commit `f6a6ea0`.
  It found zero fixtures in the source horizon, persisted parity/audit/health
  reports with zero errors, and kept the closing watcher safely disabled.
- Synthetic timing contracts prove T-30 fallback creation, T-10 upgrade,
  duplicate prevention, and exclusion of fallback CLV from promotion metrics.

Insight:
A T-30 fallback improves Actions tolerance, but it is not market close. The
quality label must remain part of every closing, CLV, and promotion report.

Remaining:

- Persist a real T-2H/T-30/T-10 lifecycle on the next fixture with Kambi
  markets. Code and dry-run evidence do not replace that live proof.

Next:

- Inspect the first scheduler activation with a real future fixture and verify
  that T-30 persists even if T-10 is delayed, then verify that a later T-10
  upgrades the closing and official CLV.

### 2026-08-01 - Production odds scheduler idempotency repair

Status: `PARTIAL`

Objective:
Ensure the deployed match-aware scheduler cannot abort regular checkpoint
capture merely because the T-10 workflow is already in the requested state.

Changes:

- Made closing-workflow enable/disable transitions idempotent by reading the
  current GitHub workflow state before applying a change.
- Added an automation contract regression for the no-op state path.
- Deployed the repair on `main@cdb83b9`.

Tests:

```text
python -m pytest tests/v2/test_automation_contract.py tests/v2/test_closing_watch.py tests/v2/test_checkpoint_capture.py tests/v2/test_closing_capture.py tests/v2/test_closing_downstream.py tests/v2/test_clv_tracking.py -q
python -m pytest -q
gh workflow run v2-odds-scheduler.yml --ref main -f lookahead_hours=2 -f days_ahead=7 -f dry_run=false
gh run watch 30673575119 --exit-status
```

Results:

- The previous scheduled run `30672553536` failed with GitHub HTTP `403`
  because it tried to disable an already disabled workflow.
- Targeted closing/checkpoint tests passed `44/44`; the full suite passed
  `394/394`.
- Hosted production write-mode run `30673575119` completed all steps.
- The current workflow state was `disabled_manually`; the new path treated it
  as a successful no-op and continued to checkpoint capture.
- With no fixture inside the current watch window, the persisted checkpoint
  job `0e4b84a64e4f44eb82412b5ba0753ed8` correctly finished `succeeded` with
  `0` due matches, `0` errors, and audit/health status `ok`.

Insight:
GitHub workflow enable/disable commands are not idempotent. State inspection
must precede mutation or an expected disabled state can suppress unrelated
checkpoint collection.

Remaining:

- The next real fixture window must still prove automatic enablement, valid
  T-10 capture, closing-line materialization, and CLV refresh.

Next:

- Inspect the first scheduler run with a fixture inside two hours, then verify
  persisted T-10, closing, and CLV evidence without simulating time.

### 2026-08-01 - Scheduled forward-scoring runtime audit

Status: `VERIFIED`

Objective:
Answer whether the current model, match-data, statistics, and odds lifecycle is
fully operational using the latest persisted and hosted-run evidence.

Changes:

- Pinned the frozen model runtime dependencies in `pyproject.toml`.
- Changed enrichment persistence to use 200-operation bulk batches.
- Updated the local ignored `.env.local` target from `app` to `ullebets_v2`.
- Fetched and stored the latest completed match dates for all seven followed
  leagues.

Tests:

```text
gh run list --limit 20 --json databaseId,name,workflowName,status,conclusion,event,createdAt,updatedAt,headSha,url
gh run view 30668128118 --log-failed
gh run watch 30672830616 --exit-status
python -m pytest -q
python scripts/forward_v2/ingest_fixtures_window.py --mode live --start-date 2026-05-16 --end-date 2026-05-24 --source-workflow production-latest-completed-2026-08-01
python scripts/forward_v2/ingest_fixtures_window.py --mode live --date 2026-07-31 --source-workflow production-latest-completed-2026-08-01
python scripts/forward_v2/backfill_match_enrichment.py --source-mode db --start-date 2026-05-18 --end-date 2026-05-24 --source-workflow production-latest-completed-rebuild-2026-08-01
```

Results:

- Latest scheduled `V2 EV Shadow Forward` run `30668128118` failed on
  `main@69e6455`.
- All four frozen scorer invocations reject the hosted runtime: manifests
  expect `numpy 2.2.2` and `pandas 2.2.3`; the unpinned install produced
  `numpy 2.5.1` and `pandas 3.0.5`.
- The shared workflow runner was inspected and its existing contract tests
  prove scheduled jobs strip command-template `--dry-run`; the earlier claim
  that production scoring was forced to dry-run was incorrect.
- Exact runtime pins now match all frozen manifests: `numpy 2.2.2`,
  `pandas 2.2.3`, `joblib 1.5.0`, and `scikit-learn 1.7.1`.
- Production fixture ingest stored 181 canonical fixtures for 16-24 May and 6
  for 31 July, with zero unmatched fixture identities.
- The first 39-match enrichment fetched every required source successfully but
  exposed one CosmosDB timeout on a single 10,085-operation canonical bulk.
- Raw statistics, incidents, shotmaps, results, and canonical results were
  preserved for all 39 affected matches. Batched canonical rebuilding then
  completed successfully from raw without refetching sources.
- Across the latest completed date per league: 41/41 matches have all four raw
  enrichment payload families, scored canonical results, and exactly 27
  corners/shots/shots-on-goal period/scope rows. There are 1,107 primary rows,
  zero duplicate primary keys, and zero missing actual values.
- Full regression suite: `394 passed`.
- Hosted run `30672830616` completed successfully in write mode on
  `main@f188c52`; V3, V4, V5, and V6 each returned `status=ok`.
- All four scorers returned zero canonical markets because no current upcoming
  model-ready markets existed. This is a valid empty production result, not a
  dry-run or source failure.

Insight:
The frozen model correctly fails closed on runtime drift. Production workflow
write mode was already correct; reproducible dependency pinning was the actual
scorer defect. Large historical enrichment batches also require bounded bulk
writes on CosmosDB even though normal daily windows are smaller.

Remaining:

- Prove one hosted scoring write before kickoff on an in-domain fixture.

Next:

- Wait for an in-domain prematch fixture, then verify the first persisted score
  and eventual untouched settlement without changing the frozen policy.

### 2026-07-31 - Match-aware GitHub Actions odds scheduling

Status: `VERIFIED`

Objective:
Retain GitHub Actions while avoiding permanent five- and ten-minute polling.

Changes:

- One hourly workflow now captures production T-3D/T-2D/T-1D checkpoints.
- The same workflow enables `run-unibet-closing.yml` only when an uncaptured
  fixture exists within two hours and disables it otherwise.
- The T-10 watcher keeps five-minute precision only during that active match
  window and still captures at most one valid T-10 snapshot per match.
- T-12H/T-2H remain available for manual research but are excluded from the
  production schedule.
- Scheduler and closing jobs use a lean `pymongo` runtime instead of installing
  the full ML dependency set on every check.

Tests:

```text
python -m pytest -q
python scripts/forward_v2/plan_closing_watch.py --lookahead-hours 2
```

Results:

- `392 passed`.
- A clean virtual environment containing only `pymongo` imported the planner,
  checkpoint, and closing CLIs successfully.
- The real read-only planner check against `ullebets_v2` returned
  `action=disable`, with zero fixtures in the next two hours.
- GitHub dry-run
  [30667410766](https://github.com/ulle73/ullebets-prod/actions/runs/30667410766)
  completed in 14 seconds with zero due targets and no workflow-state change.
- GitHub write/state run
  [30667457674](https://github.com/ulle73/ullebets-prod/actions/runs/30667457674)
  completed in 14 seconds and disabled the T-10 workflow because no fixture
  was due within two hours.
- Official runner dependencies were updated to `actions/checkout@v7`,
  `actions/setup-python@v7`, and `actions/setup-node@v7` after the first hosted
  run exposed the Node 20 deprecation warning.
- Final v7 hosted dry-run
  [30667644513](https://github.com/ulle73/ullebets-prod/actions/runs/30667644513)
  completed in 17 seconds with zero annotations. At verification time the
  match-aware scheduler was active, the T-10 workflow was disabled, and the
  manual checkpoint workflow had no cron schedule.

Insight:
GitHub Actions cannot create dynamic future cron events per fixture. Toggling a
short-interval workflow from an hourly fixture-aware planner is the closest
reliable Actions-native equivalent without wasting 288 full runs every day.

Remaining:

- The enable/capture/disable lifecycle still needs persisted proof from the
  next real fixture window.

Next:

- Inspect the next hourly planner activation and subsequent valid T-10 capture.

### 2026-07-31 - T-10 scheduler ownership and release verification

Status: `VERIFIED`

Objective:
Make the deployed scheduler, rather than a manual monitor, own repeated odds
capture and closing/CLV updates.

Changes:

- The regular checkpoint workflow captures all configured horizons except
  `T_MINUS_10M`.
- The five-minute closing workflow exclusively owns `T_MINUS_10M` to prevent
  a checkpoint race from suppressing closing-line materialization.
- A successful closing-line materialization now refreshes CLV tracking and
  forward results in the same workflow.
- Pytest uses importlib mode so the complete V1 and V2 suites can be collected
  together despite duplicate test basenames.

Tests:

```text
python -m pytest -q
```

Results:

- `386 passed`.
- Targeted checkpoint, closing downstream, and workflow contract tests:
  `23 passed`.
- `git diff --check` found no whitespace errors.
- Feature commits `7557729` and `6009db9` were merged without conflicts in a
  clean worktree based on `origin/main`; the merged checkout also passed
  `386/386` tests.
- `main` was pushed at `5aae938`; GitHub registered all 24 V2 workflows as
  active.
- Repository secrets `MONGODB_URI`, `RAPIDAPI_KEYS`, and the compatibility
  `RAPIDAPI_KEY` were configured from the ignored local environment without
  committing or printing their values.
- GitHub Actions run
  [30647673244](https://github.com/ulle73/ullebets-prod/actions/runs/30647673244)
  completed successfully on `main` in 1m45s,
  proving repository checkout, dependency installation, Mongo connectivity,
  fixture-database inspection, and the V2 healthcheck command in the hosted
  runner environment.

Insight:
The backend code already contained the capture mechanisms, but an undeployed
workflow and overlapping T-10 ownership made the live behavior unreliable.
The closing job is now the single T-10 owner and its derived outputs are part
of the same automated path.

Remaining:

- A future live fixture is still required to prove a persisted production
  T-10 snapshot, closing line, and CLV row end to end.

Next:

- Inspect the next scheduled real T-10 job run and its persisted snapshots,
  closing lines, CLV tracking, and forward results rather than running another
  manual polling loop.

### 2026-07-31 - Brazil post-match completion and missed T-10 audit

Status: `PARTIAL`

Objective:
Verify the final post-match chain and determine whether any real T-10,
closing-line, or CLV evidence was persisted.

Changes:

- Refreshed live match enrichment for source date `2026-07-30`.
- Refreshed forward settlement, CLV tracking, and forward results.
- Stopped the obsolete heartbeat after the final T-10 window was missed.

Tests:

```text
python scripts/forward_v2/ingest_match_enrichment.py --mode live --fixture-source db --date 2026-07-30 --source-workflow postmatch-final-live
python scripts/forward_v2/settle_forward_bets.py --source-workflow postmatch-final-live
python scripts/forward_v2/refresh_clv_tracking.py --mode paths-or-db
python scripts/forward_v2/refresh_forward_results.py
```

Results:

- Final match `Coritiba 0-1 Cruzeiro` has raw statistics, incidents, shotmap,
  result, canonical result, 252 canonical stat rows, and 27 primary-stat rows.
- Its 9 forward rows settled: 4 wins and 5 losses.
- Across all 67 current forward rows: 64 settled, 3 timing-excluded, 26 wins,
  and 38 losses.
- The five timing-valid EV shadow rows settled at 2 wins, 3 losses, and
  `-1.17` units (`-23.40%` descriptive ROI). They are Brazilian
  out-of-domain diagnostics, not valid V6 forward evidence.
- There are 0 valid T-10 snapshots, 0 closing lines, 0 tracked CLV rows, and 0
  duplicate snapshot-key groups.
- CLV remains 64 `missing_closing_line` and 3 `invalid_snapshot_timing`.

Insight:
The post-match backend works, but the closing acceptance failed operationally,
not mathematically. A local uncommitted workflow schedule and a delayed
thread heartbeat are not a production scheduler.

Remaining:

- Deploy a real scheduler.
- Capture a future T-10 window.
- Materialize closing odds and calculate CLV.

Next:
Select the next fixture with active Kambi markets only after the closing job is
running in the actual execution environment.

### 2026-07-30 - Real T-10, closing, and CLV preflight

Status: `PARTIAL`

Objective:
Prepare and monitor the first non-simulated T-10 capture through closing-line
materialization and CLV refresh.

Changes:

- Closing and CLV dry-runs now read the real V2 database while remaining
  write-free.
- Manual closing workflow labels no longer crash parity reporting.
- Heartbeat `ullebets-v2-postmatch-pass-30-juli` now covers the actual T-10
  windows and post-match follow-ups on 30-31 July.

Tests:

```text
python -m pytest tests/v2/test_checkpoint_capture.py tests/v2/test_closing_capture.py tests/v2/test_clv_tracking.py tests/v2/test_config_and_safety.py -q
python scripts/forward_v2/capture_closing_snapshots.py --mode fixture-db --source-workflow manual-t10-preflight --date 2026-07-30 --date 2026-07-31 --dry-run
python scripts/forward_v2/refresh_clv_tracking.py --mode paths-or-db --dry-run
```

Results:

- `27/27` targeted tests pass.
- Six future Brazil fixtures are present.
- Four kick off at `2026-07-30T18:00:00Z`, one at `22:30:00Z`, and one at
  `2026-07-31T00:30:00Z`.
- Current target history contains `319` valid T-2D/T-1D market snapshots.
- Current targets contain `31` forward bets, `0` closing lines, and `31`
  persisted CLV rows waiting on a closing line.
- Full CLV dry-run reads `67` tracked bets: `64` missing closing lines and `3`
  excluded for invalid snapshot timing.
- Preflight correctly selects `0` due matches before the first T-10 window.
- A later real-time check at `2026-07-30T23:39Z` found that five of the six
  fixture windows had passed with `0` valid T-10 snapshots and `0` closing
  lines. The final fixture starts at `2026-07-31T00:30Z`.

Insight:
The current zero closing/CLV coverage is not a database failure, but the first
five live windows were missed by the scheduled heartbeat. The final current
acceptance window opens at approximately `2026-07-31T00:15Z`.

Remaining:

- Capture a real due target without `--now` or `--dry-run`.
- Prove raw Kambi, valid T-10 snapshots, closing lines, and refreshed CLV in
  `ullebets_v2`.

Next:
The heartbeat now polls every five minutes through the final live T-10 window.
Run the real write path there and update this log only from persisted evidence.

### 2026-07-30 - End-to-end app readiness checklist

Status: `VERIFIED`

Objective:
Create one saved checkbox view showing what already works and every remaining
requirement before the complete app can be considered production-ready.

Changes:

- Added `docs/app-readiness-checklist.md`.
- Added the checklist to the mandatory `AGENTS.md` reading order.
- Linked the checklist from README and this work log.
- Applied a strict rule: only fully evidenced behavior receives `[x]`.

Results:

- Backend foundation, tested live ingest, canonical enrichment, odds ingest,
  analysis, settlement mechanics, audits, and model artifacts are checked.
- Live T-10, closing/CLV, in-domain V6 evidence, full output parity, standalone
  V2 runtime, frontend, deployment, alerting, and operational acceptance remain
  unchecked with short reasons.

Insight:
The backend is substantially implemented, but the complete app is not ready.
The remaining work is now visible without reading the full technical reports.

Next:
Update the same checklist whenever new runtime evidence changes a readiness
statement.

### 2026-07-30 - Persistent work log and agent protocol

Status: `VERIFIED`

Objective:
Create one durable first-read log so future work does not repeat expensive
tests or lose negative findings.

Changes:

- Added root `AGENTS.md`.
- Added this `docs/work-log.md`.
- Added the mandatory reading order and log link to `README.md`.
- Standardized evidence vocabulary and required log-entry fields.

Verification:

- Confirmed `AGENTS.md` and `docs/work-log.md` exist.
- Confirmed README links resolve locally.
- Confirmed the work log points to both detailed status documents.

Insight:
The project already had detailed reports, but no single mandatory entry point
that told a new agent what not to rerun.

Next:
Every later code, data, configuration, or runtime-verification session must
append or update an entry before completion.

### 2026-07-30 - Experiment 077 exact-as-of HGB

Status: `REJECTED`

Objective:
Test whether a genuinely nonlinear model family beats V6 after applying the
final leakage-safe snapshot-as-of contract.

Test:

```powershell
python scripts/offline_v2/run_ev_exact_asof_hgb_challenger.py `
  --bootstrap-iterations 100000
```

Results:

- Exact V6/HGB prediction universe: 8,822/8,822.
- Timing, forbidden-feature, duplicate-key, and universe violations: 0.
- HGB corner away/total: 424 bets, -8.42%, 2/6 positive windows.
- Residual HGB: 275 bets, -12.20%, 1/6 positive windows.
- Both paired intervals versus V6 were entirely negative.
- Full V2 regression suite: 355 passed.

Insight:
Nonlinear boosting is materially worse than regularized logistic V6 on the
corrected feature contract. More model complexity is not the missing edge.

Artifacts:
`data/v2/ev_model/experiment_077_exact_asof_hgb/`.

### 2026-07-30 - Experiments 075-076 combined microstructure

Status: `REJECTED`

Objective:
Combine snapshot movement and simultaneous alternate-line ladder information
without using future snapshots or current-window outcomes.

Results:

- Rebuilt movement and ladder matrices matched cached 14,033-row artifacts.
- All model prediction universes matched at 8,822 rows.
- 90% V6 / 5% movement / 5% ladder: 146 bets, +31.97%.
- Paired improvement versus V6: +3.31 ROI points, 95% interval -1.63 to +9.01.
- Prequential version: 147 bets, +30.91%.
- Prequential paired interval: -2.08 to +7.35.
- Neither variant proved incremental edge.

Insight:
Microstructure improves calibration slightly, but nearly every selected bet
already belongs to V6. It is a calibration shadow, not a new betting policy.

Artifacts:

- `data/v2/ev_model/experiment_075_combined_microstructure/`
- `data/v2/ev_model/experiment_076_prequential_combined_microstructure/`

### 2026-07-30 - Live timing, enrichment, and score-domain audit

Status: `PARTIAL`

Objective:
Verify only the remaining live/post-match lifecycle items for the Brazil
window.

Results:

- Four finished matches enriched successfully.
- A transport `TimeoutError` was normalized into the existing fallback path.
- Three post-freeze odds rows were excluded from settlement, ROI, and CLV.
- Real T-10 closing capture remains unproven.
- Direct V6 evaluator dry-run found 48/48 scores outside the training domain.
- V6 in-domain scores, selections, settlements, ROI, and CLV: all 0.

Insight:
Brazil data proves pipeline mechanics but cannot prove the European/Australian
model. Domain filtering is correctly failing closed.

### 2026-07-28 - V2 backend acceptance pass

Status: `VERIFIED`

Objective:
Exercise the V2 backend chain against the real `ullebets_v2` database.

Results:

- Support sync, fixture ingest, finished-match enrichment, teamprofiles, odds
  ingest, normalized offers, model snapshots, analysis, exports, and forward
  persistence completed.
- Six of six tested upcoming fixtures linked to Kambi events.
- Empty source dates were treated as valid empty responses rather than system
  failures.

Detailed evidence:
[v2-backend-verification-status.md](v2-backend-verification-status.md).

## Entry template

Copy this section for future work and insert the new entry above older entries.

````markdown
### YYYY-MM-DD - Short title

Status: `VERIFIED|PARTIAL|FAILED|UNPROVEN|BLOCKED|REJECTED`

Objective:
What was being proved or changed.

Changes:
- Files, collections, jobs, or configuration changed.

Tests:
```text
exact command or scenario
```

Results:
- Exact counts, pass/fail state, and important errors.

Insight:
What became known that was not known before.

Remaining:
- What is still unproven or blocked.

Next:
- The next justified test, not a generic wish list.
````
