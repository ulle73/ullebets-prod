# Ullebets Prod — Source Map

Det här dokumentet ska förklara **vad jag vill uppnå**, **vad jag redan har** och **var källorna finns**.

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

# MIN TES OM VARFÖR ELO / RANKING / LEAGUE_RANK FINNS

Jag har redan försökt tänka på att rå statistik inte alltid går att jämföra rakt av.

Ett lag som snittar många skott i en svag liga behöver inte vara bättre på att skapa skott än ett lag med lägre råsnitt i en starkare liga. Samma sak gäller hörnor, skott på mål och andra stats. Därför finns ranking/rating och `league_rank`-tänk i datan.

Det finns lagstyrka/ranking i:

```txt
data/leagues-and-teams.json
```

Den innehåller laginformation som kan användas för att förstå lagstyrka, till exempel `optaRank` och `optaRating` där det finns.

Jag har även haft `league_rank` per stat eftersom olika stats kan skilja sig mycket mellan ligor och lag. Ett lag kan vara högt rankat i en liga på hörnor men inte på skott på mål. Ett lag kan vara starkt totalt men ändå inte skapa många skott. Därför är det viktigt att modellen inte bara tittar på råa snitt, utan även på hur laget rankas inom sin liga och inom varje relevant stat.

Min hypotes är att modellen bör kunna använda saker som:

```txt
lagstyrka / ELO / optaRating
optaRank
league_rank per stat
styrkeskillnad mellan lagen
hur laget spelar mot topplag
hur laget spelar mot mittenlag
hur laget spelar mot bottenlag
hur laget spelar hemma/borta
hur laget spelar som favorit/underdog
hur laget skapar eller släpper till skott/hörnor mot olika typer av motstånd
```

Exempel på varför detta kan vara viktigt:

```txt
Ett lag kanske skjuter mycket mot bottenlag men nästan inget mot topplag.
Ett annat lag kanske släpper till många hörnor mot starka offensiva lag men inte mot svagare lag.
Ett topplag kanske dominerar boll men ändå inte skapar många skott på mål.
Ett lag kan vara topprankat i skott men lågt rankat i skott på mål.
```

Detta är min tes till varför dessa rankingfält finns och varför de kan vara viktiga.

Men modellen ska inte låsas till exakt hur jag tänkt. Den får använda all tillgänglig statistik, ranking, odds, linor och historiska utfall på det sätt som ger bäst testad ROI. Poängen är bara att den ska förstå att matchup, lagstyrka, liga, motståndartyp och stat-specifik ranking sannolikt är viktiga signaler.

---

# MIN TES OM FEATURE-SÖKNING

Jag vill inte att modellen bara ska testa enkla snitt som `senaste 5 matcher`.

Tesen är att bästa vägen är att låta modellen använda **alla tillgängliga parametrar som fanns före matchen** och testa många olika kombinationer för att hitta vilka features som faktiskt predikterar varje `stat_key` bäst.

Med alla tillgängliga pre-match-parametrar menas till exempel:

```txt
alla historiska SofaScore-stats vi har, men bara från matcher före aktuell match
Unibet odds + linor före match
lagstyrka / ELO / optaRating
optaRank
league_rank per stat
liga
hemma/borta
favorit/underdog
motståndartyp
stat-specifik ranking
```

Resultat, faktiskt utfall, matchstatistik efter match och CLV är **facit/labels/utvärdering**. Det ska användas för att lära modellen vad som hände och mäta ROI, men inte som input när modellen simulerar ett spel före match.

Modellen bör gärna skapa/testa features i flera tidsfönster, till exempel:

```txt
senaste 3 matcher
senaste 5 matcher
senaste 10 matcher
senaste 20 matcher
hela säsongen
hemma senaste 3/5/10/20
borta senaste 3/5/10/20
mot topplag senaste 3/5/10/20
mot mittenlag senaste 3/5/10/20
mot bottenlag senaste 3/5/10/20
som favorit senaste 3/5/10/20
som underdog senaste 3/5/10/20
```

Den bör kunna göra detta per relevant `stat_key`, till exempel:

```txt
shots / totalShots
shotsOnGoal
cornerKicks
```

Och även för stats som kan vara indirekt viktiga för skott, skott på mål och hörnor, till exempel:

```txt
possession
attacks / dangerous attacks om det finns
fouls
cards
offsides
saves
tackles
passes
crosses eller liknande om det finns i rådata
```

Poängen är inte att jag på förhand vet exakt vilka features som är bäst.

Poängen är att nya modellen ska kunna testa brett och hitta starkaste features för varje marknad/stat:

```txt
vilka features predikterar skott bäst?
vilka features predikterar skott på mål bäst?
vilka features predikterar hörnor bäst?
vilka kombinationer visar när Unibets lina historiskt varit fel?
vilka features har faktiskt lett till +ROI i backtest?
```

Efter det kan den bygga vidare från de starkaste featuresen och förbättra modellen.

Viktigt: efter-match-statistik och slutligt utfall är facit/rättning, inte pre-match-input. Modellen ska lära sig från historiken men när den simulerar ett spel ska den bara använda information som fanns före match.

---

# MIN TES OM HUR MODELLEN BÖR TESTA FEATURES OCH LÄRA SIG

Jag tänker att detta bör göras i två tydliga steg.

Steg 1: skapa en bred feature-fabrik.

```txt
Släng in / skapa så många rimliga pre-match-features som möjligt från all historik.
Gör detta per stat_key + period + scope.
Testa många kombinationer: senaste 3/5/10/20, hemma/borta, topplag/mellanlag/bottenlag, favorit/underdog, league_rank, optaRating, styrkeskillnad och andra SofaScore-stats.
Låt modellen/feature-selection hitta vilka features som faktiskt verkar starkast för varje marknad.
```

Steg 2: låt modellen lära sig av facit.

```txt
När matchen är spelad finns facit: faktisk statistik, om over/under vann, ROI och CLV där det finns.
Detta facit används för träning och utvärdering.
Modellen ska lära sig vilka pre-match-features som historiskt förklarat när Unibets odds + linor varit felprissatta.
```

Men feature-valet och modellvalet får inte göras på hela historiken och sedan testas på samma historik. Då finns risk att man bara hittar slump.

Tesen är därför att modellen bör testa detta framåt i tiden:

```txt
träna på gammal data
välj features på gammal data
testa på nästa period som modellen inte sett
flytta fram perioden
träna om / anpassa modellen
utvärdera igen
```

Målet är inte bara att hitta features som såg bäst ut historiskt. Målet är att hitta features som fortsätter fungera när modellen simulerar framtida matcher.

---

# DATAKVALITET INNAN MODELLERING

Innan modellen tränas bör systemet börja med att granska datan och filtrera bort matcher/linor som inte går att använda.

En historisk match/lina bör inte tas med i träning eller backtest om något viktigt saknas.

Exempel på sådant som bör filtreras bort eller markeras som ogiltigt:

```txt
matchen saknar korrekt matchId/eventId
matchen saknar kickoff/starttid
Unibet odds + lina saknas före match
Unibet-market går inte att mappa tydligt till stat_key + period + scope
matchstatistik efter match saknas
statistiken saknar rätt stat_key, period eller home/away/total
faktiskt utfall kan inte räknas ut
linan kan inte rättas som over/under win/loss
matchen är inställd, avbruten eller inte färdigspelad
lagmatchning mellan SofaScore och Unibet är osäker
samma match/lina finns dubbelt med konfliktande värden
```

Sådana matcher ska inte tyst blandas in i modellen. De bör antingen:

```txt
exkluderas från träning/backtest
eller sparas som invalid/needs_review
```

Det bör också skapas en enkel datarapport som visar:

```txt
hur många matcher som hittades
hur många som hade Unibet odds + linor
hur många som hade matchstatistik efter match
hur många som kunde rättas
hur många som filtrerades bort
varför de filtrerades bort
```

Poängen är att modellen bara ska tränas och backtestas på matcher där kedjan är komplett:

```txt
pre-match stats + odds/lina före match -> match spelas -> statistik/resultat efter match -> rättad over/under -> ROI/CLV-utvärdering
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

Det finns även lagstyrka/ranking och league_rank-tänk i datan. Tanken är att modellen inte bara ska titta på råa snitt, utan även kunna förstå liga, lagstyrka, motståndartyp, topplag/mellanlag/bottenlag, hemma/borta och stat-specifika rankings.

Jag vill att modellen testar brett med alla tillgängliga pre-match-parametrar och många olika feature-kombinationer, till exempel senaste 3/5/10/20 matcher, hemma/borta, topplag/mellanlag/bottenlag, favorit/underdog och league_rank per stat_key. Syftet är att hitta vilka features och kombinationer som bäst predikterar varje stat-marknad och vilka som historiskt gett bäst +ROI mot Unibets odds + linor.

Gör först datakoll: filtrera bort matcher/linor som saknar odds + lina före match, saknar matchstatistik efter match, inte kan mappas tydligt till stat_key + period + scope, inte kan rättas som over/under, är inställda/avbrutna eller har osäker lagmatchning. Sådana rader ska inte användas i träning/backtest förrän de är rättade.

Tänk två steg: först bred feature-sökning per stat_key + period + scope på historisk pre-match-data. Sedan träning/utvärdering med facit från spelade matcher. Feature-val och modellval bör testas framåt i tiden så modellen inte bara hittar slump i historiken.

Bygg om implementationen i detta repo så att systemet kan hämta kommande matcher, hämta odds + linor före match, hämta statistik efter match, rätta utfall och träna/anpassa en modell för att hitta bästa möjliga +ROI framåt.
```
