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
    source_dir, payloads, source_paths_by_date = resolve_fixture_oracle_context(
        mode="live",
        dates=["2025-10-08"],
        old_repo_root=tmp_path / "old-repo",
    )

    assert source_dir is None
    assert payloads == {}
    assert source_paths_by_date == {}


def test_resolve_fixture_oracle_context_live_uses_explicit_legacy_oracle(tmp_path) -> None:
    legacy_oracle_dir = tmp_path / "legacy-oracle"
    _write_fixture_oracle(legacy_oracle_dir, date_str="2025-10-08")

    source_dir, payloads, source_paths_by_date = resolve_fixture_oracle_context(
        mode="live",
        dates=["2025-10-08"],
        old_repo_root=tmp_path / "old-repo",
        legacy_oracle_dir=legacy_oracle_dir,
    )

    assert source_dir == legacy_oracle_dir
    assert payloads["2025-10-08"]["date"] == "2025-10-08"
    assert source_paths_by_date["2025-10-08"] == legacy_oracle_dir / "fixtures-2025-10-08.json"


def test_resolve_fixture_oracle_context_replay_defaults_to_old_repo_matches_dir(tmp_path) -> None:
    matches_for_date_dir = tmp_path / "old-repo" / "matches-for-date"
    _write_fixture_oracle(matches_for_date_dir, date_str="2025-10-08")

    source_dir, payloads, source_paths_by_date = resolve_fixture_oracle_context(
        mode="replay",
        dates=["2025-10-08"],
        old_repo_root=tmp_path / "old-repo",
    )

    assert source_dir == matches_for_date_dir
    assert payloads["2025-10-08"]["date"] == "2025-10-08"
    assert source_paths_by_date["2025-10-08"] == matches_for_date_dir / "fixtures-2025-10-08.json"


class FakeCollection:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def find(self, query: dict | None = None, projection: dict | None = None):  # noqa: ARG002
        return list(self.docs)


class FakeDatabase(dict):
    def __getitem__(self, collection_name: str):
        return dict.__getitem__(self, collection_name)


def test_resolve_fixture_oracle_context_replay_falls_back_to_legacy_match_database_and_chooses_best_entry(tmp_path) -> None:
    database = FakeDatabase(
        {
            "match-for-date": FakeCollection(
                [
                    {
                        "full": [
                            {
                                "date": "2025-11-21",
                                "savedAt": "2025-11-20T08:00:00Z",
                                "matches": [],
                                "calls": 4,
                                "successes": 0,
                                "failures": 0,
                            }
                        ]
                    },
                    {
                        "full": [
                            {
                                "date": "2025-11-21",
                                "savedAt": "2025-11-20T09:00:00Z",
                                "matches": [{"id": 14689178}],
                                "sources": [{"categoryId": "1"}],
                                "calls": 5,
                                "successes": 1,
                                "failures": 0,
                            }
                        ]
                    },
                ]
            )
        }
    )

    source_dir, payloads, source_paths_by_date = resolve_fixture_oracle_context(
        mode="replay",
        dates=["2025-11-21"],
        old_repo_root=tmp_path / "old-repo",
        legacy_match_database=database,
    )

    assert source_dir == tmp_path / "old-repo" / "matches-for-date"
    assert payloads["2025-11-21"]["savedAt"] == "2025-11-20T09:00:00Z"
    assert payloads["2025-11-21"]["matches"] == [{"id": 14689178}]
    assert payloads["2025-11-21"]["calls"] == 5
    assert source_paths_by_date["2025-11-21"].as_posix() == "mongodb-match-for-date/fixtures-2025-11-21.json"
