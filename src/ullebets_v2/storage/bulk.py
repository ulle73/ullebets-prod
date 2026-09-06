"""Small, serial batches avoid thousands of database round trips."""
from __future__ import annotations

from typing import Any
from pymongo import UpdateOne
from ullebets_v2.storage.retry import retry_idempotent


def upsert_rows(collection: Any, rows: list[dict[str, Any]], *, key_fields: tuple[str, ...]) -> int:
    # Last value wins just as sequential update_one did. Retry only $set of the
    # same documents, never increments. Counts include acknowledged inserts;
    # downstream processing must not depend on this count after uncertain writes.
    unique = {tuple(row[field] for field in key_fields): row for row in rows}
    operations = [UpdateOne(dict(zip(key_fields, key)), {"$set": row}, upsert=True) for key, row in unique.items()]
    inserted = 0
    for offset in range(0, len(operations), 50):
        batch = operations[offset:offset + 50]
        result = retry_idempotent(lambda: collection.bulk_write(batch, ordered=False))
        inserted += int(result.upserted_count)
    return inserted
