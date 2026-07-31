from __future__ import annotations

from ullebets_v2.fixtures.replay import iter_target_dates


def resolve_requested_dates(
    *,
    explicit_dates: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    allow_empty: bool = False,
) -> list[str]:
    normalized_explicit = [str(value).strip() for value in (explicit_dates or []) if str(value).strip()]
    if normalized_explicit and (start_date or end_date):
        raise ValueError("Use either explicit --date values or --start-date/--end-date, not both.")

    if start_date or end_date:
        if not start_date or not end_date:
            raise ValueError("Both --start-date and --end-date are required together.")
        return iter_target_dates(start_date, end_date)

    if normalized_explicit:
        return list(dict.fromkeys(normalized_explicit))

    if allow_empty:
        return []

    raise ValueError("Provide either --date or both --start-date and --end-date.")


def resolve_target_limit(
    limit: int | None,
    *,
    default_when_unspecified: int | None = None,
) -> int | None:
    if limit is None:
        return default_when_unspecified
    if limit <= 0:
        return None
    return int(limit)
