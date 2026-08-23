from pathlib import Path
import sys


# Vercel's Python filesystem routing needs an explicit two-segment function for
# drilldown URLs. The request handling itself stays in the shared application
# adapter, so every API route has exactly one implementation.
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
    """Vercel entrypoint for two-segment read API paths."""
