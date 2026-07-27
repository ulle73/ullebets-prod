from __future__ import annotations

from pathlib import Path
from typing import Any

from ullebets_v2.fixtures.replay import load_fixture_payload


def load_old_payloads_by_date(*, source_dir: Path, dates: list[str]) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for date_str in dates:
        source_path = source_dir / f"fixtures-{date_str}.json"
        if source_path.exists():
            payloads[date_str] = load_fixture_payload(source_path)
    return payloads


def resolve_fixture_oracle_context(
    *,
    mode: str,
    dates: list[str],
    old_repo_root: Path,
    legacy_oracle_dir: Path | None = None,
) -> tuple[Path | None, dict[str, dict[str, Any]]]:
    if mode == "replay":
        source_dir = legacy_oracle_dir or (old_repo_root / "matches-for-date")
        return source_dir, load_old_payloads_by_date(source_dir=source_dir, dates=dates)

    if legacy_oracle_dir is None:
        return None, {}

    return legacy_oracle_dir, load_old_payloads_by_date(source_dir=legacy_oracle_dir, dates=dates)
