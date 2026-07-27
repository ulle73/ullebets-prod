from __future__ import annotations

from .config import V2Config


EXPECTED_V2_DB = "ullebets_v2"


def ensure_distinct_database_roles(config: V2Config) -> dict[str, str]:
    conflicts = config.database_role_conflicts()
    if conflicts:
        raise RuntimeError(
            "Refusing to run V2 job with overlapping database roles: "
            + ", ".join(conflicts)
            + ". Configure distinct target/legacy database names."
        )
    return config.database_roles()


def ensure_v2_database(config: V2Config) -> str:
    if config.mongo_db != EXPECTED_V2_DB:
        raise RuntimeError(
            f"Refusing to run V2 job against '{config.mongo_db}'. "
            f"MONGODB_DB must be '{EXPECTED_V2_DB}'."
        )
    ensure_distinct_database_roles(config)
    return config.mongo_db
