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


@dataclass(frozen=True, order=True)
class MarketRevision:
    """Tenant-neutral immutable revision identity resolved through a trusted catalog."""

    revision_id: str
    dataset_type: str
    listing_identity: str
    content_hash: str

    def __post_init__(self) -> None:
        if not all((self.revision_id, self.dataset_type, self.listing_identity, self.content_hash)):
            raise MarketRevisionPlanError("market_revision_identity_required")


class InMemoryMarketRevisionCatalog:
    """Test double that retains every immutable revision and current pointer."""

    def __init__(self) -> None:
        self._revisions: dict[str, MarketRevision] = {}
        self._current_ids: dict[tuple[str, str], str] = {}

    def publish(self, revision: MarketRevision) -> MarketRevision:
        """Publish one content identity or return the matching existing revision."""

        existing = self._revisions.get(revision.revision_id)
        if existing is not None:
            if existing != revision:
                raise MarketRevisionPlanError("market_revision_id_conflict")
            return existing
        self._revisions[revision.revision_id] = revision
        self._current_ids[(revision.dataset_type, revision.listing_identity)] = revision.revision_id
        return revision

    def current(self, dataset_type: str, listing_identity: str) -> MarketRevision | None:
        """Resolve the latest trusted revision for one physical listing/dataset."""

        revision_id = self._current_ids.get((dataset_type, listing_identity))
        return self._revisions.get(revision_id) if revision_id is not None else None

    def read(self, revision_id: str) -> MarketRevision | None:
        """Resolve any retained pinned revision by identity."""

        return self._revisions.get(revision_id)


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
