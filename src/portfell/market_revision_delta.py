"""Pure tenant-neutral planning of missing shared market revision windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


class MarketRevisionPlanError(ValueError):
    """Raised for invalid immutable market revision planning inputs."""


@dataclass(frozen=True, order=True)
class CoverageRange:
    """Inclusive date coverage range for one canonical listing and dataset."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise MarketRevisionPlanError("coverage_range_invalid")


def plan_missing_windows(
    *,
    requested_start: date,
    requested_end: date,
    coverage: tuple[CoverageRange, ...],
    correction_overlap_days: int,
) -> tuple[CoverageRange, ...]:
    """Plan gaps only; a fully covered request creates no provider window."""

    if requested_end < requested_start:
        raise MarketRevisionPlanError("requested_range_invalid")
    if correction_overlap_days < 0:
        raise MarketRevisionPlanError("correction_overlap_invalid")
    merged_coverage = _merge_coverage(coverage, requested_start, requested_end)
    gaps: list[CoverageRange] = []
    cursor = requested_start
    for item in merged_coverage:
        if cursor < item.start:
            gaps.append(CoverageRange(cursor, item.start - timedelta(days=1)))
        cursor = max(cursor, item.end + timedelta(days=1))
    if cursor <= requested_end:
        gaps.append(CoverageRange(cursor, requested_end))
    return tuple(
        CoverageRange(
            max(requested_start, gap.start - timedelta(days=correction_overlap_days)), gap.end
        )
        for gap in gaps
    )


def _merge_coverage(
    coverage: tuple[CoverageRange, ...], requested_start: date, requested_end: date
) -> tuple[CoverageRange, ...]:
    clipped = sorted(
        CoverageRange(max(item.start, requested_start), min(item.end, requested_end))
        for item in coverage
        if item.end >= requested_start and item.start <= requested_end
    )
    merged: list[CoverageRange] = []
    for item in clipped:
        if merged and item.start <= merged[-1].end + timedelta(days=1):
            merged[-1] = CoverageRange(merged[-1].start, max(merged[-1].end, item.end))
        else:
            merged.append(item)
    return tuple(merged)
