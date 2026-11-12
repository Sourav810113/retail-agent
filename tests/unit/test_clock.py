from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.retail_agent.core.clock import FixedClock, SystemClock, format_ts


def test_format_ts_is_utc_with_microseconds_and_z():
    dt = datetime(2026, 1, 2, 3, 4, 5, 6, tzinfo=UTC)
    assert format_ts(dt) == "2026-01-02T03:04:05.000006Z"


def test_format_ts_converts_other_offsets_to_utc():
    dt = datetime(2026, 1, 2, 1, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    assert format_ts(dt) == "2026-01-01T23:00:00.000000Z"


def test_format_ts_rejects_naive():
    with pytest.raises(ValueError):
        format_ts(datetime(2026, 1, 1))


def test_fixed_clock_is_frozen_and_utc():
    instant = datetime(2026, 3, 1, 0, 30, tzinfo=timezone(timedelta(hours=5)))
    clock = FixedClock(instant)
    assert clock.now() == instant
    assert clock.now().tzinfo == UTC
    assert clock.today().isoformat() == "2026-02-28"


def test_fixed_clock_rejects_naive():
    with pytest.raises(ValueError):
        FixedClock(datetime(2026, 1, 1))


def test_system_clock_is_aware_utc():
    clock = SystemClock()
    assert clock.now().utcoffset() == timedelta(0)
    assert clock.today() == clock.now().date()
