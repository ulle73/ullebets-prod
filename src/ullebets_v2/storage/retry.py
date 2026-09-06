"""Bounded retries for idempotent MongoDB operations only."""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, TypeVar

from pymongo.errors import AutoReconnect, BulkWriteError, OperationFailure

T = TypeVar("T")
TRANSIENT_CODES = {50, 91, 189, 262, 11600, 11602, 16500}


def is_transient(exc: Exception) -> bool:
    if isinstance(exc, AutoReconnect):
        return True
    if isinstance(exc, BulkWriteError):
        errors = (exc.details.get("writeErrors") or []) + (exc.details.get("writeConcernErrors") or [])
        return bool(errors) and all(row.get("code") in TRANSIENT_CODES for row in errors)
    return isinstance(exc, OperationFailure) and exc.code in TRANSIENT_CODES


def retry_idempotent(operation: Callable[[], T], *, attempts: int = 4) -> T:
    """An ambiguous write must be safe to replay, including partial success."""
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:
            if not is_transient(exc) or attempt == attempts - 1:
                raise
            delay = 2 ** attempt
            logging.warning("Transient database %s; retry %s/%s in %ss", type(exc).__name__, attempt + 1, attempts - 1, delay)
            time.sleep(delay)
    raise AssertionError("unreachable")
