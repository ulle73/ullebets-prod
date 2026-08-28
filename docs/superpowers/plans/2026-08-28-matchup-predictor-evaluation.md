# Matchup Predictor Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an immutable T-1D matchup journal that corrects every resolvable predictor context, evaluates exact comparable markets separately, exposes honest aggregate quality metrics, and renders predictor, market, movement, and CLV states in the product.

**Architecture:** Keep replaceable `matchups_score` rows as the upcoming ranking surface and add two independent V2 collections: immutable `matchup_observations` and derived `matchup_results`. A T-1D materializer freezes one selected direction per exact context and optionally one deterministic 1.80-2.20 offer; post-match settlement joins canonical actuals and exact-line T-10/T-30 closing. A pure-Python metrics service feeds a dedicated read endpoint, while dashboard cards receive nested evaluation summaries.

**Tech Stack:** Python 3.13, PyMongo/CosmosDB Mongo API, pytest, React 19, TypeScript, TanStack Query, Vitest/Testing Library, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-28-matchup-predictor-evaluation-design.md`

## Global Constraints

- `app` and `ullebets_unibet` remain read-only references. All new state is stored independently in `ullebets_v2`.
- Every V2 write hard-fails unless `MONGODB_DB=ullebets_v2`.
- Raw source payloads, canonical actuals, frozen scores, and first-capture market evidence are immutable.
- Predictor results, market results, ROI, and CLV use exact match, stat, period, scope, direction, and policy identities.
- T-1D is the primary and only forward-evaluation anchor in version 1. Late fixtures may be displayed but cannot enter the forward sample.
- Comparable-market odds are inclusive from 1.80 through 2.20 and are selected nearest 2.00 deterministically.
- T-10 is the preferred accepted closing; T-30 is the accepted fallback.
- Same-line price CLV never substitutes a different closing line.
- Matchup evaluation cannot affect V6 selection, forward bets, model ROI, model CLV, or promotion policy.
- Public URLs remain provider-neutral.
- Existing `.playwright-cli/` content is user-owned and must not be added, removed, or committed.

## File Structure

### New backend files

- `src/ullebets_v2/matchup_evaluation/__init__.py`: public constants and service exports.
- `src/ullebets_v2/matchup_evaluation/observations.py`: selected-direction identity, exact offer selection, immutable document construction, fingerprints, and observation persistence.
- `src/ullebets_v2/matchup_evaluation/materialize.py`: database reads and T-1D observation orchestration.
- `src/ullebets_v2/matchup_evaluation/results.py`: canonical settlement, exact-line closing/CLV, terminal conflict checks, and result refresh.
- `src/ullebets_v2/matchup_evaluation/legacy.py`: bounded conversion of settled pre-journal rows into immutable descriptive evidence.
- `src/ullebets_v2/matchup_evaluation/metrics.py`: deduplicated predictor and market aggregates, score bands, rank correlation, and match-cluster confidence intervals.
- `scripts/forward_v2/materialize_matchup_observations.py`: safe T-1D CLI with match-key scoping and dry-run support.
- `scripts/forward_v2/refresh_matchup_results.py`: safe post-match refresh CLI with optional date range.
- `scripts/forward_v2/backfill_legacy_matchup_evaluation.py`: bounded, idempotent descriptive backfill without legacy-source writes.
- `tests/v2/test_matchup_evaluation_observations.py`: observation identity, selection, timing, and immutability.
- `tests/v2/test_matchup_evaluation_results.py`: predictor/market/closing settlement and immutable terminal results.
- `tests/v2/test_matchup_evaluation_legacy.py`: direction deduplication, descriptive classification, and idempotent bounded backfill.
- `tests/v2/test_matchup_evaluation_metrics.py`: denominators, bands, lift, correlation, intervals, and evidence gates.
- `frontend/src/components/MatchupEvaluation.tsx`: predictor and market result rows plus accessible market-detail trigger.
- `frontend/src/app/matchup-evaluation.fixtures.ts`: complete dashboard and aggregate test response maps.
- `frontend/src/app/matchup-evaluation.test.tsx`: overview summaries, card states, movement panel, and accessibility.

### Existing files to modify

- `src/ullebets_v2/storage/collections.py`: register `MATCHUP_OBSERVATIONS` and `MATCHUP_RESULTS`.
- `src/ullebets_v2/storage/indexes.py`: unique identity and read-path indexes.
- `src/ullebets_v2/enrichment/service.py`: identify unresolved matchup observation matches safely.
- `scripts/forward_v2/ingest_match_enrichment.py`: add unresolved-matchup recovery targeting.
- `src/ullebets_v2/read_api/service.py`: join evaluation state into cards and return aggregate metrics.
- `src/ullebets_v2/read_api/http.py`: register `/api/v1/matchups/evaluation`.
- `tests/v2/test_config_and_safety.py`: collection and index contract.
- `tests/v2/test_read_api.py`: card evaluation joins.
- `tests/v2/test_read_api_contracts.py`: aggregate route and filter contract.
- `tests/v2/test_automation_contract.py`: T-1D and post-match command ordering.
- `.github/workflows/v2-odds-scheduler.yml`: materialize due T-1D matchup observations even when zero odds rows are written.
- `.github/workflows/run-unibet-odds-checkpoints.yml`: provide the same manual/dry-run path.
- `.github/workflows/ev-shadow-settlement.yml`: recover and refresh new matchup evidence after enrichment.
- `.github/workflows/enrich-matchups-results.yml`: retain legacy settlement and refresh new results for the requested range.
- `frontend/src/domain/types.ts`: nested evaluation and aggregate response types.
- `frontend/src/data/api.ts`: aggregate query and fetcher.
- `frontend/src/data/queries.ts`: aggregate query hook.
- `frontend/src/components/OddsMovement.tsx`: accept a shared exact-market movement source used by Auto and matchups.
- `frontend/src/components/SignalCard.tsx`: render `MatchupEvaluation`.
- `frontend/src/pages/OverviewPage.tsx`: load filters and independent predictor/market summaries.
- `frontend/src/styles/live-data.css`: matchup evaluation and responsive panel styling.
- `docs/work-log.md`: exact implementation and verification evidence.
- `docs/app-readiness-checklist.md`: update only statements proved by current commands or hosted runtime.
- `docs/v2-backend-verification-status.md`: detailed new collection and lifecycle acceptance state.

---

### Task 1: Register storage and immutable observation primitives

**Files:**
- Create: `src/ullebets_v2/matchup_evaluation/__init__.py`
- Create: `src/ullebets_v2/matchup_evaluation/observations.py`
- Modify: `src/ullebets_v2/storage/collections.py:26-46`
- Modify: `src/ullebets_v2/storage/indexes.py:7-49,220-237`
- Test: `tests/v2/test_config_and_safety.py`
- Test: `tests/v2/test_matchup_evaluation_observations.py`

**Interfaces:**
- Produces: `MATCHUP_EVALUATION_POLICY_VERSION = "matchup-eval-v1"`.
- Produces: `observation_key(match_key: str, stat_key: str, period: str, scope: str) -> str`.
- Produces: `observation_fingerprint(doc: dict[str, Any]) -> str`.
- Produces: `persist_matchup_observations(collection: Any, docs: Iterable[dict[str, Any]]) -> dict[str, int]`.
- Produces collections `matchup_observations` and `matchup_results` for later tasks.

- [ ] **Step 1: Write failing storage and immutability tests**

```python
from copy import deepcopy

import pytest

from ullebets_v2.matchup_evaluation.observations import (
    ImmutableMatchupObservationConflict,
    observation_fingerprint,
    observation_key,
    persist_matchup_observations,
)
from ullebets_v2.storage.collections import MATCHUP_OBSERVATIONS, MATCHUP_RESULTS
from ullebets_v2.storage.indexes import build_core_index_plan
from tests.v2.test_teamprofiles import FakeCollection


def frozen_observation() -> dict:
    doc = {
        "observation_key": "matchup-eval-v1|m1|cornerKicks|ALL|total|T_MINUS_1D",
        "policy_version": "matchup-eval-v1",
        "checkpoint_label": "T_MINUS_1D",
        "match_key": "m1",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "total",
        "selected_direction": "over",
        "score": 91.0,
        "league_baseline": 10.7,
    }
    doc["observation_fingerprint_sha256"] = observation_fingerprint(doc)
    return doc


def test_matchup_evaluation_collections_have_unique_identities() -> None:
    plans = {row["collection"]: row["indexes"] for row in build_core_index_plan()}
    assert any(row["keys"] == [("observation_key", 1)] and row["unique"] for row in plans[MATCHUP_OBSERVATIONS])
    assert any(row["keys"] == [("observation_key", 1)] and row["unique"] for row in plans[MATCHUP_RESULTS])


def test_observation_identity_is_context_scoped_and_versioned() -> None:
    assert observation_key("match-1", "cornerKicks", "ALL", "total") == (
        "matchup-eval-v1|match-1|cornerKicks|ALL|total|T_MINUS_1D"
    )


def test_immutable_observation_replay_reuses_exact_evidence() -> None:
    fake_collection = FakeCollection([])
    doc = frozen_observation()
    first = persist_matchup_observations(fake_collection, [doc])
    second = persist_matchup_observations(fake_collection, [deepcopy(doc)])
    assert first == {"inserted": 1, "existing": 0, "conflicts": 0}
    assert second == {"inserted": 0, "existing": 1, "conflicts": 0}


def test_immutable_observation_rejects_changed_score() -> None:
    fake_collection = FakeCollection([])
    doc = frozen_observation()
    persist_matchup_observations(fake_collection, [doc])
    changed = deepcopy(doc)
    changed["score"] = 88.1
    changed["observation_fingerprint_sha256"] = observation_fingerprint(changed)
    with pytest.raises(ImmutableMatchupObservationConflict):
        persist_matchup_observations(fake_collection, [changed])
```

- [ ] **Step 2: Run the focused tests and verify the missing-module failure**

Run:

```powershell
python -m pytest tests/v2/test_config_and_safety.py tests/v2/test_matchup_evaluation_observations.py -q
```

Expected: FAIL because `ullebets_v2.matchup_evaluation` and the collection constants do not exist.

- [ ] **Step 3: Add canonical collection names and indexes**

```python
# storage/collections.py
MATCHUP_OBSERVATIONS = "matchup_observations"
MATCHUP_RESULTS = "matchup_results"
```

Add both names to `CANONICAL_COLLECTION_NAMES`. Add these plans to `build_core_index_plan()`:

```python
{
    "collection": MATCHUP_OBSERVATIONS,
    "indexes": [
        {"keys": [("observation_key", 1)], "name": "matchup_observation_key_unique", "unique": True},
        {"keys": [("match_key", 1), ("checkpoint_label", 1)], "name": "matchup_observation_match_checkpoint"},
        {"keys": [("fixture_date_stockholm", 1), ("selected_direction", 1), ("score", -1)], "name": "matchup_observation_date_direction_score"},
    ],
},
{
    "collection": MATCHUP_RESULTS,
    "indexes": [
        {"keys": [("observation_key", 1)], "name": "matchup_result_observation_unique", "unique": True},
        {"keys": [("lifecycle_status", 1), ("match_start_time", 1)], "name": "matchup_result_lifecycle_start"},
        {"keys": [("valid_for_predictor", 1), ("stat_key", 1), ("period", 1), ("scope", 1)], "name": "matchup_predictor_dimensions"},
        {"keys": [("valid_for_market", 1), ("closing_quality", 1), ("stat_key", 1)], "name": "matchup_market_dimensions"},
    ],
},
```

- [ ] **Step 4: Implement canonical fingerprints and insert-only persistence**

```python
MATCHUP_EVALUATION_POLICY_VERSION = "matchup-eval-v1"
CHECKPOINT_LABEL = "T_MINUS_1D"
FINGERPRINT_EXCLUDED_FIELDS = {"_id", "journaled_at", "observation_fingerprint_sha256"}


class ImmutableMatchupObservationConflict(RuntimeError):
    pass


def observation_key(match_key: str, stat_key: str, period: str, scope: str) -> str:
    values = [match_key, stat_key, period, scope]
    if any(not str(value).strip() for value in values):
        raise ValueError("matchup observation identity requires match, stat, period, and scope")
    return "|".join([MATCHUP_EVALUATION_POLICY_VERSION, *map(str, values), CHECKPOINT_LABEL])


def observation_fingerprint(doc: dict[str, Any]) -> str:
    payload = {key: value for key, value in doc.items() if key not in FINGERPRINT_EXCLUDED_FIELDS}
    encoded = json.dumps(_json_value(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

Implement `persist_matchup_observations()` with batched `UpdateOne({"observation_key": key}, {"$setOnInsert": doc}, upsert=True)`, stored-fingerprint validation, exact replay counting, and race re-reads matching the proven formula-journal persistence pattern. Never use `$set` for observation evidence.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
python -m pytest tests/v2/test_config_and_safety.py tests/v2/test_matchup_evaluation_observations.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the storage boundary**

```powershell
git add src/ullebets_v2/storage/collections.py src/ullebets_v2/storage/indexes.py src/ullebets_v2/matchup_evaluation tests/v2/test_config_and_safety.py tests/v2/test_matchup_evaluation_observations.py
git commit -m "feat: add immutable matchup observation storage"
```

---

### Task 2: Materialize one T-1D predictor direction and comparable offer

**Files:**
- Modify: `src/ullebets_v2/matchup_evaluation/observations.py`
- Create: `src/ullebets_v2/matchup_evaluation/materialize.py`
- Create: `scripts/forward_v2/materialize_matchup_observations.py`
- Modify: `tests/v2/test_matchup_evaluation_observations.py`

**Interfaces:**
- Consumes: `build_matchups_score_docs` from `src/ullebets_v2/matchups/service.py`.
- Consumes: `MATCHUP_OBSERVATIONS`, `MARKET_SNAPSHOTS`, `FIXTURES_CANONICAL`, and `TEAMPROFILES`.
- Produces: `select_comparable_offer(snapshot_rows: Iterable[dict[str, Any]], direction: str) -> dict[str, Any] | None`.
- Produces: `build_matchup_observation_docs(*, fixture: dict[str, Any], matchup_rows: list[dict[str, Any]], market_snapshot_rows: list[dict[str, Any]], captured_at: datetime) -> list[dict[str, Any]]`.
- Produces: `materialize_matchup_observations(*, database: Any, match_keys: Iterable[str], captured_at: datetime, dry_run: bool = False) -> dict[str, Any]`.

- [ ] **Step 1: Add failing direction, market, timing, and no-market tests**

```python
T_MINUS_1D = datetime(2026, 8, 31, 18, 0, tzinfo=UTC)


def fixture(start_time: str = "2026-09-01T18:00:00Z") -> dict:
    return {
        "match_key": "m1",
        "fixture_date_stockholm": "2026-09-01",
        "start_time": start_time,
        "league_key": "league-a",
        "home_team_name": "Home FC",
        "away_team_name": "Away FC",
    }


def matchup(*, condition: str, score: float) -> dict:
    return {
        "match_key": "m1",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "total",
        "condition": condition,
        "score": score,
        "rank_position": 1,
        "forecast": {"leagueBaseline": 10.7},
        "ranking_method": "rolling_12_weighted_45d",
        "ranking_window_matches": 12,
        "ranking_recency_half_life_days": 45.0,
    }


def snapshot(*, offer_key: str, line: float, over_odds: float, under_odds: float) -> dict:
    return {
        "match_key": "m1",
        "offer_key": offer_key,
        "snapshot_key": f"m1|{offer_key}|T_MINUS_1D",
        "snapshot_label": "T_MINUS_1D",
        "snapshot_time": T_MINUS_1D,
        "match_start_time": datetime(2026, 9, 1, 18, 0, tzinfo=UTC),
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "total",
        "line": line,
        "over_odds": over_odds,
        "under_odds": under_odds,
        "invalid_for_model": False,
    }


def test_selects_higher_direction_once_per_context() -> None:
    docs = build_matchup_observation_docs(
        fixture=fixture(start_time="2026-09-01T18:00:00Z"),
        matchup_rows=[matchup(condition="over", score=82.0), matchup(condition="under", score=18.0)],
        market_snapshot_rows=[],
        captured_at=datetime(2026, 8, 31, 18, 0, tzinfo=UTC),
    )
    assert len(docs) == 1
    assert docs[0]["selected_direction"] == "over"
    assert docs[0]["market_eligibility"] == "no_exact_market"
    assert docs[0]["valid_for_predictor"] is True


def test_equal_scores_are_audited_but_not_predictor_eligible() -> None:
    docs = build_matchup_observation_docs(
        fixture=fixture(),
        matchup_rows=[matchup(condition="over", score=50.0), matchup(condition="under", score=50.0)],
        market_snapshot_rows=[],
        captured_at=T_MINUS_1D,
    )
    assert docs[0]["selected_direction"] is None
    assert docs[0]["exclusion_reason"] == "direction_tie"


def test_comparable_offer_uses_inclusive_band_and_stable_ties() -> None:
    selected = select_comparable_offer(
        [
            snapshot(offer_key="z", line=10.5, over_odds=1.80, under_odds=2.05),
            snapshot(offer_key="b", line=11.5, over_odds=2.02, under_odds=1.86),
            snapshot(offer_key="a", line=12.5, over_odds=1.98, under_odds=1.90),
            snapshot(offer_key="x", line=13.5, over_odds=2.20, under_odds=1.75),
        ],
        direction="over",
    )
    assert selected["offer_key"] == "a"


def test_rejects_non_t1d_or_late_capture() -> None:
    docs = build_matchup_observation_docs(
        fixture=fixture(start_time="2026-09-01T18:00:00Z"),
        matchup_rows=[matchup(condition="over", score=80.0), matchup(condition="under", score=20.0)],
        market_snapshot_rows=[],
        captured_at=datetime(2026, 9, 1, 4, 0, tzinfo=UTC),
    )
    assert docs[0]["valid_for_predictor"] is False
    assert docs[0]["exclusion_reason"] == "outside_t1d_window"
```

- [ ] **Step 2: Run tests and verify missing behavior**

Run:

```powershell
python -m pytest tests/v2/test_matchup_evaluation_observations.py -q
```

Expected: FAIL because selection and materialization functions do not exist.

- [ ] **Step 3: Implement exact direction and offer selection**

```python
def select_comparable_offer(snapshot_rows: Iterable[dict[str, Any]], direction: str) -> dict[str, Any] | None:
    if direction not in {"over", "under"}:
        return None
    candidates: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for source in snapshot_rows:
        row = dict(source)
        if row.get("snapshot_label") != CHECKPOINT_LABEL or row.get("invalid_for_model") is True:
            continue
        line = _finite_float(row.get("line"))
        over_odds = _finite_float(row.get("over_odds"))
        under_odds = _finite_float(row.get("under_odds"))
        selected_odds = over_odds if direction == "over" else under_odds
        if line is None or over_odds is None or under_odds is None or over_odds <= 1.0 or under_odds <= 1.0:
            continue
        if selected_odds is None or not 1.80 <= selected_odds <= 2.20:
            continue
        order = (
            abs(selected_odds - 2.0),
            _utc_datetime(row.get("snapshot_time")),
            line,
            str(row.get("offer_key") or ""),
        )
        candidates.append((order, row))
    return dict(min(candidates, key=lambda item: item[0])[1]) if candidates else None
```

Group matchup rows by `(match_key, stat_key, period, scope)`, require one OVER and one UNDER score, select the higher score, and preserve tie observations as excluded audit rows. Validate `18 * 60 <= minutes_to_kickoff < 36 * 60` against the canonical kickoff. Store all fields named in the spec and finish each document with `observation_fingerprint_sha256`.

- [ ] **Step 4: Implement database orchestration and CLI**

```python
def materialize_matchup_observations(
    *,
    database: Any,
    match_keys: Iterable[str],
    captured_at: datetime,
    dry_run: bool = False,
) -> dict[str, Any]:
    requested = sorted({str(value) for value in match_keys if value})
    fixtures = list(database[FIXTURES_CANONICAL].find({"match_key": {"$in": requested}}, projection={"_id": 0}))
    snapshots = list(database[MARKET_SNAPSHOTS].find({"match_key": {"$in": requested}, "snapshot_label": CHECKPOINT_LABEL}, projection={"_id": 0}))
    docs: list[dict[str, Any]] = []
    for fixture_row in fixtures:
        fixture_date = str(fixture_row["fixture_date_stockholm"])
        matchup_rows = _build_rows_for_fixture(database, fixture_row, fixture_date)
        fixture_snapshots = [row for row in snapshots if row.get("match_key") == fixture_row.get("match_key")]
        docs.extend(build_matchup_observation_docs(fixture=fixture_row, matchup_rows=matchup_rows, market_snapshot_rows=fixture_snapshots, captured_at=captured_at))
    persistence = {"inserted": 0, "existing": 0, "conflicts": 0} if dry_run else persist_matchup_observations(database[MATCHUP_OBSERVATIONS], docs)
    return {"requested_matches": len(requested), "matched_fixtures": len(fixtures), "observation_docs": len(docs), "persistence": persistence, "docs": docs if dry_run else []}
```

The CLI must require at least one `--match-key`, call `ensure_v2_database`, reject simulated-time writes through `ensure_no_simulated_time_write`, bootstrap the new indexes in write mode, and print JSON without secrets.

- [ ] **Step 5: Run focused observation and CLI tests**

Run:

```powershell
python -m pytest tests/v2/test_matchup_evaluation_observations.py tests/v2/test_config_and_safety.py -q
python scripts/forward_v2/materialize_matchup_observations.py --help
```

Expected: tests PASS and CLI help exits 0.

- [ ] **Step 6: Commit T-1D materialization**

```powershell
git add src/ullebets_v2/matchup_evaluation scripts/forward_v2/materialize_matchup_observations.py tests/v2/test_matchup_evaluation_observations.py
git commit -m "feat: freeze T-1D matchup observations"
```

---

### Task 3: Invoke T-1D materialization from checkpoint workflows

**Files:**
- Modify: `.github/workflows/v2-odds-scheduler.yml:46-107`
- Modify: `.github/workflows/run-unibet-odds-checkpoints.yml:45-106`
- Modify: `tests/v2/test_automation_contract.py`

**Interfaces:**
- Consumes: capture-summary `due_targets[].checkpoint_key` and `due_targets[].match_key`.
- Consumes: `materialize_matchup_observations.py --match-key MATCH_KEY`.
- Guarantees: due T-1D matchups are frozen even when `market_snapshot_upserts == 0`.
- Preserves: formula/model scoring remains conditional on newly written snapshots.

- [ ] **Step 1: Write a failing workflow-contract test**

```python
def test_checkpoint_workflows_materialize_due_t1d_matchups_without_odds(tmp_path) -> None:
    for name in ("v2-odds-scheduler.yml", "run-unibet-odds-checkpoints.yml"):
        workflow = (REPO_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert 'row.get("checkpoint_key") == "T_MINUS_1D"' in workflow
        assert "materialize_matchup_observations.py" in workflow
        assert workflow.index("materialize_matchup_observations.py") < workflow.index("score_registered_shadow_models.py")
        matchup_block = workflow[workflow.index("materialize_matchup_observations.py") - 1600:workflow.index("materialize_matchup_observations.py") + 500]
        assert "CAPTURED_SNAPSHOTS" not in matchup_block
```

- [ ] **Step 2: Run the workflow test and verify failure**

Run:

```powershell
python -m pytest tests/v2/test_automation_contract.py::test_checkpoint_workflows_materialize_due_t1d_matchups_without_odds -q
```

Expected: FAIL because neither workflow invokes the materializer.

- [ ] **Step 3: Extract due T-1D keys independently of captured snapshot count**

Add this shell block immediately after reading the capture summary in both workflows:

```bash
mapfile -t T1D_MATCH_KEYS < <(python - "$CAPTURE_SUMMARY" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    summary = json.load(handle)
seen = set()
for row in summary.get("due_targets") or []:
    match_key = str(row.get("match_key") or "")
    if row.get("checkpoint_key") == "T_MINUS_1D" and match_key and match_key not in seen:
        seen.add(match_key)
        print(match_key)
PY
)
if [ "${#T1D_MATCH_KEYS[@]}" -gt 0 ]; then
  python -m pip install -e .
  MATCHUP_ARGS=()
  for MATCH_KEY in "${T1D_MATCH_KEYS[@]}"; do
    MATCHUP_ARGS+=(--match-key "$MATCH_KEY")
  done
  python scripts/forward_v2/materialize_matchup_observations.py --repo-root . "${MATCHUP_ARGS[@]}"
fi
```

In the reusable manual workflow, append `--dry-run` when `ULLEBETS_V2_DRY_RUN=true`. Do not put this block inside the `CAPTURED_SNAPSHOTS > 0` condition.

- [ ] **Step 4: Run automation and YAML contract tests**

Run:

```powershell
python -m pytest tests/v2/test_automation_contract.py tests/v2/test_workflow_runner.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit workflow integration**

```powershell
git add .github/workflows/v2-odds-scheduler.yml .github/workflows/run-unibet-odds-checkpoints.yml tests/v2/test_automation_contract.py
git commit -m "feat: journal matchup predictors at T-1D"
```

---

### Task 4: Settle predictor, market, same-line closing, and immutable results

**Files:**
- Create: `src/ullebets_v2/matchup_evaluation/results.py`
- Create: `scripts/forward_v2/refresh_matchup_results.py`
- Create: `tests/v2/test_matchup_evaluation_results.py`

**Interfaces:**
- Consumes: `MATCHUP_OBSERVATIONS`, `MATCH_RESULTS_CANONICAL`, `MATCH_STATS_CANONICAL`, `CLOSING_LINES`.
- Produces: `build_matchup_result_docs(*, observations, match_stats_canonical, match_results_canonical, closing_line_docs, refreshed_at) -> list[dict[str, Any]]`.
- Produces: `persist_matchup_results(collection: Any, docs: Iterable[dict[str, Any]]) -> dict[str, int]`.
- Produces: `merge_matchup_result(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> tuple[str, dict[str, Any]]` for insert, unchanged replay, mutable pending refresh, and terminal-conflict decisions.
- Produces: `refresh_matchup_results(*, database: Any, refreshed_at: datetime, date_from: str | None = None, date_to: str | None = None, dry_run: bool = False) -> dict[str, Any]`.

- [ ] **Step 1: Write failing settlement and closing tests**

```python
def observation(*, direction: str = "over", baseline: float = 10.7, market_eligibility: str = "eligible") -> dict:
    return {
        "observation_key": "matchup-eval-v1|m1|cornerKicks|ALL|total|T_MINUS_1D",
        "match_key": "m1",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "total",
        "selected_direction": direction,
        "league_baseline": baseline,
        "market_eligibility": market_eligibility,
        "line_value": 10.5 if market_eligibility == "eligible" else None,
        "selected_odds": 1.95 if market_eligibility == "eligible" else None,
        "valid_for_predictor": True,
    }


def canonical_actual(*, actual: float) -> list[dict]:
    return [{"match_key": "m1", "stat_key": "cornerKicks", "period": "ALL", "scope": "total", "actual_value": actual, "home_value": 7, "away_value": actual - 7}]


def canonical_final() -> list[dict]:
    return [{"match_key": "m1", "status_type": "finished"}]


def closing(*, line: float, quality: str, odds: float) -> dict:
    return {
        "match_key": "m1",
        "stat_key": "cornerKicks",
        "period": "ALL",
        "scope": "total",
        "line": line,
        "closing_quality": quality,
        "closing_snapshot_label": "T_MINUS_10M" if quality == "t10" else "T_MINUS_30M",
        "closing_snapshot_time": NOW,
        "closing_over_odds": odds,
        "closing_under_odds": odds,
        "accepted_for_product_clv": quality in {"t10", "t30_fallback"},
    }


def settle(*, direction: str, actual: float, line: float, odds: float) -> dict:
    observed = observation(direction=direction)
    observed.update({"line_value": line, "selected_odds": odds})
    return build_matchup_result_docs(
        observations=[observed],
        match_stats_canonical=canonical_actual(actual=actual),
        match_results_canonical=canonical_final(),
        closing_line_docs=[],
        refreshed_at=NOW,
    )[0]


def settle_with_closing(*, selected_line: float, closings: list[dict]) -> dict:
    observed = observation()
    observed["line_value"] = selected_line
    return build_matchup_result_docs(
        observations=[observed],
        match_stats_canonical=canonical_actual(actual=12),
        match_results_canonical=canonical_final(),
        closing_line_docs=closings,
        refreshed_at=NOW,
    )[0]


def resolved_result(*, actual: float, market_verdict: str) -> dict:
    return {
        "observation_key": "matchup-eval-v1|m1|cornerKicks|ALL|total|T_MINUS_1D",
        "lifecycle_status": "resolved_market",
        "actual_value": actual,
        "market_verdict": market_verdict,
        "stake_units": 1.0,
        "pnl_units": 0.95 if market_verdict == "win" else -1.0,
    }


def test_predictor_only_result_keeps_market_fields_null() -> None:
    result = build_matchup_result_docs(
        observations=[observation(direction="over", baseline=10.7, market_eligibility="no_exact_market")],
        match_stats_canonical=canonical_actual(actual=13),
        match_results_canonical=canonical_final(),
        closing_line_docs=[],
        refreshed_at=NOW,
    )[0]
    assert result["lifecycle_status"] == "resolved_predictor_only"
    assert result["predictor_verdict"] == "hit"
    assert result["signed_residual"] == pytest.approx(2.3)
    assert result["market_verdict"] is None
    assert result["stake_units"] == 0.0
    assert result["clv_pct"] is None


@pytest.mark.parametrize(
    ("direction", "actual", "line", "expected"),
    [("over", 12, 10.5, "win"), ("over", 9, 10.5, "loss"), ("under", 10, 10.0, "push")],
)
def test_market_verdict_uses_frozen_exact_line(direction, actual, line, expected) -> None:
    result = settle(direction=direction, actual=actual, line=line, odds=1.95)
    assert result["market_verdict"] == expected


def test_t10_preferred_and_different_line_does_not_become_clv() -> None:
    result = settle_with_closing(
        selected_line=10.5,
        closings=[closing(line=10.5, quality="t30_fallback", odds=1.88), closing(line=10.5, quality="t10", odds=1.84), closing(line=11.5, quality="t10", odds=1.96)],
    )
    assert result["closing_quality"] == "t10"
    assert result["closing_odds"] == 1.84
    assert result["different_line_close"] == 11.5
    assert result["clv_pct"] == pytest.approx((1.95 / 1.84 - 1.0) * 100.0)


def test_terminal_result_conflict_fails_closed() -> None:
    original = resolved_result(actual=12, market_verdict="win")
    changed = resolved_result(actual=8, market_verdict="loss")
    with pytest.raises(MatchupResultConflict):
        merge_matchup_result(original, changed)
```

- [ ] **Step 2: Run tests and verify missing-module failure**

Run:

```powershell
python -m pytest tests/v2/test_matchup_evaluation_results.py -q
```

Expected: FAIL because `matchup_evaluation.results` does not exist.

- [ ] **Step 3: Implement predictor and market verdict helpers**

```python
def predictor_result(direction: str, actual: float, baseline: float) -> tuple[float, str]:
    residual = actual - baseline if direction == "over" else baseline - actual
    verdict = "hit" if residual > 0 else "miss" if residual < 0 else "push"
    return residual, verdict


def market_result(direction: str, actual: float, line: float, odds: float) -> tuple[str, float, float]:
    delta = actual - line if direction == "over" else line - actual
    verdict = "win" if delta > 0 else "loss" if delta < 0 else "push"
    pnl = odds - 1.0 if verdict == "win" else -1.0 if verdict == "loss" else 0.0
    return verdict, 1.0, pnl


def same_line_closing(observation: dict[str, Any], closing_rows: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    exact = [
        row for row in closing_rows
        if row.get("match_key") == observation.get("match_key")
        and row.get("stat_key") == observation.get("stat_key")
        and row.get("period") == observation.get("period")
        and row.get("scope") == observation.get("scope")
        and float(row.get("line")) == float(observation.get("line_value"))
        and row.get("accepted_for_product_clv") is True
    ]
    preferred = [row for row in exact if row.get("closing_quality") == "t10"]
    fallback = [row for row in exact if row.get("closing_quality") == "t30_fallback"]
    pool = preferred or fallback
    return max(pool, key=lambda row: str(row.get("closing_snapshot_time") or "")) if pool else None
```

Use `resolve_actual_context()` from `settlement.common` for exact stat/period/scope actuals. Populate every lifecycle state from the spec. Market-null observations remain valid predictor evidence and receive zero stake rather than a loss.

- [ ] **Step 4: Implement result fingerprints and terminal conflict protection**

Exclude only `_id`, `refreshed_at`, and `result_fingerprint_sha256` from result fingerprints. Treat these fields as immutable once lifecycle status begins with `resolved_`: `actual_value`, `home_value`, `away_value`, `predictor_verdict`, `signed_residual`, `market_verdict`, `stake_units`, and `pnl_units`. `merge_matchup_result` returns `insert` for a missing row, `unchanged` for an exact fingerprint replay, and `replace_pending` for a non-terminal lifecycle refresh; terminal differences raise `MatchupResultConflict`. `persist_matchup_results` loads existing rows by `observation_key`, applies that decision for every row before any write, then performs unordered `UpdateOne({"observation_key": key}, {"$set": replacement}, upsert=True)` operations only after the complete batch passes conflict validation.

- [ ] **Step 5: Implement refresh CLI with bounded date filters**

```python
summary = refresh_matchup_results(
    database=database,
    refreshed_at=now,
    date_from=args.date_from,
    date_to=args.date_to,
    dry_run=args.dry_run,
)
print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
```

The CLI accepts either one `--date YYYY-MM-DD` or the pair `--date-from YYYY-MM-DD --date-to YYYY-MM-DD`, rejects partial/reversed ranges, bootstraps indexes only in write mode, logs a job run, and stores audit/health counts without embedding result documents or secrets.

- [ ] **Step 6: Run result tests and CLI smoke**

Run:

```powershell
python -m pytest tests/v2/test_matchup_evaluation_results.py -q
python scripts/forward_v2/refresh_matchup_results.py --help
```

Expected: PASS and help exits 0.

- [ ] **Step 7: Commit hybrid settlement**

```powershell
git add src/ullebets_v2/matchup_evaluation/results.py scripts/forward_v2/refresh_matchup_results.py tests/v2/test_matchup_evaluation_results.py
git commit -m "feat: settle matchup predictor and market results"
```

---

### Task 5: Preserve legacy evidence, recover unresolved fixtures, and wire post-match jobs

**Files:**
- Create: `src/ullebets_v2/matchup_evaluation/legacy.py`
- Create: `scripts/forward_v2/backfill_legacy_matchup_evaluation.py`
- Create: `tests/v2/test_matchup_evaluation_legacy.py`
- Modify: `src/ullebets_v2/enrichment/service.py:40-80`
- Modify: `scripts/forward_v2/ingest_match_enrichment.py:32-140`
- Modify: `.github/workflows/ev-shadow-settlement.yml:24-56`
- Modify: `.github/workflows/enrich-matchups-results.yml:27-40`
- Modify: `tests/v2/test_match_enrichment.py`
- Modify: `tests/v2/test_automation_contract.py`

**Interfaces:**
- Produces: `build_legacy_matchup_evaluation_docs(*, score_rows, generated_at) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]`.
- Produces: deterministic legacy keys `matchup-eval-v1|legacy|{entry_key}` with `evidence_class = legacy_descriptive` and both `valid_for_predictor` and `valid_for_market` false.
- Produces: `select_unresolved_matchup_match_keys(*, observation_docs, result_docs, reference_time, minimum_match_age) -> list[str]`.
- Adds CLI flag: `--include-unresolved-matchup-observations`.
- Consumes: `refresh_matchup_results.py` after canonical enrichment.
- Preserves: forward-bet recovery and formula-result ordering.

- [ ] **Step 1: Add failing recovery-selection tests**

```python
def observation(match_key: str, match_start_time: datetime) -> dict:
    return {"observation_key": f"obs-{match_key}", "match_key": match_key, "match_start_time": match_start_time}


def result(match_key: str, lifecycle_status: str) -> dict:
    return {"observation_key": f"obs-{match_key}", "match_key": match_key, "lifecycle_status": lifecycle_status}


def test_selects_started_matchup_without_terminal_result() -> None:
    keys = select_unresolved_matchup_match_keys(
        observation_docs=[observation(match_key="m1", match_start_time=NOW - timedelta(hours=5))],
        result_docs=[],
        reference_time=NOW,
        minimum_match_age=timedelta(hours=3),
    )
    assert keys == ["m1"]


def test_does_not_requeue_future_or_terminal_matchup() -> None:
    keys = select_unresolved_matchup_match_keys(
        observation_docs=[
            observation(match_key="future", match_start_time=NOW + timedelta(hours=1)),
            observation(match_key="done", match_start_time=NOW - timedelta(hours=5)),
        ],
        result_docs=[result(match_key="done", lifecycle_status="resolved_predictor_only")],
        reference_time=NOW,
        minimum_match_age=timedelta(hours=3),
    )
    assert keys == []
```

- [ ] **Step 2: Add failing workflow-order tests**

```python
def test_postmatch_workflow_recovers_and_refreshes_matchups() -> None:
    workflow = (REPO_ROOT / ".github/workflows/ev-shadow-settlement.yml").read_text(encoding="utf-8")
    enrichment = workflow.index("ingest_match_enrichment.py")
    matchup_results = workflow.index("refresh_matchup_results.py")
    assert "--include-unresolved-matchup-observations" in workflow
    assert enrichment < matchup_results


def test_daily_matchup_workflow_enriches_before_both_settlements() -> None:
    workflow = (REPO_ROOT / ".github/workflows/enrich-matchups-results.yml").read_text(encoding="utf-8")
    assert workflow.index("ingest_match_enrichment.py") < workflow.index("settle_matchups_outputs.py")
    assert workflow.index("settle_matchups_outputs.py") < workflow.index("refresh_matchup_results.py")
```

- [ ] **Step 3: Run recovery tests and verify failure**

Run:

```powershell
python -m pytest tests/v2/test_match_enrichment.py tests/v2/test_automation_contract.py -q
```

Expected: FAIL because matchup recovery and workflow commands are absent.

- [ ] **Step 4: Implement unresolved observation discovery**

```python
TERMINAL_MATCHUP_STATUSES = {
    "resolved_predictor_only",
    "resolved_market",
    "missing_actual",
    "excluded_timing",
    "excluded_mapping",
}


def select_unresolved_matchup_match_keys(
    *,
    observation_docs: list[dict[str, Any]],
    result_docs: list[dict[str, Any]],
    reference_time: datetime,
    minimum_match_age: timedelta,
) -> list[str]:
    terminal = {
        str(row.get("observation_key"))
        for row in result_docs
        if row.get("lifecycle_status") in TERMINAL_MATCHUP_STATUSES
    }
    cutoff = reference_time - minimum_match_age
    keys = {
        str(row["match_key"])
        for row in observation_docs
        if row.get("observation_key") not in terminal
        and to_utc_datetime(row.get("match_start_time")) is not None
        and to_utc_datetime(row.get("match_start_time")) <= cutoff
    }
    return sorted(keys)
```

Load only matching observations/results and merge their canonical fixture targets with existing explicit-date and forward-bet recovery targets by `match_key`.

- [ ] **Step 5: Add immutable legacy classification and bounded backfill tests**

```python
def test_legacy_rows_are_deduplicated_and_never_promoted_to_forward_proof() -> None:
    over = settled_score_row(entry_key="over-1", condition="over", score=82.0, actual=14.0, baseline=11.7)
    under = settled_score_row(entry_key="under-1", condition="under", score=61.0, actual=14.0, baseline=11.7)
    observations, results = build_legacy_matchup_evaluation_docs(score_rows=[under, over], generated_at=NOW)
    assert len(observations) == len(results) == 1
    assert observations[0]["selected_direction"] == "over"
    assert observations[0]["evidence_class"] == "legacy_descriptive"
    assert observations[0]["valid_for_predictor"] is False
    assert results[0]["predictor_verdict"] == "hit"
    assert results[0]["market_verdict"] is None
    assert results[0]["valid_for_market"] is False


def test_legacy_direction_tie_is_excluded_instead_of_guessed() -> None:
    rows = [
        settled_score_row(entry_key="over-1", condition="over", score=70.0, actual=12.0, baseline=11.7),
        settled_score_row(entry_key="under-1", condition="under", score=70.0, actual=12.0, baseline=11.7),
    ]
    observations, results = build_legacy_matchup_evaluation_docs(score_rows=rows, generated_at=NOW)
    assert observations == []
    assert results == []
```

Define `settled_score_row` in the test with one exact `(snapshot_date, match_key, stat_key, period, scope)` context and the supplied score, condition, `forecast.leagueBaseline`, `outcome_status = resolved`, and `actual_value`. Group legacy rows by that exact context, select the strictly higher OVER/UNDER score, and exclude a 50/50 score or exact directional tie. The CLI accepts required `--date-from` and `--date-to`, reads only `matchups_score`, writes only through the immutable Task 1/4 persistence functions, supports `--dry-run`, and emits inserted, unchanged, excluded-tie, unresolved, and conflict counts. It never rewrites `matchups_score`.

Run:

```powershell
python -m pytest tests/v2/test_matchup_evaluation_legacy.py -q
```

Expected: PASS after the implementation is added.

- [ ] **Step 6: Add post-match and daily workflow commands**

In `ev-shadow-settlement.yml`, add `--include-unresolved-matchup-observations` to the existing enrichment command and execute `refresh_matchup_results.py --dry-run` after canonical enrichment and before audits.

In `enrich-matchups-results.yml`, execute:

```bash
python scripts/forward_v2/ingest_match_enrichment.py \
  --mode live \
  --fixture-source db \
  --date "$DATE" \
  --source-workflow enrich-matchups-results.yml \
  --dry-run
python scripts/forward_v2/settle_matchups_outputs.py --date "$DATE" --source-workflow enrich-matchups-results.yml --dry-run
python scripts/forward_v2/refresh_matchup_results.py --date "$DATE" --dry-run
```

Preserve the reusable runner's dry-run stripping behavior.

- [ ] **Step 7: Run recovery and workflow tests**

Run:

```powershell
python -m pytest tests/v2/test_matchup_evaluation_legacy.py tests/v2/test_match_enrichment.py tests/v2/test_automation_contract.py tests/v2/test_workflow_runner.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit recovery orchestration**

```powershell
git add src/ullebets_v2/matchup_evaluation/legacy.py scripts/forward_v2/backfill_legacy_matchup_evaluation.py tests/v2/test_matchup_evaluation_legacy.py src/ullebets_v2/enrichment/service.py scripts/forward_v2/ingest_match_enrichment.py .github/workflows/ev-shadow-settlement.yml .github/workflows/enrich-matchups-results.yml tests/v2/test_match_enrichment.py tests/v2/test_automation_contract.py
git commit -m "feat: recover unresolved matchup evidence"
```

---

### Task 6: Compute predictor and market quality without double counting

**Files:**
- Create: `src/ullebets_v2/matchup_evaluation/metrics.py`
- Create: `tests/v2/test_matchup_evaluation_metrics.py`

**Interfaces:**
- Consumes: settled rows from `MATCHUP_RESULTS`.
- Produces: `build_matchup_evaluation_summary(rows: Iterable[dict[str, Any]], *, bootstrap_iterations: int = 2000, seed: int = 20260828) -> dict[str, Any]`.
- Produces: a JSON-safe `predictor`, `market`, `coverage`, and `evidence` response.
- Reports `legacyDescriptive` separately; legacy rows never enter forward confidence intervals, support gates, market ROI, or CLV.
- Uses only Python standard library so the Vercel read runtime remains compatible with `requirements.txt`.

- [ ] **Step 1: Write failing denominator, lift, and evidence-gate tests**

```python
def result(
    match_key: str,
    *,
    predictor: str,
    score: float,
    rank: int,
    market: str | None = None,
    pnl: float = 0.0,
    clv: float | None = None,
    index: int = 0,
) -> dict:
    return {
        "observation_key": f"obs-{match_key}-{index}",
        "match_key": match_key,
        "fixture_date_stockholm": f"2026-08-{(index % 30) + 1:02d}",
        "predictor_verdict": predictor,
        "signed_residual": 1.0 if predictor == "hit" else -1.0,
        "score": score,
        "rank_position": rank,
        "valid_for_predictor": True,
        "market_verdict": market,
        "valid_for_market": market is not None,
        "stake_units": 1.0 if market is not None else 0.0,
        "pnl_units": pnl,
        "clv_pct": clv,
    }


def supported_sample() -> list[dict]:
    rows = []
    for index in range(300):
        rank = (index % 30) + 1
        rows.append(
            result(
                f"m{index % 100}",
                predictor="hit" if rank <= 20 else "miss",
                score=100.0 - rank,
                rank=rank,
                index=index,
            )
        )
    return rows


def test_predictor_and_market_denominators_are_independent() -> None:
    summary = build_matchup_evaluation_summary(
        [
            result("m1", predictor="hit", market=None, score=91.0, rank=1),
            result("m2", predictor="miss", market="loss", score=82.0, rank=2, pnl=-1.0, clv=-2.0),
            result("m3", predictor="hit", market="win", score=61.0, rank=31, pnl=0.95, clv=1.5),
        ],
        bootstrap_iterations=200,
        seed=7,
    )
    assert summary["predictor"]["resolved"] == 3
    assert summary["predictor"]["nonPushHitRatePct"] == pytest.approx(66.6666667)
    assert summary["market"]["resolved"] == 2
    assert summary["market"]["roiPct"] == pytest.approx(-2.5)
    assert summary["coverage"]["marketEligiblePct"] == pytest.approx(66.6666667)


def test_same_match_rows_are_resampled_as_one_cluster() -> None:
    rows = [
        result("m1", predictor="hit", score=95.0, rank=1),
        result("m1", predictor="hit", score=94.0, rank=2),
        result("m2", predictor="miss", score=55.0, rank=30),
    ]
    first = build_matchup_evaluation_summary(rows, bootstrap_iterations=200, seed=11)
    second = build_matchup_evaluation_summary(rows, bootstrap_iterations=200, seed=11)
    assert first["predictor"]["top20LiftCi95"] == second["predictor"]["top20LiftCi95"]
    assert first["predictor"]["uniqueMatches"] == 2


def test_legacy_rows_are_reported_but_excluded_from_forward_denominator() -> None:
    forward = result("m1", predictor="hit", market=None, score=91.0, rank=1)
    legacy = {
        **result("legacy", predictor="miss", market=None, score=88.0, rank=2),
        "evidence_class": "legacy_descriptive",
        "valid_for_predictor": False,
    }
    summary = build_matchup_evaluation_summary([forward, legacy], bootstrap_iterations=200, seed=5)
    assert summary["predictor"]["resolved"] == 1
    assert summary["legacyDescriptive"]["resolved"] == 1
    assert summary["legacyDescriptive"]["nonPushHitRatePct"] == 0.0
    assert summary["market"]["resolved"] == 0


def test_support_gate_requires_all_thresholds_and_positive_lower_bound() -> None:
    summary = build_matchup_evaluation_summary(supported_sample(), bootstrap_iterations=200, seed=13)
    assert summary["evidence"]["predictorState"] == "supported"
    assert summary["evidence"]["criteria"] == {
        "resolvedContexts": True,
        "uniqueMatches": True,
        "fixtureDates": True,
        "positiveLiftLowerBound": True,
    }
```

- [ ] **Step 2: Run the metric tests and verify failure**

Run:

```powershell
python -m pytest tests/v2/test_matchup_evaluation_metrics.py -q
```

Expected: FAIL because `metrics.py` does not exist.

- [ ] **Step 3: Implement deterministic score bands and rank statistics**

```python
SCORE_BANDS = ((50.0, 60.0), (60.0, 70.0), (70.0, 80.0), (80.0, 90.0), (90.0, 100.0000001))


def _rank(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(ordered):
        end = position + 1
        while end < len(ordered) and ordered[end][1] == ordered[position][1]:
            end += 1
        average_rank = (position + 1 + end) / 2.0
        for original_index, _ in ordered[position:end]:
            ranks[original_index] = average_rank
        position = end
    return ranks


def _spearman(scores: list[float], residuals: list[float]) -> float | None:
    if len(scores) < 2:
        return None
    return _pearson(_rank(scores), _rank(residuals))
```

Compute top-20 lift as non-push hit rate for `rank_position <= 20` minus non-push hit rate for the remaining selected daily universe. Do not infer missing ranks. Return null when either comparison side lacks non-push outcomes.

- [ ] **Step 4: Implement match-cluster bootstrap and evidence states**

Group rows by `match_key`. For every iteration, sample the list of unique match keys with replacement using `random.Random(seed)`, concatenate every row belonging to each sampled key, and recompute top-20 lift. Return the empirical 2.5th and 97.5th percentiles of non-null samples. This preserves within-match correlation.

Return `thin` under 30 contexts, `descriptive` from 30 through 299, and `supported` only when all four spec gates pass: at least 300 resolved contexts, 100 unique matches, 30 fixture dates, and a positive lower 95% lift bound. Market evidence stays `descriptive` until 300 resolved market rows and must never inherit predictor support.

- [ ] **Step 5: Run metric tests**

Run:

```powershell
python -m pytest tests/v2/test_matchup_evaluation_metrics.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit quality metrics**

```powershell
git add src/ullebets_v2/matchup_evaluation/metrics.py tests/v2/test_matchup_evaluation_metrics.py
git commit -m "feat: measure matchup predictor quality"
```

---

### Task 7: Expose nested card evaluation and aggregate read API

**Files:**
- Modify: `src/ullebets_v2/read_api/service.py:225-251,344-450,607-708`
- Modify: `src/ullebets_v2/read_api/http.py:138-177`
- Modify: `tests/v2/test_read_api.py`
- Modify: `tests/v2/test_read_api_contracts.py`

**Interfaces:**
- Consumes: `MATCHUP_OBSERVATIONS`, `MATCHUP_RESULTS`, `MARKET_SNAPSHOTS`.
- Consumes: `build_matchup_evaluation_summary`.
- Produces: `read_matchup_evaluation(database: Any, filters: dict[str, str | None]) -> dict[str, Any]`.
- Produces route: `GET /api/v1/matchups/evaluation`.
- Extends each `MatchupEntry` with `evaluation.predictor`, `evaluation.market`, `evaluation.closing`, and `evaluation.provenance`.

- [ ] **Step 1: Add failing dashboard join and route tests**

```python
def test_dashboard_exposes_predictor_only_evaluation() -> None:
    score = matchup_row(snapshot_date="2026-08-22")
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([fixture_row(source_date="2026-08-22")]),
        matchups_score=FakeCollection([score]),
        matchup_observations=FakeCollection([{
            "observation_key": "obs-1", "match_key": score["match_key"], "stat_key": "fouls",
            "period": "ALL", "scope": "away", "selected_direction": "over",
            "league_baseline": 11.7, "market_eligibility": "no_exact_market",
            "policy_version": "matchup-eval-v1", "evidence_class": "forward",
            "checkpoint_label": "T_MINUS_1D", "ranking_method": "rolling_12_weighted_45d",
            "valid_for_predictor": True,
        }]),
        matchup_results=FakeCollection([{
            "observation_key": "obs-1", "match_key": score["match_key"],
            "lifecycle_status": "resolved_predictor_only", "actual_value": 14.0,
            "signed_residual": 2.3, "predictor_verdict": "hit",
            "market_verdict": None, "stake_units": 0.0, "pnl_units": 0.0,
        }]),
    )
    payload = read_dashboard(database, source_date="2026-08-22")
    evaluation = payload["matchups"][0]["evaluation"]
    assert evaluation["predictor"] == {
        "status": "resolved_predictor_only",
        "actualValue": 14.0,
        "leagueBaseline": 11.7,
        "signedResidual": 2.3,
        "verdict": "hit",
    }
    assert evaluation["market"]["eligibility"] == "no_exact_market"
    assert evaluation["market"]["verdict"] is None


def test_dashboard_labels_settled_prejournal_row_legacy_descriptive() -> None:
    score = matchup_row(snapshot_date="2026-08-22")
    score.update({"outcome_status": "resolved", "actual_value": 14.0})
    database = FakeDatabase(
        fixtures_canonical=FakeCollection([fixture_row(source_date="2026-08-22")]),
        matchups_score=FakeCollection([score]),
        matchup_observations=FakeCollection([]),
        matchup_results=FakeCollection([]),
    )
    evaluation = read_dashboard(database, source_date="2026-08-22")["matchups"][0]["evaluation"]
    assert evaluation["predictor"]["verdict"] == "hit"
    assert evaluation["predictor"]["signedResidual"] == pytest.approx(1.4)
    assert evaluation["market"]["eligibility"] == "legacy_unknown"
    assert evaluation["market"]["verdict"] is None
    assert evaluation["provenance"]["evidenceClass"] == "legacy_descriptive"
    assert evaluation["provenance"]["validForPredictor"] is False


def test_matchup_evaluation_route_keeps_denominators_separate() -> None:
    database = MemoryDatabase(
        matchup_results=MemoryCollection([
            {"observation_key": "obs-1", "match_key": "m1", "fixture_date_stockholm": "2026-08-22", "stat_key": "cornerKicks", "period": "ALL", "scope": "total", "evidence_class": "forward", "lifecycle_status": "resolved_predictor_only", "predictor_verdict": "hit", "valid_for_predictor": True},
            {"observation_key": "obs-2", "match_key": "m2", "fixture_date_stockholm": "2026-08-22", "stat_key": "cornerKicks", "period": "ALL", "scope": "total", "evidence_class": "forward", "lifecycle_status": "resolved_market", "predictor_verdict": "miss", "market_verdict": "loss", "stake_units": 1.0, "pnl_units": -1.0, "valid_for_predictor": True},
        ]),
    )
    status, payload = read_http.dispatch_get(
        database,
        "/api/v1/matchups/evaluation",
        {"dateFrom": ["2026-08-01"], "dateTo": ["2026-08-31"], "stat": ["cornerKicks"]},
    )
    assert status == HTTPStatus.OK
    assert payload["filters"]["stat"] == "cornerKicks"
    assert payload["predictor"]["resolved"] != payload["market"]["resolved"]
```

- [ ] **Step 2: Run read tests and verify failure**

Run:

```powershell
python -m pytest tests/v2/test_read_api.py tests/v2/test_read_api_contracts.py -q
```

Expected: FAIL because card evaluation and the route are absent.

- [ ] **Step 3: Add bounded evaluation loading and exact card join**

Load observations/results once per dashboard request for the visible match keys. Index them by `(match_key, stat_key, period, scope)` and attach evaluation only when the card direction equals `selected_direction`. Complementary non-selected cards receive provenance `selectedDirection: false` and null verdicts.

When no immutable observation exists, call `_legacy_matchup_evaluation(row)` for persisted rows whose `outcome_status` is `resolved`, `pending_result`, or `missing_actual`. It computes predictor actual, frozen row baseline, signed residual, and verdict from the persisted row only; sets `evidenceClass = legacy_descriptive`, `validForPredictor = false`, and `market.eligibility = legacy_unknown`; and leaves odds, ROI, closing, and CLV fields null. It must not synthesize a market loss from absent odds. This read fallback is card-only; the bounded Task 5 backfill supplies immutable legacy rows to the aggregate endpoint's separate `legacyDescriptive` bucket.

Use this serializer shape:

```python
def _matchup_evaluation_summary(observation: dict[str, Any] | None, result: dict[str, Any] | None) -> dict[str, Any] | None:
    if observation is None:
        return None
    row = result or {}
    return {
        "predictor": {
            "status": row.get("lifecycle_status") or "open",
            "actualValue": row.get("actual_value"),
            "leagueBaseline": observation.get("league_baseline"),
            "signedResidual": row.get("signed_residual"),
            "verdict": row.get("predictor_verdict"),
        },
        "market": {
            "eligibility": observation.get("market_eligibility"),
            "line": observation.get("line_value"),
            "selectedOdds": observation.get("selected_odds"),
            "verdict": row.get("market_verdict"),
            "stakeUnits": row.get("stake_units"),
            "pnlUnits": row.get("pnl_units"),
        },
        "closing": {
            "quality": row.get("closing_quality"),
            "checkpoint": row.get("closing_snapshot_label"),
            "closingOdds": row.get("closing_odds"),
            "clvPct": row.get("clv_pct"),
            "beatClosing": row.get("beat_closing_line"),
            "oddsHistory": row.get("odds_history") or [],
            "differentLineClose": row.get("different_line_close"),
        },
        "provenance": {
            "policyVersion": observation.get("policy_version"),
            "evidenceClass": observation.get("evidence_class") or "forward",
            "checkpoint": observation.get("checkpoint_label"),
            "rankingMethod": observation.get("ranking_method"),
            "validForPredictor": bool(observation.get("valid_for_predictor")),
        },
    }
```

- [ ] **Step 4: Add aggregate filters and HTTP dispatch**

Accept only `dateFrom`, `dateTo`, `league`, `stat`, `period`, `scope`, `method`, and `evidence`. Build a Mongo query from those allow-listed fields, project only metric inputs, and call `build_matchup_evaluation_summary`. Reject reversed date ranges with HTTP 400 through the existing read-API error path.

```python
if normalized_path == "/api/v1/matchups/evaluation":
    return HTTPStatus.OK, read_matchup_evaluation(
        database,
        {
            "dateFrom": _first(query, "dateFrom"),
            "dateTo": _first(query, "dateTo"),
            "league": _first(query, "league"),
            "stat": _first(query, "stat"),
            "period": _first(query, "period"),
            "scope": _first(query, "scope"),
            "method": _first(query, "method"),
            "evidence": _first(query, "evidence"),
        },
    )
```

- [ ] **Step 5: Run read API tests**

Run:

```powershell
python -m pytest tests/v2/test_read_api.py tests/v2/test_read_api_contracts.py tests/v2/test_vercel_read_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the read contract**

```powershell
git add src/ullebets_v2/read_api/service.py src/ullebets_v2/read_api/http.py tests/v2/test_read_api.py tests/v2/test_read_api_contracts.py
git commit -m "feat: expose matchup evaluation API"
```

---

### Task 8: Render predictor, market, movement, and summary states

**Files:**
- Modify: `frontend/src/domain/types.ts:57-90`
- Modify: `frontend/src/data/api.ts:1-30`
- Modify: `frontend/src/data/queries.ts:1-90`
- Modify: `frontend/src/components/OddsMovement.tsx`
- Create: `frontend/src/components/MatchupEvaluation.tsx`
- Modify: `frontend/src/components/SignalCard.tsx:18-63`
- Modify: `frontend/src/pages/OverviewPage.tsx:8-84`
- Modify: `frontend/src/styles/live-data.css`
- Create: `frontend/src/app/matchup-evaluation.fixtures.ts`
- Create: `frontend/src/app/matchup-evaluation.test.tsx`

**Interfaces:**
- Consumes: nested `MatchupEvaluation` and `MatchupEvaluationResponse` from Task 7.
- Produces: `MatchupEvaluationPanel({ evaluation }: { evaluation: MatchupEvaluation })`.
- Produces: `useMatchupEvaluation(query: MatchupEvaluationQuery)`.
- Generalizes: `OddsMovement` to accept `OddsMovementSource` without changing Auto behavior.

- [ ] **Step 1: Write failing card and summary tests**

Create `matchup-evaluation.fixtures.ts` with three complete response maps exported as `predictorOnlyResponses`, `marketResolvedResponses`, and `summaryResponses`. Reuse the valid dashboard shell fields from `frontend/src/app/App.test.tsx`; add the Task 7 nested evaluation shape. The first map has actual 14.0, baseline 11.7, predictor `hit`, and `no_exact_market`. The second has frozen odds 2.18, exact-line T-1D/T-30 history, closing 2.12, and CLV `+2.8`. The third has predictor counts 93/149 and market coverage 20/149. Every response map must include both the dashboard URL and the exact date-bounded aggregate URL shown below.

Import `fireEvent` and `screen` from Testing Library, `userEvent`, `renderApp`, and all three response maps in the test file.

```tsx
it('separates predictor hit from missing market coverage', async () => {
  renderApp('/oversikt?date=2026-08-22', predictorOnlyResponses);
  expect(await screen.findByText('Prediktor: träff')).toBeInTheDocument();
  expect(screen.getByText(/Utfall 14 mot ligasnitt 11,7/)).toBeInTheDocument();
  expect(screen.getByText('Ingen jämförbar spelmarknad')).toBeInTheDocument();
  expect(screen.queryByText('Förlorad')).not.toBeInTheDocument();
});


it('shows exact-line movement by hover, focus, and click or touch activation', async () => {
  const user = userEvent.setup();
  renderApp('/oversikt?date=2026-08-22', marketResolvedResponses);
  const trigger = await screen.findByRole('button', { name: /Visa oddsrörelse/ });
  fireEvent.pointerEnter(trigger);
  expect(screen.getByRole('dialog', { name: 'Oddsrörelse & closing' })).toBeInTheDocument();
  await user.keyboard('{Escape}');
  trigger.blur();
  trigger.focus();
  expect(screen.getByRole('dialog', { name: 'Oddsrörelse & closing' })).toBeInTheDocument();
  await user.keyboard('{Escape}');
  await user.click(trigger);
  expect(screen.getByRole('dialog', { name: 'Oddsrörelse & closing' })).toBeInTheDocument();
  expect(screen.getByText('T-1D')).toBeInTheDocument();
  expect(screen.getByText('T-30')).toBeInTheDocument();
  expect(screen.getByText(/CLV \+2,8 %/)).toBeInTheDocument();
});


it('uses separate predictor and market denominators in summary tiles', async () => {
  renderApp('/oversikt?date=2026-08-22', summaryResponses);
  expect(await screen.findByText('Predictorträff')).toBeInTheDocument();
  expect(screen.getByText('93/149 rätt riktning')).toBeInTheDocument();
  expect(screen.getByText('Marknadstäckning')).toBeInTheDocument();
  expect(screen.getByText('20/149 jämförbara odds')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run:

```powershell
Set-Location frontend
npm test -- --run src/app/matchup-evaluation.test.tsx
```

Expected: FAIL because the types, hook, components, and summaries are absent.

- [ ] **Step 3: Add exact TypeScript contracts and query hook**

```typescript
export interface MatchupEvaluation {
  predictor: { status:string;actualValue:number|null;leagueBaseline:number|null;signedResidual:number|null;verdict:'hit'|'miss'|'push'|null };
  market: { eligibility:string;line:number|null;selectedOdds:number|null;verdict:'win'|'loss'|'push'|null;stakeUnits:number|null;pnlUnits:number|null };
  closing: { quality:string|null;checkpoint:string|null;closingOdds:number|null;clvPct:number|null;beatClosing:boolean|null;oddsHistory:OddsHistoryPoint[];differentLineClose:number|null };
  provenance: { policyVersion:string|null;evidenceClass:'forward'|'legacy_descriptive';checkpoint:string|null;rankingMethod:string|null;validForPredictor:boolean };
}

export interface MatchupEvaluationQuery extends ApiQuery {
  dateFrom?:string;dateTo?:string;league?:string;stat?:string;period?:string;scope?:string;method?:string;evidence?:string;
}

export function fetchMatchupEvaluation(query:MatchupEvaluationQuery={},signal?:AbortSignal):Promise<MatchupEvaluationResponse>{
  return getJson(buildApiUrl('/matchups/evaluation',query),signal);
}
```

Add `evaluation: MatchupEvaluation | null` to `MatchupEntry`, and add a TanStack query keyed by the complete filter object.

- [ ] **Step 4: Generalize the existing accessible odds panel**

```typescript
export interface OddsMovementSource {
  selectedOdds:number|null;
  closingOdds:number|null;
  closingCheckpoint?:string|null;
  oddsHistory?:OddsHistoryPoint[];
  lineValue:number|null;
  direction?:string|null;
  homeTeamName?:string|null;
  awayTeamName?:string|null;
  clvPct?:number|null;
  beatClosingLine?:boolean|null;
}

export interface OddsMovementProps { row:OddsMovementSource;ariaLabel?:string;marketLabel?:string; }
```

Change the existing `OddsMovement` parameter type from `{ row: AutoSelection }` to `OddsMovementProps`. Preserve the current derived match/market labels when the optional labels are absent so Auto behavior and accessible names remain unchanged. `MatchupEvaluationPanel` passes explicit Swedish labels plus the exact frozen line, selected odds, accepted closing, CLV, beat-close state, and exact-line history. Extend the footer to show CLV only when `clvPct` is non-null and to say whether close was beaten. Different-line movement is labelled separately and never rendered as price CLV.

- [ ] **Step 5: Render all lifecycle states and independent summary tiles**

Use Swedish copy exactly:

- `Prediktor: träff`, `Prediktor: miss`, `Prediktor: push`.
- `Vunnen`, `Förlorad`, `Push` only for eligible market results.
- `Ingen jämförbar spelmarknad` for predictor-only rows.
- `Väntar på resultat`, `Utfall saknas`, `Sen capture – ej forward-underlag`, and `Legacy – deskriptivt` for provenance/lifecycle states.

The overview queries the aggregate endpoint with `dateFrom = dateTo = selectedDate` initially. Predictor and market tiles show their own counts and display `För tunt` when the API evidence state is thin. Do not color a descriptive positive number as proven edge.

- [ ] **Step 6: Run focused and regression frontend tests**

Run:

```powershell
Set-Location frontend
npm test -- --run src/app/matchup-evaluation.test.tsx src/app/App.test.tsx src/app/spel-resultat-clv.test.tsx
npm run typecheck
npm run lint
npm run build
```

Expected: all commands PASS.

- [ ] **Step 7: Commit the product surface**

```powershell
git add frontend/src/domain/types.ts frontend/src/data/api.ts frontend/src/data/queries.ts frontend/src/components/OddsMovement.tsx frontend/src/components/MatchupEvaluation.tsx frontend/src/components/SignalCard.tsx frontend/src/pages/OverviewPage.tsx frontend/src/styles/live-data.css frontend/src/app/matchup-evaluation.fixtures.ts frontend/src/app/matchup-evaluation.test.tsx
git commit -m "feat: show corrected matchup performance"
```

---

### Task 9: Verify the complete contract and record readiness honestly

**Files:**
- Modify: `docs/work-log.md`
- Modify: `docs/app-readiness-checklist.md`
- Modify: `docs/v2-backend-verification-status.md`

**Interfaces:**
- Consumes every implementation and test from Tasks 1-8.
- Produces a locally verified release candidate and exact remaining hosted-runtime gaps.

- [ ] **Step 1: Run targeted backend tests**

Run:

```powershell
python -m pytest tests/v2/test_matchup_evaluation_observations.py tests/v2/test_matchup_evaluation_results.py tests/v2/test_matchup_evaluation_legacy.py tests/v2/test_matchup_evaluation_metrics.py tests/v2/test_match_enrichment.py tests/v2/test_read_api.py tests/v2/test_read_api_contracts.py tests/v2/test_automation_contract.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the full backend suite**

Run:

```powershell
python -m pytest tests/v2 -q
python -m compileall src/ullebets_v2 scripts/forward_v2
```

Expected: PASS with no compile errors.

- [ ] **Step 3: Run the complete frontend verification**

Run:

```powershell
Set-Location frontend
npm test -- --run
npm run typecheck
npm run lint
npm run build
Set-Location ..
```

Expected: PASS.

- [ ] **Step 4: Prove read-only historical classification without promoting it**

Run the two new CLIs against the production database with `--dry-run` and a bounded finished date. Resolve a real upcoming T-1D key read-only instead of typing or storing a placeholder:

```powershell
$env:PYTHONPATH = (Resolve-Path -LiteralPath 'src').Path
$matchupEvaluationKey = @'
from datetime import UTC, datetime, timedelta
from pathlib import Path
from ullebets_v2.config import V2Config
from ullebets_v2.storage.mongo import get_database

database = get_database(V2Config.from_env(Path.cwd()))
now = datetime.now(tz=UTC)
row = database["fixtures_canonical"].find_one(
    {"start_time": {"$gte": now + timedelta(hours=18), "$lt": now + timedelta(hours=36)}},
    projection={"_id": 0, "match_key": 1},
    sort=[("start_time", 1)],
)
print(str((row or {}).get("match_key") or ""))
'@ | python -
if (-not [string]::IsNullOrWhiteSpace($matchupEvaluationKey)) {
  python scripts/forward_v2/materialize_matchup_observations.py --match-key $matchupEvaluationKey --dry-run
} else {
  Write-Output 'No canonical fixture is currently inside the T-1D window; forward capture remains UNPROVEN.'
}
python scripts/forward_v2/refresh_matchup_results.py --date 2026-08-22 --dry-run
python scripts/forward_v2/backfill_legacy_matchup_evaluation.py --date-from 2026-08-22 --date-to 2026-08-22 --dry-run
```

Expected: an available upcoming fixture reports T-1D eligibility or a named timing exclusion; if none is inside the window, record `UNPROVEN`. The historical refresh reports only new immutable observations, while legacy dashboard rows remain `legacy_descriptive` and outside forward proof.

- [ ] **Step 5: Verify repository cleanliness and scope**

Run:

```powershell
git diff --check
git status --short --branch
```

Expected: no whitespace errors; `.playwright-cli/` remains untracked and untouched.

- [ ] **Step 6: Update evidence documents with exact results**

In `docs/work-log.md`, record every command, pass count, dry-run count, failure, and unresolved hosted lifecycle. In `docs/v2-backend-verification-status.md`, document collection identities, timing, immutable replay, settlement, coverage, and API behavior. In `docs/app-readiness-checklist.md`, keep production lifecycle unchecked until an untouched future fixture proves T-1D capture through UI rendering and idempotent replay.

- [ ] **Step 7: Commit verification evidence**

```powershell
git add docs/work-log.md docs/app-readiness-checklist.md docs/v2-backend-verification-status.md
git commit -m "docs: record matchup evaluation verification"
```

- [ ] **Step 8: Perform final branch verification**

Run:

```powershell
git log -9 --oneline
git status --short --branch
```

Expected: implementation commits are present, the branch is clean except for the user-owned `.playwright-cli/`, and no push or deployment is claimed without separately checking the remote and hosting runtime.
