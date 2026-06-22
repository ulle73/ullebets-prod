from __future__ import annotations

from pathlib import Path

from ullebets_v2.config import resolve_env_file


def test_resolve_env_file_prefers_local_env_file(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    env_file = repo_root / ".env.local"
    env_file.write_text("MONGODB_DB=ullebets_v2\n", encoding="utf-8")

    assert resolve_env_file(repo_root) == env_file.resolve()


def test_resolve_env_file_falls_back_to_other_git_worktree(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "worktree-feature"
    repo_root.mkdir(parents=True, exist_ok=True)
    shared_root = tmp_path / "repo-main"
    shared_root.mkdir(parents=True, exist_ok=True)
    shared_env = shared_root / ".env.local"
    shared_env.write_text("RAPIDAPI_KEYS=masked\n", encoding="utf-8")

    monkeypatch.setattr(
        "ullebets_v2.config._iter_git_worktree_roots",
        lambda root: [shared_root.resolve(), repo_root.resolve()],
    )

    assert resolve_env_file(repo_root) == shared_env.resolve()
