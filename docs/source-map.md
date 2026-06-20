# Ullebets Prod — Source Map

Det här dokumentet är en källkarta för nya repot `ullebets-prod`.

Gamla repot finns här:

```txt
C:\dev\FRONTEND\ullebets-vecel
```

Syftet är inte att kopiera gamla arkitekturen. Syftet är att ge nya bygget tydliga källor: var historisk data finns, hur matcher hämtades, hur Unibet/Kambi-linor hämtades, hur statistik hämtades efter match och hur utfall/CLV/backtest gjordes.

---

# VAD JAG VILL UPPNÅ

Jag vill bygga ett nytt repo som använder historisk data för att hitta +ROI på fotbollens stat-marknader.

Fokus är framför allt:

```txt
skott
skott på mål
hörnor
```

Och dessa typer av marknader:

```txt
totalt i matchen
hemmalag totalt i matchen
bortalag totalt i matchen
hemmalag första halvlek
bortalag första halvlek
hemmalag andra halvlek
bortalag andra halvlek
```

Hypotesen är:

```txt
Om vi har historisk pre-match-data, historiska Unibet/Kambi odds + linor före match och facit efter match, då finns grunden för att träna och testa en modell som försöker hitta återkommande felprissättningar och +ROI.
```

Det färdiga systemet ska kunna:

```txt
hämta kommande matcher
hämta Unibet/Kambi odds + linor före match
hämta faktisk statistik efter match
rätta varje odds + lina mot faktiskt utfall
spara historik
träna/anpassa modellen på historiken
använda modellen för framtida marknader
```

---

# VAD JAG HAR

I gamla `ullebets-vecel` finns eller finns referenser till:

```txt
historiska matcher
historisk lagstatistik
historiska Unibet/Kambi stat-marknader
historiska odds + linor före match
resultat/utfall efter match för odds + linor
closing odds / CLV-data där det finns
rådata från API:er i teamstats-mappen
kod som visar hur gamla systemet hämtade matcher, linor, statistik och rättning
```

Viktigt: det relevanta oddsflödet för stat-marknader är **Unibet/Kambi**, inte RapidAPI 1X2.

---

# MIN ÖVERGRIPANDE TES

Min tes är att modellen ska använda så mycket relevant **pre-match-information** som möjligt, jämföra detta mot **Unibets/Kambis odds + linor före match**, och sedan använda **facit efter match** för att lära sig vilka linor som historiskt varit felprissatta.

Pre-match-information betyder allt som fanns före matchstart, till exempel tidigare SofaScore-statistik, hemma/borta, liga, motståndartyp, lagstyrka, ranking, `optaRating`, `optaRank`, `league_rank`, Unibet/Kambi-lina, odds, period, scope och marknadstyp.

Efter-match-statistik, faktiskt utfall, rättat over/under-resultat, ROI och CLV är facit. Det ska användas för träning och utvärdering, men inte som input när modellen simulerar ett beslut före match.

## Varför ranking, ELO, optaRating, optaRank och league_rank finns

Rå statistik räcker inte alltid. Ett lag som snittar många skott i en svag liga behöver inte vara bättre på att skapa skott än ett lag med lägre råsnitt i en starkare liga. Ett lag kan vara starkt totalt men svagt på skott på mål. Ett lag kan vara högt rankat på hörnor men lågt rankat på skott.

Därför finns ranking- och styrkesignaler, bland annat i:

```txt
data/leagues-and-teams.json
```

Den filen innehåller bland annat laginformation, `optaRank` och `optaRating` där det finns. Jag har också haft `league_rank` per stat eftersom stats kan skilja sig mycket mellan ligor och lag.

Tanken är inte att låsa modellen till min metod. Tanken är att ge den färdiga signaler som hjälper den förstå kontexten bakom rå statistik.

## Det viktigaste med feature-sökningen

Modellen ska inte bara testa enkla snitt som `senaste 5 matcher`.

Den ska testa brett bland all tillgänglig pre-match-statistik och göra det per:

```txt
stat_key + period + scope
```

Exempel:

```txt
shots + ALL + home
shots + ALL + away
shots + ALL + total
shots + 1ST + home
shots + 1ST + away
shots + 2ND + home
shots + 2ND + away
shotsOnGoal + ALL + home
shotsOnGoal + 1ST + home
shotsOnGoal + 2ND + away
cornerKicks + ALL + total
cornerKicks + 1ST + home
cornerKicks + 2ND + away
```

Olika marknader kan ha olika starka signaler. Det som fungerar för hemmalagets skott i full match behöver inte fungera för bortalagets skott på mål i första halvlek eller hörnor i andra halvlek.

Feature-sökningen bör överväga många kombinationer, till exempel:

```txt
senaste 3 matcher
senaste 5 matcher
senaste 10 matcher
senaste 20 matcher
hemma senaste 3/5/10/20
borta senaste 3/5/10/20
mot topplag
mot mellanlag
mot bottenlag
som favorit
som underdog
mot lag med hög/låg optaRating
mot lag med hög/låg optaRank
mot lag med hög/låg league_rank på relevant stat
lagets egna stats for
lagets egna stats against
motståndarens stats for
motståndarens stats against
styrkeskillnad mellan lagen
stat-specifik styrkeskillnad mellan lagen
Unibet/Kambi lina
Unibet/Kambi odds
marknadsnamn
period
scope
liga
```

Den får också använda indirekta SofaScore-stats om de finns i rådata, till exempel:

```txt
possession
fouls
cards
offsides
saves
tackles
passes
crosses
attacks
dangerous attacks
```

Poängen är inte att jag redan vet vilka features som är bäst. Poängen är att modellen ska kunna testa brett och hitta vilka features och kombinationer som faktiskt predikterar varje stat-marknad bäst.

Det färdiga projektet bör inte bara ge framtida marknader. Det bör också kunna visa:

```txt
vilka features var starkast
vilka stat_key + period + scope fungerade bäst
vilka marknader fungerade bäst
vilka ligor fungerade bäst
vilka oddsintervall fungerade bäst
vilka line-intervall fungerade bäst
vilka lagtyper/motståndstyper fungerade bäst
vilka features verkade vara brus
vad filtrerades bort och varför
```

## Hur modellen bör lära sig

Arbetet bör ske i två steg:

```txt
1. Skapa en bred feature-fabrik / feature-sökning per stat_key + period + scope.
2. Använd facit från spelade matcher för att träna och utvärdera vilka features, modeller och kombinationer som faktiskt fungerar.
```

Feature-val och modellval bör inte göras på hela historiken och sedan testas på samma historik. Det kan bara hitta slump. Det bör testas framåt i tiden: träna på äldre data, välj features på äldre data, testa på nästa period som modellen inte sett, flytta fram perioden, träna/anpassa igen och utvärdera igen.

## Datakvalitet först

Innan modellering ska datan granskas. Matcher eller linor ska filtreras bort om de saknar:

```txt
odds + lina före match
matchstatistik efter match
tydlig mapping till stat_key + period + scope
rättbart over/under-utfall
färdigspelad match
säker lagmatchning
```

Systemet bör kunna visa hur många matcher/linor som hittades, hur många som gick att rätta, hur många som filtrerades bort och varför.

Kort sagt: jag vill ge modellen så mycket relevant pre-match-data som möjligt, låta den testa många kombinationer, använda facit efter match för att lära sig, och sedan hitta vilka mönster som faktiskt fortsätter fungera framåt mot Unibet/Kambi-linor.

---

# ENDPOINTS OCH FILER FÖR ATT HÄMTA KOMMANDE MATCHER

Gamla filer att titta på:

```txt
rapidApi/scheduled-matches.js
rapidApi/urls.js
rapidApi/http-helpers.js
lib/engines/fixtures-engine.js
```

Endpoint-mönster som gamla repot använde:

```txt
/api/v1/sport/football/scheduled-events/{date}
/tournaments/get-scheduled-events
/tournaments/scheduled-events
/api/sport/football/scheduled-events/{date}
sport/football/scheduled-events/{date}
```

Syfte:

```txt
hämta kommande fotbollsmatcher
få matchId/eventId
få liga
få hemma-/bortalag
få starttid
```

---

# ENDPOINTS OCH FILER FÖR ATT HÄMTA UNIBET/KAMBI ODDS + LINOR

Detta är kärnan för stat-marknaderna.

Gamla filer att titta på:

```txt
lib/engines/unibet-engine.js
lib/repos/unibet.js
lib/backtest/unibetAuto.js
components/backtest/unibetOddsMapper.js
components/backtest/teamNameAliases.js
app/api/backtest/route.js
app/api/closing-lines/route.js
scripts/run-unibet-closing.js
lib/runners/backtest-runner.js
data/unibetLeagueUrls.json
.github/workflows/run-unibet-closing.yml
```

Kambi/Unibet endpoint-mönster som gamla repot använde:

```txt
Kambi listView för football/{country}/{league}
Kambi betoffer/event/{eventId}
```

Vanliga query params i gamla repot:

```txt
lang=sv_SE
market=SE
client_id=2
channel_id=1 eller 3
includeParticipants=true
useCombined=true
```

Syfte:

```txt
hitta rätt Unibet-event för en match
hämta alla betOffers för eventet
hämta odds + linor före match
hämta over/under-marknader
hämta stat-marknader som skott, skott på mål och hörnor
```

Gamla kodkedjan:

```txt
lib/runners/backtest-runner.js
  -> lib/engines/unibet-engine.js
  -> lib/repos/unibet.js
  -> lib/backtest/unibetAuto.js
  -> components/backtest/unibetOddsMapper.js
```

Gamla closing/CLV-kedjan:

```txt
.github/workflows/run-unibet-closing.yml
  -> scripts/run-unibet-closing.js
  -> lib/runners/backtest-runner.js
  -> app/api/closing-lines/route.js
  -> closing-line-tracking collection
```

---

# FILER FÖR ATT FÖRSTÅ UNIBET STAT-MAPPNING

Viktigaste filen:

```txt
components/backtest/unibetOddsMapper.js
```

Den visar hur gamla repot mappar Unibet-labels till interna statKey-värden.

Exempel:

```txt
skott på mål -> shotsOnGoal
skott -> totalShots
hörnor -> cornerKicks
kort -> yellowCards
frisparkar -> freeKicks
fouls -> fouls
tacklingar -> totalTackle
offside -> offsides
```

Den försöker också tolka:

```txt
scope: total / home / away
period: ALL / 1ST / 2ND
line
odds over
odds under
```

Syfte:

```txt
förstå hur Unibet/Kambi odds + linor översätts till spelbara stat-marknader
```

---

# ENDPOINTS OCH FILER FÖR ATT HÄMTA MATCHSTATISTIK EFTER MATCH

Gamla filer att titta på:

```txt
rapidApi/match-statistics.js
rapidApi/urls.js
rapidApi/http-helpers.js
lib/backtest/constants.js
lib/backtest/tuples.js
lib/matchupsOutcome.js
```

Endpoint-mönster som gamla repot använde:

```txt
/api/v1/event/{matchId}/statistics
/matches/get-statistics
/matches/statistics
/api/event/{matchId}/statistics
/v1/events/statistics
event/{matchId}/statistics
```

Syfte:

```txt
hämta faktisk statistik efter match
hämta skott
hämta skott på mål
hämta hörnor
hämta home value
hämta away value
hämta total value
hämta period/halvlek
```

---

# FILER FÖR RESULTAT / RÄTTNING

Gamla filer att titta på:

```txt
lib/matchupsOutcome.js
lib/backtest/tuples.js
lib/backtest/constants.js
```

Syfte:

```txt
ta faktisk statistik efter match
jämföra faktisk statistik mot odds-line
avgöra om over/under vann eller förlorade
rätta varje historisk odds + lina
```

---

# FILER FÖR HISTORISK REPLAY / BACKTEST / CLV

Gamla filer att titta på:

```txt
scripts/research_eval.js
app/api/closing-lines/route.js
lib/clvTracking.js
scripts/run-unibet-closing.js
.github/workflows/run-unibet-closing.yml
```

MongoDB collections att titta i:

```txt
teamstats
analysis-snapshots
closing-line-tracking
result-loop-bets
unibet-backtest
job_state
```

Inspecta även collections som verkar innehålla:

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

Syfte:

```txt
förstå hur gamla systemet sparade historik
förstå hur gamla systemet sparade closing odds / CLV
förstå hur gamla systemet replayade historiska odds + linor
förstå hur gamla systemet räknade historiskt utfall
```

---

# RÅDATA SOM KOPIERAS MANUELLT

Teamstats-mappen kopieras manuellt från gamla repot:

```txt
C:\dev\FRONTEND\ullebets-vecel\data\teamstats
```

Trolig ny plats i nya repot:

```txt
./data/teamstats
```

Syfte:

```txt
rådata från API:er
historisk matchstatistik
lagstatistik
underlag för att bygga historik och modell
```

---

# KORT PROMPT TILL CODEX / AGENT

```txt
Bygg en modell som hittar positiva ROI på fotbollens stat-marknader.

Du kan titta på gamla repot här för att förstå källorna:
C:\dev\FRONTEND\ullebets-vecel

Vi har historisk statistik, historiska odds + linor före match, resultat/utfall efter match för varje odds + lina, och closing/CLV-data där det finns.

Det viktiga oddsflödet är Unibet/Kambi-flödet för stat-marknader som skott, skott på mål och hörnor.

I docs/source-map.md hittar du filer, endpoints och collections som visar hur gamla systemet hämtade kommande matcher, Unibet/Kambi odds + linor, matchstatistik efter match, rättning och CLV.

Min övergripande tes finns i docs/source-map.md. Den säger i korthet: använd all tillgänglig pre-match-data, inklusive SofaScore-stats, Unibet/Kambi odds + linor, lagstyrka/ranking, optaRating/optaRank, league_rank, motståndartyp, hemma/borta, topplag/mellanlag/bottenlag och många rolling windows som 3/5/10/20 matcher. Använd efter-match-statistik och rättat utfall som facit, inte pre-match-input.

Modellen ska inte bara bygga enkla snitt. Den ska testa brett per stat_key + period + scope och kunna visa vilka features, marknader, ligor, oddsintervall, line-intervall och lag-/motståndstyper som faktiskt bar signalen och vilka som bara var brus.

Gör först datakoll: filtrera bort matcher/linor som saknar odds + lina före match, saknar matchstatistik efter match, inte kan mappas tydligt till stat_key + period + scope, inte kan rättas som over/under, är inställda/avbrutna eller har osäker lagmatchning.

Testa sedan brett med många feature-kombinationer per stat_key + period + scope. Låt modellen hitta vilka features och kombinationer som bäst predikterar respektive stat-marknad och vilka som historiskt gett bäst ROI mot Unibet/Kambi odds + linor. Feature-val och modellval bör testas framåt i tiden så modellen inte bara hittar slump i historiken.

Bygg om implementationen i detta repo så att systemet kan hämta kommande matcher, hämta odds + linor före match, hämta statistik efter match, rätta utfall och träna/anpassa en modell för att hitta bästa möjliga +ROI framåt.
```
