"""Injected clock and the single timestamp format (AD-6).

This is the only module allowed to read the real wall clock.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Protocol

_TS_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class Clock(Protocol):
    def now(self) -> datetime:
        """Current instant, timezone-aware, in UTC."""
        ...

    def today(self) -> date:
        """Current UTC calendar date."""
        ...


class SystemClock:
    """The real clock, used by the module-level app."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def today(self) -> date:
        return self.now().date()


class FixedClock:
    """A clock frozen at one instant, for tests and deterministic seeds."""

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        self._instant = instant.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self._instant

    def today(self) -> date:
        return self._instant.date()


def format_ts(dt: datetime) -> str:
    """Format an aware datetime as ``YYYY-MM-DDTHH:MM:SS.ffffffZ`` in UTC."""
    if dt.tzinfo is None:
        raise ValueError("format_ts requires a timezone-aware datetime")
    return dt.astimezone(timezone.utc).strftime(_TS_FORMAT)
