"""Deterministic average-linkage hierarchical risk clusters for Structure v2."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

from portfell.multivariate_inputs import MultivariateListingKey

CLUSTER_CORRELATION_CUT = 0.70
CLUSTER_DISTANCE_CUT = sqrt((1.0 - CLUSTER_CORRELATION_CUT) / 2.0)
CORRELATION_TOLERANCE = 1e-12


@dataclass(frozen=True)
class RiskClusterMembership:
    listing: MultivariateListingKey
    cluster_id: str


@dataclass(frozen=True)
class RedundancyWarning:
    left: MultivariateListingKey
    right: MultivariateListingKey
    correlation: float


@dataclass(frozen=True)
class RiskClusterDiagnostics:
    memberships: tuple[RiskClusterMembership, ...]
    cluster_count: int | None
    largest_redundancy_warning: RedundancyWarning | None
    availability_reasons: tuple[str, ...]

    @property
    def available(self) -> bool:
        return not self.availability_reasons


def build_hierarchical_risk_clusters(
    *,
    listings: tuple[MultivariateListingKey, ...],
    correlation: tuple[tuple[float, ...], ...],
) -> RiskClusterDiagnostics:
    reason = _validate_correlation(listings, correlation)
    if reason is not None:
        return RiskClusterDiagnostics((), None, None, (reason,))
    if not listings:
        return RiskClusterDiagnostics((), None, None, ("clusters_unavailable",))
    distances = tuple(
        tuple(
            sqrt(max(0.0, (1.0 - correlation[left][right]) / 2.0)) for right in range(len(listings))
        )
        for left in range(len(listings))
    )
    clusters: list[tuple[int, ...]] = [(index,) for index in range(len(listings))]
    while len(clusters) > 1:
        candidates: list[
            tuple[
                float,
                tuple[MultivariateListingKey, ...],
                tuple[MultivariateListingKey, ...],
                int,
                int,
            ]
        ] = []
        for left in range(len(clusters)):
            for right in range(left + 1, len(clusters)):
                first = _cluster_identities(clusters[left], listings)
                second = _cluster_identities(clusters[right], listings)
                if second < first:
                    first, second = second, first
                candidates.append(
                    (
                        _average_linkage_distance(clusters[left], clusters[right], distances),
                        first,
                        second,
                        left,
                        right,
                    )
                )
        distance, _, _, left, right = min(candidates, key=lambda item: (item[0], item[1], item[2]))
        if distance > CLUSTER_DISTANCE_CUT:
            break
        merged = tuple(
            sorted(
                (*clusters[left], *clusters[right]),
                key=lambda index: listings[index],
            )
        )
        clusters = [cluster for index, cluster in enumerate(clusters) if index not in (left, right)]
        clusters.append(merged)
        clusters.sort(key=lambda cluster: _cluster_identities(cluster, listings))
    canonical_clusters = sorted(
        clusters,
        key=lambda cluster: min(listings[index] for index in cluster),
    )
    label_by_index: dict[int, str] = {}
    for position, cluster in enumerate(canonical_clusters, start=1):
        for index in cluster:
            label_by_index[index] = f"Cluster {position}"
    memberships = tuple(
        RiskClusterMembership(listing, label_by_index[index])
        for index, listing in enumerate(listings)
    )
    return RiskClusterDiagnostics(
        memberships=memberships,
        cluster_count=len(canonical_clusters),
        largest_redundancy_warning=_largest_redundancy(listings, correlation),
        availability_reasons=(),
    )


def _average_linkage_distance(
    left: tuple[int, ...], right: tuple[int, ...], distances: tuple[tuple[float, ...], ...]
) -> float:
    values = tuple(distances[i][j] for i in left for j in right)
    return sum(values) / len(values)


def _cluster_identities(
    cluster: tuple[int, ...], listings: tuple[MultivariateListingKey, ...]
) -> tuple[MultivariateListingKey, ...]:
    return tuple(sorted(listings[index] for index in cluster))


def _validate_correlation(
    listings: tuple[MultivariateListingKey, ...], correlation: tuple[tuple[float, ...], ...]
) -> str | None:
    size = len(listings)
    if len(correlation) != size or any(len(row) != size for row in correlation):
        return "clusters_unavailable"
    for left in range(size):
        for right in range(size):
            value = correlation[left][right]
            if not isfinite(value):
                return "clusters_unavailable"
            if value < -1.0 - CORRELATION_TOLERANCE or value > 1.0 + CORRELATION_TOLERANCE:
                return "clusters_unavailable"
            if abs(value - correlation[right][left]) > CORRELATION_TOLERANCE:
                return "clusters_unavailable"
        if abs(correlation[left][left] - 1.0) > CORRELATION_TOLERANCE:
            return "clusters_unavailable"
    return None


def _largest_redundancy(
    listings: tuple[MultivariateListingKey, ...], correlation: tuple[tuple[float, ...], ...]
) -> RedundancyWarning | None:
    pairs = tuple(
        (correlation[left][right], listings[left], listings[right])
        for left in range(len(listings))
        for right in range(left + 1, len(listings))
    )
    if not pairs:
        return None
    value, left, right = sorted(pairs, key=lambda item: (-item[0], item[1], item[2]))[0]
    return RedundancyWarning(left, right, value)


__all__ = [
    "CLUSTER_CORRELATION_CUT",
    "CLUSTER_DISTANCE_CUT",
    "RedundancyWarning",
    "RiskClusterDiagnostics",
    "RiskClusterMembership",
    "build_hierarchical_risk_clusters",
]
