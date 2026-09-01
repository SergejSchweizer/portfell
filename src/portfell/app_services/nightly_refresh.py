"""Pure scheduling policy for the daily Xetra freshness check."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

VIENNA = ZoneInfo("Europe/Vienna")


def scheduled_slot(value: datetime) -> tuple[date, int, int]:
    """Return the local calendar slot; DST is handled by the IANA zone."""
    local = value.astimezone(VIENNA)
    return local.date(), local.hour, local.minute


def is_nightly_refresh_due(value: datetime, last_successful_day: date | None) -> bool:
    day, hour, minute = scheduled_slot(value)
    return hour == 20 and minute == 0 and last_successful_day != day


__all__ = ["VIENNA", "is_nightly_refresh_due", "scheduled_slot"]
