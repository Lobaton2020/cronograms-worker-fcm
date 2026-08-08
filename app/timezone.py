"""Timezone helpers. All scheduling logic uses America/Bogota by default."""

from datetime import datetime, date
from zoneinfo import ZoneInfo


def now_bogota(tz_name: str = "America/Bogota") -> datetime:
    """Return current datetime in the given timezone (default Bogota)."""
    return datetime.now(ZoneInfo(tz_name))


def current_date_bogota(tz_name: str = "America/Bogota") -> date:
    """Return today's date in Bogota."""
    return now_bogota(tz_name).date()


def current_hour_minute_bogota(tz_name: str = "America/Bogota") -> tuple[int, int]:
    """Return current hour and minute in Bogota."""
    n = now_bogota(tz_name)
    return n.hour, n.minute
