"""Tests for time_utils."""

from datetime import date, datetime
from unittest.mock import patch

import pytest

from core.bess.time_utils import (
    TIMEZONE,
    get_current_period_index,
    get_period_count,
    period_index_to_timestamp,
    timestamp_to_period_index,
)

# All mocked tests must pass through datetime.combine and datetime.fromtimestamp
# because time_utils uses both for epoch-based DST-safe arithmetic.
_DATETIME_PASSTHROUGH = {
    "combine": datetime.combine,
    "fromtimestamp": datetime.fromtimestamp,
}


def _mock_today(mock_datetime, today_date=date(2025, 11, 15)):
    """Configure mock_datetime to report a fixed 'now' date."""
    mock_now = datetime(
        today_date.year, today_date.month, today_date.day, 12, 0, tzinfo=TIMEZONE
    )
    mock_datetime.now.return_value = mock_now
    for attr, fn in _DATETIME_PASSTHROUGH.items():
        setattr(mock_datetime, attr, fn)


def test_normal_day_has_96_periods():
    """Normal day should have 96 quarterly periods."""
    normal_day = date(2025, 11, 15)  # Not a DST transition
    assert get_period_count(normal_day) == 96


@patch("core.bess.time_utils.datetime")
def test_timestamp_to_period_index_today(mock_datetime):
    """Should convert today's timestamp to period index."""
    _mock_today(mock_datetime)

    # Test various times today
    dt_morning = datetime(2025, 11, 15, 0, 0, tzinfo=TIMEZONE)
    assert timestamp_to_period_index(dt_morning) == 0  # Midnight

    dt_afternoon = datetime(2025, 11, 15, 14, 30, tzinfo=TIMEZONE)
    assert timestamp_to_period_index(dt_afternoon) == 58  # 14 * 4 + 2

    dt_evening = datetime(2025, 11, 15, 23, 45, tzinfo=TIMEZONE)
    assert timestamp_to_period_index(dt_evening) == 95  # Last period


@patch("core.bess.time_utils.datetime")
def test_timestamp_to_period_index_tomorrow(mock_datetime):
    """Should convert tomorrow's timestamp to period index."""
    _mock_today(mock_datetime)

    # Test tomorrow
    dt_tomorrow_midnight = datetime(2025, 11, 16, 0, 0, tzinfo=TIMEZONE)
    assert timestamp_to_period_index(dt_tomorrow_midnight) == 96  # Tomorrow 00:00

    dt_tomorrow_afternoon = datetime(2025, 11, 16, 14, 0, tzinfo=TIMEZONE)
    assert timestamp_to_period_index(dt_tomorrow_afternoon) == 152  # 96 + 56


@patch("core.bess.time_utils.datetime")
def test_period_index_to_timestamp(mock_datetime):
    """Should convert period index to timestamp."""
    _mock_today(mock_datetime)

    # Today
    dt = period_index_to_timestamp(0)
    assert dt.date() == date(2025, 11, 15)
    assert dt.hour == 0
    assert dt.minute == 0

    dt = period_index_to_timestamp(58)
    assert dt.date() == date(2025, 11, 15)
    assert dt.hour == 14
    assert dt.minute == 30

    # Tomorrow
    dt = period_index_to_timestamp(96)
    assert dt.date() == date(2025, 11, 16)
    assert dt.hour == 0
    assert dt.minute == 0


@patch("core.bess.time_utils.datetime")
def test_roundtrip_conversion(mock_datetime):
    """period_index → timestamp → period_index should roundtrip."""
    _mock_today(mock_datetime)

    for period_idx in [0, 56, 95, 96, 152]:
        timestamp = period_index_to_timestamp(period_idx)
        recovered_idx = timestamp_to_period_index(timestamp)
        assert recovered_idx == period_idx, f"Roundtrip failed for period {period_idx}"


@patch("core.bess.time_utils.datetime")
def test_get_current_period_index(mock_datetime):
    """Should return current period index."""
    # Mock current time as 2025-11-15 14:30
    now_time = datetime(2025, 11, 15, 14, 30, tzinfo=TIMEZONE)
    mock_datetime.now.return_value = now_time
    for attr, fn in _DATETIME_PASSTHROUGH.items():
        setattr(mock_datetime, attr, fn)

    assert get_current_period_index() == 58  # 14 * 4 + 2


def test_timestamp_must_be_timezone_aware():
    """Should raise error for naive timestamps."""
    naive_dt = datetime(2025, 11, 15, 14, 30)  # No timezone
    with pytest.raises(ValueError, match="timezone-aware"):
        timestamp_to_period_index(naive_dt)


def test_negative_period_index_raises_error():
    """Should raise error for negative period indices."""
    with pytest.raises(ValueError, match="non-negative"):
        period_index_to_timestamp(-1)


@patch("core.bess.time_utils.datetime")
def test_past_timestamp_raises_error(mock_datetime):
    """Should raise error for past timestamps (before today)."""
    _mock_today(mock_datetime)

    # Try to convert yesterday
    yesterday = datetime(2025, 11, 14, 12, 0, tzinfo=TIMEZONE)
    with pytest.raises(ValueError, match="Only today and tomorrow supported"):
        timestamp_to_period_index(yesterday)


@patch("core.bess.time_utils.datetime")
def test_future_beyond_tomorrow_raises_error(mock_datetime):
    """Should raise error for timestamps beyond tomorrow."""
    _mock_today(mock_datetime)

    # Try to convert day after tomorrow
    day_after_tomorrow = datetime(2025, 11, 17, 12, 0, tzinfo=TIMEZONE)
    with pytest.raises(ValueError, match="Only today and tomorrow supported"):
        timestamp_to_period_index(day_after_tomorrow)


def test_period_index_beyond_tomorrow_raises_error():
    """Should raise error for period indices beyond tomorrow."""
    with pytest.raises(ValueError, match="beyond tomorrow"):
        period_index_to_timestamp(200)  # Way beyond tomorrow


@patch("core.bess.time_utils.datetime")
def test_midnight_is_period_zero(mock_datetime):
    """Midnight should be period 0."""
    _mock_today(mock_datetime)

    dt = datetime(2025, 11, 15, 0, 0, tzinfo=TIMEZONE)
    assert timestamp_to_period_index(dt) == 0


@patch("core.bess.time_utils.datetime")
def test_end_of_day_is_period_95(mock_datetime):
    """23:45 should be period 95."""
    _mock_today(mock_datetime)

    dt = datetime(2025, 11, 15, 23, 45, tzinfo=TIMEZONE)
    assert timestamp_to_period_index(dt) == 95
