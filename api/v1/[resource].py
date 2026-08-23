from pathlib import Path
import sys


# Vercel supports a distinct filesystem function for each route depth. The
# implementation lives in the application package, so this file only exposes
# the one-segment routing entrypoint.
REPOSITORY_ROOT = Path.cwd()


def _configure_source_path() -> None:
    candidates = [REPOSITORY_ROOT / "src"]
    candidates.extend(parent / "src" for parent in Path(__file__).resolve().parents)
    for candidate in candidates:
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            return


_configure_source_path()

from ullebets_v2.read_api.vercel_adapter import handler as ReadApiHandler


class handler(ReadApiHandler):
    """Vercel entrypoint for single-segment read API paths."""
