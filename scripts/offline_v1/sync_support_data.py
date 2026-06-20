from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v1.config import PipelineConfig
from ullebets_v1.logging_utils import configure_logging
from ullebets_v1.sources.support_data import copy_support_files


def main() -> None:
    configure_logging()
    config = PipelineConfig.from_env()
    config.ensure_directories()
    copied = copy_support_files(config.old_repo_root, config.support_dir)
    for path in copied:
        print(f"copied_support={path}")


if __name__ == "__main__":
    main()
