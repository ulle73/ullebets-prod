from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from scripts.forward_v2.score_registered_shadow_models import run_registered_models


def _registry(tmp_path: Path) -> dict:
    models = []
    for version in range(2, 7):
        model_id = f"v{version}"
        directory = tmp_path / model_id
        directory.mkdir()
        artifact = directory / f"{model_id}.joblib"
        manifest = directory / "model_manifest.json"
        artifact.write_bytes(b"artifact")
        manifest.write_text("{}", encoding="utf-8")
        row = {
            "model_id": model_id,
            "label": model_id.upper(),
            "family": "frozen_ml",
            "artifact": str(artifact.relative_to(tmp_path)),
            "manifest": str(manifest.relative_to(tmp_path)),
        }
        if version == 6:
            policy = tmp_path / "policy.json"
            policy.write_text("{}", encoding="utf-8")
            row["selection_policy_registry"] = str(policy.relative_to(tmp_path))
            row["selection_policy_id"] = "policy-v6"
        models.append(row)
    return {"registry_id": "test", "js_formulas": {}, "frozen_models": models}


def test_runner_invokes_every_registered_frozen_model(tmp_path) -> None:
    commands: list[list[str]] = []

    def fake_runner(command, **kwargs):  # noqa: ANN001, ARG001
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"score_rows": 2, "score_persistence": {"inserted": 2}}',
            stderr="",
        )

    completed = run_registered_models(
        registry=_registry(tmp_path),
        repo_root=tmp_path,
        dry_run=True,
        runner=fake_runner,
    )

    assert [row["model_id"] for row in completed["models"]] == [
        "v2",
        "v3",
        "v4",
        "v5",
        "v6",
    ]
    assert len(commands) == 5
    assert all("--score-only" in command for command in commands)
    assert all("--dry-run" in command for command in commands)
    assert "--selection-policy-id" not in commands[0]
    assert commands[-1][-2:] == ["--selection-policy-id", "policy-v6"]


def test_runner_fails_with_model_identity_when_child_errors(tmp_path) -> None:
    def failing_v4_runner(command, **kwargs):  # noqa: ANN001, ARG001
        artifact_index = command.index("--artifact") + 1
        artifact = command[artifact_index]
        return subprocess.CompletedProcess(
            command,
            1 if "v4" in artifact else 0,
            stdout="{}",
            stderr="broken artifact",
        )

    with pytest.raises(RuntimeError, match="v4.*broken artifact"):
        run_registered_models(
            registry=_registry(tmp_path),
            repo_root=tmp_path,
            dry_run=True,
            runner=failing_v4_runner,
        )
