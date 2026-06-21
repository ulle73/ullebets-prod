from __future__ import annotations

from .config import V2Config


EXPECTED_V2_DB = "ullebets_v2"


def ensure_v2_database(config: V2Config) -> str:
    if config.mongo_db != EXPECTED_V2_DB:
        raise RuntimeError(
            f"Refusing to run V2 job against '{config.mongo_db}'. "
            f"MONGODB_DB must be '{EXPECTED_V2_DB}'."
        )
    return config.mongo_db
