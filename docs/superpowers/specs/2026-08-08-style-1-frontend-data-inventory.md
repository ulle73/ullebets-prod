# Ullebets Style-1 Frontend Data Contract

Date: 2026-08-09  
Branch: `style-1`  
Status: required runtime provenance contract

## Non-negotiable rule

The production frontend must not contain hardcoded Ullebets product data.

That means no runtime fixture containing real-looking matches, teams, scores,
odds, ROI, CLV, model values, team statistics, result snapshots or system
status. Missing backend data must render a loading, empty or error state; it must
never be replaced by plausible example values.

Unit/integration tests may use synthetic values that exist only inside test
files. Those values are not application fallbacks.

## Runtime architecture

Style-1 uses a read-only V2 HTTP layer:

- `src/ullebets_v2/read_api/`
- `scripts/forward_v2/serve_read_api.py`
- frontend client under `frontend/src/data/api.ts`

The HTTP layer may read V2 collections and may call an existing pure V2
calculation function in memory. It must not write to MongoDB, recreate betting
policy logic in TypeScript, mutate model state or persist a newly calculated
selection.

HTTP mutations (`POST`, `PUT`, `PATCH`, `DELETE`) are rejected.

## 1. Dagens matcher

Source: `fixtures_canonical`.

Approved fields:

- `match_key`
- `source_match_id`
- `source_date`
- `start_time`
- `league_key`
- `league_name`
- `home_team_key`
- `away_team_key`
- `home_team_name`
- `away_team_name`
- `status_type`

The left-hand match rail is populated only from these rows. Search/filtering is
presentation logic over returned rows and must not invent a match or status.

The default date comes from runtime local time in the browser. There is no
hardcoded default match date.

## 2. Legacy-style matchup ranking on the homepage

Primary source: persisted `matchups_score` rows produced by V2's existing
matchup engine in `src/ullebets_v2/matchups/service.py`.

Approved fields include:

- `entry_key`
- `snapshot_date`
- `match_key`
- league/home/away identities
- `stat_key`
- `stat_label`
- `period`
- `period_label`
- `scope`
- `condition` (`over` / `under`)
- `score`
- `rank_position`
- `is_top_50`
- `market_bias`
- `forecast.leagueBaseline`

### The 0-100 matchup score is valid

`matchups_score.score` is the legitimate legacy-style 0-100 matchup ranking and
may be shown on the homepage as `Matchup-score` / `Score`.

It must not be relabelled as:

- odds
- V6 model probability
- confidence
- proof
- ROI / EV
- forward edge

Arbitrary 0-100 values that do not come from the V2 matchup engine remain
forbidden.

### Safe read-only fallback when `matchups_score` is not persisted

The existing scheduled `dump-matchups.yml` currently executes the matchup dump
in dry-run mode. Therefore a production-looking read surface cannot assume that
`matchups_score` is always persisted.

If no persisted matchup rows exist for the selected date, the read API may call
V2's existing `build_matchups_score_docs` **in memory only** provided all of the
following are true:

1. the target fixture has not started yet;
2. inputs come from real `fixtures_canonical` and `teamprofiles` rows;
3. current teamprofiles are preferred for upcoming fixtures, otherwise only the
   latest dated profile that is no later than the current runtime date may be
   used;
4. the calculation is not persisted;
5. the calculation function/thresholds are not copied or reimplemented in the
   frontend/read layer;
6. if V2 cannot produce a row, the UI shows missing data rather than inventing a
   replacement.

Historical or already-started matches must never be recomputed using today's
teamprofiles. They require persisted matchup rows.

This fallback changes only read presentation availability. It does not modify
V2's matchup algorithm or any production write workflow.

## 3. Match detail / teamprofiles

Source: `teamprofiles`.

Approved data:

- `team_key`
- `league_key`
- `match_type` (`home` / `away`)
- `profile_date`
- `generated_at`
- `games`
- `statistics.for`
- `statistics.against`
- `statistics.leagueAverage`
- per-stat/per-period `value`, `rank`, `history`
- `specials` only when its concrete meaning is understood

For an upcoming fixture, current data is allowed. For a started/historical
fixture, match detail must use a dated profile at or before that fixture's
source date and must not silently substitute the `current` profile.

## 4. Odds / checkpoints

Sources:

- `market_offers`
- `market_snapshots`
- existing Kambi/Unibet V2 ingest

Approved mapped stat families include V2's actual mapper keys such as:
`shotsOnGoal`, `totalShots`, `cornerKicks`, `yellowCards`, `freeKicks`, `fouls`,
`totalTackle`, `offsides`.

Approved periods: `ALL`, `1ST`, `2ND`.  
Approved scopes: `home`, `away`, `total`.

Never display Bet365 or any other bookmaker/provider unless V2 actually supplies
that source.

Checkpoint timing/quality comes from `market_snapshots`; absent checkpoints are
missing, not fabricated.

## 5. V6 model scores

Source: `ev_model_scores`.

Approved model fields include:

- `model_id`
- `model_status`
- `match_key`
- `stat_key`
- `period`
- `scope`
- `direction`
- `line_value`
- `offered_odds`
- `predicted_win_probability`
- `expected_roi_units`
- `valid_for_policy_evaluation`
- `invalid_for_model`

Presentation transforms are allowed:

- probability fraction -> percentage
- EV unit fraction -> percentage labelled model EV
- decimal odds formatting

Do not turn these values into a fabricated 0-100 confidence score.

## 6. Auto / registered forward selections

Source: `forward_bets`.

The frontend consumes persisted registered selections. It does not reproduce
V6 selection thresholds or decide that a raw model score is a bet.

Approved fields include selection identity, policy/model identity, market
identity, line, saved/selected odds, model probability, expected ROI, start time
and validity/exclusion flags.

Evidence wording is `Forward-test` when that is what V2 says; never `proven
edge` unless a separate promotion contract actually says so.

## 7. Resultatloop and Historik

Source: `forward_results`.

Approved data includes persisted settlement, exclusion, ROI/PnL, closing and CLV
states. Excluded rows remain visible as excluded and must not be counted as
losses.

Summary counters must count the complete collection, not merely the page of rows
returned for display.

Missing CLV is missing; it is never converted to `0%`.

## 8. Modell & proof

Sources:

- `ev_model_scores`
- `forward_bets`
- `forward_results`
- registered model/policy identities persisted in V2

The Style-1 model page may show factual collection counts and persisted IDs. It
must not contain static ROI, proof-progress or backtest figures as runtime
product data.

Historical research numbers belong in explicitly sourced research/documentation
surfaces, not as a fake live dashboard metric.

## 9. Systemstatus

Sources:

- `job_runs`
- `health_reports`
- `audit_reports`

The read API recursively strips keys whose names indicate credentials/secrets
before returning operational documents. API keys, connection strings, passwords,
tokens or secret material must never be rendered.

## 10. Watchlist

Watchlist may persist only stable references/IDs in browser local storage. It may
not cache a second copy of product data as a runtime fallback. Match names,
league, kickoff and other content are resolved from the current V2 response.

## 11. Allowed presentation logic

Allowed:

- filtering/searching returned data
- Swedish labels for stat/scope/period/status
- timestamp/date formatting
- probability/EV/odds display formatting
- responsive layout
- sorting rows according to already returned rank/score
- local watchlist references

Not allowed:

- hardcoded product rows
- synthetic fallback matches/scores
- recomputing V6 policy eligibility in TypeScript
- changing matchup/model thresholds
- treating missing values as zero
- claiming a provider that V2 does not have
- using current profiles to retroactively recompute historical matchups

## 12. CI gate

Style-1 CI must fail if the removed runtime preview/snapshot data files return.
Frontend verification also runs locked dependency installation, dependency
audit, strict TypeScript, ESLint, tests and production build.

The backend isolation workflow runs the complete existing Python regression
suite on the same Style-1 tree.

## Conclusion

The homepage can preserve the original Ullebets product concept without
hardcoding anything:

`fixtures_canonical` supplies Dagens matcher and V2's existing matchup engine
supplies the OVER/UNDER ranking, including the real legacy-style matchup score,
stat/scope/period, bias payload and league baseline. Other pages read their own
persisted V2 collections.

When the source is absent, the UI says it is absent. It does not manufacture a
more attractive answer.