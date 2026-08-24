# All-Model Shadow Journal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Beräkna, arkivera, rätta och pedagogiskt jämföra varje aktiv EV-formel och fryst modell vid varje giltig oddssnapshot utan att blanda ihop skuggobservationer med verkliga forward-val.

**Architecture:** Ett registerstyrt materialiseringslager normaliserar både V2 JS-runtimens formelvärden och immutable `ev_model_scores` till `formula_observations`. Ett separat rebuildbart resultatlager återanvänder settlement/CLV-domänen, och Read API aggregerar filtrerade resultat till `/api/v1/formula-performance`; `/modell` presenterar jämförelsen ovanför befintlig runtime-status.

**Tech Stack:** Python 3.11+, PyMongo, pandas/joblib, Node.js 24, TypeScript, React 19, TanStack Query, Vitest/Testing Library, GitHub Actions, Vercel.

**Spec:** `docs/superpowers/specs/2026-08-25-all-model-shadow-journal.md`

## Global Constraints

- Nya writes får endast ske mot `MONGODB_DB=ullebets_v2`; `app` och `ullebets_unibet` är read-only.
- `forward_bets` och frysta modellartefakter får inte muteras av skuggjournalen.
- Positivt EV betyder strikt `expected_roi_units > 0`; 1u är en virtuell insats, inte ett verkligt placerat spel.
- Snapshot-, score- och observationstiming måste vara strikt före kickoff.
- Out-of-domain ML-scorer arkiveras men exkluderas från insats, ROI, CLV-rankning och promotion evidence.
- Samma exakta input måste vara idempotent; ändrad immutable evidens måste hårdfela.
- Underlagsnivån `comparable` kräver minst 300 rättade observationer och 150 unika matcher.

---

### Task 1: Versionslåst formelregister och immutable observationsdomän

**Files:**
- Create: `models/ev/shadow_formula_registry_v1.json`
- Create: `src/ullebets_v2/formula_journal/__init__.py`
- Create: `src/ullebets_v2/formula_journal/registry.py`
- Create: `src/ullebets_v2/formula_journal/observations.py`
- Modify: `src/ullebets_v2/storage/collections.py`
- Create: `tests/v2/test_formula_journal_observations.py`

**Interfaces:**
- Consumes: JS-rader med `evDetails`; ML-rader från `ev_model_scores`.
- Produces: `load_formula_registry(path) -> dict`, `build_js_observation_docs(...) -> list[dict]`, `build_ml_observation_docs(...) -> list[dict]`, `persist_formula_observations(collection, docs) -> dict[str, int]`.

- [ ] **Step 1: Skriv failing tests för JS/ML-normalisering**

```python
def test_js_formula_values_become_independent_shadow_observations():
    docs = build_js_observation_docs(lines=[line_with_two_ev_details()], context=context(), runtime_sha256="a" * 64, registry=registry())
    assert {row["formula_id"] for row in docs} == {"js:evPct", "js:evPctLeagueAvg"}
    assert all(row["shadow_stake_units"] == 1.0 for row in docs)

def test_out_of_domain_ml_score_is_archived_without_stake():
    [doc] = build_ml_observation_docs(scores=[ml_score(valid=False)], registry=registry())
    assert doc["valid_for_comparison"] is False
    assert doc["shadow_stake_units"] == 0.0
```

- [ ] **Step 2: Kör testfilen och verifiera rött**

Run: `python -m pytest tests/v2/test_formula_journal_observations.py -q`
Expected: FAIL eftersom `ullebets_v2.formula_journal` saknas.

- [ ] **Step 3: Implementera registervalidering, sannolikhetskonvertering och stabila nycklar**

```python
def probability_from_ev(*, expected_roi_units: float, offered_odds: float) -> float:
    value = (1.0 + expected_roi_units) / offered_odds
    if not 0.0 <= value <= 1.0:
        raise ValueError("derived probability must be between zero and one")
    return value
```

Registerfilen ska lista JS-label/familj samt V2–V6 artifact/manifest/model-ID. Observationens SHA-256 ska beräknas från ett explicit immutable payload, utan `journaled_at`. Collection-konstanterna `FORMULA_OBSERVATIONS` och `FORMULA_RESULTS` ska samtidigt läggas till i den kanoniska collection-listan.

- [ ] **Step 4: Lägg till failing replay/conflict-tests och implementera `$setOnInsert`**

```python
def test_persistence_replays_identical_doc_and_rejects_changed_odds():
    assert persist_formula_observations(collection, [doc()])["inserted"] == 1
    assert persist_formula_observations(collection, [doc()])["existing"] == 1
    with pytest.raises(ImmutableFormulaObservationConflict):
        persist_formula_observations(collection, [doc(offered_odds=9.0)])
```

- [ ] **Step 5: Kör observationsdomänens tester**

Run: `python -m pytest tests/v2/test_formula_journal_observations.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add models/ev/shadow_formula_registry_v1.json src/ullebets_v2/formula_journal src/ullebets_v2/storage/collections.py tests/v2/test_formula_journal_observations.py
git commit -m "feat: add immutable all-model shadow observations"
```

### Task 2: Exakt snapshotmaterialisering och registerstyrd modellscoring

**Files:**
- Create: `src/ullebets_v2/formula_journal/materialize.py`
- Create: `scripts/forward_v2/materialize_formula_journal.py`
- Create: `scripts/forward_v2/score_registered_shadow_models.py`
- Create: `tests/v2/test_formula_journal_materialize.py`
- Create: `tests/v2/test_registered_shadow_model_runner.py`
- Modify: `.github/workflows/v2-odds-scheduler.yml`
- Modify: `.github/workflows/run-unibet-closing.yml`
- Modify: `.github/workflows/ev-shadow-forward.yml`
- Modify: `tests/v2/test_automation_contract.py`

**Interfaces:**
- Consumes: `market_snapshots`, fixtures, V2 support/history, `ev_model_scores`, `shadow_formula_registry_v1.json`.
- Produces: `materialize_formula_observations(database, oracle, registry, now, match_keys=None, dry_run=False) -> dict` och en CLI som skriver audit/job/health-status.

- [ ] **Step 1: Skriv failing test för två checkpoints och samtliga emitterade JS-värden**

```python
def test_materializer_keeps_same_market_at_two_checkpoints_separate():
    summary = materialize_formula_observations(database=db_with_t3d_and_t2h(), oracle=FakeOracle(), registry=registry(), now=NOW)
    assert summary["js_observations"] == 4
    assert database[FORMULA_OBSERVATIONS].distinct("snapshot_label") == ["T_MINUS_2H", "T_MINUS_3D"]
```

- [ ] **Step 2: Kör materialiseringstesten och verifiera rött**

Run: `python -m pytest tests/v2/test_formula_journal_materialize.py -q`
Expected: FAIL eftersom materialiseringstjänsten saknas.

- [ ] **Step 3: Implementera gruppning per match och exakt snapshot**

Materialiseraren ska bygga odds-tuples direkt från sparade `market_snapshots`, skapa en `V2JsModelOracle` med V2 read-databasen, normalisera samtliga numeriska `evDetails` och därefter normalisera registrerade `ev_model_scores`. Den får inte refetcha odds.

- [ ] **Step 4: Skriv failing test för registerrunnerns fem artefakter och felpropagering**

```python
def test_runner_invokes_every_registered_frozen_model_and_fails_on_child_error(monkeypatch):
    completed = run_registered_models(registry=registry_with_v2_to_v6(), repo_root=ROOT, dry_run=True, runner=fake_runner)
    assert [row["model_id"] for row in completed["models"]] == ["v2", "v3", "v4", "v5", "v6"]
    with pytest.raises(RuntimeError, match="v4"):
        run_registered_models(registry=registry_with_v2_to_v6(), repo_root=ROOT, dry_run=True, runner=failing_v4_runner)
```

- [ ] **Step 5: Implementera CLI-runner och workflowkontrakt**

Runnern ska anropa befintlig scorer med `--score-only` för varje registerrad och endast koppla V6:s frysta online-policy. Workflows ska köra runnern följt av journalmaterialisering efter lyckad oddscapture.

- [ ] **Step 6: Kör fokuserade tester**

Run: `python -m pytest tests/v2/test_formula_journal_materialize.py tests/v2/test_registered_shadow_model_runner.py tests/v2/test_automation_contract.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/ullebets_v2/formula_journal/materialize.py scripts/forward_v2/materialize_formula_journal.py scripts/forward_v2/score_registered_shadow_models.py tests/v2/test_formula_journal_materialize.py tests/v2/test_registered_shadow_model_runner.py tests/v2/test_automation_contract.py .github/workflows
git commit -m "feat: score every registered formula at each checkpoint"
```

### Task 3: Gemensam rättning, CLV och rebuildbart resultatlager

**Files:**
- Create: `src/ullebets_v2/formula_journal/results.py`
- Create: `scripts/forward_v2/refresh_formula_results.py`
- Create: `tests/v2/test_formula_journal_results.py`
- Modify: `.github/workflows/postmatch-enrichment.yml`
- Modify: `tests/v2/test_automation_contract.py`

**Interfaces:**
- Consumes: positiva, jämförelsegiltiga `formula_observations`, canonical actuals, closing lines och market snapshots.
- Produces: `build_formula_result_docs(...) -> list[dict]`, `refresh_formula_results(database, now, dry_run=False) -> dict`.

- [ ] **Step 1: Skriv failing rättnings- och CLV-test**

```python
def test_positive_shadow_observation_is_settled_and_gets_official_clv():
    [row] = build_formula_result_docs(observations=[observation(direction="over", line=4.5, odds=2.0)], actuals=[actual(6)], closing_lines=[closing(over_odds=1.8, official=True)], refreshed_at=NOW)
    assert row["settlement_result"] == "win"
    assert row["pnl_units"] == 1.0
    assert row["official_clv"] is True
    assert row["beat_closing_line"] is True
```

- [ ] **Step 2: Kör resultatlagrets test och verifiera rött**

Run: `python -m pytest tests/v2/test_formula_journal_results.py -q`
Expected: FAIL eftersom resultatlagret saknas.

- [ ] **Step 3: Implementera adapter till befintlig settlement/CLV-domän**

Adapterfält ska använda `observation_key` som tracking-identitet, `shadow_stake_units` som stake och samma `settle_line`/closing lookup som befintliga forward-resultat. Resultatdokument får uppdateras idempotent eftersom de är härledda, men källobservationen får aldrig ändras.

- [ ] **Step 4: Implementera CLI och postmatch-hook**

CLI:n ska skriva job/audit/health-mått, stödja `--dry-run`, och postmatch-workflow ska köra refresh efter canonical statistik och closing har uppdaterats.

- [ ] **Step 5: Kör rättnings- och automationskontrakt**

Run: `python -m pytest tests/v2/test_formula_journal_results.py tests/v2/test_automation_contract.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/ullebets_v2/formula_journal/results.py scripts/forward_v2/refresh_formula_results.py tests/v2/test_formula_journal_results.py tests/v2/test_automation_contract.py .github/workflows/postmatch-enrichment.yml
git commit -m "feat: settle shadow formula observations with clv"
```

### Task 4: Mongoindex och filtrerbart jämförelse-API

**Files:**
- Modify: `src/ullebets_v2/storage/indexes.py`
- Create: `src/ullebets_v2/read_api/formula_performance.py`
- Modify: `src/ullebets_v2/read_api/http.py`
- Create: `tests/v2/test_formula_performance_api.py`
- Modify: `tests/v2/test_parity_framework.py`

**Interfaces:**
- Consumes: `formula_observations` och `formula_results`.
- Produces: `read_formula_performance(database, *, filters..., limit=100, offset=0) -> dict` och GET `/api/v1/formula-performance`.

- [ ] **Step 1: Skriv failing API-test för filter, ROI, CLV, Brier och underlagsnivå**

```python
def test_formula_performance_filters_checkpoint_and_reports_clustered_evidence():
    status, payload = dispatch_get(database(), "/api/v1/formula-performance", {"stat": ["cornerKicks"], "checkpoint": ["T_MINUS_2H"]})
    assert status == 200
    assert payload["summary"]["settled"] == 2
    assert payload["groups"][0]["uniqueMatches"] == 2
    assert payload["groups"][0]["evidenceLevel"] == "early"
    assert payload["groups"][0]["roiPct"] == 50.0
```

- [ ] **Step 2: Kör API-testet och verifiera 404/rött**

Run: `python -m pytest tests/v2/test_formula_performance_api.py -q`
Expected: FAIL med 404 eller saknad modul.

- [ ] **Step 3: Implementera query, metriker och stabil sortering**

Filtren ska vara `formula`, `family`, `stat`, `scope`, `period`, `direction`, `league`, `checkpoint`, `status` och `mode=positive_ev|all_scores`. Defaultsortering är rättade observationer fallande, sedan formellabel och ID; inte ROI fallande.

- [ ] **Step 4: Lägg till collection constants och indexplan**

`formula_observations` får unikt index på `observation_key` samt filterindex; `formula_results` får unikt index på `observation_key` samt index för status/formel/dimensioner. Collection-konstanterna från Task 1 ska importeras och användas.

- [ ] **Step 5: Kör API- och indexkontrakten**

Run: `python -m pytest tests/v2/test_formula_performance_api.py tests/v2/test_parity_framework.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/ullebets_v2/storage src/ullebets_v2/read_api tests/v2/test_formula_performance_api.py tests/v2/test_parity_framework.py
git commit -m "feat: expose filtered shadow formula performance"
```

### Task 5: Pedagogisk modelljämförelse i UI

**Files:**
- Modify: `frontend/src/domain/types.ts`
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/data/queries.ts`
- Create: `frontend/src/data/formula-performance-query.ts`
- Create: `frontend/src/components/FormulaPerformanceFilters.tsx`
- Create: `frontend/src/components/FormulaPerformanceTable.tsx`
- Modify: `frontend/src/pages/ModelPage.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/src/app/formula-performance.test.tsx`

**Interfaces:**
- Consumes: `FormulaPerformanceResponse` från `/api/v1/formula-performance` och URL-parametrar.
- Produces: `useFormulaPerformance(query)`, filterkomponent och responsiv tabell på `/modell`.

- [ ] **Step 1: Skriv failing UI-test för pedagogisk summering och URL-filter**

```tsx
it('shows comparable formula metrics and writes stat filter to the URL', async () => {
  renderApp('/modell', apiFixture());
  expect(await screen.findByRole('heading', { name: 'Modelljämförelse' })).toBeVisible();
  expect(screen.getByText('12,5 %')).toBeVisible();
  await userEvent.selectOptions(screen.getByLabelText('Statistik'), 'cornerKicks');
  expect(window.location.search).toContain('stat=cornerKicks');
});
```

- [ ] **Step 2: Kör UI-testet med Node 24 och verifiera rött**

Run: `$env:PATH='C:\Users\ryd\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH; npm test -- --run src/app/formula-performance.test.tsx`
Expected: FAIL eftersom jämförelsekomponenterna saknas.

- [ ] **Step 3: Implementera typer, query hook och URL-parser**

`FormulaPerformanceResponse` ska vara explicit typad för summary, facets, groups och page. Query-parametrar ska använda samma namn som Read API och behålla delad `date` utan att skicka den till performance-endpointen.

- [ ] **Step 4: Implementera sammanfattningsrutor, filter och tabell**

Tabellen visar `Formel`, `Underlag`, `ROI`, `CLV`, `Slår closing`, `Brier`; badges översätter `early/growing/comparable` till `Tidigt/Växande/Jämförbart`. Nullvärden visas som `—`, aldrig som noll.

- [ ] **Step 5: Lägg till responsiv CSS och tillgänglighetskontrakt**

På under 760px blir filter en kolumn och varje tabellrad får etiketter via `data-label`; varje select har synlig label och laddning/fel/tomt använder `StateNotice`.

- [ ] **Step 6: Kör fokuserat test, hela frontendsviten och build**

Run: `$env:PATH='C:\Users\ryd\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH; npm test -- --run src/app/formula-performance.test.tsx; npm test -- --run; npm run build`
Expected: Fokustest PASS, hela Vitest-sviten PASS och Vite build PASS.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src
git commit -m "feat: add pedagogical formula comparison ui"
```

### Task 6: Full verifiering, runtime recovery och evidensdokumentation

**Files:**
- Modify: `docs/work-log.md`
- Modify: `docs/app-readiness-checklist.md` endast om komplett aktuell evidens ändrar readiness
- Modify: `docs/v2-backend-verification-status.md`
- Modify: `docs/ev-model-experiments.md`

**Interfaces:**
- Consumes: samtliga leverabler från Task 1–5.
- Produces: verifierad lokal release, V2 dry-run/production recovery-mått och spårbar dokumentation.

- [ ] **Step 1: Kör full backendsvit**

Run: `python -m pytest tests/v2 -q`
Expected: Samtliga tester PASS; endast redan känd, dokumenterad cache-warning tolereras.

- [ ] **Step 2: Kör full frontendverifiering med Node 24**

Run: `$env:PATH='C:\Users\ryd\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH; npm test -- --run; npm run build`
Expected: Samtliga tester och build PASS.

- [ ] **Step 3: Kör registerscoring/materialisering/resultat i dry-run mot V2**

Run: `python scripts/forward_v2/score_registered_shadow_models.py --repo-root . --dry-run; python scripts/forward_v2/materialize_formula_journal.py --repo-root . --dry-run; python scripts/forward_v2/refresh_formula_results.py --repo-root . --dry-run`
Expected: Alla registermodeller lyckas, ingen legacy-write, och summaries innehåller exakta input/output/conflict-counts.

- [ ] **Step 4: Kör idempotent recovery-write mot endast `ullebets_v2` och verifiera API**

Run: samma tre CLI utan `--dry-run`, därefter en omkörning av materialisering/resultat och GET `/api/v1/formula-performance?limit=5` mot isolerad Read API-process.
Expected: första körningen kan infoga saknade rader; replay visar endast `existing`/oförändrade resultat, noll conflicts, och API returnerar 200 med aktuella counts.

- [ ] **Step 5: Gör visuell QA på desktop och mobil**

Öppna `/modell`, verifiera standardvy och minst ett stat/checkpoint-filter, spara screenshots och inspektera dem för läsbar hierarki, overflow, tomma värden och korrekta underlagsbadges.

- [ ] **Step 6: Uppdatera evidensdokument**

Arbetsloggen ska ange exakta commands, tester, DB-counts, conflicts, rättade/öppna, CLV coverage, kvarvarande `UNPROVEN` och nästa berättigade test. Experimentloggen ska registrera journalen som observationsinfrastruktur, inte som ny modell eller bevisad edge.

- [ ] **Step 7: Commit**

```powershell
git add docs/work-log.md docs/app-readiness-checklist.md docs/v2-backend-verification-status.md docs/ev-model-experiments.md
git commit -m "docs: record all-model shadow journal evidence"
```

- [ ] **Step 8: Integrera och verifiera leverans**

Rebase/merge till `main`, pusha `origin/main`, verifiera remote SHA, Vercel deployment SHA/status och GET `/api/v1/formula-performance` samt `/modell` på live-host. Rapportera lokalt, Git och hosted runtime som tre separata evidensnivåer.
