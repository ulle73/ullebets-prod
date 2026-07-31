from pathlib import Path

import pytest

from ullebets_v2.config import V2Config
from ullebets_v2.safety import (
    ensure_distinct_database_roles,
    ensure_no_simulated_time_write,
    ensure_v2_database,
)


def test_v2_config_reads_env_and_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "MONGODB_URI=mongodb://localhost:27017\n"
        "MONGODB_DB=ullebets_v2\n"
        "LEGACY_APP_MONGODB_DB=app\n"
        "LEGACY_UNIBET_MONGODB_DB=ullebets_unibet\n"
        "ULLEBETS_OLD_REPO_ROOT=C:\\dev\\frontend\\ullebets-vecel\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    config = V2Config.from_env(tmp_path)

    assert config.mongo_uri == "mongodb://localhost:27017"
    assert config.mongo_db == "ullebets_v2"
    assert config.legacy_app_db == "app"
    assert config.legacy_unibet_db == "ullebets_unibet"
    assert config.old_repo_root == Path(r"C:\dev\frontend\ullebets-vecel")
    assert config.data_dir == tmp_path / "data" / "v2"
    assert config.raw_dir == tmp_path / "data" / "v2" / "raw"
    assert config.reports_dir == tmp_path / "data" / "v2" / "reports"
    assert config.database_roles() == {
        "target": "ullebets_v2",
        "legacy_app": "app",
        "legacy_unibet": "ullebets_unibet",
    }


def test_ensure_v2_database_rejects_wrong_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text("MONGODB_DB=app\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = V2Config.from_env(tmp_path)

    with pytest.raises(RuntimeError, match="ullebets_v2"):
        ensure_v2_database(config)


def test_ensure_v2_database_accepts_expected_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text("MONGODB_DB=ullebets_v2\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = V2Config.from_env(tmp_path)

    ensure_v2_database(config)


def test_ensure_distinct_database_roles_rejects_target_legacy_overlap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "MONGODB_DB=ullebets_v2\n"
        "LEGACY_APP_MONGODB_DB=ullebets_v2\n"
        "LEGACY_UNIBET_MONGODB_DB=ullebets_unibet\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    config = V2Config.from_env(tmp_path)

    with pytest.raises(RuntimeError, match="target_matches_legacy_app"):
        ensure_distinct_database_roles(config)


def test_simulated_time_is_only_allowed_for_dry_runs() -> None:
    ensure_no_simulated_time_write(
        time_override=None,
        dry_run=False,
        job_name="live-job",
    )
    ensure_no_simulated_time_write(
        time_override="2026-01-01T00:00:00Z",
        dry_run=True,
        job_name="replay-job",
    )

    with pytest.raises(RuntimeError, match="simulated time"):
        ensure_no_simulated_time_write(
            time_override="2026-01-01T00:00:00Z",
            dry_run=False,
            job_name="live-job",
        )
