# Ullebets Style-1 Frontend Design

Date: 2026-08-08
Branch: `style-1`
Status: approved visual direction; implementation pending

## Objective

Build the complete Ullebets frontend as an isolated presentation layer without
changing any existing V1/V2 model, prediction, odds, settlement, storage,
workflow, or database behavior.

The visual target is the approved Deep Navy version of the existing Ullebets
layout: preserve the old product's information hierarchy and fast scanability,
but remove excessive nested borders, reduce decorative pills, strengthen
typographic hierarchy, and make the product feel more trustworthy and premium.

The frontend must never fabricate a bookmaker, market, score, result, ROI, CLV,
or model state that the backend does not actually expose. Empty or unproven
states must be shown as such.

## Non-negotiable safety boundary

This branch is presentation-only.

Do not modify:

- `src/ullebets_v1/**`
- `src/ullebets_v2/**`
- `scripts/**`
- `models/**`
- existing GitHub Actions workflow behavior
- database write paths
- model artifacts or policy registries
- settlement, ROI, CLV, prediction, odds, fixture, or mapping logic

The frontend is added under a new top-level `frontend/` directory. It may define
read-only TypeScript contracts that describe the future frontend API, but it
must not add server-side business logic to satisfy those contracts in this
styling branch.

## Product architecture

Use a standalone frontend application:

- React
- TypeScript
- Vite
- React Router for routes
- TanStack Query for read-only server-state boundaries and future API wiring
- Lucide React for icons
- Motion for restrained transitions and micro-interactions
- CSS Modules or a small token-driven global CSS layer for styling
- Vitest + React Testing Library for component/route behavior
- ESLint + TypeScript strict mode

Avoid a heavy component framework. The UI is distinctive enough that a large
pre-styled system would create more override work than value. Reusable local
primitives should be used for buttons, pills, panels, tabs, status badges,
empty states, skeletons, tooltips, and tables.

No animation may communicate data that is not real. Motion is limited to hover,
focus, tab changes, route transitions, disclosure panels, and list entry/exit.
Respect `prefers-reduced-motion`.

## Visual system

### Core palette

- Page background: `#07111D`
- Primary panel: `#0C1724`
- Content card: `#101C29`
- Elevated/hover surface: `#142231`
- Primary text: `#F5F7FA`
- Secondary text: `#8B98A8`
- Muted text: `#647386`
- Brand/active: `#20B8C4`
- Over: `#32C78A`
- Under: `#EF5C68`
- Proof/premium: `#C9A44C`
- Default border: `rgba(255,255,255,0.08)`
- Strong border: `rgba(255,255,255,0.12)`

No neon glow. No decorative gradients as a primary visual device. Shadows are
subtle and used only to create depth between real surfaces.

### Border rule

Use spacing to separate sections and borders to separate interactive/content
objects.

The page must not recreate the old chain of:

`workspace border -> section border -> column border -> card border -> inner divider -> pill border`

Target maximum visible hierarchy:

1. page background
2. primary left/right panel boundary
3. content cards and interactive controls

Tabs, filter rows, Over/Under columns, card metadata groups, and stat groupings
are borderless unless an actual control requires a hit target.

### Typography and density

- Inter or system sans stack
- Strong numeric hierarchy for model score and odds when available
- Team names and recommendation wording are more prominent than metadata
- League, scope, period, and supporting statistics are secondary
- Cards are approximately 15-20% denser than the legacy layout
- More whitespace between functional sections, less dead space inside cards

### Semantic color

- Cyan: brand, navigation, selection, focus
- Green: Over only
- Red: Under only
- Gold: proof-ready or genuinely exceptional verified status only
- Everything else: neutral navy/gray

Do not use purple/blue/cyan pills simultaneously for ordinary metadata.

## Global shell

Desktop retains the legacy split-screen mental model:

- left: `Dagens matcher`
- right: active workspace/page

The left match rail remains available on the main analysis surfaces and can be
collapsed at narrower desktop widths.

Mobile changes to a single-column flow with a top bar and a match-drawer/filter
sheet. No desktop card may simply overflow horizontally on mobile.

Top-level navigation preserves the familiar old Ullebets labels:

- Översikt
- Auto
- Watchlist
- Resultatloop
- Historik

Additional deep pages are reached contextually rather than crowding the primary
navigation.

## Frontend routes

The complete Style-1 frontend consists of nine user-facing route families.

### 1. `/` and `/oversikt` — Översikt

The approved Deep Navy dashboard.

Contains:

- date selector
- match count
- search
- Alla / Kommande / Pågår / Resultat filters
- league filter
- match list grouped by league
- status counters: date, shortlist, proof-ready, alerts, played
- advanced league/stat filters
- top Over and Under recommendation columns
- compact recommendation cards
- data freshness/warning treatment when necessary

This page preserves the old two-column Over/Under scan because it is already a
learned product pattern for the current user, but removes nested visual boxes.

### 2. `/auto` — Auto

Ranked automatic model output for the selected date/window.

Contains:

- strongest eligible selections first
- model/domain eligibility state
- score/EV/odds only when present in the data contract
- checkpoint freshness
- filter by league/stat/scope/period
- explicit exclusion state for out-of-domain or non-actionable model output

No Brazilian/OOD score may be presented as proven model evidence.

### 3. `/watchlist` — Watchlist

User-curated matches/signals.

In Style-1 this is frontend-local state only (`localStorage`) so no new backend
write logic is introduced. The data objects stored are identifiers and display
preferences, never canonical betting/model data.

Contains:

- watched matches
- watched signal rows
- kickoff countdown/time
- latest known freshness state
- empty state explaining how to add an item

### 4. `/resultatloop` — Resultatloop

Operational result loop for active/open and recently settled selections.

Contains:

- open vs settled vs excluded states
- match
- market
- selection
- offered line/odds if available
- actual outcome if settled
- win/loss/push/excluded state
- timing or data-quality exclusion reason when relevant

It must never merge operational descriptive results with model-specific proven
ROI.

### 5. `/historik` — Historik

Historical results and performance exploration.

Contains:

- date range
- league/stat/scope/period filters
- settled table/list
- ROI/PnL only for the selected evidence family actually returned
- closing odds and CLV only when valid live closing data exists
- coverage indicators
- clear empty/unproven state when closing/CLV evidence is absent

Historical descriptive numbers and forward model proof receive distinct labels.

### 6. `/matcher/:matchId` — Match detail

The primary drill-down page.

Header:

- league
- kickoff/status
- home and away teams
- freshness/warning indicator

Sections:

- best signals
- all model/analysis signals
- available Unibet/Kambi market snapshots
- checkpoint timeline: T-3D, T-2D, T-1D, T-2H, T-30, T-10 where present
- team comparison by canonical stat
- historical form relevant to the selected stat/scope/period
- result and settlement after finish
- closing/CLV only when valid

No other bookmaker branding is permitted unless a future backend contract
explicitly provides it.

### 7. `/lag/:teamId` — Team statistics

Dedicated team profile for the readiness requirement to expose team statistics
by stat, period, and scope.

Contains:

- team/league identity
- canonical corners / total shots / shots on goal first
- selectable stat
- ALL / 1ST / 2ND period
- home / away / total or for/against scope where supported by the actual data
- recent match rows
- averages and distribution summaries only from provided data
- links back to related fixtures

### 8. `/modell` — Modell & proof

Trust page for the model rather than a marketing page.

Contains:

- active production model identifier
- supported training-domain leagues
- current forward-evidence state
- immutable policy summary
- distinction between historical backtest and untouched forward evidence
- promotion-gate progress only from real backend metrics
- explicit `UNPROVEN`/`BLOCKED` presentation where current evidence is missing

The page must not present historical +28.65% ROI as proven future performance.

### 9. `/systemstatus` — Data & system status

Operational transparency page.

Contains:

- data freshness by source/subsystem
- latest fixture/odds/stat/result update
- source connectivity state
- mapping/audit warnings
- missed/available checkpoint coverage
- closing/CLV coverage
- model-domain exclusions
- recent job health when exposed

This is the destination for warning badges shown elsewhere in the product.

## Planned read API contract

Style-1 defines the client interfaces and URL contract but does not implement
backend endpoints. A later backend/API branch can satisfy these without
rewriting the UI.

Version all routes under `/api/v1`.

### Core endpoints

1. `GET /api/v1/dashboard?date=YYYY-MM-DD`
   - counters, league groups, fixture summaries, top signal summaries,
     freshness summary

2. `GET /api/v1/fixtures?date=YYYY-MM-DD&status=&league_id=`
   - fixture list for the left rail and match pages

3. `GET /api/v1/fixtures/:matchId`
   - canonical match identity, teams, league, kickoff, result/status

4. `GET /api/v1/fixtures/:matchId/signals`
   - analysis/model signal rows with eligibility and evidence labels

5. `GET /api/v1/fixtures/:matchId/odds`
   - normalized Unibet/Kambi market snapshots and checkpoint metadata

6. `GET /api/v1/fixtures/:matchId/stats`
   - team/match canonical stats needed by the match detail page

7. `GET /api/v1/predictions?date=&state=&league_id=&stat_key=&scope=&period=`
   - forward/operational prediction rows for Auto and Resultatloop

8. `GET /api/v1/results?from=&to=&league_id=&stat_key=&scope=&period=`
   - settled/open/excluded result rows

9. `GET /api/v1/performance?from=&to=&evidence_family=&league_id=&stat_key=`
   - PnL/ROI/CLV aggregates with explicit coverage and evidence family

10. `GET /api/v1/teams/:teamId/stats?stat_key=&period=&scope=`
    - team-profile statistics

11. `GET /api/v1/model/status`
    - active artifact/policy, domain, promotion/evidence state

12. `GET /api/v1/system/status`
    - freshness, source, audit, mapping and job-health summaries

13. `GET /api/v1/meta/leagues`
    - league filter metadata

14. `GET /api/v1/meta/stats`
    - canonical stat/scope/period filter metadata

There are no Style-1 write endpoints. Watchlist is local-only until an explicit
product/auth persistence requirement is approved.

## Data truth and empty states

Every view must support four distinct data states:

1. loading
2. valid empty
3. unavailable/failed
4. present but unproven/non-actionable

These states must not be collapsed into a generic red error.

Examples:

- no fixtures on a date -> valid empty
- no T-10 yet because the window has not occurred -> unproven
- closing runner/source failure -> failed/unavailable
- Brazil V6 score outside the fitted domain -> present but non-actionable

This distinction is a core trust feature.

## Components

Build reusable components around stable product concepts rather than page-only
markup:

- `AppShell`
- `MatchRail`
- `TopNav`
- `StatusCounter`
- `FilterBar`
- `LeagueGroup`
- `MatchRow`
- `SignalCard`
- `SignalScore`
- `DirectionBadge`
- `EvidenceBadge`
- `DataFreshness`
- `CheckpointTimeline`
- `TeamStatTable`
- `PerformanceSummary`
- `ResultTable`
- `SystemHealthPanel`
- `EmptyState`
- `ErrorState`
- `Skeleton`
- `Tooltip`

The styling system should use CSS custom-property tokens for color, spacing,
radii, type scale, shadows, transitions and focus rings.

## Accessibility

Minimum requirements:

- keyboard-accessible navigation and controls
- visible focus ring distinct from hover
- semantic buttons/links/forms
- sufficient contrast
- color is never the only Over/Under or win/loss indicator
- `aria-current` for active navigation
- labels for icon-only controls
- reduced-motion support
- responsive zoom without clipped content

## Responsive behavior

Target classes:

- large desktop: split rail + workspace
- normal laptop: narrower/collapsible rail + workspace
- tablet: rail becomes drawer, content remains full-width
- mobile: one column, compact header, filters in sheet, cards become stacked

Tables must provide a mobile list/card representation when horizontal scrolling
would make the decision information difficult to parse.

## Testing strategy

No Style-1 commit is considered verified merely because it renders.

Every implementation commit must run the applicable subset of:

- `npm run typecheck`
- `npm run lint`
- `npm run test -- --run`
- `npm run build`
- route smoke tests
- component interaction tests
- responsive visual/manual checks for desktop and mobile

The final branch verification must also run the existing Python regression suite
or an equivalent unchanged-backend CI check to prove the frontend work did not
modify backend behavior.

Verification evidence must be recorded per commit. A frontend-only CI workflow
may be added for `style-1` if it is isolated and does not alter any existing
production workflow behavior.

## Commit strategy

Prefer small reviewable commits:

1. design/spec only
2. frontend scaffold + tooling + tokens
3. shared shell/navigation/match rail
4. Overview + Auto
5. Watchlist + Resultatloop + Historik
6. Match detail + Team statistics
7. Model + System status
8. responsive/accessibility polish
9. final verification/documentation

At each commit:

- inspect the diff against its parent
- verify only intended paths changed
- run the relevant frontend checks
- inspect CI/status where available
- stop and repair before the next commit if verification fails

## Definition of done for Style-1

Style-1 is complete when:

- all nine route families render and navigate correctly
- the approved Deep Navy system is applied consistently everywhere
- the legacy information hierarchy remains recognizable
- nested-border clutter is removed across the product
- desktop, laptop, tablet and mobile layouts are usable
- loading, empty, failure and unproven states are styled
- no unavailable bookmaker/data values are fabricated
- frontend test/type/lint/build checks pass
- existing backend files and logic are unchanged from the branch point
- a final branch-vs-main diff proves frontend isolation

A read API implementation and production deployment are separate work items and
are not part of this styling branch.