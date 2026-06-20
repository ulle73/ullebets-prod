from __future__ import annotations

from pathlib import Path
import shutil


SUPPORT_FILENAMES = (
    "leagues-and-teams.json",
    "unibetLeagueUrls.json",
)


def resolve_support_source_files(old_repo_root: Path) -> list[Path]:
    data_dir = old_repo_root / "data"
    return [data_dir / name for name in SUPPORT_FILENAMES]


def copy_support_files(old_repo_root: Path, target_dir: Path) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source_path in resolve_support_source_files(old_repo_root):
        if not source_path.exists():
            raise FileNotFoundError(f"Missing support source file: {source_path}")
        target_path = target_dir / source_path.name
        shutil.copy2(source_path, target_path)
        copied.append(target_path)
    return copied
