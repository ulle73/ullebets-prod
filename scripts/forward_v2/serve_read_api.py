from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ullebets_v2.config import V2Config
from ullebets_v2.read_api.http import serve
from ullebets_v2.storage.mongo import get_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the read-only Ullebets V2 API for the frontend.")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = V2Config.from_env(args.repo_root)
    database = get_database(config)
    print(f"Ullebets read API: http://{args.host}:{args.port}/api/v1/health")
    try:
        serve(database, host=args.host, port=args.port)
    except KeyboardInterrupt:
        pass
    finally:
        database.client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
