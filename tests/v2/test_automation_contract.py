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


def test_closing_workflow_runs_frequently_enough_for_t_minus_10m() -> None:
    workflow = (
        repo_root()
        / ".github"
        / "workflows"
        / "run-unibet-closing.yml"
    ).read_text(encoding="utf-8")

    assert 'cron: "2-57/5 * * * *"' in workflow
    assert "dependency_profile: lean" in workflow
    assert "--refresh-derived" in workflow


def test_regular_checkpoint_workflow_leaves_t30_and_t10_to_closing_job() -> None:
    workflow = (
        repo_root()
        / ".github"
        / "workflows"
        / "run-unibet-odds-checkpoints.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" not in workflow
    assert "dependency_profile: lean" in workflow
    assert "--exclude-checkpoint T_MINUS_30M" in workflow
    assert "--exclude-checkpoint T_MINUS_10M" in workflow


def test_match_aware_odds_scheduler_owns_production_checkpoints_and_closing_watch() -> None:
    workflow = (
        repo_root()
        / ".github"
        / "workflows"
        / "v2-odds-scheduler.yml"
    ).read_text(encoding="utf-8")

    assert 'cron: "23 * * * *"' in workflow
    assert "actions: write" in workflow
    assert "actions/checkout@v7" in workflow
    assert "actions/setup-python@v7" in workflow
    assert "plan_closing_watch.py" in workflow
    assert "CURRENT_STATE=$(gh api" in workflow
    assert 'if [ "$CURRENT_STATE" = "active" ]' in workflow
    assert "Closing watcher is already disabled" in workflow
    assert "gh workflow enable run-unibet-closing.yml" in workflow
    assert "gh workflow disable run-unibet-closing.yml" in workflow
    assert "capture_odds_checkpoints.py" in workflow
    assert "--exclude-checkpoint T_MINUS_12H" in workflow
    assert "--exclude-checkpoint T_MINUS_2H" not in workflow
    assert "--exclude-checkpoint T_MINUS_30M" in workflow
    assert "--exclude-checkpoint T_MINUS_10M" in workflow


def test_checkpoint_capture_workflows_score_v6_only_after_new_snapshots() -> None:
    workflows = {
        "v2-odds-scheduler.yml": "capture_odds_checkpoints.py",
        "run-unibet-closing.yml": "capture_closing_snapshots.py",
    }

    for workflow_name, capture_command in workflows.items():
        workflow = (
            repo_root()
            / ".github"
            / "workflows"
            / workflow_name
        ).read_text(encoding="utf-8")

        assert capture_command in workflow
        assert "CAPTURED_SNAPSHOTS=" in workflow
        assert 'if [ "$CAPTURED_SNAPSHOTS" -gt 0 ]; then' in workflow
        assert "python -m pip install -e ." in workflow
        assert "score_ev_shadow_model.py" in workflow
        assert "ev_scope_interaction_recency45_asof_capped_v6_shadow.joblib" in workflow
        assert "v6_corners_away_total_forward_v1" in workflow


def test_shared_runner_uses_current_node24_actions() -> None:
    workflow = (
        repo_root()
        / ".github"
        / "workflows"
        / "v2-python-job.yml"
    ).read_text(encoding="utf-8")

    assert "actions/checkout@v7" in workflow
    assert "actions/setup-python@v7" in workflow
    assert "actions/setup-node@v7" in workflow
    assert "actions/checkout@v4" not in workflow
    assert "actions/setup-python@v5" not in workflow
    assert "actions/setup-node@v4" not in workflow


def test_lean_shared_runner_makes_v2_package_importable_before_command_rendering() -> None:
    """Prevent lean jobs from failing before their configured Python command runs."""
    workflow = (
        repo_root()
        / ".github"
        / "workflows"
        / "v2-python-job.yml"
    ).read_text(encoding="utf-8")

    assert "PYTHONPATH: ${{ github.workspace }}/src" in workflow

    environment = {"PYTHONPATH": str(repo_root() / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            "from ullebets_v2.automation import render_workflow_command; "
            "print(render_workflow_command('python job.py --dry-run', dry_run=False), end='')",
        ],
        cwd=repo_root(),
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "python job.py\n"


def test_full_runtime_pins_frozen_model_dependencies() -> None:
    project = (repo_root() / "pyproject.toml").read_text(encoding="utf-8")

    assert 'numpy==2.2.2' in project
    assert 'pandas==2.2.3' in project
    assert 'joblib==1.5.0' in project
    assert 'scikit-learn==1.7.1' in project


def test_workflow_directory_flags_missing_source_workflow_and_runner_dry_run_wiring() -> None:
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
        )
        mutated = re.sub(
            r"^      dry_run: \$\{\{ inputs\.dry_run \|\| false \}\}\r?\n",
            "",
            mutated,
            count=1,
            flags=re.MULTILINE,
        )
        workflow_path.write_text(mutated, encoding="utf-8")
        report = inspect_workflow_directory(workflow_dir)
    finally:
        workflow_path.write_bytes(original_bytes)

    flagged = {row["file"]: row for row in report["file_reports"]}
    assert "run-unibet-forward.yml" in report["invalid_content_files"]
    assert flagged["run-unibet-forward.yml"]["status"] == "warn"
    assert "missing_explicit_source_workflow" in flagged["run-unibet-forward.yml"]["findings"]
    assert "missing_runner_dry_run_wiring" in flagged["run-unibet-forward.yml"]["findings"]


def test_workflow_directory_flags_missing_workflow_dispatch_dry_run_input() -> None:
    workflow_dir = repo_root() / ".github" / "workflows"
    workflow_path = workflow_dir / "run-unibet-forward.yml"
    original_bytes = workflow_path.read_bytes()
    original = original_bytes.decode("utf-8")
    try:
        mutated = re.sub(
            r'^      dry_run:\r?\n'
            r'^        description: "Run without writes \(smoke test\)\."\r?\n'
            r'^        required: false\r?\n'
            r'^        default: false\r?\n'
            r'^        type: boolean\r?\n',
            "",
            original,
            count=1,
            flags=re.MULTILINE,
        )
        workflow_path.write_text(mutated, encoding="utf-8")
        report = inspect_workflow_directory(workflow_dir)
    finally:
        workflow_path.write_bytes(original_bytes)

    flagged = {row["file"]: row for row in report["file_reports"]}
    assert "run-unibet-forward.yml" in report["invalid_content_files"]
    assert flagged["run-unibet-forward.yml"]["status"] == "warn"
    assert "missing_workflow_dispatch_dry_run_input" in flagged["run-unibet-forward.yml"]["findings"]


def test_workflow_directory_accepts_shared_dry_run_gate_without_literal_flag() -> None:
    workflow_dir = repo_root() / ".github" / "workflows"
    workflow_path = workflow_dir / "run-unibet-forward.yml"
    original_bytes = workflow_path.read_bytes()
    original = original_bytes.decode("utf-8")
    try:
        mutated = original.replace("--dry-run", "", 1) + "\n      dry_run: false\n"
        workflow_path.write_text(mutated, encoding="utf-8")
        report = inspect_workflow_directory(workflow_dir)
    finally:
        workflow_path.write_bytes(original_bytes)

    flagged = {row["file"]: row for row in report["file_reports"]}
    assert flagged["run-unibet-forward.yml"]["status"] == "ok"


def test_workflow_directory_flags_missing_required_backfill_source_mode() -> None:
    workflow_dir = repo_root() / ".github" / "workflows"
    workflow_path = workflow_dir / "backfill-teamstats-from-date.yml"
    original_bytes = workflow_path.read_bytes()
    original = original_bytes.decode("utf-8")
    try:
        mutated = original.replace("--source-mode db \\\n", "", 1).replace("--source-mode db \\\r\n", "", 1)
        workflow_path.write_text(mutated, encoding="utf-8")
        report = inspect_workflow_directory(workflow_dir)
    finally:
        workflow_path.write_bytes(original_bytes)

    flagged = {row["file"]: row for row in report["file_reports"]}
    assert "backfill-teamstats-from-date.yml" in report["invalid_content_files"]
    assert flagged["backfill-teamstats-from-date.yml"]["status"] == "warn"
    assert "missing_required_workflow_fragments" in flagged["backfill-teamstats-from-date.yml"]["findings"]


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


def test_workflow_directory_flags_missing_analysis_snapshot_source_fragment() -> None:
    workflow_dir = repo_root() / ".github" / "workflows"
    workflow_path = workflow_dir / "run-auto-analysis-checkpoints.yml"
    original_bytes = workflow_path.read_bytes()
    original = original_bytes.decode("utf-8")
    try:
        mutated = original.replace("--snapshot-source db ", "", 1)
        workflow_path.write_text(mutated, encoding="utf-8")
        report = inspect_workflow_directory(workflow_dir)
    finally:
        workflow_path.write_bytes(original_bytes)

    flagged = {row["file"]: row for row in report["file_reports"]}
    assert "run-auto-analysis-checkpoints.yml" in report["invalid_content_files"]
    assert flagged["run-auto-analysis-checkpoints.yml"]["status"] == "warn"
    assert "missing_required_workflow_fragments" in flagged["run-auto-analysis-checkpoints.yml"]["findings"]


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
    assert payload["overall_status"] == "ok"
    assert payload["workflow_files"]["missing_parity_files"] == []
    assert payload["workflow_files"]["invalid_content_files"] == []
    assert payload["env_example"]["missing_required_keys"] == []
    assert payload["database_roles"]["target_db"] == "ullebets_v2"
    assert payload["database_roles"]["legacy_app_db"] == "app"
    assert payload["database_roles"]["legacy_unibet_db"] == "ullebets_unibet"
    assert payload["database_roles"]["role_names_are_distinct"] is True
    assert payload["legacy_dependency_contract"]["default_runtime_blocker_count"] == 0
    assert payload["legacy_dependency_contract"]["default_runtime_blocking_workflows"] == []
    assert payload["legacy_dependency_contract"]["checkout_mismatch_count"] == 0


def test_legacy_dependency_contract_summarizes_native_vs_legacy_workflows() -> None:
    workflow_report = inspect_workflow_directory(repo_root() / ".github" / "workflows")
    summary = summarize_legacy_dependency_contract(workflow_report=workflow_report, old_repo_exists=True)

    assert summary["workflow_count"] > 0
    assert summary["default_runtime_blocker_count"] == 0
    assert summary["native_ready_workflow_count"] > 0
    assert summary["checkout_mismatch_count"] == 0
    rows = {row["old_workflow"]: row for row in summary["rows"]}
    assert rows["run-unibet-backtests.yml"]["default_runtime"]["old_repo"] is False
    assert rows["run-unibet-closing.yml"]["default_runtime"]["old_repo"] is False
    assert rows["backfill-teamstats-from-date.yml"]["default_runtime"]["legacy_app_db"] is False
    assert rows["backfill-teamstats-from-date.yml"]["parity_or_replay"]["legacy_app_db"] is True
    assert rows["run-auto-analysis-checkpoints.yml"]["default_runtime"]["old_repo"] is False
    assert rows["ai-bets-daily.yml"]["default_runtime"]["old_repo"] is False


def test_ev_forward_workflow_uses_only_registered_v6_primary_policy() -> None:
    workflow = (
        repo_root()
        / ".github"
        / "workflows"
        / "ev-shadow-forward.yml"
    ).read_text(encoding="utf-8")

    assert workflow.count("score_ev_shadow_model.py") == 1
    assert (
        "ev_scope_interaction_recency45_asof_capped_v6_shadow.joblib"
        in workflow
    )
    assert "forward_policy_registry_v1.json" in workflow
    assert (
        "v6_corners_away_total_forward_v1"
        in workflow
    )
    assert "--selection-policy-registry" in workflow
    assert "--selection-policy-id" in workflow
    assert "ev_logistic_recency45_asof_capped_v3" not in workflow
    assert "ev_nested_logistic_recency45_asof_capped_v4_shadow" not in workflow
    assert "ev_ensemble_v3_75_v4_25_shadow" not in workflow


def test_ev_forward_workflow_is_manual_recovery_only() -> None:
    workflow = (
        repo_root()
        / ".github"
        / "workflows"
        / "ev-shadow-forward.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" not in workflow
    assert "workflow_dispatch:" in workflow


def test_legacy_ev_backtest_is_manual_parity_only() -> None:
    workflow = (
        repo_root()
        / ".github"
        / "workflows"
        / "run-unibet-backtests.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" not in workflow
    assert "Legacy EV Parity Replay" in workflow
