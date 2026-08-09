# Match Detail Analytics Design

## Objective

Rebuild the existing V2 match detail route as the selected Ullebets analytics screen while keeping all data read-only, leakage-safe, and sourced from the single cached match-detail API response.

Visual source of truth: `docs/design-references/match-detail-analytics-target.png`.

## Information Architecture

- The match header keeps league, kickoff, team identity, logos, and period controls compact.
- `Statistik` is the default match tab. `Odds & EV` and `Matchdata` remain visible navigation targets but model cards are not mixed into the statistics surface.
- The primary comparison shows both `FOR` and `EMOT` for every stat. Home bars grow left from the metric spine; away bars grow right. Exact values, ranks, league-average markers, and the direct home/away delta stay aligned.
- Shooting tempo occupies the full width and compares both teams in `LEDER`, `LIKA`, and `UNDERLAGE` states.
- Ten-minute shot volume uses two synchronized line charts, one per team, with `FOR`, `EMOT`, and league average on the same scale.
- First-goal percentages use four rings. Average first-goal minutes use one shared 0-45 timeline with clustered markers when values coincide.

## Data Contract

The existing `/api/v1/matches/:matchKey` response remains the only page request. It is extended with:

- support-team image URLs;
- profile date, generated timestamp, and sample size;
- `for` and `against` values, ranks, and league averages for each stat and period;
- shooting tempo by score state;
- shots per ten-minute window;
- first-goal percentages and average minutes.

Historical matches continue to use profiles as of the match date. Upcoming matches continue to use current profiles. Missing values remain `null`; the frontend never invents values or form.

## Interaction And Responsive Behavior

- Period controls switch between `ALL`, `1ST`, and `2ND` without another request.
- Match tabs are keyboard-operable. Statistics remain the implemented default; unavailable tab surfaces show an explicit state rather than fabricated data.
- Desktop follows the source layout. Tablet preserves the central comparison spine. Mobile turns each metric into a compact mirrored row and allows the chart regions to scroll horizontally without clipping labels.
- Tooltips expose exact chart values on pointer and keyboard focus.

## Performance

- No additional client-side waterfalls.
- Chart geometry is implemented with lightweight semantic HTML/CSS and the existing icon library; no heavy chart dependency is added.
- Derived view models are computed once per API payload and period selection.
- Lower chart regions use `content-visibility` so the match header and comparison render first.

## Verification

- Python contract tests prove against values, specials, logos, null handling, and historical as-of selection.
- React tests prove period switching, opposing comparison semantics, simultaneous `FOR`/`EMOT`, one 0-45 first-goal axis, and both ten-minute series.
- Typecheck, lint, frontend tests, Python tests, production build, desktop browser interaction, mobile browser interaction, and visual comparison against the selected mockup are required before handoff.

