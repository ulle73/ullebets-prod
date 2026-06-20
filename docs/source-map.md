# Ullebets Prod — Source Map

Det här dokumentet ska förklara **vad jag vill uppnå**, **vad jag redan har**, **min övergripande tes** och **var källorna finns**.

Gamla repot finns här:

```txt
C:\dev\FRONTEND\ullebets-vecel
```

Nya repot heter:

```txt
ullebets-prod
```

---

# VAD JAG VILL UPPNÅ

Jag vill bygga ett nytt repo som kan skapa en modell för att hitta positiva ROI-spel på fotbollens stat-marknader.

Fokus är framför allt:

```txt
skott
skott på mål
hörnor
```

Och marknader som:

```txt
totalt i matchen
hemmalag totalt i matchen
bortalag totalt i matchen
hemmalag första halvlek
bortalag första halvlek
hemmalag andra halvlek
bortalag andra halvlek
```

Målet är att modellen ska kunna lära sig från historiken:

```txt
vilka odds + linor som historiskt varit felprissatta
vilka lag/statistikmönster som skapat värde
vilka marknader som gett positiv ROI
vilka kommande odds + linor som därför är värda att spela
```

Hypotesen är enkel:

```txt
Om vi har historisk statistik, historiska odds + linor före match och resultatet/utfallet på varje odds + lina efter match, då finns grunden för att testa och träna fram en modell som försöker hitta +ROI-spel.
```

Det nya repot ska därför kunna:

```txt
hämta kommande matcher
hämta odds + linor före match
hämta statistik efter match
rätta varje odds + lina mot faktiskt utfall
spara historik
träna/anpassa modellen på historiken
använda modellen för att hitta bästa möjliga +ROI framåt
```

---

# VAD JAG HAR

Jag har redan mycket av det som behövs i gamla `ullebets-vecel`.

Det viktiga är:

```txt
historiska matcher
historisk lagstatistik
historiska odds + linor före match
historiska Unibet/Kambi stat-marknader
resultat/utfall efter match för odds + linor
closing odds / CLV-data där det finns
rådata från API:er i teamstats-mappen
kod som visar hur gamla systemet hämtade matcher, odds, linor, statistik och rättning
```

Det viktiga oddsflödet för modellen är **inte** RapidAPI 1X2-odds.

Det viktiga är **Unibet/Kambi-flödet** som hämtar stat-marknader, odds och linor för till exempel:

```txt
skott
skott på mål
hörnor
```

---

# MIN ÖVERGRIPANDE TES

Min tes är att det bör gå att bygga en modell som hittar +ROI genom att använda **all historisk pre-match-information** vi har, jämföra den mot **Unibets odds + linor före match**, och sedan använda **facit efter match** för att lära sig vilka linor som historiskt varit felprissatta.

Med pre-match-information menas allt som fanns tillgängligt innan matchen spelades: tidigare SofaScore-statistik, lagens historiska prestationer, hemma/borta, liga, lagstyrka, ranking, `league_rank`, Unibets odds, Unibets linor, period, scope och marknadstyp. Efter-match-statistik, faktiskt utfall, rättat over/under-resultat, ROI och CLV är facit. Det ska användas för träning och utvärdering, men inte som input när modellen simulerar ett spel före match.

Jag har haft ELO/ranking/`optaRating`/`optaRank` och `league_rank` eftersom rå statistik inte alltid går att jämföra rakt av. Ett lag som snittar många skott i en svag liga behöver inte vara bättre på att skapa skott än ett lag med lägre råsnitt i en starkare liga. Ett lag kan vara starkt totalt men svagt på skott på mål. Ett lag kan vara högt rankat i hörnor men lågt rankat i skott. Därför bör modellen kunna förstå liga, lagstyrka, motståndartyp, topplag/mellanlag/bottenlag, hemma/borta, favorit/underdog och stat-specifik ranking.

Det finns lagstyrka/ranking i:

```txt
data/leagues-and-teams.json
```

Den innehåller laginformation som kan användas för att förstå lagstyrka, till exempel `optaRank` och `optaRating` där det finns. Jag har även haft `league_rank` per stat eftersom olika stats kan skilja sig mycket mellan ligor och lag. Tanken är inte att låsa modellen till exakt hur jag har tänkt, utan att ge den färdiga signaler som kan hjälpa den förstå kontexten bakom rå statistik.

Modellen bör inte bara testa enkla snitt som `senaste 5 matcher`. Den bör skapa och testa många olika feature-kombinationer för varje `stat_key + period + scope`. Exempel på kombinationer jag vill att den överväger är senaste 3/5/10/20 matcher, hemma/borta senaste 3/5/10/20, mot topplag/mellanlag/bottenlag, som favorit/underdog, mot lag med hög/låg styrka, mot lag med hög/låg `league_rank` på relevant stat, styrkeskillnad mellan lagen och andra SofaScore-stats som kan påverka skott, skott på mål och hörnor.

Det betyder att modellen gärna får använda även indirekta stats om de finns i rådata, till exempel possession, fouls, cards, offsides, saves, tackles, passes, crosses, attacks eller dangerous attacks. Poängen är inte att jag redan vet vilka features som är bäst. Poängen är att modellen ska kunna testa brett och hitta vilka features som faktiskt predikterar respektive stat-marknad bäst och vilka kombinationer som historiskt gett bäst ROI mot Unibets odds + linor.

Jag tänker att arbetet bör ske i två steg. Först skapas en bred feature-fabrik där modellen får testa många rimliga pre-match-features per `stat_key + period + scope`. Sedan används facit från spelade matcher för att träna och utvärdera modellen. Feature-val och modellval bör inte göras på hela historiken och sedan testas på samma historik, eftersom det kan hitta slump. Det bör testas framåt i tiden: träna på äldre data, välj features på äldre data, testa på nästa period som modellen inte sett, flytta fram perioden, träna/anpassa igen och utvärdera igen.

Innan någon modellering görs bör datan granskas. Matcher eller linor som saknar odds + lina före match, saknar matchstatistik efter match, inte kan mappas tydligt till `stat_key + period + scope`, inte kan rättas som over/under, är inställda/avbrutna eller har osäker lagmatchning ska inte användas i träning/backtest förrän de är rättade. Systemet bör kunna visa hur många matcher/linor som hittades, hur många som gick att rätta, hur många som filtrerades bort och varför.

Kort sagt: jag vill ge modellen så mycket relevant pre-match-data som möjligt, låta den testa många kombinationer, använda facit efter match för att lära sig, och sedan hitta vilka mönster som faktiskt fortsätter fungera när den simulerar framtida spel mot Unibets odds + linor.

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

# ENDPOINTS OCH FILER FÖR ATT HÄMTA UNIBET ODDS + LINOR

Detta är kärnan för backtest och modell.

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

Unibet/Kambi endpoint-mönster:

```txt
https://eu1.offering-api.kambicdn.com/offering/v2018/ubse/listView/football/{country}/{league}.json
https://eu1.offering-api.kambicdn.com/offering/v2018/ubse/betoffer/event/{eventId}.json
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
förstå hur Unibet odds + linor översätts till spelbara stat-marknader
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
Bygg en modell som hittar positiva ROI-spel på fotbollens stat-marknader.

Du kan titta på gamla repot här för att förstå källorna:
C:\dev\FRONTEND\ullebets-vecel

Vi har historisk statistik, historiska odds + linor före match, resultat/utfall efter match för varje odds + lina, och closing/CLV-data där det finns.

Det viktiga oddsflödet är Unibet/Kambi-flödet för stat-marknader som skott, skott på mål och hörnor.

I docs/source-map.md hittar du filer, endpoints och collections som visar hur gamla systemet hämtade kommande matcher, Unibet odds + linor, matchstatistik efter match, rättning och CLV.

Min övergripande tes finns i docs/source-map.md. Den säger i korthet: använd all tillgänglig pre-match-data, inklusive SofaScore-stats, Unibet odds + linor, lagstyrka/ranking, optaRating/optaRank, league_rank, motståndartyp, hemma/borta, topplag/mellanlag/bottenlag och många rolling windows som 3/5/10/20 matcher. Använd efter-match-statistik och rättat utfall som facit, inte pre-match-input.

Gör först datakoll: filtrera bort matcher/linor som saknar odds + lina före match, saknar matchstatistik efter match, inte kan mappas tydligt till stat_key + period + scope, inte kan rättas som over/under, är inställda/avbrutna eller har osäker lagmatchning.

Testa sedan brett med många feature-kombinationer per stat_key + period + scope. Låt modellen hitta vilka features och kombinationer som bäst predikterar respektive stat-marknad och vilka som historiskt gett bäst ROI mot Unibets odds + linor. Feature-val och modellval bör testas framåt i tiden så modellen inte bara hittar slump i historiken.

Bygg om implementationen i detta repo så att systemet kan hämta kommande matcher, hämta odds + linor före match, hämta statistik efter match, rätta utfall och träna/anpassa en modell för att hitta bästa möjliga +ROI framåt.
```
