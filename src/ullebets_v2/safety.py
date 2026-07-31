from __future__ import annotations

from .config import V2Config


EXPECTED_V2_DB = "ullebets_v2"


def ensure_no_simulated_time_write(
    *,
    time_override: object | None,
    dry_run: bool,
    job_name: str,
) -> None:
    if time_override is not None and not dry_run:
        raise RuntimeError(
            f"{job_name} refuses a production write with simulated time. "
            "Use --now only together with --dry-run."
        )


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
