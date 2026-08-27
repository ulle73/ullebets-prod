# Durable closing capture and unified results design

Date: 2026-08-27

Status: Approved by the user for implementation

## Decision

Ullebets will use a portable Python closing watcher on free standard
GitHub-hosted runners. A scheduled GitHub event is only a redundant seed that
starts a watcher several hours before kickoff; it is not the clock that must
hit T-30 or T-10. The running watcher uses canonical fixture times and MongoDB
state to perform the actual timed capture, recovery, and audit work.

T-30 is an accepted product closing. T-10 remains the preferred later closing
and upgrades T-30 when available. Every persisted and rendered CLV value keeps
its actual closing checkpoint and age so the two qualities remain auditable.

The frontend will have one forward-bet destination labelled `Spel & resultat`.
It will combine open, settled, and excluded rows and replace the duplicate Auto
and Resultatloop destinations.

## Constraints

- Setup and ongoing execution must cost 0 SEK and use no trial plan.
- Standard GitHub-hosted runners are currently free for this public repository.
- Legacy MongoDB databases remain read-only references. All new state belongs
  to `ullebets_v2` and every V2 write continues to fail closed on another
  database name.
- Raw odds and immutable model observations are not rewritten.
- A change in the product closing definition must not silently rewrite the
  historical model-promotion contract after outcomes have been inspected.
- No provider name may enter public URLs.

## Closing and CLV semantics

Closing policy V2 has two accepted qualities:

1. `t10`: preferred close from an accepted T-10 observation.
2. `t30`: accepted close from an accepted T-30 observation when T-10 is absent.

The derived closing row always selects T-10 over T-30. It stores:

- policy version;
- actual checkpoint label;
- actual observation time and minutes before kickoff;
- accepted-for-product-CLV flag;
- eligible-for-existing-promotion-CLV flag;
- exact market identity, line, direction prices, and price history.

Product CLV and beat-close calculations accept both V2 qualities. Existing
promotion evidence remains T-10-only until a separately versioned forward
promotion policy is declared prospectively. This prevents a product decision
from retroactively changing an already inspected model gate.

The UI never uses the word `saknas` for a valid T-30 comparison. It names the
evidence:

- `Slog closing +X.X % · T-10`;
- `Missade closing -X.X % · T-10`;
- `Slog closing +X.X % · T-30`;
- `Missade closing -X.X % · T-30`;
- `Väntar på closing` before the capture window;
- `Closing missad` after kickoff when neither accepted close exists.

## Watcher architecture

### Seed workflow

The closing workflow stays enabled. A lightweight scheduled seed runs at
off-peak minute offsets several times per hour. It exits immediately when no
eligible fixture is near. When an uncovered fixture is inside the configured
lookahead, it starts or joins one bounded watch session.

The existing hourly odds workflow no longer enables or disables the closing
workflow. It continues to own ordinary long-horizon checkpoint capture.

### Watch session

One watch session covers a bounded cluster of kickoffs and runs for less than
the GitHub-hosted six-hour job limit. The initial implementation uses a
four-hour fixture lookahead and a five-and-a-half-hour workflow timeout.

The watcher:

1. loads upcoming canonical fixtures and their accepted snapshots;
2. claims a MongoDB lease with a unique owner and expiry;
3. writes a heartbeat at least once per minute;
4. waits using UTC fixture time rather than repeated GitHub scheduling;
5. begins T-30 attempts near 35 minutes before kickoff and retries through the
   accepted T-30 window;
6. begins T-10 attempts near 11 minutes before kickoff and retries each minute
   through five minutes before kickoff;
7. refreshes closing, CLV, forward results, and registered forward evidence
   after a newly persisted snapshot;
8. records terminal per-match checkpoint outcomes and releases the lease.

Capture remains idempotent. Repeated attempts may reuse existing accepted rows
but may not overwrite immutable raw odds or frozen prediction evidence.

### Recovery

Scheduled seed runs share the existing global closing concurrency group. If a
watcher exits or fails, the next seed reads the expired heartbeat/lease and
resumes the remaining fixture window. Manual `workflow_dispatch` remains
available for safe recovery and dry-run verification.

MongoDB, not runner memory, is the source of truth for:

- session owner and lease expiry;
- heartbeat and last successful poll;
- pending fixtures and required checkpoints;
- capture attempts and source errors;
- terminal captured, missed, or no-market states.

## Read API design

The Auto read path already joins selections and results, so it becomes the
single server-side source for the unified page. The frontend must not combine
independent Auto and Resultatloop responses client-side.

Each grouped forward row adds:

- accepted closing count;
- T-10 and T-30 closing counts;
- beat-closing count and rate;
- signed average and per-observation CLV;
- closing status and quality;
- selected and closing odds;
- closing checkpoint/time/age;
- exact-market odds history;
- observation-level comparison details for grouped checkpoint journals.

Odds-history items contain snapshot label, observation time, odds, line,
selected-state, closing-state, and quality. History never mixes a different
stat, scope, period, line, or direction into one movement series.

Legacy official-CLV fields remain temporarily available for API compatibility,
but the new accepted-closing fields drive the product UI.

## Frontend design

Top navigation exposes one destination: `Spel & resultat`. `/auto` remains the
canonical route. `/resultatloop` redirects to `/auto?status=settled` so old
bookmarks keep working.

The unified page has URL-backed filters for:

- `Öppna`;
- `Rättade`;
- `Exkluderade`;
- model family, league, stat, scope, period, direction, and checkpoint.

Model EV and CLV are distinct columns because they answer different questions:

- model EV is the expected edge at capture time;
- CLV is the realized price comparison against the accepted market close.

A row with one observation shows its signed CLV and beat/miss label directly.
A grouped checkpoint row shows mean CLV and `N/M slog closing`; its detail
panel lists every underlying observation.

Hover, keyboard focus, and touch activation open the same odds-movement panel.
It shows chronological exact-market prices, highlights selected observations,
and marks T-30/T-10 closing. The content is not hover-only.

Summary cards show settled plays, ROI, accepted mean CLV, beat-close rate, and
closing coverage split into T-10, T-30, waiting, and missed. T-30 is included
in accepted product CLV but never visually merged into T-10 coverage.

## Provenance repair

The V2 market adapter must pass `snapshot_label` and `snapshot_type` into the
prediction frame. Score persistence and forward prediction already copy those
fields, so repairing the adapter restores the full source path and removes
false `bäst saknas` labels.

An integration test must use a real adapter market row and prove:

`market snapshot -> adapter prediction frame -> score -> forward bet -> read API`.

Synthetic tests that inject the label downstream are insufficient.

## Error handling and observability

The watcher distinguishes:

- valid empty source response;
- source/provider error;
- missing event mapping;
- market temporarily suspended;
- lease lost;
- no T-30 capture;
- T-30 captured but T-10 missed;
- both accepted checkpoints captured.

T-30-only is a successful product closing with degraded checkpoint quality,
not `CLV saknas`. Missing both accepted checkpoints after kickoff is a failed
closing lifecycle. GitHub job summaries and persisted health/audit rows expose
counts and exact affected match keys without secrets.

The watcher exits non-zero for an unrecovered session failure or for a finished
target with neither accepted close. T-30 captured/T-10 missed is persisted as a
visible degraded state and warning while CLV remains usable.

## Testing and acceptance

Implementation is test-driven and must cover:

- session planning around multiple kickoff clusters;
- UTC boundary behavior for T-30 and T-10;
- lease claim, heartbeat, expiry, takeover, and release;
- runner restart after T-30 but before T-10;
- retry after valid empty, mapping failure, and transient source failure;
- idempotent duplicate seed and capture attempts;
- T-30 accepted product CLV and later T-10 upgrade;
- existing T-10-only promotion metrics remaining unchanged;
- provenance through the real V2 adapter path;
- read-contract grouping and exact-market price history;
- unified route, redirect, filters, CLV states, and accessible detail panel;
- workflow contract proving no enable/disable toggling and a bounded session
  below the hosted-runner limit.

Local completion requires targeted backend tests, the full V2 suite, frontend
tests, TypeScript, ESLint, production build, workflow contract tests, and
`git diff --check`.

Production remains `PARTIAL` until a real untouched match proves:

`watch session -> T-30 -> T-10 or explicit miss -> closing -> CLV -> settlement -> unified UI`.

T-30-only can prove accepted product CLV. T-10 capture coverage must be
reported separately and cannot be inferred from T-30 success.

## Non-goals

- No new paid or trial infrastructure.
- No rewrite of the odds provider integration.
- No mutation of legacy databases or raw source evidence.
- No change to model/backtest thresholds to improve inspected outcomes.
- No claim of positive forward EV from operational CLV coverage.
