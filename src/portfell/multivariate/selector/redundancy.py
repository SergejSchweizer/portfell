"""Deterministic Bivariate redundancy reduction for large optimizer universes."""

from __future__ import annotations

from dataclasses import dataclass

from portfell.multivariate.contracts.common import EvidenceAvailability, ListingIdentity
from portfell.multivariate.contracts.decision_reasons import DecisionReasonCode


@dataclass(frozen=True, slots=True)
class RedundancyCandidate:
    listing: ListingIdentity
    pareto_rank: int
    sortino: float
    annualized_geometric_return: float
    expected_shortfall: float
    annualized_volatility: float


@dataclass(frozen=True, slots=True)
class RedundancyRejection:
    listing: ListingIdentity
    representative: ListingIdentity
    pearson: float | None
    tail_dependence: float | None = None
    drawdown_overlap: float | None = None
    before_common_observations: int | None = None
    after_common_observations: int | None = None


@dataclass(frozen=True, slots=True)
class RedundancyResult:
    selected: tuple[ListingIdentity, ...]
    rejected: tuple[RedundancyRejection, ...]
    applied: bool
    availability: EvidenceAvailability = EvidenceAvailability.AVAILABLE
    reason_code: DecisionReasonCode = DecisionReasonCode.REDUNDANCY_REPRESENTED
    before_common_observations: int | None = None
    after_common_observations: int | None = None


def _pair_key(left: ListingIdentity, right: ListingIdentity) -> tuple[ListingIdentity, ListingIdentity]:
    return (left, right) if left <= right else (right, left)


def _correlation(
    left: ListingIdentity,
    right: ListingIdentity,
    correlations: dict[tuple[ListingIdentity, ListingIdentity], float],
) -> float:
    if left == right:
        return 1.0
    value = correlations.get(_pair_key(left, right))
    if value is None:
        raise ValueError(f"missing Pearson correlation for {left.token} / {right.token}")
    if not -1.0 <= value <= 1.0:
        raise ValueError("Pearson correlation must be in [-1, 1]")
    return value


def _optional_pair_value(
    left: ListingIdentity,
    right: ListingIdentity,
    values: dict[tuple[ListingIdentity, ListingIdentity], float] | None,
) -> float | None:
    if values is None:
        return None
    return values.get(_pair_key(left, right))


def _average_distance(
    left: tuple[ListingIdentity, ...],
    right: tuple[ListingIdentity, ...],
    correlations: dict[tuple[ListingIdentity, ListingIdentity], float],
) -> float:
    distances = [1.0 - _correlation(a, b, correlations) for a in left for b in right]
    return sum(distances) / len(distances)


def _representative(candidates: tuple[RedundancyCandidate, ...]) -> RedundancyCandidate:
    return min(
        candidates,
        key=lambda candidate: (
            candidate.pareto_rank,
            -candidate.sortino,
            -candidate.annualized_geometric_return,
            candidate.expected_shortfall,
            candidate.annualized_volatility,
            candidate.listing,
        ),
    )


def reduce_redundancy(
    candidates: tuple[RedundancyCandidate, ...],
    *,
    correlations: dict[tuple[ListingIdentity, ListingIdentity], float],
    maximum_size: int = 250,
    tail_dependence: dict[tuple[ListingIdentity, ListingIdentity], float] | None = None,
    drawdown_overlap: dict[tuple[ListingIdentity, ListingIdentity], float] | None = None,
    before_common_observations: int | None = None,
    after_common_observations: int | None = None,
) -> RedundancyResult:
    """Average-linkage cluster to exactly maximum_size and pick deterministic representatives."""

    if maximum_size < 1:
        raise ValueError("maximum_size must be positive")
    ordered = tuple(sorted(candidates, key=lambda candidate: candidate.listing))
    if len({candidate.listing for candidate in ordered}) != len(ordered):
        raise ValueError("candidates must have unique full listing identities")
    if len(ordered) <= maximum_size:
        return RedundancyResult(
            tuple(candidate.listing for candidate in ordered),
            (),
            False,
            EvidenceAvailability.NOT_APPLICABLE,
            DecisionReasonCode.REDUNDANCY_NOT_REQUIRED,
            before_common_observations,
            after_common_observations,
        )

    by_listing = {candidate.listing: candidate for candidate in ordered}
    clusters: list[tuple[ListingIdentity, ...]] = [(candidate.listing,) for candidate in ordered]
    while len(clusters) > maximum_size:
        best: tuple[float, tuple[ListingIdentity, ...], tuple[ListingIdentity, ...], int, int] | None = None
        for left_index in range(len(clusters) - 1):
            for right_index in range(left_index + 1, len(clusters)):
                left = clusters[left_index]
                right = clusters[right_index]
                candidate = (
                    _average_distance(left, right, correlations),
                    left,
                    right,
                    left_index,
                    right_index,
                )
                if best is None or candidate[:3] < best[:3]:
                    best = candidate
        if best is None:
            raise RuntimeError("unable to choose a cluster merge")
        _, left, right, left_index, right_index = best
        merged = tuple(sorted((*left, *right)))
        clusters = [
            cluster
            for index, cluster in enumerate(clusters)
            if index not in {left_index, right_index}
        ]
        clusters.append(merged)
        clusters.sort()

    representatives: list[ListingIdentity] = []
    rejections: list[RedundancyRejection] = []
    for cluster in sorted(clusters):
        cluster_candidates = tuple(by_listing[listing] for listing in cluster)
        representative = _representative(cluster_candidates)
        representatives.append(representative.listing)
        for listing in cluster:
            if listing != representative.listing:
                rejections.append(
                    RedundancyRejection(
                        listing=listing,
                        representative=representative.listing,
                        pearson=_correlation(listing, representative.listing, correlations),
                        tail_dependence=_optional_pair_value(
                            listing, representative.listing, tail_dependence
                        ),
                        drawdown_overlap=_optional_pair_value(
                            listing, representative.listing, drawdown_overlap
                        ),
                        before_common_observations=before_common_observations,
                        after_common_observations=after_common_observations,
                    )
                )
    return RedundancyResult(
        tuple(sorted(representatives)),
        tuple(sorted(rejections, key=lambda rejection: rejection.listing)),
        True,
        EvidenceAvailability.AVAILABLE,
        DecisionReasonCode.REDUNDANCY_REPRESENTED,
        before_common_observations,
        after_common_observations,
    )
