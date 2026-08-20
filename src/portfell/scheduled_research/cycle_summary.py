"""Redacted terminal summary for one scheduled research cycle."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CycleSummary:
    cycle_date: str
    market_revision: str | None
    project_count: int
    successful_projects: int
    failed_projects: int
    reused_runs: int
    new_runs: int

    def __post_init__(self) -> None:
        counts = (
            self.project_count,
            self.successful_projects,
            self.failed_projects,
            self.reused_runs,
            self.new_runs,
        )
        if any(count < 0 for count in counts):
            raise ValueError("cycle summary counts cannot be negative")
        if self.successful_projects + self.failed_projects > self.project_count:
            raise ValueError("terminal project counts cannot exceed project_count")

    def public_dict(self) -> dict[str, object]:
        """Return count-only evidence; credentials and project payloads are intentionally absent."""

        return {
            "cycle_date": self.cycle_date,
            "market_revision": self.market_revision,
            "project_count": self.project_count,
            "successful_projects": self.successful_projects,
            "failed_projects": self.failed_projects,
            "reused_runs": self.reused_runs,
            "new_runs": self.new_runs,
        }
