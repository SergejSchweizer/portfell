"""Due-time helper for embedding Sunday research into the existing long-running worker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from portfell.scheduled_research.integration import SundayCycleResult, SundayRuntime, run_sunday_cycle
from portfell.scheduled_research.scheduler import CRON_EXPRESSION, CRON_TZ, next_sunday_run


@dataclass
class SundayWorkerSchedule:
    runtime: SundayRuntime
    lock_path: Path
    next_run: datetime

    @classmethod
    def start(cls, *, runtime: SundayRuntime, lock_path: Path, now: datetime) -> "SundayWorkerSchedule":
        return cls(runtime=runtime, lock_path=lock_path, next_run=next_sunday_run(now))

    def run_if_due(self, now: datetime) -> SundayCycleResult | None:
        """Run at most once when due and advance immediately to the next Sunday slot."""

        if now.astimezone(self.next_run.tzinfo) < self.next_run:
            return None
        cycle_date = self.next_run.date().isoformat()
        result = run_sunday_cycle(cycle_date=cycle_date, runtime=self.runtime, lock_path=self.lock_path)
        self.next_run = next_sunday_run(now)
        return result


SCHEDULE_DESCRIPTION = f"CRON_TZ={CRON_TZ}; {CRON_EXPRESSION}"
