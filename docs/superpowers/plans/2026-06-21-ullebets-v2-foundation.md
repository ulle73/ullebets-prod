# Ullebets V2 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the V2 safety/config/index/support-data foundation so every later ingest job can write only to `ullebets_v2`, log its runs, and normalize support data without depending on the old repo runtime.

**Architecture:** Add a new `src/ullebets_v2/` package beside the existing offline V1 code and keep the first slice intentionally small: configuration, database safety, Mongo index bootstrap, job-run ledger, support-data loaders, and a smoke test. This is better than starting with fixtures or odds because the old system's biggest weakness is not missing code; it is unsafe writes, weak traceability, and mixed raw/derived state.

**Tech Stack:** Python 3.11+, PyMongo, pytest, existing `src/ullebets_v1` config/path patterns, MongoDB (`ullebets_v2`)

---

## Scope split

The full V2 spec spans multiple independent subsystems. This plan intentionally covers only the first self-contained subsystem:

- foundation and safety
- support-data normalization
- bootstrap scripts
- smoke-test path

Follow-up plans should cover:

- fixtures + canonical match mapping
- teamstats/result ingest
- Unibet raw odds + snapshot policy
- prediction persistence + settlement + audits
- automation and reporting

## File structure

### Create

- `src/ullebets_v2/__init__.py`
  - package marker for V2
- `src/ullebets_v2/config.py`
  - V2 config object and `.env.local` loading
- `src/ullebets_v2/safety.py`
  - hard guard that blocks writes unless `MONGODB_DB == "ullebets_v2"`
- `src/ullebets_v2/storage/__init__.py`
  - storage package marker
- `src/ullebets_v2/storage/mongo.py`
  - safe Mongo client helpers
- `src/ullebets_v2/storage/indexes.py`
  - idempotent index bootstrap
- `src/ullebets_v2/jobs/__init__.py`
  - jobs package marker
- `src/ullebets_v2/jobs/job_runs.py`
  - job-run start/finish helpers
- `src/ullebets_v2/support/__init__.py`
  - support package marker
- `src/ullebets_v2/support/schemas.py`
  - normalized support-data document builders
- `src/ullebets_v2/support/loaders.py`
  - local JSON loaders for leagues and league URLs
- `src/ullebets_v2/support/opta.py`
  - Opta payload fetch and mapping helpers
- `scripts/forward_v2/bootstrap_indexes.py`
  - CLI for creating V2 indexes
- `scripts/forward_v2/sync_support_data.py`
  - CLI for support-data import/sync
- `scripts/forward_v2/smoke_test_v2.py`
  - CLI smoke test that exercises safety + indexes + support sync
- `tests/v2/test_v2_config.py`
  - config/safety tests
- `tests/v2/test_job_runs.py`
  - job run ledger tests
- `tests/v2/test_support_sync.py`
  - support-data normalization tests

### Modify

- `pyproject.toml`
  - ensure `src/ullebets_v2` and `tests/v2` are covered by package/test discovery if needed
- `README.md`
  - add one short V2 foundation section after code exists

## Task 1: Add V2 config and write safety guard

**Files:**
- Create: `src/ullebets_v2/__init__.py`
- Create: `src/ullebets_v2/config.py`
- Create: `src/ullebets_v2/safety.py`
- Test: `tests/v2/test_v2_config.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from ullebets_v2.config import V2Config
from ullebets_v2.safety import ensure_v2_database


def test_v2_config_reads_env_and_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "MONGODB_URI=mongodb://localhost:27017\n"
        "MONGODB_DB=ullebets_v2\n"
        "ULLEBETS_OLD_REPO_ROOT=C:\\\\dev\\\\frontend\\\\ullebets-vecel\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    config = V2Config.from_env(tmp_path)

    assert config.mongo_uri == "mongodb://localhost:27017"
    assert config.mongo_db == "ullebets_v2"
    assert config.old_repo_root == Path(r"C:\dev\frontend\ullebets-vecel")
    assert config.raw_dir == tmp_path / "data" / "v2" / "raw"


def test_ensure_v2_database_rejects_wrong_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text("MONGODB_DB=app\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config = V2Config.from_env(tmp_path)

    with pytest.raises(RuntimeError, match="ullebets_v2"):
        ensure_v2_database(config)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/v2/test_v2_config.py -v`

Expected:

- FAIL with `ModuleNotFoundError: No module named 'ullebets_v2'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/ullebets_v2/__init__.py
"""Ullebets V2 runtime."""
```

```python
# src/ullebets_v2/config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from ullebets_v1.config import load_dotenv_map


@dataclass(frozen=True)
class V2Config:
    repo_root: Path
    env_file: Path
    old_repo_root: Path
    data_dir: Path
    raw_dir: Path
    normalized_dir: Path
    reports_dir: Path
    mongo_uri: str | None
    mongo_db: str

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> "V2Config":
        root = (repo_root or Path.cwd()).resolve()
        env_file = root / ".env.local"
        dotenv_values = load_dotenv_map(env_file)
        data_dir = root / "data" / "v2"
        return cls(
            repo_root=root,
            env_file=env_file,
            old_repo_root=Path(
                os.getenv("ULLEBETS_OLD_REPO_ROOT")
                or dotenv_values.get("ULLEBETS_OLD_REPO_ROOT")
                or r"C:\dev\frontend\ullebets-vecel"
            ),
            data_dir=data_dir,
            raw_dir=data_dir / "raw",
            normalized_dir=data_dir / "normalized",
            reports_dir=data_dir / "reports",
            mongo_uri=os.getenv("MONGODB_URI") or dotenv_values.get("MONGODB_URI"),
            mongo_db=os.getenv("MONGODB_DB") or dotenv_values.get("MONGODB_DB") or "",
        )

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.raw_dir, self.normalized_dir, self.reports_dir):
            path.mkdir(parents=True, exist_ok=True)
```

```python
# src/ullebets_v2/safety.py
from __future__ import annotations

from ullebets_v2.config import V2Config


def ensure_v2_database(config: V2Config) -> None:
    if config.mongo_db != "ullebets_v2":
        raise RuntimeError(
            f"Unsafe database target '{config.mongo_db or '<missing>'}'. Expected 'ullebets_v2'."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/v2/test_v2_config.py -v`

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/ullebets_v2/__init__.py src/ullebets_v2/config.py src/ullebets_v2/safety.py tests/v2/test_v2_config.py
git commit -m "feat: add ullebets v2 config and db safety guard"
```

### Task 2: Add safe Mongo helpers and job-run ledger

**Files:**
- Create: `src/ullebets_v2/storage/__init__.py`
- Create: `src/ullebets_v2/storage/mongo.py`
- Create: `src/ullebets_v2/jobs/__init__.py`
- Create: `src/ullebets_v2/jobs/job_runs.py`
- Test: `tests/v2/test_job_runs.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from ullebets_v2.jobs.job_runs import build_job_run_started_doc, build_job_run_finished_update


def test_build_job_run_started_doc_sets_expected_fields() -> None:
    now = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    doc = build_job_run_started_doc(
        job_name="sync_support_data",
        job_args={"mode": "full"},
        now=now,
    )

    assert doc["job_name"] == "sync_support_data"
    assert doc["status"] == "running"
    assert doc["job_args"] == {"mode": "full"}
    assert doc["started_at"] == now
    assert "run_id" in doc


def test_build_job_run_finished_update_marks_success() -> None:
    now = datetime(2026, 6, 21, 12, 5, tzinfo=timezone.utc)
    update = build_job_run_finished_update(
        status="succeeded",
        metrics={"upserts": 4},
        now=now,
    )

    assert update["$set"]["status"] == "succeeded"
    assert update["$set"]["finished_at"] == now
    assert update["$set"]["metrics"] == {"upserts": 4}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/v2/test_job_runs.py -v`

Expected:

- FAIL with `ModuleNotFoundError` or missing symbol errors

- [ ] **Step 3: Write minimal implementation**

```python
# src/ullebets_v2/storage/__init__.py
"""Mongo storage helpers for Ullebets V2."""
```

```python
# src/ullebets_v2/jobs/__init__.py
"""Job helpers for Ullebets V2."""
```

```python
# src/ullebets_v2/storage/mongo.py
from __future__ import annotations

from pymongo import MongoClient

from ullebets_v2.config import V2Config
from ullebets_v2.safety import ensure_v2_database


def create_v2_mongo_client(config: V2Config) -> MongoClient:
    if not config.mongo_uri:
        raise RuntimeError("MONGODB_URI is required for V2 jobs.")
    ensure_v2_database(config)
    return MongoClient(config.mongo_uri)


def get_v2_database(client: MongoClient, config: V2Config):
    ensure_v2_database(config)
    return client[config.mongo_db]
```

```python
# src/ullebets_v2/jobs/job_runs.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_job_run_started_doc(*, job_name: str, job_args: dict, now: datetime | None = None) -> dict:
    timestamp = now or utc_now()
    return {
        "run_id": f"{job_name}:{timestamp.isoformat()}:{uuid4().hex[:8]}",
        "job_name": job_name,
        "job_args": job_args,
        "status": "running",
        "started_at": timestamp,
        "finished_at": None,
        "metrics": {},
        "error": None,
    }


def build_job_run_finished_update(*, status: str, metrics: dict | None = None, error: str | None = None, now: datetime | None = None) -> dict:
    return {
        "$set": {
            "status": status,
            "finished_at": now or utc_now(),
            "metrics": metrics or {},
            "error": error,
        }
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/v2/test_job_runs.py -v`

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/ullebets_v2/storage/__init__.py src/ullebets_v2/storage/mongo.py src/ullebets_v2/jobs/__init__.py src/ullebets_v2/jobs/job_runs.py tests/v2/test_job_runs.py
git commit -m "feat: add ullebets v2 mongo helpers and job run ledger"
```

### Task 3: Bootstrap indexes for safe V2 collections

**Files:**
- Create: `src/ullebets_v2/storage/indexes.py`
- Create: `scripts/forward_v2/bootstrap_indexes.py`
- Modify: `src/ullebets_v2/storage/mongo.py`
- Test: `tests/v2/test_support_sync.py`

- [ ] **Step 1: Write the failing test**

```python
from ullebets_v2.storage.indexes import build_index_plan


def test_build_index_plan_contains_core_collections() -> None:
    plan = build_index_plan()
    names = {item["collection"] for item in plan}

    assert "job_runs" in names
    assert "support_leagues" in names
    assert "support_teams" in names
    assert "support_sources" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/v2/test_support_sync.py::test_build_index_plan_contains_core_collections -v`

Expected:

- FAIL because `build_index_plan` does not exist

- [ ] **Step 3: Write minimal implementation**

```python
# src/ullebets_v2/storage/indexes.py
from __future__ import annotations


def build_index_plan() -> list[dict]:
    return [
        {
            "collection": "job_runs",
            "indexes": [
                {"keys": [("run_id", 1)], "kwargs": {"unique": True}},
                {"keys": [("job_name", 1), ("started_at", -1)], "kwargs": {}},
            ],
        },
        {
            "collection": "support_sources",
            "indexes": [
                {"keys": [("source_type", 1), ("version_hash", 1)], "kwargs": {"unique": True}},
            ],
        },
        {
            "collection": "support_leagues",
            "indexes": [
                {"keys": [("league_key", 1)], "kwargs": {"unique": True}},
            ],
        },
        {
            "collection": "support_teams",
            "indexes": [
                {"keys": [("team_key", 1)], "kwargs": {"unique": True}},
                {"keys": [("league_key", 1), ("team_name", 1)], "kwargs": {}},
            ],
        },
    ]
```

```python
# scripts/forward_v2/bootstrap_indexes.py
from __future__ import annotations

from ullebets_v2.config import V2Config
from ullebets_v2.storage.indexes import build_index_plan
from ullebets_v2.storage.mongo import create_v2_mongo_client, get_v2_database


def main() -> None:
    config = V2Config.from_env()
    config.ensure_directories()
    client = create_v2_mongo_client(config)
    try:
        db = get_v2_database(client, config)
        for item in build_index_plan():
            collection = db[item["collection"]]
            for index in item["indexes"]:
                collection.create_index(index["keys"], **index["kwargs"])
        print("OK bootstrap_indexes")
    finally:
        client.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/v2/test_support_sync.py::test_build_index_plan_contains_core_collections -v`

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/ullebets_v2/storage/indexes.py scripts/forward_v2/bootstrap_indexes.py tests/v2/test_support_sync.py
git commit -m "feat: add v2 index bootstrap plan"
```

### Task 4: Normalize support data from local files

**Files:**
- Create: `src/ullebets_v2/support/__init__.py`
- Create: `src/ullebets_v2/support/schemas.py`
- Create: `src/ullebets_v2/support/loaders.py`
- Test: `tests/v2/test_support_sync.py`

- [ ] **Step 1: Write the failing test**

```python
from ullebets_v2.support.schemas import build_support_documents


def test_build_support_documents_creates_leagues_and_teams() -> None:
    leagues = {
        "Premier League": {
            "leagueId": 17,
            "categoryId": 1,
            "teams": [
                {"id": 100, "name": "Arsenal", "slug": "arsenal"},
                {"id": 101, "name": "Chelsea", "slug": "chelsea"},
            ],
        }
    }
    league_urls = {"Premier League": "https://example.test/premier-league"}

    docs = build_support_documents(leagues, league_urls)

    assert docs["sources"]["source_type"] == "support_sync"
    assert docs["leagues"][0]["league_key"] == "premier-league"
    assert docs["leagues"][0]["unibet_league_url"] == "https://example.test/premier-league"
    assert docs["teams"][0]["team_key"] == "premier-league:100"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/v2/test_support_sync.py::test_build_support_documents_creates_leagues_and_teams -v`

Expected:

- FAIL because support schema helpers do not exist

- [ ] **Step 3: Write minimal implementation**

```python
# src/ullebets_v2/support/__init__.py
"""Support-data helpers for Ullebets V2."""
```

```python
# src/ullebets_v2/support/schemas.py
from __future__ import annotations

from hashlib import sha256
import json


def slugify(value: str) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("&", "and")
        .replace("/", "-")
        .replace(" ", "-")
    )


def build_support_documents(leagues_data: dict, league_urls_data: dict) -> dict:
    serialized = json.dumps(
        {"leagues": leagues_data, "league_urls": league_urls_data},
        sort_keys=True,
        ensure_ascii=False,
    )
    version_hash = sha256(serialized.encode("utf-8")).hexdigest()

    leagues = []
    teams = []
    for league_name, payload in leagues_data.items():
        league_key = slugify(league_name)
        leagues.append(
            {
                "league_key": league_key,
                "league_name": league_name,
                "league_id": payload.get("leagueId"),
                "category_id": payload.get("categoryId"),
                "season_id": payload.get("seasonId"),
                "unibet_league_url": league_urls_data.get(league_name),
            }
        )
        for team in payload.get("teams", []):
            teams.append(
                {
                    "team_key": f"{league_key}:{team.get('id')}",
                    "league_key": league_key,
                    "team_id": team.get("id"),
                    "team_name": team.get("name"),
                    "team_slug": team.get("slug"),
                    "image_url": team.get("imageUrl"),
                    "opta_id": team.get("optaId"),
                    "opta_rank": team.get("optaRank"),
                    "opta_rating": team.get("optaRating"),
                }
            )

    return {
        "sources": {
            "source_type": "support_sync",
            "version_hash": version_hash,
        },
        "leagues": leagues,
        "teams": teams,
    }
```

```python
# src/ullebets_v2/support/loaders.py
from __future__ import annotations

from pathlib import Path
import json

from ullebets_v2.config import V2Config


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_support_inputs(config: V2Config) -> tuple[dict, dict]:
    leagues_path = config.old_repo_root / "data" / "leagues-and-teams.json"
    urls_path = config.old_repo_root / "data" / "unibetLeagueUrls.json"
    return load_json(leagues_path), load_json(urls_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/v2/test_support_sync.py::test_build_support_documents_creates_leagues_and_teams -v`

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/ullebets_v2/support/__init__.py src/ullebets_v2/support/schemas.py src/ullebets_v2/support/loaders.py tests/v2/test_support_sync.py
git commit -m "feat: add v2 support data normalization"
```

### Task 5: Add support sync CLI and smoke test

**Files:**
- Create: `src/ullebets_v2/support/opta.py`
- Create: `scripts/forward_v2/sync_support_data.py`
- Create: `scripts/forward_v2/smoke_test_v2.py`
- Modify: `README.md`
- Test: `tests/v2/test_support_sync.py`

- [ ] **Step 1: Write the failing test**

```python
from ullebets_v2.support.opta import merge_opta_fields


def test_merge_opta_fields_updates_matching_team() -> None:
    teams = [
        {
            "team_key": "premier-league:100",
            "team_name": "Arsenal",
            "opta_id": 42,
            "opta_rank": None,
            "opta_rating": None,
        }
    ]
    opta_rows = [
        {"optaId": 42, "rank": 11, "currentRating": 88.7},
    ]

    merged = merge_opta_fields(teams, opta_rows)

    assert merged[0]["opta_rank"] == 11
    assert merged[0]["opta_rating"] == 88.7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/v2/test_support_sync.py::test_merge_opta_fields_updates_matching_team -v`

Expected:

- FAIL because `merge_opta_fields` does not exist

- [ ] **Step 3: Write minimal implementation**

```python
# src/ullebets_v2/support/opta.py
from __future__ import annotations


def merge_opta_fields(teams: list[dict], opta_rows: list[dict]) -> list[dict]:
    by_id = {
        int(row["optaId"]): row
        for row in opta_rows
        if row.get("optaId") is not None
    }
    merged = []
    for team in teams:
        row = by_id.get(int(team["opta_id"])) if team.get("opta_id") is not None else None
        merged.append(
            {
                **team,
                "opta_rank": row.get("rank") if row else team.get("opta_rank"),
                "opta_rating": row.get("currentRating") if row else team.get("opta_rating"),
            }
        )
    return merged
```

```python
# scripts/forward_v2/sync_support_data.py
from __future__ import annotations

from ullebets_v2.config import V2Config
from ullebets_v2.jobs.job_runs import build_job_run_finished_update, build_job_run_started_doc
from ullebets_v2.storage.mongo import create_v2_mongo_client, get_v2_database
from ullebets_v2.support.loaders import load_support_inputs
from ullebets_v2.support.schemas import build_support_documents


def main() -> None:
    config = V2Config.from_env()
    config.ensure_directories()
    client = create_v2_mongo_client(config)
    try:
        db = get_v2_database(client, config)
        run = build_job_run_started_doc(job_name="sync_support_data", job_args={"mode": "local"})
        db["job_runs"].insert_one(run)
        leagues_data, league_urls_data = load_support_inputs(config)
        docs = build_support_documents(leagues_data, league_urls_data)
        db["support_sources"].update_one(
            {"source_type": docs["sources"]["source_type"], "version_hash": docs["sources"]["version_hash"]},
            {"$set": docs["sources"]},
            upsert=True,
        )
        if docs["leagues"]:
            db["support_leagues"].bulk_write(
                [
                    {
                        "updateOne": {
                            "filter": {"league_key": doc["league_key"]},
                            "update": {"$set": doc},
                            "upsert": True,
                        }
                    }
                    for doc in docs["leagues"]
                ]
            )
        if docs["teams"]:
            db["support_teams"].bulk_write(
                [
                    {
                        "updateOne": {
                            "filter": {"team_key": doc["team_key"]},
                            "update": {"$set": doc},
                            "upsert": True,
                        }
                    }
                    for doc in docs["teams"]
                ]
            )
        db["job_runs"].update_one(
            {"run_id": run["run_id"]},
            build_job_run_finished_update(
                status="succeeded",
                metrics={"league_count": len(docs["leagues"]), "team_count": len(docs["teams"])},
            ),
        )
        print("OK sync_support_data")
    finally:
        client.close()


if __name__ == "__main__":
    main()
```

```python
# scripts/forward_v2/smoke_test_v2.py
from __future__ import annotations

from ullebets_v2.config import V2Config
from ullebets_v2.safety import ensure_v2_database


def main() -> None:
    config = V2Config.from_env()
    ensure_v2_database(config)
    config.ensure_directories()
    print("OK smoke_test_v2")


if __name__ == "__main__":
    main()
```

```markdown
# README.md

## Ullebets V2 foundation

Run the first V2 safety/bootstrap steps with:

```bash
python scripts/forward_v2/bootstrap_indexes.py
python scripts/forward_v2/sync_support_data.py
python scripts/forward_v2/smoke_test_v2.py
```
```

- [ ] **Step 4: Run test to verify it passes**

Run:

- `pytest tests/v2/test_support_sync.py::test_merge_opta_fields_updates_matching_team -v`
- `python scripts/forward_v2/smoke_test_v2.py`

Expected:

- pytest PASS
- CLI prints `OK smoke_test_v2`

- [ ] **Step 5: Commit**

```bash
git add src/ullebets_v2/support/opta.py scripts/forward_v2/sync_support_data.py scripts/forward_v2/smoke_test_v2.py README.md tests/v2/test_support_sync.py
git commit -m "feat: add v2 support sync cli and smoke test"
```

## Self-review

### Spec coverage

- strict `ullebets_v2` write safety: covered in Task 1 and reused everywhere
- new foundation in current repo: covered by new `src/ullebets_v2` package and `scripts/forward_v2`
- raw/derived separation start point: this plan creates the scaffolding and support-data normalized layer only; raw fixture/teamstats/odds layers are intentionally deferred to follow-up plans
- support-data sync parity: covered in Task 4 and Task 5
- health/smoke/bootstrap/indexes: covered in Task 3 and Task 5
- traceability per job: covered in Task 2

### Placeholder scan

No `TODO`, `TBD`, or implicit "handle later" steps are used inside the executable tasks. The deferred subsystems are explicitly called out as separate follow-up plans instead of being hidden inside vague steps.

### Type consistency

- `V2Config` is introduced in Task 1 and reused consistently in Tasks 2, 3, and 5
- `job_runs` uses `run_id`, `job_name`, `status`, `metrics`, `started_at`, `finished_at` consistently
- support collections use `league_key` and `team_key` consistently

## Why this first plan is better than starting with ingest

Starting with fixture or odds ingest would recreate the old mistake:

- code that fetches data before the write target is safe
- data that lands before indexes and run ledgers exist
- mappings that spread before contracts are fixed

This first plan is better because it locks in the constraints that the old system lacked:

- safe DB target
- explicit V2 package boundary
- repeatable bootstrap
- job traceability
- normalized support-data contract

## Weaknesses in the old system this plan directly attacks

- default writes to `app`
- support-data split across typoed collections and local files
- lack of a shared job-run ledger
- no stable V2 bootstrap path

## Expensive assumption to keep watching

Even after this plan, the riskiest assumption remains:

"The same league/team identity can be carried safely from local support files into future fixture, teamstats, and Unibet mappings."

That is why the next plan must build canonical `league_key`, `team_key`, `match_key`, and source-link tables before heavy odds ingestion starts.
