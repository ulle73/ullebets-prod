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

Use two terminals.

### Terminal 1 — V2 read API

```bash
cd frontend
npm run dev:api
```

This starts the read-only API on `http://127.0.0.1:8787`.

Health check:

```text
http://127.0.0.1:8787/api/v1/health
```

The API rejects write methods and does not persist frontend state.

### Terminal 2 — frontend

```bash
cd frontend
npm run dev
```

Vite normally starts on `http://localhost:5173` and proxies `/api/*` to the read API.

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