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

## Team profile responsive width and hover alignment - 2026-08-30

**Findings**

- [P1] Post-fix rendered hover evidence is unavailable.
  Location: `/lag/:teamId`, all bars in both FÖR and MOT charts.
  Evidence: the supplied implementation screenshot shows the 30-column value
  row extending beyond its intended plot alignment and a hover marker several
  columns away from the pointer. The implementation now uses Recharts'
  measured responsive container instead of CSS-scaling a fixed 1100 px chart,
  but this session has no controllable in-app browser for an after-capture.
  Impact: source-level and automated evidence prove the coordinate-system fix,
  but the actual first/middle/last hover states cannot be visually accepted.
  Fix: capture the revised route at the same viewport and verify that each
  pointer position highlights and labels the same stat/period column.

**Source and intended state**

- Source visual truth:
  `C:/Users/ryd/AppData/Local/Temp/codex-clipboard-f612f822-16a4-43ac-8225-38485f4f085a.png`
- Source pixels: 1613 x 969; CSS viewport and device density not provided.
- Intended route: `/lag/:teamId`, dark desktop theme, home profile, 30 sorted
  stat/period combinations in each of the separate FÖR and MOT charts.
- Post-fix implementation screenshot: unavailable.
- Primary automated interaction contract: both chart regions own a
  `.recharts-responsive-container`; both retain exactly 30 stat identities.
- Console errors: not checked because no browser-rendered state was available.

**Required fidelity surfaces**

- Fonts and typography: unchanged; exact rendered label legibility remains
  blocked pending the after-capture.
- Spacing and layout rhythm: the page, cards and plots now use full available
  width; hard `1016/1100 px` minimum widths are removed; the value grid aligns
  to the plot's 60 px left and 26 px right drawable offsets.
- Colors and visual tokens: unchanged existing green/amber/red and league-line
  tokens.
- Image quality and assets: no image assets are involved; Recharts renders the
  data visualization.
- Copy and content: unchanged; all ten stats and all three periods remain in
  each chart and are covered by the existing behavior test.

**Comparison history**

- Pre-fix finding: the fixed 1100 px `BarChart` was visually stretched to
  `100%` by CSS while its internal hover coordinate system remained fixed;
  labels also retained hard minimum widths.
- Fix made: replaced the fixed chart with `ResponsiveContainer`, removed the
  forced wrapper width and overflow minimums, expanded the profile to full
  width, and aligned the footer grid with the drawable plot bounds.
- Post-fix comparison: blocked because no valid rendered implementation
  screenshot or browser hover capture is available in this session.

**Implementation Checklist**

- Capture the full revised team page at the source desktop width.
- Hover the first, a middle and the final stat and confirm tooltip identity.
- Check that neither chart nor its value row creates horizontal page overflow.
- Compare the revised chart region with the supplied screenshot in one image.

final result: blocked

## Team profile all-period sorting - 2026-08-30

**Findings**

- [P1] Post-fix implementation capture is unavailable.
  Location: `/lag/:teamId`, FÖR and MOT league-comparison charts.
  Evidence: the supplied implementation screenshot shows only ten bars and a
  period selector, while the supplied target shows many combinations ordered
  from highest positive deviation at the left to lowest negative deviation at
  the right. Code and behavior tests now build 30 sorted combinations and
  remove that selector, but this session still has no controllable in-app
  browser for a valid rendered after-image.
  Impact: exact bar density, text legibility, panel height and spacing cannot
  be visually accepted from code and DOM assertions alone.
  Fix: capture the deployed team route at the same desktop state and compare
  both images together.

**Evidence and state**

- Source visual truth: `C:/Users/ryd/AppData/Local/Temp/codex-clipboard-7dd4fa8d-3ebc-440e-97bb-a490265b93f5.png`
- Pre-fix implementation: `C:/Users/ryd/AppData/Local/Temp/codex-clipboard-0453359c-5d89-498c-aebb-f6b3fa2737ea.png`
- Source pixels: 1034 x 370; pre-fix implementation pixels: 1619 x 940.
- Intended state: desktop dark theme, one FÖR graph and one MOT graph, home
  profile, all three periods represented in each graph, descending deviation.
- Post-fix implementation screenshot: unavailable.
- Automated evidence: 30 unique combinations per graph; positive-to-negative
  ordering; null comparisons last; no period selector; zero-origin marker on
  every combination.
- Console errors: not checked because no browser-rendered post-fix state was
  available.

**Required fidelity surfaces**

- Fonts and typography: blocked pending post-fix capture; sizes were reduced
  for 30-column density.
- Spacing and layout rhythm: blocked pending post-fix capture; both chart
  panels remain separate and share the same 1100 px plot contract.
- Colors and visual tokens: unchanged green/amber/red and league-average line
  tokens from the previous implementation.
- Image quality and assets: no raster assets are required; Recharts owns the
  chart rendering.
- Copy and content: all ten stat names, all three Swedish period labels, FÖR,
  MOT, home/away context and liga-relative legend are implemented and tested.

**Comparison history**

- First visible comparison: P1 because only one period and ten bars were shown.
- Fix made: period moved into each row identity, 30 rows are always generated,
  sorting is descending by percentage deviation, and period controls removed.
- Post-fix comparison: blocked because the rendered implementation screenshot
  could not be captured.

**Implementation Checklist**

- Capture the deployed route at desktop width.
- Verify left-to-right order visually matches descending percentage labels.
- Verify 30 labels remain readable without obscuring the zero line.
- Compare the new capture with the target in one combined image input.

final result: blocked
