# Matchup Clarity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Göra matchupöversikten snabb att tolka, separera predictor- och marknadsutfall och ersätta synliga statusord med tillgängliga ikoner.

**Architecture:** Utöka den rena backendaggregatorn med baseline- och poängintervallsdiagnostik, exponera det befintliga API-svaret med tydliga TypeScript-typer och bygg sedan små, återanvändbara presenterande frontendkomponenter. Kortets primära yta förblir kompakt medan `details` innehåller full predictor-, marknads- och oddsproveniens.

**Tech Stack:** Python 3, pytest, React 19, TypeScript 6, lucide-react, Testing Library/Vitest, CSS.

---

### Task 1: Lås predictor-metrikens kontrakt

**Files:**
- Modify: `tests/v2/test_matchup_evaluation_metrics.py`
- Modify: `src/ullebets_v2/matchup_evaluation/metrics.py`

1. Lägg till ett misslyckande test för median signerat avstånd, bästa konstanta riktning och lift i procentenheter.
2. Lägg till ett misslyckande test för fasta score buckets inklusive tomt intervall och push-exkludering ur träffprocenten.
3. Kör `python -m pytest tests/v2/test_matchup_evaluation_metrics.py -q` och verifiera att de nya assertionerna faller.
4. Implementera deterministiska hjälpfunktioner och svarsfält utan att ändra befintliga nämnare.
5. Kör samma test och verifiera grönt.

### Task 2: Lås API- och frontendtyper

**Files:**
- Modify: `tests/v2/test_read_api_contracts.py`
- Modify: `frontend/src/domain/types.ts`

1. Lägg till kontraktsassertioner för de nya predictor- och bucketfälten.
2. Kör endast relevant API-kontraktstest och verifiera rött före implementering om mappning saknas.
3. Utöka `MatchupEvaluationResponse` med explicita typer för baseline och score buckets.
4. Kör relevant backendtest samt `npm run typecheck --prefix frontend`.

### Task 3: Bygg en tillgänglig ikonstatus

**Files:**
- Create: `frontend/src/components/VerdictIcon.tsx`
- Modify: `frontend/src/app/matchup-evaluation.test.tsx`

1. Ändra testet så att det kräver `Prediktor: träff` och `Marknad: vunnen` via tillgängliga namn men avvisar synlig statusordstext.
2. Kör `npm test --prefix frontend -- --run src/app/matchup-evaluation.test.tsx` och verifiera rött.
3. Implementera lucide-baserad ikonmappning för hit/miss/push/pending/missing med `aria-label` och tooltip.
4. Kör testet igen.

### Task 4: Förenkla matchupkortet och bevara detaljer

**Files:**
- Modify: `frontend/src/components/SignalCard.tsx`
- Modify: `frontend/src/components/MatchupEvaluation.tsx`
- Modify: `frontend/src/components/MarketBiasIndicator.tsx`
- Modify: `frontend/src/pages/OverviewPage.tsx`
- Modify: `frontend/src/app/matchup-evaluation.test.tsx`

1. Lägg testassertioner för `Rankingpoäng`, `#1 av 1`, predictortröskel, faktiskt utfall, signerat avstånd och expanderbar detalj.
2. Kör det riktade frontendtestet och verifiera rött.
3. Byt primäretikett, skicka ranktotal från respektive filtrerad riktningslista och flytta detaljinnehåll till `details`.
4. Byt den missvisande rubriken `Mot Unibet-linan` till en presentation som tydligt skiljer lagprofil från predictortröskel.
5. Kör det riktade frontendtestet igen.

### Task 5: Dela sammanfattningen och visa rankingdiagnostik

**Files:**
- Modify: `frontend/src/pages/OverviewPage.tsx`
- Modify: `frontend/src/styles/live-data.css`
- Modify: `frontend/src/app/matchup-evaluation.test.tsx`

1. Lägg testassertioner för separata `Prediktor`- och `Spelbara marknader`-sektioner, baseline-lift, closingtäckning och score bucket med observationstal.
2. Kör testet och verifiera rött.
3. Implementera kompakt tvådelad sammanfattning och expanderbar rankingdiagnostik.
4. Lägg responsiva och tillgängliga stilar för statusikoner, detaljexpander och diagnostik.
5. Kör testet igen.

### Task 6: Slutverifiera och dokumentera

**Files:**
- Modify: `docs/work-log.md`
- Modify: `docs/app-readiness-checklist.md` endast om verifierad readiness faktiskt ändras

1. Kör `python -m pytest tests/v2/test_matchup_evaluation_metrics.py tests/v2/test_read_api_contracts.py -q` eller smalare markerade kontraktstest om hela filen är oproportionerlig.
2. Kör `npm test --prefix frontend -- --run src/app/matchup-evaluation.test.tsx`.
3. Kör `npm run typecheck --prefix frontend`, `npm run lint --prefix frontend` och `npm run build --prefix frontend`.
4. Uppdatera arbetsloggen med exakta kommandon, resultat och kvarvarande forwardbevis.
5. Kontrollera `git diff --check`, bevara `.playwright-cli/`, committa och pusha `main`.
6. Verifiera att `origin/main` pekar på den pushade committen; kalla inte detta liveverifierat utan separat hostingbevis.
