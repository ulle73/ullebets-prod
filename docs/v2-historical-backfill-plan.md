# Ullebets V2 Historical Backfill Plan

## Goal

Backfill enough historical data into `ullebets_v2` so that V2 can:

- build stable `teamprofiles`
- build `matchups_score` and `matchups_league_avg`
- build `model_snapshots`
- settle future forward bets from V2-owned data

This is not a blind database copy. V2 should import historical source facts and then rebuild derived outputs inside V2.

## Current Observed Source Inventory

Observed on `2026-07-27`.

| Source DB | Collection | Count | Observed date span | Role |
| --- | --- | ---: | --- | --- |
| `app` | `match-for-date` | 292 | `2025-10-07` -> `2026-08-03` | historical fixtures source |
| `app` | `teamstats` | 536 | `2023-12-10` -> `2026-07-26` | historical stats/incidents/shotmap/results source |
| `app` | `unibet-backtest` | 1156 | `2025-11-21` -> `2026-05-24` | historical odds snapshot surrogate |
| `app` | `closing-line-tracking` | 61 | `2026-03-29` -> `2026-05-27` | legacy CLV parity reference |
| `app` | `result-loop-bets` | 26 | `2026-03-30` -> `2026-05-26` | legacy settlement parity reference |
| `app` | `analysis-snapshots` | 16 | sparse | legacy analysis parity reference |
| `app` | `auto-analysis-runs` | 5 | sparse | legacy analysis parity reference |
| `app` | `auto-analysis-bets` | 227 | sparse | legacy analysis parity reference |
| `app` | `ai-generated-bets` | 9070 | sparse | legacy export parity reference |
| `ullebets_unibet` | `raw_odds_snapshots` | 5 | `2026-06-20` only | higher-fidelity but tiny odds archive |
| `ullebets_unibet` | `matches` | 1 | `2026-05-29` only | helper only |
| `ullebets_unibet` | `odds_fetch_jobs` | 10 | sparse | scheduling audit only |
| `ullebets_unibet` | `raw_source_snapshots` | 16 | sparse | migrated legacy output snapshots, not source truth |
| `ullebets_unibet` | `source_shortlist_items` | 113 | sparse | migrated analysis shortlist, not source truth |

## Import Policy

### Import as source facts

These collections are good enough to seed V2-owned raw and canonical data.

| Legacy source | Why import | V2 targets |
| --- | --- | --- |
| `app.match-for-date` | best historical fixture calendar and match identity source | `raw_fixtures`, `fixtures_canonical`, `fixture_source_links` |
| `app.teamstats` | best historical source for statistics, incidents, shotmap, results | `raw_match_statistics`, `raw_incidents`, `raw_shotmaps`, `raw_results`, `match_results_canonical`, `match_stats_canonical` |
| `app.unibet-backtest` | only broad historical odds archive currently available, even if derived | `raw_odds_kambi`, `unibet_event_links`, `market_offers` with `source_provider=legacy_unibet_backtest` |
| `ullebets_unibet.raw_odds_snapshots` | small but higher-fidelity odds payload archive | `raw_odds_kambi`, `unibet_event_links`, `market_offers`, optionally `market_snapshots` |

### Use only for parity, audit, or repair

These should not be copied into primary V2 product tables as truth.

| Legacy source | Use |
| --- | --- |
| `app.teamprofiles` | compare V2 profile shape and coverage only |
| `app.matchups-score` | parity check only |
| `app.matchups-league-avg` | parity check only |
| `app.closing-line-tracking` | parity/audit against V2 CLV rebuild only |
| `app.result-loop-bets` | parity/audit against V2 settlement only |
| `app.analysis-snapshots` | parity/audit only |
| `app.auto-analysis-runs` | parity/audit only |
| `app.auto-analysis-bets` | parity/audit only |
| `app.ai-generated-bets` | parity/audit only |
| `ullebets_unibet.odds_fetch_jobs` | checkpoint scheduling audit only |
| `ullebets_unibet.matches` | fallback helper for event/match audit only |
| `ullebets_unibet.raw_source_snapshots` | archived legacy outputs only |
| `ullebets_unibet.source_shortlist_items` | archived shortlist outputs only |

### Do not import as product truth

These are old derived outputs. Copying them would make V2 dependent on old mistakes.

- `app.teamprofiles`
- `app.matchups-score`
- `app.matchups-league-avg`
- `app.analysis-snapshots`
- `app.auto-analysis-runs`
- `app.auto-analysis-bets`
- `app.ai-generated-bets`
- `app.result-loop-bets`
- `app.closing-line-tracking`

## Exact Backfill Mapping

### 1. Fixtures

Source:

- `app.match-for-date`

Target:

- `raw_fixtures`
- `fixtures_canonical`
- `fixture_source_links`

Mechanism:

- Use `scripts/forward_v2/ingest_fixtures_window.py --mode replay`
- Let V2 normalize fixture identity from legacy payloads instead of copying legacy docs

Acceptance:

- V2 has canonical fixtures for the historical window
- no duplicate `match_key`
- every finished `teamstats` match can be joined to a `fixtures_canonical` row

### 2. Match enrichment

Source:

- `app.teamstats`

Target:

- `raw_match_statistics`
- `raw_incidents`
- `raw_shotmaps`
- `raw_results`
- `match_results_canonical`
- `match_stats_canonical`

Mechanism:

- Use `scripts/forward_v2/ingest_match_enrichment.py --mode replay`
- For any already-imported V2 raw rows, use `scripts/forward_v2/backfill_match_enrichment.py --source-mode db`

Acceptance:

- `verify_match_enrichment.py` reports no missing stats/incidents/shotmaps for imported dates
- `match_results_canonical.home_team_key` and `.away_team_key` are never `unknown:None` for matched fixtures

### 3. Teamprofiles

Source:

- V2 canonical enrichment only

Target:

- `teamprofiles`

Mechanism:

- Use `scripts/forward_v2/build_teamprofiles.py`
- Build one current profile snapshot after the historical enrichment window is loaded
- Later, if historical parity requires it, build dated profile snapshots per target prediction day

Acceptance:

- for upcoming fixtures, both home and away teams exist in `teamprofiles`
- model adapter returns non-empty `homeBundle` and `awayBundle`
- old stray `unknown:None` profiles are removed or overwritten

### 4. Historical odds

Source priority:

1. `ullebets_unibet.raw_odds_snapshots` where available
2. `app.unibet-backtest` as broad historical surrogate

Target:

- `raw_odds_kambi`
- `unibet_event_links`
- `market_offers`
- later `market_snapshots` if checkpoint timestamps are reconstructable

Mechanism:

- use `scripts/forward_v2/ingest_unibet_odds.py --mode legacy-backtest` for `app.unibet-backtest`
- create a dedicated importer for `ullebets_unibet.raw_odds_snapshots` instead of forcing them through the legacy backtest adapter

Important:

- `app.unibet-backtest` is not real raw Kambi payload history
- import it only with explicit provenance flags such as `payload_kind=legacy_unibet_backtest`
- do not present it as first-party raw truth in audits

Acceptance:

- historical odds rows in V2 are tagged by provenance
- markets can be joined to V2 fixtures via `match_key`
- V2 can measure which historical rows came from surrogate legacy backtest docs vs. true raw snapshots

## Minimal Backfill Needed To Unlock The App

The app does not need every legacy collection first. It needs enough historical match coverage to build usable team profiles for the teams in upcoming fixtures.

Minimal unlock sequence:

1. backfill historical fixtures from `app.match-for-date`
2. backfill historical enrichment from `app.teamstats`
3. rebuild `teamprofiles`
4. verify that upcoming fixture teams have both home and away history
5. rerun `build_matchups_score`
6. rerun `build_model_snapshots`

Current blocker observed on `2026-07-27`:

- V2 only has finished enrichment for `2026-07-26`
- that gives many teams only one role history, for example only `home` or only `away`
- `model_snapshots` therefore stays at `0`

## Recommended Execution Order

### Phase A: unlock profiles and model input

Backfill a historical enrichment window first. This is the first task that actually unblocks the app.

Recommended starting window:

- same leagues as the forward-test target leagues
- at least the full current season to date
- if that is too large operationally, start with the last 30-60 days of finished matches

Run order:

1. replay fixtures into V2
2. replay teamstats into V2
3. run `verify_match_enrichment.py`
4. rebuild current `teamprofiles`
5. rerun `build_matchups_score.py`
6. rerun `build_model_snapshots.py`

### Phase B: seed historical odds provenance

Only after Phase A works:

1. import historical odds from `app.unibet-backtest`
2. import any available `ullebets_unibet.raw_odds_snapshots`
3. audit by provenance and date coverage

### Phase C: rebuild derived outputs inside V2

Do not copy old derived collections. Rebuild these from V2-owned source facts:

- `matchups_score`
- `matchups_league_avg`
- `model_snapshots`
- `settled_bets`
- `closing_lines`
- `clv_tracking`
- `analysis_runs`
- `analysis_candidates`
- `analysis_snapshots`
- `prediction_exports`

## Gaps In The Current Tooling

The current repo can do most of the normalization already, but the backfill ergonomics are still weak.

Needed next implementation steps:

1. Add a batch fixture replay runner for historical windows that explicitly uses `app.match-for-date`.
2. Add a batch teamprofile rebuild runner over a date window or a “current from all finished matches” mode with cleanup for stale profiles.
3. Add a dedicated importer for `ullebets_unibet.raw_odds_snapshots`.
4. Add a historical coverage audit:
   - finished fixture count by date
   - enriched match count by date
   - teamprofile coverage by team and role
   - odds coverage by date and market

## Decision Rules

- If a legacy collection contains source facts, import and normalize it.
- If a legacy collection contains a model output, ranking, shortlist, or settlement conclusion, do not import it as truth.
- If provenance is weak, keep the import but tag it explicitly.
- If fixture identity and team identity cannot be linked confidently, mark it unmatched. Do not guess.

## Why This Is Better Than Copying Old Outputs

The expensive wrong assumption would be that copying old `teamprofiles`, `matchups`, and analysis docs is the fastest route.

It is not.

That would:

- hide old mapping mistakes
- keep V2 dependent on legacy semantics
- make audits meaningless
- leave you unable to rebuild from raw

The correct shortcut is to import old source facts once, normalize them into V2, and let V2 own every derived layer from there.
