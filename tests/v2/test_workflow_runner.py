from __future__ import annotations

from ullebets_v2.automation.runner import render_workflow_command


def test_render_workflow_command_keeps_dry_run_when_requested() -> None:
    command = "python foo.py \\\n  --source-workflow bar.yml \\\n  --dry-run\n"
    assert render_workflow_command(command, dry_run=True) == command


def test_render_workflow_command_strips_standalone_dry_run_line_and_previous_backslash() -> None:
    command = "python foo.py \\\n  --source-workflow bar.yml \\\n  --dry-run\n"
    assert render_workflow_command(command, dry_run=False) == "python foo.py \\\n  --source-workflow bar.yml\n"


def test_render_workflow_command_strips_inline_dry_run_from_array_assignment() -> None:
    command = 'ARGS=(--mode fixture-db --source-workflow run.yml --dry-run)\npython foo.py "${ARGS[@]}"\n'
    assert render_workflow_command(command, dry_run=False) == 'ARGS=(--mode fixture-db --source-workflow run.yml )\npython foo.py "${ARGS[@]}"\n'
