# Ullebets V2 Backend

Det här repot är V2-backend-replacementen för `C:/dev/frontend/ullebets-vecel`.
Frontend ingår inte här. Fokus är raw-first ingest, canonical mapping, audits, parity reports, `job_runs` och säkra CLI-jobb runt `ullebets_v2`.

## Säkerhet

- Alla V2-jobb hard-failar om `MONGODB_DB` inte är `ullebets_v2`.
- `app` och `ullebets_unibet` används bara som read-only referenskällor.
- GitHub Actions i det här repot kör för närvarande i safe mode med `--dry-run` tills riktiga DB-writes godkänns.
- Odds- och modellkedjan har fortfarande ett explicit read-only beroende på originalrepot för legacy JS-oraclen. Actions checkar därför ut originalrepot separat tills de beroendena är helt internaliserade.

## Lokala kommandon

Installera Python-beroenden:

```bash
python -m pip install -e .
```

Foundation smoke:

```bash
python scripts/forward_v2/smoke_test_v2.py
```

No-side-effect healthcheck:

```bash
python scripts/forward_v2/healthcheck_v2.py
python scripts/forward_v2/healthcheck_v2.py --check-connectivity --ping-db --check-fixture-db
```

Indexplan:

```bash
python scripts/forward_v2/bootstrap_indexes.py --dry-run
```

Paritetsmatris:

```bash
python scripts/forward_v2/materialize_parity_reports.py --dry-run
```

## Automation

`.github/workflows/` speglar originalets workflow-namn men kör V2-CLI-jobben.
Varje workflow pekar på ett isolerat V2-flöde och sätter `MONGODB_DB=ullebets_v2`.
Så länge DB-writes är låsta använder workflows `--dry-run` för att bevisa driftkontrakt, inputs och externa beroenden utan att mutera data.


