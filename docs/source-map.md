# Ullebets Prod — Source Map

Det här är bara en källkarta.

Gamla repot finns här:

```txt
C:\dev\FRONTEND\ullebets-vecel
```

## Kort prompt

```txt
Bygg en modell som hittar positiv ROI på fotbollens stat-marknader.

Titta på gamla repot här för att förstå datakällorna:
C:\dev\FRONTEND\ullebets-vecel

Vi har historiska matcher, historisk lagstatistik, historiska Unibet-odds + linor före match, resultat/utfall efter match för varje odds + lina, och CLV/closing-data där det finns.

Därför borde det gå att skapa en modell som lär sig vilka odds + linor som varit felprissatta historiskt och som kan anpassa sig för att hitta bästa möjliga ROI framåt.

Nedan finns gamla filer, endpoints och MongoDB-collections som visar hur matcher, Unibet-odds + linor, statistik, resultat, rättning och CLV hämtades.
```

## Vad vi har

```txt
historiska matcher
historisk lagstatistik
historiska Unibet-odds
historiska Unibet-linor före match
resultat/utfall efter match för varje odds + lina
closing odds / CLV-data där det finns
rådata från API:er i teamstats-mappen
```

## Vad nya repot ska kunna sätta upp

```txt
hämta kommande matcher
hitta rätt Unibet-event för matchen
hämta Unibet odds + linor före match
hämta matchstatistik efter match
rätta odds + linor mot faktiskt utfall
spara historik
träna/anpassa en modell på historiken
hitta kommande marknader med bäst chans till positiv ROI
```

## Viktigt om odds

De viktiga oddsen för modellen är inte RapidAPI 1X2-oddsen.

Det viktiga flödet är Unibet/Kambi-flödet som hämtar stat-marknader, linor och odds, t.ex. skott, skott på mål och hörnor.

RapidAPI/SofaScore kan användas för matcher och matchstatistik, men statline-oddsen ska förstås via Unibet-filerna nedan.

## Kommande matcher

Gamla filer:

```txt
rapidApi/scheduled-matches.js
rapidApi/urls.js
rapidApi/http-helpers.js
lib/engines/fixtures-engine.js
```

Endpoint-mönster:

```txt
/api/v1/sport/football/scheduled-events/{date}
/tournaments/get-scheduled-events
/tournaments/scheduled-events
/api/sport/football/scheduled-events/{date}
sport/football/scheduled-events/{date}
```

## Unibet odds + linor för stat-marknader

Detta är kärnan för backtest och modell.

Gamla filer:

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
```

Viktiga Unibet/Kambi endpoint-mönster:

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

Unibet league URL-config:

```txt
data/unibetLeagueUrls.json
```

Den filen innehåller baseUrl för ligor som Premier League, La Liga, Bundesliga, Serie A, Brasileirão Série A, Ligue 1 och A-League Men.

## Hur Unibet-flödet fungerar i gamla repot

```txt
1. Hämta matcher för datum.
2. Matcha matchen mot Unibet-listView via liga, hemma/borta-lag och starttid.
3. Få Unibet eventId.
4. Hämta betOffers för eventId.
5. Mappa Unibet betOffers till stat-tuples.
6. Varje tuple innehåller statKey, scope, period, line och odds för over/under.
7. Spara eller använd raderna för backtest, closing/CLV och modell.
```

Kodkedja:

```txt
lib/runners/backtest-runner.js
  -> lib/engines/unibet-engine.js
  -> lib/repos/unibet.js
  -> lib/backtest/unibetAuto.js
  -> components/backtest/unibetOddsMapper.js
```

Closing/CLV-kedja:

```txt
.github/workflows/run-unibet-closing.yml
  -> scripts/run-unibet-closing.js
  -> lib/runners/backtest-runner.js
  -> app/api/closing-lines/route.js
  -> closing-line-tracking collection
```

## Unibet stat-mappning

Gamla fil:

```txt
components/backtest/unibetOddsMapper.js
```

Den mappar Unibet-labels till interna statKeys:

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

Obs: detta är källlogik att förstå, inte nödvändigtvis perfekt kod att kopiera rakt av.

## Matchstatistik efter match

Gamla filer:

```txt
rapidApi/match-statistics.js
rapidApi/urls.js
rapidApi/http-helpers.js
lib/backtest/constants.js
lib/backtest/tuples.js
lib/matchupsOutcome.js
```

Endpoint-mönster:

```txt
/api/v1/event/{matchId}/statistics
/matches/get-statistics
/matches/statistics
/api/event/{matchId}/statistics
/v1/events/statistics
event/{matchId}/statistics
```

Dessa filer visar hur gamla repot läste ut faktisk statistik efter match:

```txt
skott
skott på mål
hörnor
home value
away value
total value
period
```

## Resultat / rättning

Gamla fil:

```txt
lib/matchupsOutcome.js
```

Den visar hur gamla repot tog faktisk matchstatistik efter match och avgjorde utfall för en marknad/line.

## CLV / historisk replay

Gamla filer:

```txt
app/api/closing-lines/route.js
scripts/research_eval.js
lib/clvTracking.js
```

De visar hur gamla repot använde historiska snapshots, teamstats och closing-line-tracking för replay, ROI och CLV.

## MongoDB collections att inspecta

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

## Rådata

Teamstats-mappen kopieras manuellt från:

```txt
C:\dev\FRONTEND\ullebets-vecel\data\teamstats
```

Trolig ny plats:

```txt
./data/teamstats
```
