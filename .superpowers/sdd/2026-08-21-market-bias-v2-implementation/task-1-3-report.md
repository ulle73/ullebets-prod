# Market-Bias V2 Tasks 1-3 Report

Date: 2026-08-21
Branch: `codex/market-bias-v2`
Status: `PARTIAL`

## Scope

Implemented only the storage/domain/service foundation. No matchup ranking,
V6, model, ROI, CLV, API, or frontend code changed.

## Task 1 - Storage Contracts And Indexes

Files changed:

- `src/ullebets_v2/storage/collections.py`
- `src/ullebets_v2/storage/indexes.py`
- `tests/v2/test_config_and_safety.py`

Red command and output:

```text
python -m pytest tests/v2/test_config_and_safety.py -q
ERROR: ImportError: cannot import name 'MARKET_BIAS_OBSERVATIONS'
```

Green command and output:

```text
python -m pytest tests/v2/test_config_and_safety.py -q
6 passed in 0.91s
```

Commit: `e2dbf1ac64fc78c9c38efe2f02f856ea8fc34468` (`feat: register market bias storage`)

## Task 2 - Pure Domain Logic

Files changed:

- `src/ullebets_v2/market_bias/__init__.py`
- `src/ullebets_v2/market_bias/domain.py`
- `tests/v2/test_market_bias_domain.py`

Red command and output:

```text
python -m pytest tests/v2/test_market_bias_domain.py -q
ERROR: ModuleNotFoundError: No module named 'ullebets_v2.market_bias'
```

Green command and output:

```text
python -m pytest tests/v2/test_market_bias_domain.py -q
8 passed in 0.28s
```

Commit: `29098703a56053030518c7a2fe2f57519525ff03` (`feat: calculate auditable market bias`)

## Task 3 - Immutable Service And Reports

Files changed:

- `src/ullebets_v2/market_bias/persistence.py`
- `src/ullebets_v2/market_bias/reports.py`
- `src/ullebets_v2/market_bias/service.py`
- `tests/v2/test_market_bias_service.py`
- `docs/work-log.md`
- `.superpowers/sdd/2026-08-21-market-bias-v2-implementation/task-1-3-report.md`

Red command and output:

```text
python -m pytest tests/v2/test_market_bias_service.py tests/v2/test_job_runs.py -q
ERROR: ModuleNotFoundError: No module named 'ullebets_v2.market_bias.persistence'
```

Green command and output:

```text
python -m pytest tests/v2/test_market_bias_service.py tests/v2/test_job_runs.py -q
9 passed in 1.36s
```

Final verification:

```text
python -m pytest tests/v2 -q
446 passed in 23.82s

python -m compileall -q src
PASS

git diff --check
PASS

codegraph sync
Already up to date
```

Commit: `c454c900477e2514edf0a563253243b1e459b718` (`feat: persist and audit market bias`)

## Self-Review

- Observations cannot persist a changed immutable source/line/outcome/timing
  payload under the same `observation_key`.
- Exact replays do not write a second observation; profiles upsert only by
  `profile_key`.
- Profile construction requires explicit `as_of`, `profile_date`, and `run_id`.
- The service returns documents and report rows without touching the database
  in dry-run mode; write mode records one started/finished `job_runs` lifecycle.
- The implementation is limited to the requested foundation and does not read
  legacy MongoDB databases at runtime.

## Concerns

- Bootstrap identity resolution and audited Parquet coverage are not implemented
  or production-tested.
- Forward V2 candidate extraction, scheduled jobs, index bootstrap execution,
  matchup/API integration, and frontend rendering remain unimplemented.
- No production database write was performed; all persistence evidence uses
  focused in-memory contract tests.
