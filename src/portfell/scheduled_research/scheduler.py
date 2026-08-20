"""Exact Sunday scheduler contract, non-overlap lock, and stable project coordination."""

from __future__ import annotations

import fcntl
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from portfell.scheduled_research.cycle_summary import CycleSummary

CRON_TZ = "Europe/Vienna"
CRON_EXPRESSION = "0 9 * * 0"
SUNDAY_HOUR = 9


@dataclass(frozen=True, slots=True)
class ProjectTerminal:
    project_slug: str
    successful: bool
    reused_runs: int
    new_runs: int


@contextmanager
def cycle_lock(path: Path) -> Iterator[bool]:
    """Acquire one non-blocking flock; False means another cycle already owns the lock."""

    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    acquired = False
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            acquired = False
        yield acquired
    finally:
        if acquired:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def next_sunday_run(now: datetime) -> datetime:
    """Resolve the next 09:00 Europe/Vienna execution with timezone/DST semantics."""

    zone = ZoneInfo(CRON_TZ)
    local = now.astimezone(zone)
    days_ahead = (6 - local.weekday()) % 7
    candidate_date = (local + timedelta(days=days_ahead)).date()
    candidate = datetime(
        candidate_date.year,
        candidate_date.month,
        candidate_date.day,
        SUNDAY_HOUR,
        0,
        tzinfo=zone,
    )
    if candidate <= local:
        candidate_date = candidate_date + timedelta(days=7)
        candidate = datetime(
            candidate_date.year,
            candidate_date.month,
            candidate_date.day,
            SUNDAY_HOUR,
            0,
            tzinfo=zone,
        )
    return candidate


def coordinate_cycle(
    *,
    cycle_date: str,
    project_slugs: tuple[str, ...],
    refresh_market: Callable[[], str],
    run_project: Callable[[str, str], ProjectTerminal],
) -> CycleSummary:
    """Refresh shared market state once, then process projects in stable isolated order."""

    revision = refresh_market()
    terminals: list[ProjectTerminal] = []
    for project_slug in sorted(set(project_slugs)):
        try:
            terminals.append(run_project(project_slug, revision))
        except Exception:
            terminals.append(ProjectTerminal(project_slug, False, 0, 0))
    return CycleSummary(
        cycle_date=cycle_date,
        market_revision=revision,
        project_count=len(terminals),
        successful_projects=sum(terminal.successful for terminal in terminals),
        failed_projects=sum(not terminal.successful for terminal in terminals),
        reused_runs=sum(terminal.reused_runs for terminal in terminals),
        new_runs=sum(terminal.new_runs for terminal in terminals),
    )
