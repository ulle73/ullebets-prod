# Ullebets Offline V1 Design

> Goal: build a local, rebuildable offline pipeline that reads historical football stat-market data from the old sources, audits it, normalizes it into a new model-friendly structure, engineers leakage-safe features, and runs walk-forward evaluation for `totalShots`, `shotsOnGoal`, and `cornerKicks`.

## 1. Design summary

`docs/source-map.md` is the product spec. The old repo at `C:\dev\FRONTEND\ullebets-vecel` is only a source map and logic reference, not an architecture to preserve.

Offline V1 will therefore use:

- old `MongoDB` as a `read-only` historical extract layer
- local `data/teamstats` as raw historical match/stat support data
- copied support files from the old repo such as `data/leagues-and-teams.json` and `data/unibetLeagueUrls.json`
- a new local derived structure built for audit, normalization, feature engineering, walk-forward backtest, and model training

Offline V1 will not build:

- live fixture ingestion
- live Unibet/Kambi odds capture
- a frontend
- a new persistent production database

Those are explicitly deferred to phase 2.

## 2. Evidence-driven source choices

The current workspace and old `MongoDB` were inspected directly.

### 2.1 Historical source hierarchy

The old `MongoDB` currently exposes these collections with data:

- `teamstats`
- `unibet-backtest`
- `analysis-snapshots`
- `result-loop-bets`
- `closing-line-tracking`

Observed sizes at inspection time:

- `unibet-backtest`: about `1156` docs, `166816` lines, `156206` settled lines
- `analysis-snapshots`: `16` docs, `113` shortlist rows
- `result-loop-bets`: `26` rows
- `closing-line-tracking`: `61` rows
- `teamstats`: `536` docs

### 2.2 Main historical corpus

`unibet-backtest` is the primary historical corpus for line-level modeling in V1 because it is the only broad source that combines:

- bookmaker line
- bookmaker odds
- stat key
- scope
- period
- settled outcome fields such as `actual` and `win`
- historical snapshot history via `snapshots[]`

### 2.3 Enrichment and validation sources

The other collections remain useful, but not as the main training universe:

- `closing-line-tracking`: CLV and prematch price-path enrichment where coverage exists
- `analysis-snapshots`: shortlist validation and model-vs-selection comparisons
- `result-loop-bets`: later operational settlement checks and shape validation
- `teamstats`: match-level historical stats and pre-match feature source

### 2.4 Support metadata

The old repo contains support files that should be copied into the new repo and versioned locally:

- `data/leagues-and-teams.json`
- `data/unibetLeagueUrls.json`

These are support inputs, not live dependencies.

## 3. Architecture

Offline V1 uses a layered local architecture:

1. `extract`
2. `audit`
3. `normalize`
4. `features`
5. `backtest + models`
6. `reports`

Each layer reads from the previous one and can be rebuilt from scratch.

### 3.1 Technology choices

- Python-first runtime
- Parquet as canonical derived file format
- DuckDB as the local analytical query engine
- pandas + pyarrow for IO/transforms
- scikit-learn for first-pass models

DuckDB is a dependency of the new project, not a requirement for the old repo.

### 3.2 Rebuildability

Derived outputs are disposable artifacts. The source of truth in V1 is:

- `read-only` old `MongoDB`
- local raw files
- copied local support metadata
- deterministic pipeline code

If a bug is found, the intended fix is to delete the derived layer and rebuild it.

## 4. Proposed local data layout

```text
data/
  teamstats/                            # existing raw local cache
  support/
    leagues-and-teams.json
    unibetLeagueUrls.json
  derived/
    offline_v1/
      ullebets_v1.duckdb
      raw/
        mongo_unibet_backtest.parquet
        mongo_analysis_snapshots.parquet
        mongo_result_loop_bets.parquet
        mongo_closing_line_tracking.parquet
        mongo_teamstats_index.parquet
      normalized/
        matches.parquet
        team_stats_long.parquet
        market_lines.parquet
        market_snapshots.parquet
        line_clv.parquet
        source_coverage.parquet
      features/
        stat_target=totalShots.parquet
        stat_target=shotsOnGoal.parquet
        stat_target=cornerKicks.parquet
      models/
        baseline_metrics.json
        walk_forward_metrics.json
        calibration_model.pkl
      reports/
        audit_summary.json
        audit_summary.md
        normalization_summary.json
        walk_forward_summary.json
        signal_report.md
```

Parquet is the durable local format. DuckDB is an index/query layer over those Parquet datasets.

## 5. Normalized schema

Normalization must be generic for all stat types, while V1 modeling focuses on the three primary targets.

### 5.1 `matches.parquet`

One row per canonical match.

Key fields:

- `match_id`
- `event_id`
- `match_date`
- `kickoff_ts`
- `league_name`
- `league_slug`
- `home_team_name`
- `away_team_name`
- `home_team_id`
- `away_team_id`
- `match_source`
- `team_match_quality`

### 5.2 `market_lines.parquet`

One row per settled market side.

Key fields:

- `line_id`
- `match_id`
- `bet_key`
- `source_collection`
- `stat_key`
- `period`
- `scope`
- `direction`
- `line_value`
- `odds_decimal`
- `market_label`
- `condition_label`
- `event_id`
- `generated_at`
- `actual_value`
- `settlement_result`
- `is_settled`
- `quality_status`
- `filter_reason`

### 5.3 `market_snapshots.parquet`

One row per historical prematch snapshot side.

Key fields:

- `snapshot_line_id`
- `match_id`
- `bet_key`
- `snapshot_fetched_at`
- `stat_key`
- `period`
- `scope`
- `direction`
- `line_value`
- `odds_decimal`
- `event_id`

This table makes it possible to run replay using a true prematch cutoff instead of only the final settled root line.

### 5.4 `line_clv.parquet`

One row per trackable pick or market side with CLV coverage.

Key fields:

- `tracking_key`
- `match_id`
- `stat_key`
- `period`
- `scope`
- `direction`
- `line_value`
- `opening_odds`
- `closing_odds`
- `opening_observed_at`
- `closing_observed_at`
- `prematch_observation_count`
- `clv_pct`
- `beat_closing_line`

### 5.5 `team_stats_long.parquet`

One row per match, team role, period, and stat item extracted from local `teamstats`.

Key fields:

- `match_id`
- `kickoff_ts`
- `league_name`
- `team_name`
- `opponent_name`
- `team_role`
- `period`
- `stat_item_key`
- `stat_item_name`
- `team_value`
- `opponent_value`
- `total_value`

This is intentionally generic and must preserve all stat types that can be extracted.

### 5.6 `source_coverage.parquet`

One row per match/line with cross-source status and failure reasons.

Key fields:

- `match_id`
- `bet_key`
- `has_unibet_line`
- `has_snapshot_history`
- `has_teamstats_match`
- `has_support_metadata`
- `has_outcome`
- `has_clv`
- `match_mapping_confidence`
- `stat_mapping_confidence`
- `filter_reason`

## 6. Stat registry

V1 must not hardcode only three stats into ingestion or normalization.

There will be a stat registry/config layer with:

- canonical `stat_key`
- label aliases
- modeling enabled/disabled flag
- settlement support flag
- target variable role

Initial modeled targets:

- `totalShots`
- `shotsOnGoal`
- `cornerKicks`

Known preserved-but-not-modeled examples:

- `yellowCards`
- `fouls`
- `offsides`
- `freeKicks`
- `totalTackle`

## 7. Data quality gates

Any match line that fails a gate stays preserved in normalized data but is excluded from modeling.

Hard modeling gates:

- missing odds or line value
- missing or unmapped `stat_key`
- missing `period` or `scope`
- missing settled outcome
- missing teamstats match
- ambiguous team mapping
- missing kickoff timestamp
- snapshot timestamp after kickoff for replay rows
- unsupported settlement semantics

The reports must show:

- total rows seen
- total rows filtered
- filter reasons
- per-stat coverage
- per-period coverage
- per-scope coverage
- per-league coverage

## 8. Leakage policy

Leakage discipline is a hard design constraint.

Allowed as features:

- prematch market information
- rolling team stats built only from matches before the replay cutoff
- support metadata such as league rank, Opta rating, team strength
- derived opponent/context features built strictly from prior matches

Forbidden as features:

- `actual_value`
- `settlement_result`
- `win/loss/push`
- `clv_pct`
- `beat_closing_line`
- any post-kickoff enrichment

Replay cutoff policy:

- for root-line backtests without snapshots, the line can be evaluated historically but should not be treated as a high-confidence prematch timestamped replay row unless timing evidence exists
- for snapshot-based replay, `snapshot_fetched_at` is the cutoff

## 9. Feature strategy

Feature engineering is broad and leakage-safe.

### 9.1 Generic feature factory

The feature factory should operate per:

- `stat_key`
- `period`
- `scope`

### 9.2 Required feature groups

- market features
  - line
  - odds
  - implied probability
  - over/under pair context when recoverable
- rolling raw performance
  - last `3/5/10/20`
  - home-only last `3/5/10/20`
  - away-only last `3/5/10/20`
- for/against splits
  - team for
  - team against
  - opponent for
  - opponent against
- context features
  - home/away
  - league
  - opponent type
  - favorite/underdog proxy if available
- strength/ranking features
  - `optaRating`
  - `optaRank`
  - `league_rank`
  - strength deltas
- indirect stat context
  - possession
  - passes
  - attacks
  - dangerous attacks
  - saves
  - fouls
  - cards
  - offsides

### 9.3 V1 modeling focus

V1 models only:

- `totalShots`
- `shotsOnGoal`
- `cornerKicks`

and only for:

- `ALL + total`
- `ALL + home`
- `ALL + away`
- `1ST + home`
- `1ST + away`
- `2ND + home`
- `2ND + away`

## 10. Evaluation strategy

V1 must separate:

- data audit
- baseline backtest
- walk-forward model evaluation
- CLV validation

### 10.1 Baselines

The first backtests should include:

- market/odds baseline where recoverable
- simple historical average baselines
- rule-based EV ranking from legacy fields where present

### 10.2 First models

The first models should be simple and inspectable:

- regularized classification/regression for outcome or realized ROI proxy
- league/stat/period/scope segmented training where sample size allows

### 10.3 Walk-forward

Forward-only training/evaluation is required. V1 should use rolling windows and report:

- sample counts
- ROI
- hit rate
- CLV where coverage exists
- drawdown
- strongest/weakest segments

## 11. Outputs

V1 must produce:

- audit report
- normalization report
- feature coverage report
- walk-forward metrics
- ROI/CLV summary
- candidate signal report for the three target stats

The reports must also state what was excluded and what remains too weak to trust.

## 12. Why this design

This design intentionally breaks from the old system shape because the old storage layers mix:

- extraction
- enriched research artifacts
- settlement state
- shortlist state
- CLV tracking

Those are valuable sources, but poor canonical modeling tables.

Offline V1 therefore treats the old system as raw material and reconstructs a cleaner analytical model:

- generic stat ingestion
- explicit source lineage
- explicit quality gates
- explicit leakage rules
- explicit separation between raw, normalized, feature, and model layers

That is the shortest path to proving whether historical `+ROI` exists for the three primary stat markets without inheriting the old storage design.
