# Design QA

## Match analytics

## Result

**PASSED** for the implemented match-detail scope on 2026-08-09.

The final implementation was compared together with the selected visual target at the same 1009 px desktop width. No P0 or P1 visual defects remain. The remaining visible differences are data-driven: the verified runtime fixture is Burnley-Wolverhampton rather than the Cruzeiro-Mirassol example, and unavailable source values are omitted rather than invented.

## Evidence

- Target: `docs/design-references/match-detail-analytics-target.png`
- Desktop implementation: `docs/design-references/match-detail-analytics-implementation-desktop.png`
- Mobile implementation: `docs/design-references/match-detail-analytics-implementation-mobile.png`
- Bottom-section verification: `docs/design-references/match-detail-analytics-implementation-bottom.png`
- Verified route: `http://localhost:5173/matcher/sofascore%3A14023960`
- Desktop viewport: 1009 x 1558
- Mobile viewport: 390 x 844

## Visual comparison

1. The first comparison found three blocking mismatches: the global application header remained visible, team crests fell back to initials, and the content was too vertically loose.
2. Focus mode now removes the global shell navigation, the three match tabs lead the page, real local team crests render, and the complete desktop document is 1585 px high.
3. Home and away bars use one comparable scale and point toward the central metric spine. League-average ticks and ranks remain visible.
4. Shot-tempo states use compact bars; 10-minute output uses two line charts; the first-goal panel uses four markers on one 0-45 minute axis.
5. At 390 px, the document has no body-level horizontal overflow (`scrollWidth == clientWidth == 375`). The dense stat table scrolls inside its own panel.

## Interaction and runtime checks

- FT, 1H and 2H period controls switch local views without an extra API request.
- Statistik, Lag & odds and Backtest tabs switch to their matching panels.
- Real V2 match data, team profiles and local crest assets render without synthetic fallback data.
- The browser console returned zero errors in desktop and mobile checks.
- Frontend typecheck, lint, all 23 frontend tests, production build, and all 401 V2 backend tests passed.

## Auto forward ledger

### Result

**PARTIAL** on 2026-08-10.

The desktop implementation is visually and functionally verified against the
live V2 read API. Mobile acceptance remains outstanding.

### Evidence

- Target: `docs/design-references/auto-forward-ledger-target.png`
- Implemented route: `http://localhost:5173/auto`
- Live read: 67 raw rows -> 4 canonical straight exposures
- Excluded: 46 combo legs and 8 shadow-only rows
- Collapsed: 9 repeated export exposures
- Registered V6: 0; legacy: 4
- Full backend suite: 434 passed
- Full frontend suite: 23 passed
- Frontend typecheck, lint, and production build passed
- Desktop V6 empty state and Legacy ledger rendered with zero console errors

### Remaining visual checks

1. Repeat at a mobile viewport and verify no body-level horizontal overflow.
2. Fix any mobile-only mismatch before changing this result to passed.

final result: partial

## Team profile FÖR/MOT charts - 2026-08-30

**Findings**

- [P1] Rendered reference comparison is unavailable.
  Location: `/lag/:teamId`, both league-comparison charts.
  Evidence: the source visual was opened at its original 1276 x 477 pixels,
  but this Codex session did not expose the required controllable in-app
  browser, so no browser-rendered implementation screenshot could be captured.
  Impact: typography, spacing, plot proportions, bar density, responsive
  overflow, and exact palette cannot be accepted from code and tests alone.
  Fix: capture the implemented route at a matching desktop viewport and compare
  source and implementation in one combined image input.

**Source and intended state**

- Source visual truth: `C:/Users/ryd/AppData/Local/Temp/codex-clipboard-4c4ffcf7-3ec7-45b5-ab4b-5bce59412a01.png`
- Source pixels: 1276 x 477, density not provided.
- Intended implementation route: `/lag/:teamId`.
- Intended viewport: 1276 CSS px wide, device scale factor 1.
- State: dark theme, home profile, total period, FÖR chart above MOT chart.
- Implementation screenshot: unavailable.
- Primary interactions covered by automated tests: home/away presence, total /
  first half / second half presence, ten fixed stat keys in both graphs.
- Console errors: not checked because no browser-rendered evidence was available.

**Required fidelity surfaces**

- Fonts and typography: blocked pending rendered comparison.
- Spacing and layout rhythm: blocked pending rendered comparison.
- Colors and visual tokens: implementation uses existing product tokens plus
  green/amber/red semantic chart tokens; exact visual match remains blocked.
- Image quality and assets: no imagery or custom graphic assets are required;
  bars are rendered by Recharts rather than handcrafted SVG or CSS art.
- Copy and content: implemented FÖR, MOT, ligasnitt legend, home/away and all
  three periods; code and behavior tests pass.

**Full-view and focused comparison evidence**

- Full-view comparison: blocked; implementation screenshot unavailable.
- Focused chart-region comparison: blocked for the same reason.
- Comparison history: no valid first visual pass could be performed, so no
  visual fixes are claimed.

**Implementation Checklist**

- Capture the actual team route at the matched desktop viewport.
- Combine source and implementation screenshots in one comparison image.
- Check positive bars start exactly at zero and have no green tail below it.
- Check both charts and all period/context controls, then resolve every P0-P2.

final result: blocked
