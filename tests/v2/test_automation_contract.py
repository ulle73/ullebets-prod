from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from ullebets_v2.verification.automation import (
    inspect_env_example,
    inspect_workflow_directory,
    summarize_legacy_dependency_contract,
)


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
    original_bytes = workflow_path.read_bytes()
    original = original_bytes.decode("utf-8")
    try:
        mutated = re.sub(
            r"^\s*--source-workflow run-unibet-forward\.yml \\\r?\n",
            "",
            original,
            count=1,
            flags=re.MULTILINE,
        ).replace("--dry-run", "", 1)
        workflow_path.write_text(mutated, encoding="utf-8")
        report = inspect_workflow_directory(workflow_dir)
    finally:
        workflow_path.write_bytes(original_bytes)

    flagged = {row["file"]: row for row in report["file_reports"]}
    assert "run-unibet-forward.yml" in report["invalid_content_files"]
    assert flagged["run-unibet-forward.yml"]["status"] == "warn"
    assert "missing_explicit_source_workflow" in flagged["run-unibet-forward.yml"]["findings"]
    assert "missing_dry_run_guard" in flagged["run-unibet-forward.yml"]["findings"]


def test_workflow_directory_flags_missing_required_legacy_checkout() -> None:
    workflow_dir = repo_root() / ".github" / "workflows"
    workflow_path = workflow_dir / "backfill-teamstats-from-date.yml"
    original_bytes = workflow_path.read_bytes()
    original = original_bytes.decode("utf-8")
    try:
        mutated = re.sub(r"^\s*checkout_legacy_repo:\s*true\r?\n", "", original, count=1, flags=re.MULTILINE)
        workflow_path.write_text(mutated, encoding="utf-8")
        report = inspect_workflow_directory(workflow_dir)
    finally:
        workflow_path.write_bytes(original_bytes)

    flagged = {row["file"]: row for row in report["file_reports"]}
    assert "backfill-teamstats-from-date.yml" in report["invalid_content_files"]
    assert flagged["backfill-teamstats-from-date.yml"]["status"] == "warn"
    assert "missing_legacy_repo_checkout" in flagged["backfill-teamstats-from-date.yml"]["findings"]


def test_workflow_directory_flags_missing_required_workflow_fragment() -> None:
    workflow_dir = repo_root() / ".github" / "workflows"
    workflow_path = workflow_dir / "update-teamstats-and-teamprofiles.yml"
    original_bytes = workflow_path.read_bytes()
    original = original_bytes.decode("utf-8")
    try:
        mutated = original.replace("--fixture-source db \\\n", "", 1).replace("--fixture-source db \\\r\n", "", 1)
        workflow_path.write_text(mutated, encoding="utf-8")
        report = inspect_workflow_directory(workflow_dir)
    finally:
        workflow_path.write_bytes(original_bytes)

    flagged = {row["file"]: row for row in report["file_reports"]}
    assert "update-teamstats-and-teamprofiles.yml" in report["invalid_content_files"]
    assert flagged["update-teamstats-and-teamprofiles.yml"]["status"] == "warn"
    assert "missing_required_workflow_fragments" in flagged["update-teamstats-and-teamprofiles.yml"]["findings"]


def test_env_example_covers_required_v2_keys() -> None:
    report = inspect_env_example(repo_root() / ".env.example")
    assert report["exists"] is True
    assert report["missing_required_keys"] == []
    assert report["mongo_db"] == "ullebets_v2"
    assert report["legacy_app_db"] == "app"
    assert report["legacy_unibet_db"] == "ullebets_unibet"
    assert report["legacy_repo_root"] == "./.deps/original-backend"


def test_healthcheck_v2_cli_reports_native_gap_contract() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/forward_v2/healthcheck_v2.py"],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "MONGODB_DB": "ullebets_v2"},
    )
    payload = json.loads(completed.stdout)
    assert payload["overall_status"] == "warn"
    assert payload["workflow_files"]["missing_parity_files"] == []
    assert payload["workflow_files"]["invalid_content_files"] == []
    assert payload["env_example"]["missing_required_keys"] == []
    assert payload["database_roles"]["target_db"] == "ullebets_v2"
    assert payload["database_roles"]["legacy_app_db"] == "app"
    assert payload["database_roles"]["legacy_unibet_db"] == "ullebets_unibet"
    assert payload["database_roles"]["role_names_are_distinct"] is True
    assert payload["legacy_dependency_contract"]["default_runtime_blocker_count"] > 0
    assert "run-unibet-backtests.yml" in payload["legacy_dependency_contract"]["default_runtime_blocking_workflows"]
    assert payload["legacy_dependency_contract"]["checkout_mismatch_count"] == 0


def test_legacy_dependency_contract_summarizes_native_vs_legacy_workflows() -> None:
    workflow_report = inspect_workflow_directory(repo_root() / ".github" / "workflows")
    summary = summarize_legacy_dependency_contract(workflow_report=workflow_report, old_repo_exists=True)

    assert summary["workflow_count"] > 0
    assert summary["default_runtime_blocker_count"] > 0
    assert summary["native_ready_workflow_count"] > 0
    assert summary["checkout_mismatch_count"] == 0
    rows = {row["old_workflow"]: row for row in summary["rows"]}
    assert rows["run-unibet-backtests.yml"]["default_runtime"]["old_repo"] is True
    assert rows["run-unibet-closing.yml"]["default_runtime"]["old_repo"] is False
    assert rows["backfill-teamstats-from-date.yml"]["default_runtime"]["legacy_app_db"] is True
