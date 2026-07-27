import json

from ullebets_v2.fixtures.oracle import resolve_fixture_oracle_context


def _write_fixture_oracle(source_dir, *, date_str: str) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date_str,
        "savedAt": f"{date_str}T12:00:00Z",
        "matches": [],
    }
    (source_dir / f"fixtures-{date_str}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_resolve_fixture_oracle_context_live_defaults_to_no_legacy_oracle(tmp_path) -> None:
    source_dir, payloads = resolve_fixture_oracle_context(
        mode="live",
        dates=["2025-10-08"],
        old_repo_root=tmp_path / "old-repo",
    )

    assert source_dir is None
    assert payloads == {}


def test_resolve_fixture_oracle_context_live_uses_explicit_legacy_oracle(tmp_path) -> None:
    legacy_oracle_dir = tmp_path / "legacy-oracle"
    _write_fixture_oracle(legacy_oracle_dir, date_str="2025-10-08")

    source_dir, payloads = resolve_fixture_oracle_context(
        mode="live",
        dates=["2025-10-08"],
        old_repo_root=tmp_path / "old-repo",
        legacy_oracle_dir=legacy_oracle_dir,
    )

    assert source_dir == legacy_oracle_dir
    assert payloads["2025-10-08"]["date"] == "2025-10-08"


def test_resolve_fixture_oracle_context_replay_defaults_to_old_repo_matches_dir(tmp_path) -> None:
    matches_for_date_dir = tmp_path / "old-repo" / "matches-for-date"
    _write_fixture_oracle(matches_for_date_dir, date_str="2025-10-08")

    source_dir, payloads = resolve_fixture_oracle_context(
        mode="replay",
        dates=["2025-10-08"],
        old_repo_root=tmp_path / "old-repo",
    )

    assert source_dir == matches_for_date_dir
    assert payloads["2025-10-08"]["date"] == "2025-10-08"
