from pathlib import Path

import pytest

from ullebets_v2.config import V2Config
from ullebets_v2.safety import ensure_v2_database


def test_v2_config_reads_env_and_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "MONGODB_URI=mongodb://localhost:27017\n"
        "MONGODB_DB=ullebets_v2\n"
        "ULLEBETS_OLD_REPO_ROOT=C:\\dev\\frontend\\ullebets-vecel\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    config = V2Config.from_env(tmp_path)

    assert config.mongo_uri == "mongodb://localhost:27017"
    assert config.mongo_db == "ullebets_v2"
    assert config.old_repo_root == Path(r"C:\dev\frontend\ullebets-vecel")
    assert config.data_dir == tmp_path / "data" / "v2"
    assert config.raw_dir == tmp_path / "data" / "v2" / "raw"
    assert config.reports_dir == tmp_path / "data" / "v2" / "reports"


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
