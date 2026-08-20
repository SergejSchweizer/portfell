"""Hard eligibility stage for the Multivariate optimizer universe."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from portfell.multivariate.contracts.common import (
    DecisionStageId,
    EvidenceAvailability,
    ListingIdentity,
)
from portfell.multivariate.contracts.decision_reasons import DecisionReasonCode
from portfell.multivariate.contracts.decisions import (
    DecisionArtifact,
    DecisionCandidate,
    DecisionRejection,
)
from portfell.multivariate.contracts.history import (
    HistoryRange,
    ResearchStage,
    ResearchUniverseSnapshot,
)


@dataclass(frozen=True, slots=True)
class SelectorMetrics:
    listing: ListingIdentity
    annualized_geometric_return: float | None
    sharpe: float | None
    sortino: float | None
    annualized_volatility: float | None
    expected_shortfall: float | None
    maximum_drawdown: float | None
    observation_count: int | None
    distribution_frequency: str | None


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    eligible: tuple[SelectorMetrics, ...]
    rejected: tuple[tuple[ListingIdentity, DecisionReasonCode], ...]


@dataclass(frozen=True, slots=True)
class SelectionStageEvidence:
    decision: DecisionArtifact
    before_snapshot: ResearchUniverseSnapshot
    after_snapshot: ResearchUniverseSnapshot


_REQUIRED_METRICS = (
    "annualized_geometric_return",
    "sharpe",
    "sortino",
    "annualized_volatility",
    "expected_shortfall",
    "maximum_drawdown",
)


def apply_eligibility(
    rows: tuple[SelectorMetrics, ...],
    *,
    allowed_distribution_frequencies: tuple[str, ...] = (),
    minimum_observations: int = 2,
) -> EligibilityResult:
    """Remove only listings that fail frozen hard rules and record one reason each."""

    allowed = set(allowed_distribution_frequencies)
    eligible: list[SelectorMetrics] = []
    rejected: list[tuple[ListingIdentity, DecisionReasonCode]] = []
    for row in sorted(rows, key=lambda item: item.listing):
        if any(getattr(row, metric) is None for metric in _REQUIRED_METRICS):
            rejected.append((row.listing, DecisionReasonCode.DATA_UNAVAILABLE))
            continue
        if row.observation_count is None or row.observation_count < minimum_observations:
            rejected.append((row.listing, DecisionReasonCode.INSUFFICIENT_HISTORY))
            continue
        if allowed and row.distribution_frequency not in allowed:
            rejected.append((row.listing, DecisionReasonCode.DISTRIBUTION_NOT_ALLOWED))
            continue
        eligible.append(row)
    return EligibilityResult(tuple(eligible), tuple(rejected))


def _snapshot(
    *,
    project_slug: str,
    revision: str,
    listings: tuple[ListingIdentity, ...],
    removed_count: int,
    removal_reasons: dict[str, int],
    observed_history: HistoryRange,
    common_history: HistoryRange,
) -> ResearchUniverseSnapshot:
    return ResearchUniverseSnapshot(
        project_slug=project_slug,
        revision=revision,
        stage=ResearchStage.MULTIVARIATE,
        availability=EvidenceAvailability.AVAILABLE,
        listing_count=len(listings),
        unique_isin_count=len({listing.isin for listing in listings}),
        removed_count=removed_count,
        removal_reasons=removal_reasons,
        observed_history_envelope=observed_history,
        common_usable_history=common_history,
    )


def eligibility_evidence(
    *,
    run_id: str,
    objective: str,
    project_slug: str,
    pinned_revision: str,
    rows: tuple[SelectorMetrics, ...],
    result: EligibilityResult,
    algorithm_version: str,
    profile_version: str,
    observed_history: HistoryRange = HistoryRange(None, None, None),
    common_history: HistoryRange = HistoryRange(None, None, None),
) -> SelectionStageEvidence:
    """Build immutable before/after snapshots and the eligibility DecisionArtifact."""

    before = tuple(sorted(row.listing for row in rows))
    after = tuple(sorted(row.listing for row in result.eligible))
    reason_counts = Counter(reason.value for _, reason in result.rejected)
    before_snapshot = _snapshot(
        project_slug=project_slug,
        revision=pinned_revision,
        listings=before,
        removed_count=0,
        removal_reasons={},
        observed_history=observed_history,
        common_history=common_history,
    )
    after_snapshot = _snapshot(
        project_slug=project_slug,
        revision=pinned_revision,
        listings=after,
        removed_count=len(result.rejected),
        removal_reasons=dict(sorted(reason_counts.items())),
        observed_history=observed_history,
        common_history=common_history,
    )
    decision = DecisionArtifact(
        run_id=run_id,
        objective=objective,
        stage=DecisionStageId.INPUT_ELIGIBILITY,
        pinned_revisions=(pinned_revision,),
        candidates=tuple(DecisionCandidate(listing.token) for listing in before),
        selected_ids=tuple(listing.token for listing in after),
        rejections=tuple(
            DecisionRejection(listing.token, reason) for listing, reason in result.rejected
        ),
        status=EvidenceAvailability.AVAILABLE,
        reason_code=DecisionReasonCode.ELIGIBLE,
        algorithm_version=algorithm_version,
        profile_version=profile_version,
        listing_scope=before,
    )
    return SelectionStageEvidence(decision, before_snapshot, after_snapshot)
