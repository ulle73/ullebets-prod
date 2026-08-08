# Ullebets Style-1 Frontend Data Inventory

Date: 2026-08-08
Branch: `style-1`
Status: provenance gate for frontend implementation

## Purpose

This document is the data-truth contract between the existing Ullebets V2/V6
backend and the Style-1 frontend. A visible production-looking UI value is
allowed only when it is listed here (or later added here with an exact source),
or when it is an explicitly documented deterministic presentation transform of
a listed value.

The frontend is not allowed to invent missing product semantics to make a mockup
look complete.

## Evidence vocabulary used by the UI

- `analysis`: grounded analytical/model output, not necessarily selected by the
  registered forward policy.
- `forward-test`: a registered immutable forward selection; still under forward
  validation and not proven profit.
- `historical`: backtest/history evidence only.
- `excluded`: present data that is invalid for performance or outside the model
  domain.
- `official-closing`: a valid official closing observation (`t10` under the
  current closing contract).
- `fallback-closing`: T-30 fallback (`t30_fallback`), never official CLV.
- `unavailable`: the backend has no value for the requested concept.

## 1. Match and league identity

Backend source: `fixtures_canonical`, built by
`src/ullebets_v2/fixtures/replay.py` and live fixture ingest.

| UI concept | Exact source field(s) | Allowed transform | Notes |
|---|---|---|---|
| Match id | `match_key` | route-safe string | Canonical key; do not manufacture numeric IDs. |
| Source match id | `source_match_id` | string | Secondary/debug identity only. |
| Kickoff | `start_time` | localized date/time | Never invent live minute. |
| Date | `source_date` / date of `start_time` | localized date | Prefer canonical kickoff for display grouping. |
| League | `league_name`, `league_key` | text | Grounded. |
| Home team | `home_team_name`, `home_team_key` | text | Grounded. |
| Away team | `away_team_name`, `away_team_key` | text | Grounded. |
| Match status | `status_type` | translated label | Do not infer live minute from wall clock. |
| Mapping confidence | `mapping_confidence` | optional diagnostic | System-status/detail only. |

### Not currently approved

- Team crest/logo URL: no stable frontend image field has been mapped.
- Competition logo: no stable frontend image field has been mapped.
- Live score/minute: do not infer beyond grounded result/status data.

Use typographic initials/neutral team marks until a real crest source is mapped.

## 2. Unibet/Kambi markets and odds

Backend sources:

- `market_offers`
- `market_snapshots`
- `src/ullebets_v2/odds/mapper.py`
- `src/ullebets_v2/checkpoints/service.py`

Grounded mapped stat keys currently include:

- `shotsOnGoal`
- `totalShots`
- `cornerKicks`
- `yellowCards`
- `freeKicks`
- `fouls`
- `totalTackle`
- `offsides`

Grounded periods: `ALL`, `1ST`, `2ND`.
Grounded scopes: `home`, `away`, `total`.

| UI concept | Exact source field(s) | Allowed transform | Notes |
|---|---|---|---|
| Bookmaker/source | `source_provider` and Kambi ingest provenance | display `Unibet/Kambi` only when source contract matches | Never show Bet365 or another bookmaker without backend data. |
| Market stat | `stat_key` | Swedish display-name map | UI label only; internal key remains unchanged. |
| Scope | `scope` | home/away/total -> Swedish label | For team scope, combine with canonical team name. |
| Period | `period` | ALL/1ST/2ND -> match/1:a/2:a | Deterministic. |
| Line | `line` / normalized `line_value` | number formatting | No arbitrary rounding beyond display precision. |
| Over odds | `over_odds` | decimal odds format | Grounded. |
| Under odds | `under_odds` | decimal odds format | Grounded. |
| Snapshot label | `snapshot_label` | T-3D/T-2D/etc label map | Grounded checkpoint. |
| Snapshot time | `snapshot_time` | localized time | Grounded. |
| Minutes to kickoff | `minutes_to_kickoff` | integer/minutes | Grounded when present. |
| Snapshot validity | `invalid_for_model` | valid/excluded badge | Never silently hide timing invalidity in performance views. |

### Product distinction

A mapped market is not automatically a recommended V6 bet. Overview may show
grounded analytical markets, but Auto/actionable ranking is governed by the
registered forward selection output, not by the market mapper alone.

## 3. Checkpoint timeline and freshness

Backend sources:

- `market_snapshots`
- `src/ullebets_v2/checkpoints/policy.py`
- `src/ullebets_v2/checkpoints/service.py`

Current checkpoint keys:

- `T_MINUS_3D` — forward, 60-84h
- `T_MINUS_2D` — forward, 36-60h
- `T_MINUS_1D` — forward, 18-36h
- `T_MINUS_12H` — research, 6-18h
- `T_MINUS_2H` — research, 1-6h
- `T_MINUS_30M` — near-closing, 15-50m
- `T_MINUS_10M` — closing, 5-15m

Allowed display fields:

- `snapshot_label`
- `snapshot_type`
- `snapshot_time`
- `match_start_time`
- `minutes_to_kickoff`
- `horizon_days`
- `invalid_for_model`
- `source_workflow`
- `capture_mode`
- `captured_at`

The UI may derive `latest checkpoint` by taking the most recent valid grounded
snapshot for the selected match/market. It may not claim a missed checkpoint is
a source failure unless health/job evidence says it failed; a window that has
not occurred is an unproven/not-yet state.

## 4. Model score rows

Backend source: `ev_model_scores`, built by
`src/ullebets_v2/ev_model/forward_scores.py`.

Grounded fields include:

- `score_key`
- `score_type`
- `model_id`
- `model_status`
- `match_key`
- `sample_key`
- `side_key`
- `snapshot_key`
- `offer_key`
- `snapshot_label`
- `snapshot_type`
- `stat_key`
- `period`
- `scope`
- `line_value`
- `direction`
- `offered_odds`
- `market_side_probability`
- `predicted_win_probability`
- `expected_roi_units`
- `odds_snapshot_time`
- `match_start_time`
- `score_created_at`
- `valid_for_policy_evaluation`
- `invalid_for_model`

### Allowed headline metrics

1. **Model probability**
   - Source: `predicted_win_probability`.
   - Display: percentage, e.g. `61.4%`.
   - Label explicitly as model probability, not confidence/proof.

2. **Expected value / expected ROI**
   - Source: `expected_roi_units`.
   - Display: percentage (`value * 100`) when the field uses unit fraction.
   - Label `Modell-EV` or equivalent.

3. **Offered odds**
   - Source: `offered_odds`.
   - Display as decimal odds.

### Forbidden until separately specified

- Legacy-style `72.3`, `83.5`, `85.4` generic score.
- Any invented `confidence`, `strength`, `quality` or stars derived by arbitrary
  thresholds.
- A green/gold treatment that implies a model row is a registered selection
  when it is only a candidate score.

## 5. Training-domain status

Backend source: `src/ullebets_v2/ev_model/domain.py` and model evaluation output.

Grounded domain report fields:

- `status`
- `scores_total`
- `scores_in_domain`
- `scores_out_of_domain`
- `missing_category_counts`
- `unknown_category_counts`
- `supported_categories`

Current V6-supported leagues, from the frozen model/project evidence:

- A-League Men
- Bundesliga
- La Liga
- Ligue 1
- Premier League
- Italian Serie A / normalized Serie A domain label

Brazilian V6 rows are diagnostic/OOD under the current fitted model domain.
Frontend behavior:

- may show the row in diagnostics or match detail
- must label it excluded/outside model domain
- must not rank it as a recommended Auto selection
- must not include it in model ROI/CLV proof

## 6. Registered V6 forward selections

Backend source: `forward_bets` / registered-policy prediction docs built by
`src/ullebets_v2/ev_model/forward_predictions.py`.

Current registered forward policy source:
`models/ev/forward_policy_registry_v1.json`.

Current policy identity:

- policy id: `v6_corners_away_total_forward_v1`
- model status on registered selections: `forward_test_only`
- stat: `cornerKicks`
- scopes: `away`, `total`
- minimum EV: strictly above `0.075`
- maximum EV: strictly below `0.25`

Important: the frontend consumes persisted/returned registered selections. It
must not independently reproduce the policy and decide that a raw score is a
selection.

Grounded selection fields include:

- `prediction_key`
- `selection_key`
- `prediction_type`
- `model_id`
- `model_status`
- `selection_policy_id`
- `selection_policy_status`
- `selection_policy_registry_id`
- `selection_policy_filters`
- `source_score_key`
- `match_key`
- `stat_key`
- `period`
- `scope`
- `direction`
- `line_value`
- `selected_odds`
- `saved_odds`
- `predicted_win_probability`
- `expected_roi_units`
- `minimum_ev`
- `maximum_ev`
- `odds_snapshot_time`
- `match_start_time`
- `prediction_created_at`
- `valid_for_forward_evaluation`
- `invalid_for_model`

UI evidence label: **Forward-test**, not `Proof`, not `Verified edge`.

## 7. Settlement and Resultatloop

Backend source: `forward_results`, built by
`src/ullebets_v2/forward_results/service.py`.

This is the preferred UI read shape for Resultatloop/Historik because it already
joins selection, CLV and settlement states while preserving exclusions.

Grounded identity/market fields:

- `result_loop_key`
- `prediction_key`
- `selection_key`
- `match_key`
- `source_match_id`
- `home_team_name`
- `away_team_name`
- `league_name`
- `stat_key`
- `period`
- `scope`
- `direction`
- `line_value`
- `saved_odds`
- `match_start_time`

Grounded lifecycle fields:

- `event_started`
- `timing_status`
- `invalid_for_model`
- `valid_for_performance`
- `settlement_status`
- `actual_value`
- `home_value`
- `away_value`
- `settlement_result`
- `win`
- `roi_units`
- `pnl_units`
- `stake_units`
- `settled_at`
- `result_loop_status`
- `status_reason`
- `refreshed_at`

Known `result_loop_status` families include:

- `open`
- `pending`
- `settled`
- `unresolved`
- `excluded`

The UI must preserve excluded rows and reasons instead of treating them as
losses or silently removing them from all operational views.

## 8. Closing and CLV

Backend sources:

- `closing_lines`
- `clv_tracking`
- joined `forward_results`
- `src/ullebets_v2/closing/service.py`

Grounded closing fields include:

- opening/latest/closing snapshot labels and times
- opening/latest/closing odds
- `closing_quality`
- `closing_is_official`
- `closing_age_minutes`
- `prematch_observation_count`
- `invalid_snapshot_count`
- `price_history`

Grounded Resultatloop CLV fields include:

- `closing_quality`
- `official_clv`
- `clv_basis`
- `closing_odds`
- `clv_pct`
- `implied_edge_delta`
- `beat_closing_line`
- `clv_status`
- `closing_line_available`
- `prematch_observation_count`

### Required presentation rule

- `t10` / backend official closing -> may contribute to official CLV display.
- `t30_fallback` -> show as fallback/reference only.
- missing closing line -> `CLV saknas` / unproven, not `0%`.
- invalid timing -> excluded warning, not a numeric CLV.

## 9. Team statistics

Backend source: `teamprofiles`, built by
`src/ullebets_v2/teamprofiles/service.py`.

Grounded profile fields:

- `team_key`
- `league_key`
- `match_type` (`home` / `away`)
- `profile_date`
- `generated_at`
- `games`
- `statistics`
- `specials`
- `meta`

`statistics` supports:

- `for`
- `against`
- `leagueAverage`

per stat and period (`ALL`, `1ST`, `2ND`), including available:

- `value`
- `rank`
- `history`

History items include grounded opponent/date/match identity plus team `val` and
opponent `oppVal`.

### Approved team-page metrics

- team average for/against
- league average
- league rank when present
- recent history values
- home/away profile context

### Caution on `specials`

The collection contains calculated specials, but each displayed frontend
special must be mapped by name/meaning before use. Do not revive old `bias` or
`tempo` UI labels simply because a numeric field appears somewhere in the
specials object.

## 10. Model and proof page

Grounded sources:

- frozen V6 model manifest
- registered forward-policy registry
- model/domain evaluation output
- promotion evaluator output
- persisted forward results / CLV

The promotion evaluator can expose:

- `eligible_for_promotion`
- `status`
- `multiple_comparison_family_size`
- `multiple_comparison_adjusted_p`
- `blocking_reasons`

The project readiness criteria also require enough settled bets/match clusters,
CLV coverage, positive mean CLV, positive clustered lower bound and clean audit
evidence. The frontend must show actual evaluator progress when a read model
supplies it; it must not fabricate progress bars from static target constants.

Historical `+28.65%` from the strongest inspected V6 policy may be shown only in
an explicitly **Historisk backtest** section, accompanied by the current
forward-evidence status. It is not a current ROI figure.

## 11. System status

Grounded sources:

- `job_runs`
- `health_reports`
- `audit_reports`
- `parity_reports`
- source-connectivity audit output
- checkpoint/closing coverage derived from grounded rows

`job_runs` includes:

- `run_id`
- `job_name`
- `source_workflow`
- `target_window`
- `job_args`
- `status`
- `started_at`
- `finished_at`
- `metrics`
- `error`

Source-connectivity diagnostics expose endpoint health, but frontend adapters
must strip operational secrets/credential metadata. Do not render API key tails,
connection strings or secret-bearing payloads.

## 12. Status counters on the dashboard

Approved now:

- selected date
- canonical match count
- played/finished count when match/result status supports it
- watchlist count (local UI state)
- alert/warning count only if defined from grounded health/audit/read-model
  warnings

Not approved without a read-model definition:

- `proof-ready` count
- generic `strong` count
- generic `confidence` count

## 13. Allowed deterministic UI transforms

The following are presentation, not business logic:

- ISO/UTC timestamp -> localized Swedish date/time
- decimal probability `0.614` -> `61.4%`
- EV unit fraction `0.112` -> `+11.2% Modell-EV`
- decimal odds -> fixed sensible decimal precision
- stat keys -> Swedish display labels
- scope + team identity -> `Hemmalaget`, `Bortalaget`, or team-name wording
- period keys -> `Match`, `1:a halvlek`, `2:a halvlek`
- checkpoint keys -> compact `T-3D`, `T-2D`, `T-1D`, `T-2H`, `T-30`, `T-10`
- machine status strings -> Swedish human-readable labels while preserving the
  underlying status semantics

Not allowed as presentation transforms:

- recomputing policy eligibility
- recomputing model scores
- changing EV thresholds
- deriving proprietary confidence tiers without an approved contract
- treating missing as zero
- turning fallback closing into official closing

## 14. Style-1 fixture rules

Because the read API is not implemented on this branch, UI fixtures/adapters are
allowed only for rendering and tests.

Every fixture object must:

- satisfy the TypeScript read model
- use fields that exist in this inventory
- avoid unsupported bookmakers/metrics
- be clearly located under frontend fixture/mock infrastructure
- avoid pretending that synthetic data is fresh production evidence

Prefer examples derived from repository tests or already documented matches over
inventing new product semantics.

## Gate conclusion

The backend already contains enough grounded structure to design the complete
frontend without guessing core product semantics:

- canonical fixtures
- mapped Unibet/Kambi stat markets
- checkpoint snapshots
- V6 model probabilities and expected EV
- registered forward-test selections
- forward result/settlement states
- closing/CLV quality states
- team profiles and league averages
- model-domain/promotion diagnostics
- job/health/audit status

The biggest UI correction versus the legacy mockup is deliberate: there is no
approved generic 0-100 signal score. Style-1 should make the actual model
probability, EV, odds and evidence state easier to understand instead of hiding
them behind an invented score.