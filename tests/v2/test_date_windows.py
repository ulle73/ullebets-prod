import pytest

from ullebets_v2.date_windows import resolve_requested_dates, resolve_target_limit


def test_resolve_requested_dates_dedupes_explicit_dates_in_order() -> None:
    assert resolve_requested_dates(explicit_dates=["2026-07-25", "2026-07-25", "2026-07-26"]) == [
        "2026-07-25",
        "2026-07-26",
    ]


def test_resolve_requested_dates_builds_range() -> None:
    assert resolve_requested_dates(start_date="2026-07-25", end_date="2026-07-27") == [
        "2026-07-25",
        "2026-07-26",
        "2026-07-27",
    ]


def test_resolve_requested_dates_rejects_mixed_modes() -> None:
    with pytest.raises(ValueError, match="either explicit --date values or --start-date/--end-date"):
        resolve_requested_dates(
            explicit_dates=["2026-07-25"],
            start_date="2026-07-25",
            end_date="2026-07-26",
        )


def test_resolve_requested_dates_requires_complete_range() -> None:
    with pytest.raises(ValueError, match="Both --start-date and --end-date are required together"):
        resolve_requested_dates(start_date="2026-07-25")


def test_resolve_requested_dates_can_allow_empty() -> None:
    assert resolve_requested_dates(allow_empty=True) == []


def test_resolve_target_limit_returns_none_when_unspecified() -> None:
    assert resolve_target_limit(None) is None


def test_resolve_target_limit_uses_default_when_unspecified() -> None:
    assert resolve_target_limit(None, default_when_unspecified=1) == 1


def test_resolve_target_limit_treats_zero_as_unbounded() -> None:
    assert resolve_target_limit(0) is None


def test_resolve_target_limit_keeps_positive_values() -> None:
    assert resolve_target_limit(7) == 7
