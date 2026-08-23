from datetime import UTC, datetime

from ullebets_v2.fixtures.dates import fixture_date_stockholm
from ullebets_v2.fixtures.persistence import backfill_fixture_date_stockholm


class RecordingCollection:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = [dict(row) for row in rows]
        self.batch_sizes: list[int] = []

    def find(self, query: dict | None = None, projection: dict | None = None):  # noqa: ARG002
        return [dict(row) for row in self.rows]

    def bulk_write(self, operations: list[object], ordered: bool) -> None:
        assert ordered is False
        self.batch_sizes.append(len(operations))
        for operation in operations:
            match_key = operation._filter["match_key"]  # type: ignore[attr-defined]
            values = operation._doc["$set"]  # type: ignore[attr-defined]
            target = next(row for row in self.rows if row["match_key"] == match_key)
            target.update(values)


class RecordingDatabase(dict):
    def __getitem__(self, key: str) -> RecordingCollection:
        return dict.__getitem__(self, key)


def test_fixture_date_stockholm_converts_utc_kickoff_across_local_midnight() -> None:
    assert fixture_date_stockholm(datetime(2025, 10, 8, 22, 0, tzinfo=UTC)) == "2025-10-09"


def test_backfill_fixture_date_stockholm_preserves_source_provenance_and_updates_only_derived_dates() -> None:
    collection = RecordingCollection(
        [
            {
                "match_key": "needs-correction",
                "source_date": "2026-08-22",
                "fixture_date_stockholm": "2026-08-22",
                "start_time": datetime(2026, 8, 21, 19, 0, tzinfo=UTC),
            },
            {
                "match_key": "missing-derived-date",
                "source_date": "2026-08-22",
                "start_time": datetime(2026, 8, 22, 11, 30, tzinfo=UTC),
            },
            {
                "match_key": "already-correct",
                "source_date": "2026-08-22",
                "fixture_date_stockholm": "2026-08-23",
                "start_time": datetime(2026, 8, 23, 14, 0, tzinfo=UTC),
            },
            {
                "match_key": "missing-kickoff",
                "source_date": "2026-08-22",
                "start_time": None,
            },
        ]
    )
    database = RecordingDatabase(fixtures_canonical=collection)

    summary = backfill_fixture_date_stockholm(database, batch_size=1)

    by_key = {row["match_key"]: row for row in collection.rows}
    assert summary == {
        "scanned": 4,
        "eligible": 3,
        "would_update": 2,
        "updated": 2,
        "already_correct": 1,
        "missing_start_time": 1,
        "missing_match_key": 0,
    }
    assert collection.batch_sizes == [1, 1]
    assert by_key["needs-correction"]["fixture_date_stockholm"] == "2026-08-21"
    assert by_key["missing-derived-date"]["fixture_date_stockholm"] == "2026-08-22"
    assert by_key["needs-correction"]["source_date"] == "2026-08-22"
    assert "fixture_date_stockholm" not in by_key["missing-kickoff"]
