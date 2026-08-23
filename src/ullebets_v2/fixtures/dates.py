from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


PRODUCT_TIMEZONE = "Europe/Stockholm"
PRODUCT_TZ = ZoneInfo(PRODUCT_TIMEZONE)


def fixture_date_stockholm(start_time: datetime | None) -> str | None:
    """Return the product calendar date for a canonical fixture kickoff."""
    if not isinstance(start_time, datetime):
        return None
    normalized = start_time if start_time.tzinfo is not None else start_time.replace(tzinfo=UTC)
    return normalized.astimezone(PRODUCT_TZ).date().isoformat()
