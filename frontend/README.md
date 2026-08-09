# Ullebets Style-1 frontend

Style-1 has no runtime product fixtures. The UI reads V2 through the read-only API in `src/ullebets_v2/read_api/`.

## Requirements

- Node.js 22
- Python 3.13
- V2 Python dependencies installed from the repository root
- `MONGODB_URI` available through the environment/root `.env.local` according to the existing `V2Config`

## First setup

From the repository root:

```bash
python -m pip install -e .
cd frontend
npm ci
```

## Run locally

```bash
cd frontend
npm run dev
```

This starts both the read-only API on `http://127.0.0.1:8787` and Vite on
`http://localhost:5173`. Vite is exposed only after the API healthcheck and
current-date dashboard warmup succeed. Stopping the command stops both
processes.

To start only the API for diagnostics:

```bash
npm run dev:api
```

Health check: `http://127.0.0.1:8787/api/v1/health`.

The API rejects write methods and does not persist frontend state.

Vite proxies `/api/*` to the read API.

Successful read responses use bounded server-side caching, single-flight
background revalidation, ETags and gzip. Current/future dashboard data has a
short fresh window and can be served stale briefly while Cosmos refreshes in
the background; historical and support responses can be cached longer. Errors
and healthchecks are never cached.

## Data behavior

- `Dagens matcher` -> `fixtures_canonical`
- homepage OVER/UNDER matchups -> persisted `matchups_score` when available
- if persisted matchup rows are absent, only **upcoming** fixtures may be calculated read-only using V2's existing matchup engine and real current `teamprofiles`
- started/historical matches are never recomputed from current profiles
- Auto -> `forward_bets`
- Resultatloop/Historik -> `forward_results`
- match checkpoints -> `market_snapshots`
- team pages -> `teamprofiles`
- model page -> V2 model/forward/result collections
- system page -> `job_runs`, `health_reports`, `audit_reports`

If a source is missing, the UI shows an empty/error state. It does not substitute hardcoded matches, scores, odds or metrics.

## Verification

```bash
npm run typecheck
npm run lint
npm run test -- --run
npm run build
```

GitHub Actions additionally performs dependency audits, blocks the removed runtime preview/snapshot files from returning, and runs the full existing Python regression suite on Style-1.
