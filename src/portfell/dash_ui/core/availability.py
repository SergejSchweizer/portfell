"""Typed availability states for browser presentation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AvailabilityState(StrEnum):
    AVAILABLE = "available"
    NOT_RUN = "not_run"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class Availability:
    state: AvailabilityState
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.state is not AvailabilityState.AVAILABLE and not self.reason:
            raise ValueError("non-available state requires a reason")
