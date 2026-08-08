"""Tests for app.timezone."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.timezone import (
    current_date_bogota,
    current_hour_minute_bogota,
    now_bogota,
)


def test_now_bogota_returns_aware_datetime():
    result = now_bogota()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None
    assert result.tzinfo == ZoneInfo("America/Bogota")


def test_now_bogota_offset_is_minus_5():
    # America/Bogota is UTC-5 (no DST)
    result = now_bogota()
    assert result.utcoffset().total_seconds() == -5 * 3600


def test_current_date_bogota_returns_date():
    result = current_date_bogota()
    assert isinstance(result, type(__import__("datetime").date.today()))


def test_current_hour_minute_bogota_returns_ints():
    h, m = current_hour_minute_bogota()
    assert isinstance(h, int)
    assert isinstance(m, int)
    assert 0 <= h <= 23
    assert 0 <= m <= 59


def test_now_bogota_custom_timezone(mocker):
    mocker.patch("app.timezone.datetime")
    from datetime import datetime as real_dt
    fake = real_dt(2026, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
    mocker.patch("app.timezone.datetime.now", return_value=fake)
    result = now_bogota("UTC")
    assert result.hour == 12
    assert result.tzinfo == ZoneInfo("UTC")
