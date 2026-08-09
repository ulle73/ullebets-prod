# Match Detail Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recreate the selected Ullebets match-detail analytics design with real V2 teamprofile data, exact chart geometry, responsive behavior, and no additional API waterfall.

**Architecture:** Extend the existing `read_match_detail` response into a stable presentation contract, then render focused React components from that one payload. Keep charts dependency-free and derive all coordinates from numeric data so the first-goal timeline and comparison scales are mathematically correct.

**Tech Stack:** Python 3.12, MongoDB read API, React 19, TypeScript 6, TanStack Query, Lucide React, CSS, Vitest, pytest.

## Global Constraints

- V2 remains read-only through this endpoint and writes only target `ullebets_v2` elsewhere.
- Historical profile selection remains as-of the match date; upcoming matches use current profiles.
- Missing data is rendered as missing, never estimated.
- `FOR` and `EMOT` are simultaneously visible.
- V6 and Legacy are not rendered in the statistics tab.
- The selected visual target is `docs/design-references/match-detail-analytics-target.png`.

---

### Task 1: Match Detail Read Contract

**Files:**
- Modify: `src/ullebets_v2/read_api/service.py`
- Modify: `tests/v2/test_read_api.py`

**Interfaces:**
- Consumes: `teamprofiles.statistics`, `teamprofiles.specials`, `support_teams.team_image_url`.
- Produces: `match.homeTeamImageUrl`, `match.awayTeamImageUrl`, expanded `teamStats`, and `teamProfiles.home/away` presentation objects.

- [ ] **Step 1: Write failing API contract tests**

Add profile fixtures containing `for`, `against`, both league-average groups, `shotsPerMinute`, `shotsPerTenMinutes`, `firstGoal`, ranks, and support-team image URLs. Assert that `read_match_detail()` returns every value and preserves the historical as-of profile selection.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python -m pytest tests/v2/test_read_api.py -q`

Expected: failures for missing image, against, profile metadata, and specials fields.

- [ ] **Step 3: Implement the presentation contract**

Add small pure serializers in `service.py`:

```python
def _profile_summary(profile: dict[str, Any] | None) -> dict[str, Any] | None: ...
def _team_support(database: Any, team_keys: list[str]) -> dict[str, dict[str, Any]]: ...
```

Extend `_stat_rows()` to emit explicit home/away `for` and `against` values, ranks, and league averages. Query only the two support-team documents required for the match.

- [ ] **Step 4: Run focused API tests**

Run: `python -m pytest tests/v2/test_read_api.py -q`

Expected: all tests pass.

### Task 2: Typed Frontend View Models And Tests

**Files:**
- Modify: `frontend/src/domain/types.ts`
- Create: `frontend/src/pages/match-detail/view-model.ts`
- Create: `frontend/src/pages/match-detail/view-model.test.ts`

**Interfaces:**
- Consumes: the Task 1 JSON contract.
- Produces: `buildStatRows(data, period)`, `buildShotTempo(data)`, `buildTenMinuteSeries(data)`, and `buildFirstGoalMarkers(data)`.

- [ ] **Step 1: Write failing view-model tests**

Cover shared scales, home/away deltas, stable interval order, missing values, and exact first-goal positions:

```ts
expect(buildFirstGoalMarkers(data).homeScored.position).toBeCloseTo(28.2 / 45);
expect(buildFirstGoalMarkers(data).awayConceded.position).toBeCloseTo(28.2 / 45);
```

- [ ] **Step 2: Run the focused frontend test and verify failure**

Run: `npm test -- --run src/pages/match-detail/view-model.test.ts`

Expected: failure because the view-model module does not exist.

- [ ] **Step 3: Add strict response types and pure view-model builders**

Represent all nullable API fields explicitly. Normalize only display order and chart scale; never replace missing values with zero.

- [ ] **Step 4: Run the focused test**

Run: `npm test -- --run src/pages/match-detail/view-model.test.ts`

Expected: all tests pass.

### Task 3: Match Analytics Components

**Files:**
- Create: `frontend/src/pages/match-detail/MatchHeader.tsx`
- Create: `frontend/src/pages/match-detail/StatComparison.tsx`
- Create: `frontend/src/pages/match-detail/ShotTempo.tsx`
- Create: `frontend/src/pages/match-detail/TenMinuteChart.tsx`
- Create: `frontend/src/pages/match-detail/FirstGoalPanel.tsx`
- Create: `frontend/src/pages/match-detail/MatchAnalytics.test.tsx`
- Modify: `frontend/src/pages/MatchDetailPage.tsx`

**Interfaces:**
- Consumes: Task 2 view models and `MatchDetailResponse`.
- Produces: the complete interactive `Statistik` tab.

- [ ] **Step 1: Write failing component tests**

Assert logos and accessible fallbacks, simultaneous `FOR`/`EMOT`, period changes, all three score states, two ten-minute charts, one 0-45 timeline, and explicit empty states.

- [ ] **Step 2: Run component tests and verify failure**

Run: `npm test -- --run src/pages/match-detail/MatchAnalytics.test.tsx`

Expected: failures because the new components do not exist.

- [ ] **Step 3: Implement the components and replace the current page**

Use semantic buttons, tabs, tables/rows, figures, and accessible labels. Use normal DOM/CSS for bars and the existing Lucide package for icons. Keep the page on one query and keep unavailable tabs honest.

- [ ] **Step 4: Run component tests**

Run: `npm test -- --run src/pages/match-detail/MatchAnalytics.test.tsx`

Expected: all tests pass.

### Task 4: Faithful Responsive Styling

**Files:**
- Create: `frontend/src/styles/match-detail.css`
- Modify: `frontend/src/styles/global.css`
- Modify: `frontend/src/main.tsx` or the existing stylesheet entry if required

**Interfaces:**
- Consumes: Task 3 class names and design source dimensions.
- Produces: desktop, tablet, and mobile visual parity.

- [ ] **Step 1: Add match-detail tokens and desktop grid**

Implement the near-black surfaces, central metric spine, opposing bars, compact typography, and restrained mint/coral/cyan states without changing unrelated screens.

- [ ] **Step 2: Add exact chart geometry styles**

Use CSS custom properties for proportional values. First-goal marker position must use `left: calc(var(--minute) / 45 * 100%)`; stat bars use the shared per-row max.

- [ ] **Step 3: Add tablet and mobile layouts**

Preserve data labels and controls at `1100px`, `780px`, and `480px`; allow charts to scroll rather than compress into unreadable labels.

- [ ] **Step 4: Run static verification**

Run: `npm run typecheck && npm run lint && npm test -- --run && npm run build`

Expected: all commands pass.

### Task 5: Runtime And Design QA

**Files:**
- Create: `design-qa.md`
- Update: `docs/work-log.md`
- Update: `docs/app-readiness-checklist.md` only if readiness evidence changes

**Interfaces:**
- Consumes: selected source mockup and rendered local route.
- Produces: browser evidence and final verification record.

- [ ] **Step 1: Run backend regression tests**

Run: `python -m pytest tests/v2 -q`

Expected: all tests pass.

- [ ] **Step 2: Start the existing combined dev runtime**

Run from `frontend`: `npm run dev`

Expected: API ready on `8787`, Vite ready on `5173`.

- [ ] **Step 3: Verify desktop and mobile interactions in the in-app browser**

Open a real match route, switch periods and tabs, inspect empty values, confirm no console errors, and capture desktop plus mobile screenshots.

- [ ] **Step 4: Perform blocking design QA**

Compare the selected mockup and implementation screenshots at the same state. Record source path, implementation path, viewport, focused comparisons, fixes, and `final result: passed` in `design-qa.md`.

- [ ] **Step 5: Update repository verification records**

Record exact commands, pass counts, browser route, remaining gaps, and the design-QA artifact in `docs/work-log.md`. Change readiness checkboxes only when complete evidence supports them.

