from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ullebets_v2.verification.automation import inspect_env_example, inspect_workflow_directory


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_workflow_directory_covers_parity_matrix() -> None:
    report = inspect_workflow_directory(repo_root() / ".github" / "workflows")
    assert report["exists"] is True
    assert report["missing_parity_files"] == []
    assert report["missing_helper_files"] == []
    assert report["invalid_content_files"] == []
    assert all(row["status"] == "ok" for row in report["file_reports"])


def test_workflow_directory_flags_missing_source_workflow_and_dry_run() -> None:
    workflow_dir = repo_root() / ".github" / "workflows"
    workflow_path = workflow_dir / "run-unibet-forward.yml"
    original = workflow_path.read_text(encoding="utf-8")
    try:
        mutated = original.replace("--source-workflow run-unibet-forward.yml \\\n", "", 1).replace("--dry-run", "", 1)
        workflow_path.write_text(mutated, encoding="utf-8")
        report = inspect_workflow_directory(workflow_dir)
    finally:
        workflow_path.write_text(original, encoding="utf-8")

    flagged = {row["file"]: row for row in report["file_reports"]}
    assert "run-unibet-forward.yml" in report["invalid_content_files"]
    assert flagged["run-unibet-forward.yml"]["status"] == "warn"
    assert "missing_explicit_source_workflow" in flagged["run-unibet-forward.yml"]["findings"]
    assert "missing_dry_run_guard" in flagged["run-unibet-forward.yml"]["findings"]


def test_env_example_covers_required_v2_keys() -> None:
    report = inspect_env_example(repo_root() / ".env.example")
    assert report["exists"] is True
    assert report["missing_required_keys"] == []
    assert report["mongo_db"] == "ullebets_v2"
    assert report["legacy_app_db"] == "app"
    assert report["legacy_unibet_db"] == "ullebets_unibet"
    assert report["legacy_repo_root"] == "./.deps/original-backend"


def test_healthcheck_v2_cli_reports_clean_contract() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/forward_v2/healthcheck_v2.py"],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "MONGODB_DB": "ullebets_v2"},
    )
    payload = json.loads(completed.stdout)
    assert payload["overall_status"] == "ok"
    assert payload["workflow_files"]["missing_parity_files"] == []
    assert payload["workflow_files"]["invalid_content_files"] == []
    assert payload["env_example"]["missing_required_keys"] == []
    assert payload["database_roles"]["target_db"] == "ullebets_v2"
    assert payload["database_roles"]["legacy_app_db"] == "app"
    assert payload["database_roles"]["legacy_unibet_db"] == "ullebets_unibet"
    assert payload["database_roles"]["role_names_are_distinct"] is True
