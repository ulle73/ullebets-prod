# Ullebets Prod — Source Map

Det här dokumentet ska bara förklara **vad vi vill uppnå**, **vad vi redan har** och **var källorna finns**.

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

Bygg om implementationen i detta repo så att systemet kan hämta kommande matcher, hämta odds + linor före match, hämta statistik efter match, rätta utfall och träna/anpassa en modell för att hitta bästa möjliga +ROI framåt.
```
