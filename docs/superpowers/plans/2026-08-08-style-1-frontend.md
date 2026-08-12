# Style-1 Frontend Implementation Plan

Date: 2026-08-08
Branch: `style-1`
Design spec: `docs/superpowers/specs/2026-08-08-style-1-frontend-design.md`
Data contract: `docs/superpowers/specs/2026-08-08-style-1-frontend-data-inventory.md`

## Goal

Implement the complete Deep Navy Ullebets frontend without changing any
existing backend/model/business logic. Every production-looking value must be
traceable to the frontend data inventory. Every feature commit is prepared with
TDD in an isolated local frontend workspace and is pushed to `style-1` only
after typecheck, lint, tests and build pass.

## Protected paths

The implementation must not modify:

- `src/ullebets_v1/**`
- `src/ullebets_v2/**`
- `scripts/**`
- `models/**`
- existing production workflow behavior

Allowed implementation paths:

- `frontend/**`
- branch-only/path-scoped frontend verification workflow
- Style-1 docs/work-log updates

## Verification contract per implementation commit

Before each GitHub commit:

1. Write the behavior test first in the isolated frontend workspace.
2. Run the narrow test and observe the intended failure.
3. Implement the minimum behavior.
4. Re-run the narrow test and observe success.
5. Run `npm run typecheck`.
6. Run `npm run lint`.
7. Run `npm run test -- --run`.
8. Run `npm run build`.
9. Review the staged file set and confirm protected paths are absent.
10. Commit/push atomically to `style-1`.
11. Inspect the GitHub commit diff and branch CI/status before continuing.

Configuration-only bootstrap changes are allowed without a behavior RED test,
but no user-facing production behavior is added under that exception.

## Task 1 — Frontend foundation and truth layer

### Files

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/tsconfig.json`
- `frontend/vite.config.ts`
- `frontend/eslint.config.js`
- `frontend/index.html`
- `frontend/src/test/setup.ts`
- `frontend/src/domain/types.ts`
- `frontend/src/domain/formatters.ts`
- `frontend/src/domain/formatters.test.ts`
- `frontend/src/data/preview-data.ts`
- `frontend/src/data/read-repository.ts`
- `frontend/src/styles/tokens.css`
- `frontend/src/styles/global.css`
- `.github/workflows/style-1-frontend.yml`

### TDD behaviors

- Probability is displayed as a percentage and remains explicitly a model
  probability.
- EV is displayed from `expected_roi_units`, not a generic score.
- Missing CLV renders as unavailable, never `0%`.
- T-30 is labelled fallback, T-10 official when the source state says so.
- Internal stat/scope/period keys map deterministically to Swedish display
  labels.
- Preview data contains no unsupported bookmaker and no generic 0-100 score.

### Commit

`feat(frontend): scaffold style-1 foundation`

## Task 2 — Application shell, navigation and match rail

### Files

- `frontend/src/main.tsx`
- `frontend/src/app/App.tsx`
- `frontend/src/app/providers.tsx`
- `frontend/src/app/routes.tsx`
- `frontend/src/components/AppShell.tsx`
- `frontend/src/components/TopNav.tsx`
- `frontend/src/components/MatchRail.tsx`
- `frontend/src/components/LeagueGroup.tsx`
- `frontend/src/components/MatchRow.tsx`
- `frontend/src/components/primitives/**`
- route/shell tests

### TDD behaviors

- Primary navigation exposes exactly Översikt, Auto, Watchlist, Resultatloop and
  Historik.
- Drill-down routes are reachable but do not crowd primary navigation.
- Desktop shell renders persistent match rail and workspace.
- Mobile shell exposes match rail through an accessible drawer/dialog.
- Active route exposes `aria-current`.
- Keyboard focus remains visible.

### Commit

`feat(frontend): build style-1 application shell`

## Task 3 — Complete Overview -> Match vertical slice

### Files

- `frontend/src/pages/OverviewPage.tsx`
- `frontend/src/pages/MatchDetailPage.tsx`
- `frontend/src/components/FilterBar.tsx`
- `frontend/src/components/SignalCard.tsx`
- `frontend/src/components/SignalMetric.tsx`
- `frontend/src/components/DirectionBadge.tsx`
- `frontend/src/components/EvidenceBadge.tsx`
- `frontend/src/components/DataFreshness.tsx`
- `frontend/src/components/CheckpointTimeline.tsx`
- `frontend/src/components/TeamStatTable.tsx`
- `frontend/src/components/StateNotice.tsx`
- vertical-slice tests

### TDD behaviors

- Overview renders grounded match identity, league, kickoff and filters.
- Signal cards display direction, stat, scope, period, model probability,
  model-EV and offered odds only when the read model provides them.
- The UI does not render `Bet365` or a synthetic 0-100 score.
- OOD analysis is visually excluded/non-actionable.
- Match detail shows grounded checkpoints and distinguishes missing/not-yet from
  failed states.
- Team comparison uses mapped team-profile values/league averages only.
- Loading, valid-empty, unavailable and excluded states all have distinct UI.
- The complete slice is usable at desktop and mobile widths.

### Commit

`feat(frontend): complete overview match vertical slice`

## Task 4 — Auto

### Files

- `frontend/src/pages/AutoPage.tsx`
- `frontend/src/components/SelectionList.tsx`
- Auto tests

### TDD behaviors

- Actionable Auto ranking consumes only registered `forward-test` selections.
- Raw analytical/OOD rows never enter the actionable list.
- Forward-test state is labelled as forward validation, not proof.
- Probability, EV and odds remain source-backed.
- No client-side recreation of V6 policy eligibility occurs.

### Commit

`feat(frontend): build auto forward-test view`

## Task 5 — Watchlist, Resultatloop and Historik

### Files

- `frontend/src/pages/WatchlistPage.tsx`
- `frontend/src/pages/ResultsLoopPage.tsx`
- `frontend/src/pages/HistoryPage.tsx`
- `frontend/src/components/ResultTable.tsx`
- `frontend/src/components/PerformanceSummary.tsx`
- local watchlist hook/storage adapter
- page tests

### TDD behaviors

- Watchlist stores identifiers/preferences only; odds/results are re-read from
  repository data.
- Resultatloop distinguishes open, pending, settled, unresolved and excluded.
- Excluded rows retain the source reason.
- T-30 fallback is never rendered as official CLV.
- Missing CLV renders unavailable rather than zero.
- Historik labels historical/descriptive and forward evidence separately.
- PnL/ROI are shown only for rows valid for performance.

### Commit

`feat(frontend): build watchlist results and history views`

## Task 6 — Team, Model and System Status

### Files

- `frontend/src/pages/TeamPage.tsx`
- `frontend/src/pages/ModelPage.tsx`
- `frontend/src/pages/SystemStatusPage.tsx`
- `frontend/src/components/SystemHealthPanel.tsx`
- related tests

### TDD behaviors

- Team page renders for/against, league average, rank and history only from the
  mapped team-profile contract.
- Model page separates historical backtest from untouched forward evidence.
- Historical +28.65% is never presented as current proven ROI.
- Promotion status and blockers are source-backed.
- System status renders job/health/audit state without credentials or secret
  fragments.

### Commit

`feat(frontend): build team model and system views`

## Task 7 — Responsive, accessibility and visual polish

### Files

- shared component/page CSS
- responsive styles
- accessibility/regression tests

### TDD behaviors

- No decision-critical desktop table requires unreadable horizontal scrolling
  on mobile.
- Icon-only controls have accessible names.
- Over/Under, result and health meaning is not color-only.
- Reduced-motion preference disables non-essential transitions.
- Focus styling is visible on interactive controls.
- All nine route families smoke-render without console/test errors.

### Commit

`style(frontend): polish responsive accessible style-1 UI`

## Task 8 — Final verification and project evidence

### Verification

Run locally:

```text
npm run typecheck
npm run lint
npm run test -- --run
npm run build
```

Then verify on GitHub:

- Style-1 frontend workflow green at branch HEAD.
- `main...style-1` diff contains no changes under protected backend/model paths.
- Full existing Python backend regression suite passes in a clean hosted
  verification run, or equivalent current backend CI evidence is attached.
- No generated secrets, caches, build output or `node_modules` are committed.
- Search the branch diff/content for unsupported `Bet365`, generic legacy score
  fixtures and accidental production claims.

Update `docs/work-log.md` with:

- objective/status
- exact frontend files/subsystems
- exact verification commands/results
- frontend CI evidence
- protected-path diff evidence
- remaining read-API/deployment work

### Commit

`docs: verify complete style-1 frontend`

## Completion gate

Do not call Style-1 complete until every route, state and verification above is
finished. A polished Overview alone is not completion. A green frontend build
alone is not proof that backend isolation was preserved.