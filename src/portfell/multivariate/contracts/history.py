"""Canonical ResearchUniverseSnapshot and history evidence semantics."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from portfell.multivariate.contracts.common import EvidenceAvailability
from portfell.multivariate.contracts.serialization import canonical_json


class ResearchStage(StrEnum):
    METADATA = "metadata"
    UNIVARIATE = "univariate"
    BIVARIATE = "bivariate"
    MULTIVARIATE = "multivariate"
    FINAL_PORTFOLIO = "final_portfolio"


RESEARCH_STAGE_ORDER: tuple[ResearchStage, ...] = tuple(ResearchStage)


@dataclass(frozen=True, slots=True)
class HistoryRange:
    first_date: str | None
    last_date: str | None
    observation_count: int | None

    def __post_init__(self) -> None:
        if self.observation_count is not None and self.observation_count < 0:
            raise ValueError("observation_count cannot be negative")
        if self.observation_count is None and (self.first_date is not None or self.last_date is not None):
            raise ValueError("unavailable observation count cannot carry guessed dates")


@dataclass(frozen=True, slots=True)
class PairHistorySummary:
    pair_count: int
    shared_observation_min: int | None
    shared_observation_median: float | None
    shared_observation_max: int | None

    def __post_init__(self) -> None:
        if self.pair_count < 0:
            raise ValueError("pair_count cannot be negative")


@dataclass(frozen=True, slots=True)
class WalkForwardRange:
    split_id: str
    training: HistoryRange
    test: HistoryRange


@dataclass(frozen=True, slots=True)
class ResearchUniverseSnapshot:
    project_slug: str
    revision: str
    stage: ResearchStage
    availability: EvidenceAvailability
    listing_count: int | None
    unique_isin_count: int | None
    removed_count: int | None
    removal_reasons: Mapping[str, int] = field(default_factory=dict)
    observed_history_envelope: HistoryRange = field(default_factory=lambda: HistoryRange(None, None, None))
    common_usable_history: HistoryRange = field(default_factory=lambda: HistoryRange(None, None, None))
    pair_history: PairHistorySummary | None = None
    aligned_optimization_history: HistoryRange | None = None
    walk_forward_ranges: tuple[WalkForwardRange, ...] = ()
    final_refit_history: HistoryRange | None = None

    def __post_init__(self) -> None:
        if not self.project_slug or not self.revision:
            raise ValueError("project_slug and revision are required")
        if self.listing_count is not None and self.listing_count < 0:
            raise ValueError("listing_count cannot be negative")
        if self.unique_isin_count is not None and self.unique_isin_count < 0:
            raise ValueError("unique_isin_count cannot be negative")
        if self.listing_count is not None and self.unique_isin_count is not None and self.unique_isin_count > self.listing_count:
            raise ValueError("unique ISIN count cannot exceed listing count")
        if self.removed_count is not None and self.removed_count < 0:
            raise ValueError("removed_count cannot be negative")
        if any(count < 0 for count in self.removal_reasons.values()):
            raise ValueError("removal reason counts cannot be negative")

    @property
    def snapshot_id(self) -> str:
        return hashlib.sha256(canonical_json(self).encode()).hexdigest()
