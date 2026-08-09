# Design QA: match analytics

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
