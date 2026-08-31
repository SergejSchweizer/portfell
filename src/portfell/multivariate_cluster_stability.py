"""Deterministic moving-block bootstrap stability for v2 risk clusters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_clusters import (
    RiskClusterDiagnostics,
    build_hierarchical_risk_clusters,
)
from portfell.multivariate_structure_v2 import correlation_from_covariance
from portfell.risk_model import estimate_risk_model

BOOTSTRAP_REPLICATES = 100
BOOTSTRAP_BLOCK_LENGTH = 21
BOOTSTRAP_SEED = 41


@dataclass(frozen=True)
class PairClusterStability:
    left: MultivariateListingKey
    right: MultivariateListingKey
    co_cluster_probability: float


@dataclass(frozen=True)
class CanonicalClusterStability:
    cluster_id: str
    mean_co_cluster_probability: float | None
    minimum_co_cluster_probability: float | None
    availability_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ClusterBootstrapStability:
    pairs: tuple[PairClusterStability, ...]
    clusters: tuple[CanonicalClusterStability, ...]
    replicate_count: int
    block_length: int
    seed: int
    availability_reasons: tuple[str, ...]

    @property
    def available(self) -> bool:
        return not self.availability_reasons


def build_cluster_bootstrap_stability(
    *,
    return_rows: Sequence[Mapping[str, Any]],
    listings: tuple[MultivariateListingKey, ...],
    canonical_clusters: RiskClusterDiagnostics,
) -> ClusterBootstrapStability:
    try:
        import numpy as np  # type: ignore[import-not-found]
    except ImportError:
        return _unavailable("cluster_bootstrap_numpy_unavailable")
    if not canonical_clusters.available:
        return _unavailable("clusters_unavailable")
    dates, values = _aligned_values(return_rows, listings)
    if len(dates) < 2 or not listings:
        return _unavailable("cluster_bootstrap_insufficient_history")
    pair_keys = tuple(
        (listings[left], listings[right])
        for left in range(len(listings))
        for right in range(left + 1, len(listings))
    )
    counts = {pair: 0 for pair in pair_keys}
    generator = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled_indexes: list[int] = []
        while len(sampled_indexes) < len(dates):
            start = int(generator.integers(0, len(dates)))
            sampled_indexes.extend(
                (start + offset) % len(dates) for offset in range(BOOTSTRAP_BLOCK_LENGTH)
            )
        sampled_indexes = sampled_indexes[: len(dates)]
        rows = tuple(
            {
                "isin": listing.isin,
                "exchange": listing.exchange,
                "code": listing.code,
                "date": f"bootstrap-{position:06d}",
                "return": values[source_index][listing_index],
            }
            for position, source_index in enumerate(sampled_indexes)
            for listing_index, listing in enumerate(listings)
        )
        try:
            covariance = estimate_risk_model(
                rows,
                listings=tuple(key.as_tuple() for key in listings),
                estimator="ledoit_wolf",
                window_policy="full",
            ).covariance
        except KeyError, TypeError, ValueError:
            return _unavailable("cluster_bootstrap_risk_model_unavailable")
        correlation, reason = correlation_from_covariance(covariance)
        if reason is not None:
            return _unavailable("cluster_bootstrap_correlation_unavailable")
        clusters = build_hierarchical_risk_clusters(listings=listings, correlation=correlation)
        if not clusters.available:
            return _unavailable("cluster_bootstrap_cluster_unavailable")
        membership = {row.listing: row.cluster_id for row in clusters.memberships}
        for pair in pair_keys:
            if membership[pair[0]] == membership[pair[1]]:
                counts[pair] += 1
    pairs = tuple(
        PairClusterStability(left, right, counts[(left, right)] / BOOTSTRAP_REPLICATES)
        for left, right in pair_keys
    )
    pair_probability = {(row.left, row.right): row.co_cluster_probability for row in pairs}
    canonical_membership = {row.listing: row.cluster_id for row in canonical_clusters.memberships}
    cluster_rows: list[CanonicalClusterStability] = []
    for cluster_id in sorted(set(canonical_membership.values()), key=_cluster_sort_key):
        members = tuple(
            sorted(
                listing for listing, label in canonical_membership.items() if label == cluster_id
            )
        )
        if len(members) < 2:
            cluster_rows.append(
                CanonicalClusterStability(
                    cluster_id,
                    None,
                    None,
                    ("cluster_stability_not_applicable_singleton",),
                )
            )
            continue
        probabilities = tuple(
            pair_probability[_ordered_pair(members[left], members[right])]
            for left in range(len(members))
            for right in range(left + 1, len(members))
        )
        cluster_rows.append(
            CanonicalClusterStability(
                cluster_id,
                sum(probabilities) / len(probabilities),
                min(probabilities),
                (),
            )
        )
    return ClusterBootstrapStability(
        pairs, tuple(cluster_rows), BOOTSTRAP_REPLICATES, BOOTSTRAP_BLOCK_LENGTH, BOOTSTRAP_SEED, ()
    )


def _aligned_values(
    return_rows: Sequence[Mapping[str, Any]], listings: tuple[MultivariateListingKey, ...]
) -> tuple[tuple[str, ...], tuple[tuple[float, ...], ...]]:
    by_listing: dict[MultivariateListingKey, dict[str, float]] = {key: {} for key in listings}
    for row in return_rows:
        key = MultivariateListingKey(
            str(row.get("isin", "")),
            str(row.get("exchange", "")),
            str(row.get("code", "")),
        )
        if key in by_listing:
            by_listing[key][str(row.get("date", ""))] = float(row["return"])
    if not listings or any(not by_listing[key] for key in listings):
        return (), ()
    common = set(by_listing[listings[0]])
    for listing in listings[1:]:
        common &= by_listing[listing].keys()
    dates = tuple(sorted(common))
    values = tuple(tuple(by_listing[listing][date] for listing in listings) for date in dates)
    return dates, values


def _ordered_pair(
    left: MultivariateListingKey, right: MultivariateListingKey
) -> tuple[MultivariateListingKey, MultivariateListingKey]:
    return (left, right) if left < right else (right, left)


def _cluster_sort_key(cluster_id: str) -> tuple[int, str]:
    try:
        return int(cluster_id.rsplit(" ", 1)[1]), cluster_id
    except IndexError, ValueError:
        return 2**31 - 1, cluster_id


def _unavailable(reason: str) -> ClusterBootstrapStability:
    return ClusterBootstrapStability(
        (),
        (),
        BOOTSTRAP_REPLICATES,
        BOOTSTRAP_BLOCK_LENGTH,
        BOOTSTRAP_SEED,
        (reason,),
    )


__all__ = [
    "BOOTSTRAP_BLOCK_LENGTH",
    "BOOTSTRAP_REPLICATES",
    "BOOTSTRAP_SEED",
    "CanonicalClusterStability",
    "ClusterBootstrapStability",
    "PairClusterStability",
    "build_cluster_bootstrap_stability",
]
