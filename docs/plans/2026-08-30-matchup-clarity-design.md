# Matchup clarity design

## Mål

Översikten ska gå att läsa på några sekunder utan att blanda ihop tre olika saker:

1. rankingpoängen som sorterar dagens matchups;
2. prediktorns rättade utfall mot den frysta ligabaselinen;
3. ett eventuellt spelutfall och dess closing/CLV.

Vyn ska samtidigt behålla revisionsbar detaljdata för den som öppnar ett kort.

## Informationshierarki

Varje kort har två nivåer:

- Den synliga nivån visar match, riktning, stat, period, rankingpoäng, placering och ett kompakt rättat predictorutfall.
- En expanderbar detaljnivå visar predictortröskel, faktiskt utfall, signerat avstånd, marknadsutfall, odds, CLV, closingkvalitet och oddshistorik.

`Rankingpoäng` ersätter `Score`. Poängen beskrivs uttryckligen som en sorteringspoäng, inte en sannolikhet. Placeringen visas som `#x av y` där `y` är antalet visade rader i samma riktning efter aktiva filter.

## Statusspråk

Synliga statusord som `TRÄFF`, `MISS`, `VUNNEN` och `FÖRLORAD` ersätts av ikoner:

- grön cirkel med bock: träff/vinst;
- röd cirkel med kryss: miss/förlust;
- gul minusikon: push;
- neutral klocka: väntar/öppen;
- neutral varningsikon: resultat eller jämförbar marknad saknas.

Ikonerna får alltid en svensk `aria-label` och tooltip. Färg är därför inte den enda informationsbäraren.

## Predictor och marknad

Predictorresultatet visas alltid först och bedöms endast mot den frysta ligabaselinen. En rad ska exempelvis kunna läsas som `14,0 mot 11,7 · +2,3`.

Marknadsresultatet är separat. Om en exakt jämförbar marknad finns visas odds och status samt en knapp för oddsrörelse/closing. Om marknad saknas visas den precisa orsaken och den räknas inte in i marknads-ROI eller CLV.

## Sammanfattning

Sammanfattningen delas i två namngivna block:

- `Prediktor`: rättade kontexter, träffprocent, medianavstånd och skillnad mot bästa konstanta riktning på samma observationer.
- `Spelbara marknader`: jämförbara/rättade marknader, ROI, closingtäckning, genomsnittlig CLV och antal som slog closing.

Baseline är deskriptiv och leakage-säker: efter rättning beräknas hur en strategi som alltid valt OVER respektive alltid valt UNDER hade träffat på exakt samma observationer. Den bästa av dessa jämförs med prediktorn. Den används inte för urval och presenteras inte som bevis för framtida edge.

## Rankingdiagnostik

API:t grupperar rättade predictorobservationer i fasta poängintervall: `90–100`, `80–89,9`, `70–79,9` och `<70`. Varje intervall visar antal, träffprocent och medianavstånd. Tomma intervall visas som otillräckligt underlag, inte `0 %`.

## Filter och responsivitet

Liga och stat är kvar som de primära filtren. Förklarande och diagnostiska mått ligger i en expanderbar panel så att standardvyn inte blir en dashboard av intern terminologi. Kortens detaljsektion använder ett vanligt `details/summary`-mönster som fungerar med tangentbord utan JavaScript-specialfall.

## Viktig begränsning

Den dyraste ännu oprövade premissen är fortsatt att rankingstyrkan överlever fler nya in-domain forwardmatcher. Ingen UI-förenkling eller historisk baseline får formuleras som bevis för positiv framtida ROI.
