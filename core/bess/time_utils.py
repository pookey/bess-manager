"""Time utilities for quarterly period handling.

KEY PRINCIPLE: All arrays start at index 0 = today 00:00.
Period indices are continuous integers from today's 00:00.

This module provides conversion between timestamps and period indices,
handling DST transitions correctly.

IMPORTANT — Python ZoneInfo datetime arithmetic pitfall:
    datetime + timedelta and datetime - datetime both operate on wall-clock
    time with ZoneInfo, not on actual elapsed (UTC) time. On DST transition
    days this produces incorrect results (e.g. a 23-hour spring-forward day
    appears as 24 hours). All elapsed-time calculations in this module use
    epoch-based arithmetic (.timestamp()) to avoid this.
"""

import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def set_timezone(tz_name: str) -> None:
    """Set the global timezone from HA config. Must be called before scheduling."""
    global TIMEZONE
    TIMEZONE = ZoneInfo(tz_name)


# Timezone — overridden at startup by set_timezone() from HA config
TIMEZONE = ZoneInfo("Europe/Stockholm")
INTERVAL_MINUTES = 15  # Quarterly resolution
PERIODS_PER_HOUR = 4
PERIODS_PER_DAY_NORMAL = 96


def _midnight_epoch(target_date: date) -> float:
    """Get the UTC epoch for midnight of the given date in local timezone."""
    return datetime.combine(target_date, time(0, 0), tzinfo=TIMEZONE).timestamp()


def _epoch_to_local(epoch: float) -> datetime:
    """Convert a UTC epoch to a timezone-aware local datetime."""
    return datetime.fromtimestamp(epoch, tz=TIMEZONE)


def get_period_count(target_date: date) -> int:
    """Get number of quarterly periods in a day.

    Handles DST transitions:
    - Normal day: 96 periods (24 hours * 4)
    - DST spring: 92 periods (23 hours * 4)
    - DST fall: 100 periods (25 hours * 4)

    Args:
        target_date: The calendar date

    Returns:
        Number of quarterly periods in this day
    """
    start_epoch = _midnight_epoch(target_date)
    end_epoch = _midnight_epoch(target_date + timedelta(days=1))
    elapsed_hours = (end_epoch - start_epoch) / 3600

    return int(elapsed_hours * PERIODS_PER_HOUR)


def timestamp_to_period_index(dt: datetime) -> int:
    """Convert timestamp to continuous period index from today's 00:00.

    Only supports today and tomorrow.

    Args:
        dt: Timestamp to convert (must be timezone-aware)

    Returns:
        Continuous index where:
        - Today 00:00 → 0
        - Today 14:00 → 56
        - Today 23:45 → 95
        - Tomorrow 00:00 → 96
        - Tomorrow 14:00 → 152

    Example:
        >>> dt = datetime(2025, 11, 15, 14, 30, tzinfo=TIMEZONE)
        >>> timestamp_to_period_index(dt)
        58  # (14 * 4) + 2 = 58

    Raises:
        ValueError: If dt is not timezone-aware, or not today/tomorrow
    """
    if dt.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware")

    today = datetime.now(tz=TIMEZONE).date()
    target_date = dt.date()
    days_from_today = (target_date - today).days

    # Validate: only today and tomorrow supported
    if days_from_today < 0:
        raise ValueError(
            f"Only today and tomorrow supported, got {target_date} (today is {today})"
        )
    if days_from_today > 1:
        raise ValueError(
            f"Only today and tomorrow supported, got {target_date} (today is {today})"
        )

    # Use epoch arithmetic for DST-safe elapsed time
    day_start_epoch = _midnight_epoch(target_date)
    elapsed_minutes = (dt.timestamp() - day_start_epoch) / 60
    period_within_day = int(elapsed_minutes / INTERVAL_MINUTES)

    if days_from_today == 0:
        return period_within_day
    else:
        today_periods = get_period_count(today)
        return today_periods + period_within_day


def period_index_to_timestamp(period_index: int) -> datetime:
    """Convert period index to timestamp for debugging/display.

    Only supports today and tomorrow (0-191).

    Args:
        period_index: Continuous index from today 00:00 (0-191)

    Returns:
        Timestamp for this period

    Example:
        >>> period_index_to_timestamp(0)
        datetime(2025, 11, 15, 0, 0, tzinfo=ZoneInfo('Europe/Stockholm'))
        >>> period_index_to_timestamp(56)
        datetime(2025, 11, 15, 14, 0, tzinfo=ZoneInfo('Europe/Stockholm'))
        >>> period_index_to_timestamp(96)
        datetime(2025, 11, 16, 0, 0, tzinfo=ZoneInfo('Europe/Stockholm'))

    Raises:
        ValueError: If period_index is negative or > 191 (beyond tomorrow)
    """
    if period_index < 0:
        raise ValueError(f"Period index must be non-negative, got {period_index}")

    today = datetime.now(tz=TIMEZONE).date()
    today_periods = get_period_count(today)

    if period_index < today_periods:
        # Today — use epoch arithmetic for DST safety
        epoch = _midnight_epoch(today) + period_index * INTERVAL_MINUTES * 60
        return _epoch_to_local(epoch)
    else:
        # Tomorrow
        tomorrow = today + timedelta(days=1)
        tomorrow_periods = get_period_count(tomorrow)
        max_period = today_periods + tomorrow_periods - 1

        if period_index > max_period:
            raise ValueError(
                f"Period index {period_index} beyond tomorrow "
                f"(max: {max_period} = today {today_periods} + tomorrow {tomorrow_periods})"
            )

        period_within_tomorrow = period_index - today_periods
        epoch = (
            _midnight_epoch(tomorrow) + period_within_tomorrow * INTERVAL_MINUTES * 60
        )
        return _epoch_to_local(epoch)


def get_current_period_index() -> int:
    """Get current period index.

    Returns:
        Current period as continuous index from today 00:00
        (typically 0-95 for current day)

    Example:
        At 14:30 → returns 58
    """
    now = datetime.now(tz=TIMEZONE)
    return timestamp_to_period_index(now)


def format_period(period_index: int) -> str:
    """Format period index as HH:MM time string for logging.

    Args:
        period_index: Period index (0-95 for today, 96-191 for tomorrow)

    Returns:
        Formatted time string like "14:30" or "00:00"

    Example:
        >>> format_period(0)
        "00:00"
        >>> format_period(58)
        "14:30"
        >>> format_period(95)
        "23:45"
    """
    try:
        timestamp = period_index_to_timestamp(period_index)
        return timestamp.strftime("%H:%M")
    except ValueError:
        # Fallback for invalid period indices
        return f"period_{period_index}"
