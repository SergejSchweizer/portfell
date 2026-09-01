from datetime import UTC, date, datetime

from portfell.app_services.nightly_refresh import is_nightly_refresh_due, scheduled_slot


def test_nightly_slot_uses_vienna_timezone_across_dst() -> None:
    winter = datetime(2026, 1, 15, 19, 0, tzinfo=UTC)
    summer = datetime(2026, 7, 15, 18, 0, tzinfo=UTC)
    assert scheduled_slot(winter) == (date(2026, 1, 15), 20, 0)
    assert scheduled_slot(summer) == (date(2026, 7, 15), 20, 0)


def test_refresh_is_once_per_local_calendar_day() -> None:
    now = datetime(2026, 7, 15, 18, 0, tzinfo=UTC)
    assert is_nightly_refresh_due(now, None)
    assert not is_nightly_refresh_due(now, date(2026, 7, 15))
    assert not is_nightly_refresh_due(datetime(2026, 7, 15, 18, 1, tzinfo=UTC), None)
