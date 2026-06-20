from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


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


@dataclass(frozen=True)
class PipelineConfig:
    repo_root: Path
    env_file: Path
    old_repo_root: Path
    data_dir: Path
    support_dir: Path
    derived_dir: Path
    raw_dir: Path
    normalized_dir: Path
    features_dir: Path
    models_dir: Path
    reports_dir: Path
    mongo_uri: str | None
    mongo_db: str

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> "PipelineConfig":
        resolved_root = (repo_root or Path(os.getcwd())).resolve()
        env_file = resolved_root / ".env.local"
        dotenv_values = load_dotenv_map(env_file)

        old_repo_root = Path(
            os.getenv("ULLEBETS_OLD_REPO_ROOT")
            or dotenv_values.get("ULLEBETS_OLD_REPO_ROOT")
            or r"C:\dev\FRONTEND\ullebets-vecel"
        )
        data_dir = resolved_root / "data"
        support_dir = data_dir / "support"
        derived_dir = data_dir / "derived" / "offline_v1"

        return cls(
            repo_root=resolved_root,
            env_file=env_file,
            old_repo_root=old_repo_root,
            data_dir=data_dir,
            support_dir=support_dir,
            derived_dir=derived_dir,
            raw_dir=derived_dir / "raw",
            normalized_dir=derived_dir / "normalized",
            features_dir=derived_dir / "features",
            models_dir=derived_dir / "models",
            reports_dir=derived_dir / "reports",
            mongo_uri=os.getenv("MONGODB_URI") or dotenv_values.get("MONGODB_URI"),
            mongo_db=(
                os.getenv("MONGODB_DB")
                or dotenv_values.get("MONGODB_DB")
                or dotenv_values.get("SOURCE_DB")
                or "app"
            ),
        )

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.support_dir,
            self.derived_dir,
            self.raw_dir,
            self.normalized_dir,
            self.features_dir,
            self.models_dir,
            self.reports_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
