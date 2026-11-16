"""Clock and timezone helpers. Streaks and quests depend on the user's local date, not UTC."""
from datetime import date, datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones


def utcnow() -> datetime:
    """Return the current time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


def local_date(tz_name: str, now: datetime | None = None) -> date:
    """Return the calendar date in the given IANA timezone."""
    return (now or utcnow()).astimezone(ZoneInfo(tz_name)).date()


@lru_cache(maxsize=1)
def _known_timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def is_valid_timezone(name: str) -> bool:
    """Check membership rather than calling ZoneInfo, which treats its input as a file path."""
    return name in _known_timezones()
