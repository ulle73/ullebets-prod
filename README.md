# Ullebets V2 Backend

Det här repot är V2-backend-replacementen för `C:/dev/frontend/ullebets-vecel`.
Det innehåller även den fristående `frontend/`-klienten och ett strikt read-only
API för produktvyn. Fokus är raw-first ingest, canonical mapping, audits,
parity reports, `job_runs` och säkra CLI-jobb runt `ullebets_v2`.

## Börja här

Alla utvecklare och agenter ska läsa följande innan de ändrar kod eller kör
tester:

1. [AGENTS.md](AGENTS.md) - obligatoriska arbets-, evidens- och säkerhetsregler
2. [docs/work-log.md](docs/work-log.md) - aktuell state, redan utförda tester,
   insikter, blockerare och nästa motiverade test
3. [docs/app-readiness-checklist.md](docs/app-readiness-checklist.md) - enkel
   checklista över vad som fungerar och exakt vad som återstår
4. [docs/v2-backend-verification-status.md](docs/v2-backend-verification-status.md)
   - full backend-verifiering
5. [docs/ev-model-experiments.md](docs/ev-model-experiments.md) - fullständig
   modell- och backtesthistorik

`docs/work-log.md` ska uppdateras efter varje arbetspass som ändrar kod, data,
konfiguration, dokumentation eller verifierad runtime-state. Kör inte om dyra
eller live-beroende tester innan loggen kontrollerats.

## Säkerhet

- Alla V2-jobb hard-failar om `MONGODB_DB` inte är `ullebets_v2`.
- `app` och `ullebets_unibet` används bara som read-only referenskällor.
- GitHub Actions i det här repot kör nu write-mode som standard genom den delade `v2-python-job.yml`-runnern.
- Emergency stop finns via repo-variabeln `ULLEBETS_V2_FORCE_DRY_RUN=1`, som tvingar tillbaka alla V2-workflows till dry-run utan YAML-ändringar.
- Odds- och modellkedjan har fortfarande ett explicit read-only beroende på originalrepot för legacy JS-oraclen. Actions checkar därför ut originalrepot separat tills de beroendena är helt internaliserade.
- Eftersom databasen redan är versionsseparerad via `ullebets_v2` hålls collection-namn suffixfria. `*_v2`-namn finns bara kvar som legacy-cleanup-mappning för tidiga bootstrap-körningar.

## Lokala kommandon

Installera Python-beroenden:

```bash
python -m pip install -e .
```

Foundation smoke:

```bash
python scripts/forward_v2/smoke_test_v2.py
```

No-side-effect healthcheck:

```bash
python scripts/forward_v2/healthcheck_v2.py
python scripts/forward_v2/healthcheck_v2.py --check-connectivity --ping-db --check-fixture-db
```

## Vercel-hosting

`vercel.json` bygger `frontend/` som en SPA och exponerar samma read-only
`/api/v1/*`-kontrakt som används lokalt genom Python-funktionen
`api/v1/[...path].py`. Klienten ansluter därmed till API:t på samma origin och
databasanslutningen lämnar aldrig webbläsaren.

Vercel-projektet ska ha följande **Production**-miljövariabler:

- `MONGODB_URI` - den privata anslutningen till Cosmos/MongoDB
- `MONGODB_DB=ullebets_v2` - andra databasnamn stoppas av V2:s säkerhetsguard

Sätt aldrig `MONGODB_URI` som en `VITE_*`-variabel och kopiera inte
`.env.local` till Vercel. Python-funktionen tillåter endast `GET` och `HEAD`;
alla skrivmetoder får `405`.

Indexplan:

```bash
python scripts/forward_v2/bootstrap_indexes.py --dry-run
```

Normalisera gamla bootstrap-namn i en redan skapad V2-databas:

```bash
python scripts/forward_v2/standardize_collection_names.py --dry-run
```

Paritetsmatris:

```bash
python scripts/forward_v2/materialize_parity_reports.py --dry-run
```

Historisk backfill-plan:

- [docs/v2-historical-backfill-plan.md](C:/Users/ryd/.config/superpowers/worktrees/ullebets-prod/feature-ullebets-v2-backend/docs/v2-historical-backfill-plan.md)

Senaste backend-verifieringsstatus:

- [docs/v2-backend-verification-status.md](C:/Users/ryd/.config/superpowers/worktrees/ullebets-prod/feature-ullebets-v2-backend/docs/v2-backend-verification-status.md)
- [data/v2/reports/backend-verification-status-2026-07-28.json](C:/Users/ryd/.config/superpowers/worktrees/ullebets-prod/feature-ullebets-v2-backend/data/v2/reports/backend-verification-status-2026-07-28.json)

## EV shadow model

Den tidigare Poisson/XGBoost-ML-delen återanvänds som datakälla och
walk-forward-infrastruktur, inte som godkända modeller. Den aktiva
shadow-kandidaten är en regulariserad logistisk marknadsmodell med:

- 90 dagars rullande träningsfönster
- 45 dagars recency-halvering
- exakt snapshot-as-of historik med tre timmars availability-buffer
- minst 7,5 procent beräknad model-EV
- mindre än 25 procent beräknad model-EV för att avstå från extrapolation
- högst ett val per match/stat/period/scope

Artifact och manifest:

```text
models/ev/ev_logistic_recency45_asof_capped_v3/
```

En nested-regulariserad V4-challenger finns i
`models/ev/ev_nested_logistic_recency45_asof_capped_v4_shadow/`, men dess
manifest tillåter endast `score_only`. Den kan inte skapa bets eller ersätta
V3 innan nya orörda forward-resultat motiverar det.

En V5-ensemble finns i
`models/ev/ev_ensemble_v3_75_v4_25_shadow/`. Den kombinerar fasta
`75%` V3- och `25%` V4-sannolikheter och är också hårt begränsad till
`score_only`. Historiskt gav den `279` bets, `+13,05%` ROI och `6/6`
positiva outer-fönster, men det klustrade intervallet korsar fortfarande noll.

V6 finns i
`models/ev/ev_scope_interaction_recency45_asof_capped_v6_shadow/`.
Den återanvänder V4 men tillåter hårt regulariserade slopeavvikelser för
home/away scope. Historiskt gav den `234` bets, `+18,03%` ROI och ett
matchklustrat intervall på `+3,62%` till `+32,14%`. Resultatet klarar inte
korrigeringen för `124` inspekterade varianter och V6 är därför strikt
`score_only`.

Frys predictioner före kickoff:

```bash
python scripts/forward_v2/score_ev_shadow_model.py --repo-root .
```

Jobbet läser aldrig target-matchernas outcomes. Alla prematch-sidor och deras
frysta features/probabilities/EV sparas immutabelt i `ev_model_scores`;
endast val som passerar V3-policyn skrivs till `forward_bets`. Båda lagren är
idempotenta. Score-arkivet gör att V3 och alternativa policyer senare kan
jämföras på identiska, orörda forward-matcher utan att skapa flera verkliga
exponeringar. Modellen är endast godkänd för shadow-test. Historiska
experiment, leakage-fynd och auditresultat finns i
`docs/ev-model-experiments.md`.

Jämför V3-V6 från samma immutabla score-arkiv:

```bash
python scripts/forward_v2/evaluate_ev_score_archive.py --repo-root .
```

Utvärderaren fryser den första score-batchen med ett spelbart val per match.
Den skriver endast audit/job-status och muterar varken scores eller bets.
Stat- och scope-jämförelserna är förregistrerade i
`models/ev/score_policy_registry_v5.json`. V5-registret ärver hela den frysta
V4-kedjan och lägger endast till den exakta V6 corner/away+total-kandidaten.
Registry-fingerprint
`5b8a699fc874d9f967aaaab81b68ff85f61c28dbf5fb634860f768b04889794d`
sparas i rapporten, och samtliga tjugo policys behandlas som samma
forward-jämförelsefamilj.

Utvärderaren läser dessutom den fitted kategoridomänen direkt ur respektive
modellartefakt. Scores från okända ligor bevaras men exkluderas från selection,
ROI, CLV och promotion. De nuvarande `192` V3-V6-score-raderna gäller
Brasileirão Série A, som inte finns i modellernas sex träningsligor; därför är
samtliga diagnostiska och `0` räknas som in-domain forward-bevis.

Den senaste falsifieringsauditen finns under
`data/v2/ev_model/experiment_038_candidate_falsification/`. V3 överlever alla
leave-one-league- och leave-one-window-tester men dess matchklustrade
konfidensintervall korsar fortfarande noll. V4 blir negativ när Serie A tas
bort och får därför inte ersätta V3.

Den starkaste historiska hypotesen är den frysta score-only-policyn
`v6_scope_interaction_corners_away_total_primary_challenger`: hörnor för
away/total över alla perioder med oförändrad EV-gräns `7,5–25%`. Den gav
historiskt `156` bets över `99` matcher, `+28,65%` ROI och ett matchklustrat
95%-intervall på `+11,33%` till `+45,27%`. Efter hela den dåvarande
159-testerfamiljen var p-värdet `0,0207`; alla leave-one-league/window-resultat
var positiva och en prissänkning på `0,10` behöll `+22,05%` ROI.

Detta är fortfarande inte bevisad +EV. Modellen blir negativ med 60 dagars
träning och utfallet är känsligt runt den exakta `7,5%`-tröskeln. Policyn är
därför fryst före nya in-domain-resultat och får varken skapa riktiga bets
eller ändras efter settlement.

Ett separat prior-window-only test visar att scope-signalen kan upptäckas
utan att läsa det aktuella testfönstret. En router som väntar på minst `10`
tidigare bets per scope och kräver positiv tidigare ROI gav `86` bets,
`+35,50%` ROI och ett klustrat intervall på `+14,22%` till `+54,80%`.
Robusthetsfamiljen hade `0` framtidsrader och flera närliggande inställningar
var positiva efter 72-testers korrigering. Routern är fortfarande
research-only; endast registry V2 räknas som fryst forward-bevisning.

Ett exakt scope-placebo över alla `46 656` möjliga ommärkningar gav däremot
p-värde `0,079`. Senare V4-hörnfönster var generellt lönsamma även utan
away/total-routing (`+26,42%` ROI), så historiken bevisar inte att just
scope-identiteten orsakar edgen. Away/total behålls endast som en
förregistrerad forward-hypotes.

Med exakt samma corner/away/total-policy gav V3 `+14,37%` och V4 `+28,54%`
ROI. Paired bootstrap ger `97,01%` sannolikhet att V4 är bättre, men
skillnadsintervallet är `-0,64` till `+28,81` procentenheter och
74-testerskorrigeringen misslyckas. V4:s selektivitet är därför lovande men
fortfarande score-only.

V4:s EV är inte pålitlig i extremvärden. En 24-varianters threshold-audit
visar en positiv platå vid `5–7,5%` minimum-EV, men `9%+` blir instabilt och
`12,5%+` är negativt. Den frysta `7,5–25%`-gränsen behålls därför exakt; högre
beräknad EV får inte automatiskt större förtroende eller stake.

V4 är inte bara en generell corner-under-strategi. I samma universe gav alla
under `-3,10%`, alla over `-12,50%`, marknadsfavoriten `-8,05%` och longshot
`-7,31%`. Tre matchade random-placebos gav familjejusterade p-värden `0,0162`,
`0,0071` och `0,0384`. Det stödjer verklig historisk marknads-/sidoselektivitet
i modellen, men forward-settlement och CLV krävs fortfarande.

Promotion sker automatiskt först efter minst `300` settled bets och `150`
matchkluster, minst `80%` CLV-täckning, positiv genomsnittlig CLV, positiv
matchklustrad 95%-nedre gräns, korrigerat p-värde under `0,05` och noll
timing-/outcome-/duplicate-/feature-auditfel. Just nu har samtliga policys
status `insufficient_evidence`.

Produktionsautomation fångar T-3D, T-2D, T-1D och T-2H i det timvisa
matchmedvetna scheduler-jobbet. När en ännu ej fångad match finns inom två
timmar aktiveras femminuters-workflowen, som ensam äger T-30M och T-10M. Utan
en sådan match är femminuters-workflowen avstängd.

T-30M är en robust near-close fallback. Endast T-10M rapporteras som officiell
closing-CLV; T-30M lagras och rapporteras separat som fallback. En senare
giltig T-10M-snapshot ersätter automatiskt T-30M som canonical closing. Om
varken T-30M eller T-10M finns skapas ingen closing line från äldre snapshots.

T-12H är fortsatt manuell research. T-2H samlas nu i produktion men behåller
sin historiska researchklass i modellauditen. Horisontauditen visade att de
ursprungliga fyra fönstren endast täckte 17,15% av den historiska V3-modellens
val; med research-fönstren är jämförbar horisonttäckning 86,63%.

Samma audit för den exakta V6 corner/away+total-policyn gav `27/156`
historiska val (`17,31%`) i de fyra obligatoriska fönstren och `128/156`
(`82,05%`) med T-12H/T-2H. Historiken innehöll inga V6-val vid T-1D eller
T-10M, så dessa checkpoints är framtida diagnostik och får inte tillskrivas
den historiska ROI:n.

Simulerad tid får bara användas i dry-run. Alla capture-, scoring- och
settlementjobb stoppar om `--now` kombineras med en riktig write. Kontrollera
och reparera äldre derived snapshots med:

```bash
python scripts/forward_v2/invalidate_simulated_snapshots.py
python scripts/forward_v2/invalidate_simulated_snapshots.py --apply
```

Kommandot ändrar inte raw Kambi-payloads eller frysta predictions. Det markerar
endast berörda `market_snapshots` som ogiltiga och återbygger closing-data från
återstående giltiga prematchobservationer.

## Automation

`.github/workflows/` speglar originalets workflow-namn men kör V2-CLI-jobben.
Varje workflow pekar på ett isolerat V2-flöde och sätter `MONGODB_DB=ullebets_v2`.
Den delade runnern strippar workflowens inlagda `--dry-run`-flagga i write-mode, så samma workflow-definition kan användas både för live writes och för global emergency dry-run.


