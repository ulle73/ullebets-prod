# Ullebets Style-1 Frontend Design

Date: 2026-08-08
Branch: `style-1`
Status: approved visual direction; provenance gate required before implementation

## Objective

Build the complete Ullebets frontend as an isolated presentation layer without
changing any existing V1/V2 model, prediction, odds, settlement, storage,
workflow, or database behavior.

The visual target is the approved Deep Navy evolution of the old Ullebets
interface: preserve the fast sports-product scanability and familiar five-item
navigation, while reducing nested borders, decorative pills and competing
colors. The result should feel like a trustworthy professional sports-analysis
product rather than a casino, crypto terminal or generic admin dashboard.

Visual polish is subordinate to data truth. The frontend must never fabricate a
bookmaker, market, score, result, ROI, CLV, model state, team crest, freshness
state or recommendation that cannot be traced to an existing backend field or
an explicitly documented display transformation.

## Non-negotiable safety boundary

`style-1` is presentation-only.

Do not modify:

- `src/ullebets_v1/**`
- `src/ullebets_v2/**`
- `scripts/**`
- `models/**`
- existing production GitHub Actions behavior
- database write paths
- model artifacts or policy registries
- settlement, ROI, CLV, prediction, odds, fixture, mapping or model logic

All frontend implementation lives under a new top-level `frontend/` directory.
A branch-only frontend CI workflow may be added if it is path-scoped and cannot
change production jobs.

A future read API is a separate implementation concern. This branch may define
TypeScript read models and adapters, but it must not add server-side business
logic merely to make a mock UI convenient.

## Gate 0: backend-to-UI provenance inventory

No page implementation starts until the relevant visible fields have been
mapped in the frontend data inventory.

For every visible value or state, record:

1. UI concept/label.
2. Backend collection or deterministic output.
3. Exact field or source fields.
4. Whether the UI displays the raw value or an allowed deterministic
   transformation.
5. Freshness/timing semantics.
6. Evidence/domain semantics.
7. Empty, unavailable and excluded behavior.

If a field has no mapped source, it is omitted or shown as unavailable. The
frontend must not fill gaps with plausible-looking values.

### Hard truth rules

- No bookmaker name may be invented. Current odds presentation is grounded in
  Unibet/Kambi source data. Bet365 or any other bookmaker must not appear unless
  a later backend contract explicitly supplies it.
- The legacy visual `72.3` / `85.4` style score is not automatically preserved.
  V2/V6 exposes grounded values such as `predicted_win_probability` and
  `expected_roi_units`; no synthetic 0-100 confidence score may be introduced
  without a documented and approved transformation.
- An analysis/model score is not the same as a registered V6 forward selection.
  Their evidence labels must remain distinct.
- A registered V6 selection is still `forward_test_only`; it is not proven
  profit.
- Out-of-domain scores, including Brazilian V6 diagnostics, may be displayed as
  excluded/non-actionable diagnostics but never as proof or a recommended bet.
- Historical backtest performance may be shown only as historical evidence. It
  must never be visually merged with untouched forward performance.
- T-30 closing is `t30_fallback`; it must never be presented as official CLV.
  Official CLV requires the backend's official closing state (currently T-10).
- League averages may only come from grounded team-profile league-average
  fields or another documented read model.
- Old UI concepts such as arbitrary biases, tempo badges, proprietary strength
  labels or team crests must not be retained unless their exact source is
  mapped.
- Color is semantic, not evidence. Gold does not upgrade an unproven state.

## Product architecture

Use a standalone frontend application:

- React
- TypeScript in strict mode
- Vite
- React Router
- TanStack Query as the read-only server-state boundary
- Radix UI primitives for accessible interactive foundations
- Lucide React for icons
- Motion for restrained micro-interactions
- token-driven CSS owned by Ullebets
- Vitest + React Testing Library
- ESLint

Use Radix only where behavior/accessibility is valuable (for example Dialog,
Dropdown Menu, Select, Tabs, Tooltip, Popover and Scroll Area). Do not adopt a
pre-styled component framework. Ullebets owns its visual language.

Motion is limited to hover/focus feedback, route/tab changes, drawers,
disclosures and list entry/exit. Respect `prefers-reduced-motion`. Animation may
never imply changing odds, confidence or system health when the underlying data
did not change.

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

No neon glow. No decorative gradient as a primary visual device. Shadows are
subtle and only establish depth between real surfaces.

### Border rule

Use spacing to separate sections and borders to separate actual content or
interactive objects.

Do not recreate:

`workspace border -> section border -> column border -> card border -> divider -> pill border`

Target maximum visible hierarchy:

1. page background
2. primary left rail/workspace surfaces
3. content cards and controls

Tabs, filter rows, Over/Under groupings, metadata groups and stat sections are
borderless unless the element is itself interactive.

### Typography and density

- system/Inter-like sans stack
- team names and the actual bet instruction dominate metadata
- model probability, EV and offered odds use tabular/numeric hierarchy
- league, scope, period, checkpoint and evidence state remain secondary
- recommendation cards are roughly 15-20% denser than the legacy layout
- more macro whitespace between sections; less dead micro-space inside cards

### Semantic color

- cyan: brand, selection, focus and navigation
- green: Over
- red: Under
- gold: verified proof/premium state only when the backend state warrants it
- neutral navy/gray: ordinary metadata

Do not create a rainbow of purple/blue/cyan metadata pills.

## Information architecture

### Primary navigation

Keep five primary destinations only:

- Översikt
- Auto
- Watchlist
- Resultatloop
- Historik

These are the recurrent user tasks and preserve the learned Ullebets structure.

### Contextual drill-down routes

- `/matcher/:matchId`
- `/lag/:teamId`
- `/modell`
- `/systemstatus`

They are reached from context, badges or detail links rather than competing in
the primary navigation.

Desktop keeps the old split mental model: `Dagens matcher` on the left and the
active workspace on the right. On smaller widths the rail collapses into a
Radix-based drawer/sheet pattern.

## Route contracts

### `/` and `/oversikt` — Översikt

Purpose: answer, within seconds, what matches exist and what grounded analysis
is worth inspecting.

May show:

- date and fixture count from canonical fixture data
- search/status/league/stat filters derived from available rows
- match list grouped by league
- top Over/Under analysis rows when grounded data exists
- model probability and/or expected EV when supplied by the row type
- offered odds only from grounded Unibet/Kambi data
- checkpoint/freshness state
- explicit evidence badge: analysis, forward-test selection, excluded/OOD, etc.

Do not add a `proof-ready` counter until a precise backend/read-model definition
exists. Do not invent a generic 0-100 score.

### `/auto` — Auto

Purpose: show the strongest currently eligible automatic V6 forward-test
selections, not every analytical market.

Current registered V6 policy semantics must remain visible: corners only,
away/total scopes, EV strictly above the registered minimum and below the
registered maximum, and training-domain filtering. The UI consumes selection
state; it does not reimplement policy logic.

OOD diagnostic scores may be shown in a separate excluded section but never in
the actionable ranking.

### `/watchlist` — Watchlist

User-curated match/signal identifiers stored in `localStorage` in Style-1.
Canonical/model values are always re-read from the data adapter; localStorage
must not become a second truth store for odds, model values or results.

### `/resultatloop` — Resultatloop

Use the forward-result read model. Distinguish:

- open
- pending
- settled
- unresolved
- excluded

Show settlement, actual value, PnL/ROI and CLV only when those fields are valid
for the row. Preserve timing/exclusion reasons.

### `/historik` — Historik

Historical exploration with date/stat/league/scope/period filters. Performance
must always name its evidence family. Official CLV and T-30 fallback coverage
are distinct.

### `/matcher/:matchId` — Match detail

Primary vertical-slice drill-down:

- canonical fixture identity, league, kickoff and status
- grounded model/analysis signals
- Unibet/Kambi market snapshots
- checkpoint timeline where rows exist
- team/profile comparison where available
- result/settlement after finish
- closing and CLV only when valid

Do not assume team crest URLs or live match minute data until mapped.

### `/lag/:teamId` — Team statistics

Use team-profile data for:

- team/league identity
- home/away profile context
- `for` / `against`
- league average
- rank when available
- ALL / 1ST / 2ND
- history rows and recent opponents
- specials only when each displayed special has a documented mapping

### `/modell` — Modell & proof

Trust/transparency page:

- active model/artifact identifier
- supported training domain
- registered forward policy summary
- current domain/exclusion state
- historical evidence clearly labelled historical
- forward evidence clearly labelled untouched/forward
- promotion-gate result and blocking reasons only from an actual evaluator/read
  model

Never turn historical `+28.65%` into a current ROI headline.

### `/systemstatus` — Data & system status

Read-only operational transparency from job runs, health/audit reports,
checkpoint coverage and data freshness. Do not expose credentials, masked API
key fragments, raw connection strings or other operational secrets.

## Read-model-first contract

Style-1 freezes frontend domain models, not a speculative REST surface.

The frontend should depend on six coarse read capabilities:

1. `DashboardReadModel`
2. `MatchDetailReadModel`
3. `PredictionsReadModel`
4. `ResultsReadModel`
5. `TeamReadModel`
6. `SystemStatusReadModel`

Adapters may use grounded in-repo fixtures during Style-1. Their TypeScript
shape must be traceable to the provenance inventory.

A later `frontend-read-api` branch can choose the smallest HTTP surface needed
to populate these models. `/api/v1` remains the likely namespace, but endpoint
count and boundaries are intentionally not frozen here.

There are no Style-1 write endpoints.

## Vertical-slice gate

Before scaling page markup, finish one complete flow:

`Dagens matcher -> Översikt -> Match detail -> signal -> odds/stats/model status`

The slice must include:

- desktop and mobile layout
- loading state
- valid empty state
- unavailable/error state
- excluded/unproven state
- keyboard navigation
- focus visibility
- grounded example fixtures
- route tests

Only after this slice passes its verification gate should the same primitives be
expanded to Auto, Watchlist, Resultatloop, Historik, Team, Model and System
Status.

## Data-state taxonomy

Every async/read surface supports four primary states:

1. loading
2. valid empty
3. unavailable/failed
4. present but unproven/non-actionable

Examples:

- no fixtures for a date -> valid empty
- T-10 window not yet reached -> unproven/not-yet-available
- failed source/job -> unavailable/failed
- Brazil V6 score outside training domain -> present but excluded
- T-30 closing without T-10 -> fallback available, official CLV unavailable

Do not collapse them into a single red error state.

## Reusable product components

Build around stable domain concepts:

- `AppShell`
- `TopNav`
- `MatchRail`
- `LeagueGroup`
- `MatchRow`
- `FilterBar`
- `SignalCard`
- `SignalMetric`
- `DirectionBadge`
- `EvidenceBadge`
- `DataFreshness`
- `CheckpointTimeline`
- `TeamStatTable`
- `PerformanceSummary`
- `ResultTable`
- `SystemHealthPanel`
- `StateNotice`
- `Skeleton`

Use Radix primitives underneath dialogs, selects, tooltips, popovers, menus,
tabs and scroll areas instead of rebuilding keyboard/focus behavior manually.

## Accessibility

Minimum requirements:

- keyboard-accessible navigation and controls
- visible focus distinct from hover
- semantic buttons, links, headings, forms and tables
- sufficient text/control contrast
- color never acts as the only Over/Under, win/loss or health indicator
- `aria-current` for active navigation
- labels for icon-only actions
- reduced-motion support
- no clipped content at browser zoom

## Responsive behavior

- large desktop: persistent match rail + workspace
- laptop: narrower/collapsible rail + workspace
- tablet: rail becomes drawer; workspace full width
- mobile: single column, compact header, filter controls in dialog/drawer

Decision-critical data must not require unreadable horizontal table scrolling;
provide responsive list/card renderings where needed.

## Testing and commit gate

A commit is not verified because it renders.

Every implementation commit runs the applicable subset of:

- `npm run typecheck`
- `npm run lint`
- `npm run test -- --run`
- `npm run build`
- route/component behavior tests
- responsive smoke checks

For every commit:

1. inspect the diff against its parent
2. confirm only intended paths changed
3. run the applicable frontend verification
4. inspect branch CI/status when available
5. repair failures before starting the next commit

Final verification additionally proves that protected backend/model/workflow
paths are unchanged from the Style-1 branch point and reruns the existing Python
regression suite (or an equivalent clean backend CI check).

## Implementation sequence

1. revise design contract and create provenance inventory
2. create detailed implementation plan
3. scaffold frontend/tooling/design tokens + isolated frontend CI
4. build shell and complete Overview -> Match vertical slice
5. verify the slice before expansion
6. build Auto
7. build Watchlist + Resultatloop + Historik
8. build Team + Model + System Status
9. responsive/accessibility polish and route/state coverage
10. final frontend and backend-isolation verification
11. update mandatory project work log

## Definition of done for Style-1

Style-1 is complete only when:

- all nine route families render and navigate correctly
- the five primary navigation destinations remain simple and coherent
- all visible data is provenance-backed or an explicitly allowed deterministic
  display transform
- no unsupported bookmaker or invented score/value appears
- V6/OOD/historical/forward/closing evidence states remain semantically honest
- Deep Navy styling is consistent across every route
- nested-border clutter is removed across the product
- desktop, laptop, tablet and mobile are usable
- loading, empty, failed and excluded/unproven states are designed
- frontend type/lint/test/build gates pass
- backend/model/workflow logic remains unchanged from the branch point
- final branch review finds no fabricated production claims

The read API implementation and production deployment remain separate work
items unless explicitly moved into a later branch.