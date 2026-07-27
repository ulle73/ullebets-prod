from __future__ import annotations

from pathlib import Path
from typing import Any

from ullebets_v2.config import load_dotenv_map
from ullebets_v2.parity.workflow_matrix import WORKFLOW_PARITY_MATRIX


REQUIRED_ENV_KEYS = [
    "MONGODB_URI",
    "MONGODB_DB",
    "ULLEBETS_OLD_REPO_ROOT",
    "RAPIDAPI_KEYS",
    "RAPIDAPI_SPORTAPI7_BASE_URL",
    "RAPIDAPI_SOFASCORE_BASE_URL",
    "RAPIDAPI_SPORT_API_REAL_TIME_BASE_URL",
    "RAPIDAPI_SOFASCORE_SPORT_API_BASE_URL",
    "RAPIDAPI_SOFASPORT_BASE_URL",
    "SOFASCORE_PUBLIC_API_BASE_URL",
    "OPTA_RANKINGS_URL",
    "DEFAULT_LEAGUE_RANKING_URL",
]

HELPER_WORKFLOW_FILES = ["v2-healthcheck.yml", "v2-python-job.yml"]


def expected_parity_workflow_files() -> list[str]:
    return sorted({str(entry["old_workflow"]) for entry in WORKFLOW_PARITY_MATRIX})


def inspect_workflow_directory(workflow_dir: Path) -> dict[str, Any]:
    existing = sorted(path.name for path in workflow_dir.glob("*.yml")) if workflow_dir.exists() else []
    expected_parity = expected_parity_workflow_files()
    missing_parity = [name for name in expected_parity if name not in existing]
    missing_helpers = [name for name in HELPER_WORKFLOW_FILES if name not in existing]
    known = set(expected_parity) | set(HELPER_WORKFLOW_FILES)
    extra = [name for name in existing if name not in known]
    return {
        "path": str(workflow_dir),
        "exists": workflow_dir.exists(),
        "existing_files": existing,
        "expected_parity_files": expected_parity,
        "missing_parity_files": missing_parity,
        "missing_helper_files": missing_helpers,
        "extra_files": extra,
        "parity_workflow_count": len(expected_parity),
        "existing_workflow_count": len(existing),
    }


def inspect_env_example(env_file: Path) -> dict[str, Any]:
    values = load_dotenv_map(env_file)
    missing_required = [key for key in REQUIRED_ENV_KEYS if key not in values]
    return {
        "path": str(env_file),
        "exists": env_file.exists(),
        "required_keys": REQUIRED_ENV_KEYS,
        "missing_required_keys": missing_required,
        "mongo_db": values.get("MONGODB_DB"),
        "legacy_repo_root": values.get("ULLEBETS_OLD_REPO_ROOT"),
    }
