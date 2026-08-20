"""Pure statistics run-control presentation model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RunStatus(StrEnum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class StatisticsRunControl:
    stage_id: str
    status: RunStatus
    phase: str | None
    completed_units: int | None
    total_units: int | None
    percent: float | None
    message: str | None
    can_start: bool
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.percent is not None and not 0.0 <= self.percent <= 100.0:
            raise ValueError("percent must be between 0 and 100")
        if self.completed_units is not None and self.completed_units < 0:
            raise ValueError("completed_units cannot be negative")
        if self.total_units is not None and self.total_units < 0:
            raise ValueError("total_units cannot be negative")
        if self.status is RunStatus.FAILED and not self.failure_reason:
            raise ValueError("failed status requires failure_reason")


def normalize_progress(completed_units: int | None, total_units: int | None) -> float | None:
    """Normalize progress without inventing zero for unavailable totals."""

    if completed_units is None or total_units is None or total_units <= 0:
        return None
    completed = min(max(completed_units, 0), total_units)
    return (completed / total_units) * 100.0
