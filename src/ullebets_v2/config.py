from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess


def load_dotenv_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _iter_git_worktree_roots(repo_root: Path) -> list[Path]:
    try:
        completed = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []

    roots: list[Path] = []
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line.startswith("worktree "):
            continue
        candidate = Path(line.removeprefix("worktree ").strip()).resolve()
        if candidate not in roots:
            roots.append(candidate)
    return roots


def resolve_env_file(repo_root: Path) -> Path:
    direct = (repo_root / ".env.local").resolve()
    if direct.exists():
        return direct

    for worktree_root in _iter_git_worktree_roots(repo_root):
        candidate = (worktree_root / ".env.local").resolve()
        if candidate.exists():
            return candidate

    return direct


@dataclass(frozen=True)
class V2Config:
    repo_root: Path
    env_file: Path
    old_repo_root: Path
    support_dir: Path
    data_dir: Path
    raw_dir: Path
    normalized_dir: Path
    reports_dir: Path
    exports_dir: Path
    mongo_uri: str | None
    mongo_db: str

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> "V2Config":
        resolved_root = (repo_root or Path(os.getcwd())).resolve()
        env_file = resolve_env_file(resolved_root)
        dotenv_values = load_dotenv_map(env_file)

        data_dir = resolved_root / "data" / "v2"
        return cls(
            repo_root=resolved_root,
            env_file=env_file,
            old_repo_root=Path(
                os.getenv("ULLEBETS_OLD_REPO_ROOT")
                or dotenv_values.get("ULLEBETS_OLD_REPO_ROOT")
                or r"C:\dev\frontend\ullebets-vecel"
            ),
            support_dir=resolved_root / "data" / "support",
            data_dir=data_dir,
            raw_dir=data_dir / "raw",
            normalized_dir=data_dir / "normalized",
            reports_dir=data_dir / "reports",
            exports_dir=data_dir / "exports",
            mongo_uri=os.getenv("MONGODB_URI") or dotenv_values.get("MONGODB_URI"),
            mongo_db=os.getenv("MONGODB_DB") or dotenv_values.get("MONGODB_DB") or "ullebets_v2",
        )

    def resolve_support_file(self, filename: str) -> Path:
        local_path = self.support_dir / filename
        if local_path.exists():
            return local_path
        return self.old_repo_root / "data" / filename

    def default_leagues_path(self) -> Path:
        return self.resolve_support_file("leagues-and-teams.json")

    def default_league_urls_path(self) -> Path:
        return self.resolve_support_file("unibetLeagueUrls.json")

    def ensure_directories(self) -> None:
        for path in (
            self.support_dir,
            self.data_dir,
            self.raw_dir,
            self.normalized_dir,
            self.reports_dir,
            self.exports_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
