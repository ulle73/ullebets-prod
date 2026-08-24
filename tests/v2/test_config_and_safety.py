from pathlib import Path

import pytest

from ullebets_v2.config import V2Config
from ullebets_v2.safety import (
    ensure_distinct_database_roles,
    ensure_no_simulated_time_write,
    ensure_v2_database,
)
from ullebets_v2.storage.collections import (
    CANONICAL_COLLECTION_NAMES,
    FORMULA_OBSERVATIONS,
    FORMULA_RESULTS,
    MARKET_BIAS_OBSERVATIONS,
    MARKET_BIAS_PROFILES,
)
from ullebets_v2.storage.indexes import (
    build_core_index_plan,
    build_formula_journal_index_plan,
)


def test_formula_journal_has_a_focused_bootstrap_index_plan() -> None:
    plan = build_formula_journal_index_plan()

    assert [row["collection"] for row in plan] == [
        FORMULA_OBSERVATIONS,
        FORMULA_RESULTS,
    ]
    assert plan[0]["indexes"][0] == {
        "keys": [("observation_key", 1)],
        "name": "observation_key_unique",
        "unique": True,
    }
    assert plan[1]["indexes"][0] == {
        "keys": [("observation_key", 1)],
        "name": "formula_result_observation_unique",
        "unique": True,
    }


def test_market_bias_collections_are_canonical_and_indexed() -> None:
    assert MARKET_BIAS_OBSERVATIONS in CANONICAL_COLLECTION_NAMES
    assert MARKET_BIAS_PROFILES in CANONICAL_COLLECTION_NAMES

    plans = {row["collection"]: row["indexes"] for row in build_core_index_plan()}
    observation_indexes = {row["name"]: row for row in plans[MARKET_BIAS_OBSERVATIONS]}
    profile_indexes = {row["name"]: row for row in plans[MARKET_BIAS_PROFILES]}

    assert observation_indexes["observation_key_unique"]["unique"] is True
    assert observation_indexes["team_context_outcome_available"]["keys"] == [
        ("team_key", 1),
        ("venue_context", 1),
        ("market_scope", 1),
        ("stat_key", 1),
        ("period", 1),
        ("outcome_available_at", -1),
    ]
    assert observation_indexes["match_market_context"]["keys"] == [
        ("match_key", 1),
        ("stat_key", 1),
        ("market_scope", 1),
        ("period", 1),
    ]
    assert profile_indexes["profile_key_unique"]["unique"] is True
    assert profile_indexes["profile_date_team_context"]["keys"] == [
        ("profile_date", 1),
        ("team_key", 1),
        ("venue_context", 1),
        ("market_scope", 1),
        ("stat_key", 1),
        ("period", 1),
    ]


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
