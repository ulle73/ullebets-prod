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

Vi har historisk data, historiska Unibet-odds och linor före match, resultat på varje odds + lina efter match, samt historisk lagstatistik.

Därför borde det gå att skapa en modell som lär sig vilka odds + linor som varit felprissatta historiskt och som kan anpassa sig för att hitta bästa möjliga ROI framåt.

Nedan finns gamla filer, endpoints och MongoDB-collections som visar hur matcher, odds, linor, statistik, resultat och CLV hämtades.
```

## Vad vi har

```txt
historiska matcher
historiska lagstats
historiska odds från Unibet
historiska linor före match
resultat/utfall efter match för varje odds + lina
closing odds / CLV-data där det finns
rådata från API:er i teamstats-mappen
```

## Vad nya repot ska kunna sätta upp

```txt
hämta kommande matcher
hämta odds + linor före match
hämta matchstatistik efter match
rätta odds + linor mot faktiskt utfall
spara historik
träna/anpassa en modell på historiken
hitta kommande marknader med bäst chans till positiv ROI
```

## Kommande matcher

Gamla filer:

```txt
rapidApi/scheduled-matches.js
rapidApi/urls.js
rapidApi/http-helpers.js
```

Endpoint-mönster:

```txt
/api/v1/sport/football/scheduled-events/{date}
/tournaments/get-scheduled-events
/tournaments/scheduled-events
/api/sport/football/scheduled-events/{date}
sport/football/scheduled-events/{date}
```

## Matchstatistik efter match

Gamla filer:

```txt
rapidApi/match-statistics.js
rapidApi/urls.js
rapidApi/http-helpers.js
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

## Odds + linor

Gamla filer:

```txt
rapidApi/odds.js
rapidApi/urls.js
rapidApi/http-helpers.js
```

Endpoint-mönster:

```txt
/api/v1/event/{matchId}/odds/{market}/all
/matches/get-all-odds
/matches/all-odds
/api/event/{matchId}/odds/{market}/all
/v1/events/odds/all
```

Gamla market IDs som testades:

```txt
1
5
226
317
100
```

## Statistikfält / stat-extraktion

Gamla filer:

```txt
lib/backtest/constants.js
lib/backtest/tuples.js
```

De visar exempel på hur gamla repot läste ut:

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

Den visar hur gamla repot tog faktisk matchstatistik efter match och avgjorde utfall för en marknad.

## CLV / historisk replay

Gamla fil:

```txt
scripts/research_eval.js
```

Den visar hur gamla repot använde historiska snapshots, teamstats och closing-line-tracking för historisk replay, ROI och CLV.

## MongoDB collections att inspecta

```txt
teamstats
analysis-snapshots
closing-line-tracking
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
