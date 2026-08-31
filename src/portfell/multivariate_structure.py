"""Deterministic, empirical portfolio-structure statistics."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from portfell.contract_versioning import ContractVersion, stable_contract_id
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_model import MultivariateRiskModelArtifact
from portfell.multivariate_spectral import analyze_symmetric_matrix
from portfell.table_io import JsonRow

STRUCTURE_CONTRACT = ContractVersion("multivariate.structure", 1)
COMPONENT_EXPLAINED_VARIANCE_THRESHOLDS = (0.8, 0.9, 0.95)
CLUSTER_CORRELATION_THRESHOLD = 0.7


@dataclass(frozen=True)
class ComponentLoading:
    component_id: str
    listing: MultivariateListingKey
    loading: float


@dataclass(frozen=True)
class MultivariateStructureArtifact:
    structure_id: str
    risk_model_id: str
    date_start: str
    date_end: str
    observation_count: int
    eigenvalues: tuple[float, ...]
    explained_variance: tuple[float, ...]
    cumulative_explained_variance: tuple[float, ...]
    effective_rank: float
    effective_independent_drivers: float
    cluster_by_listing: tuple[tuple[MultivariateListingKey, str], ...]
    loadings: tuple[ComponentLoading, ...]
    strongest_common_driver: MultivariateListingKey | None
    largest_redundancy_warning: JsonRow | None
    availability_reasons: tuple[str, ...]

    @property
    def available(self) -> bool:
        return not self.availability_reasons

    def summary(self) -> JsonRow:
        clusters = {cluster for _, cluster in self.cluster_by_listing}
        dominant = self.explained_variance[0] if self.explained_variance else None
        thresholds = {
            f"components_for_{int(threshold * 100)}pct": next(
                (
                    index + 1
                    for index, value in enumerate(self.cumulative_explained_variance)
                    if value >= threshold
                ),
                None,
            )
            for threshold in COMPONENT_EXPLAINED_VARIANCE_THRESHOLDS
        }
        return {
            "structure_id": self.structure_id,
            "risk_model_id": self.risk_model_id,
            "candidate_etf_count": len(self.cluster_by_listing),
            "risk_cluster_count": len(clusters),
            "dominant_component_share": dominant,
            "effective_rank": self.effective_rank,
            "effective_independent_drivers": self.effective_independent_drivers,
            "period": {
                "date_start": self.date_start,
                "date_end": self.date_end,
                "observation_count": self.observation_count,
            },
            "thresholds": thresholds,
            "strongest_common_driver": _listing_row(self.strongest_common_driver),
            "largest_redundancy_warning": self.largest_redundancy_warning,
            "availability_reasons": list(self.availability_reasons),
        }

    def component_page(self, *, component_id: str, limit: int = 25, offset: int = 0) -> JsonRow:
        safe_limit, safe_offset = max(1, min(limit, 100)), max(0, offset)
        rows = [item for item in self.loadings if item.component_id == component_id]
        rows.sort(key=lambda item: (-abs(item.loading), item.listing))
        page = rows[safe_offset : safe_offset + safe_limit]
        return {
            "component_id": component_id,
            "total": len(rows),
            "limit": safe_limit,
            "offset": safe_offset,
            "rows": [
                {
                    "isin": item.listing.isin,
                    "exchange": item.listing.exchange,
                    "code": item.listing.code,
                    "loading": item.loading,
                }
                for item in page
            ],
        }


def build_multivariate_structure(
    risk_model: MultivariateRiskModelArtifact,
) -> MultivariateStructureArtifact:
    """Calculate v1 neutral PCA and threshold clusters from a canonical artifact."""

    if not risk_model.available or not risk_model.covariance:
        return _unavailable(risk_model, "risk_model_unavailable")
    spectral = analyze_symmetric_matrix(
        risk_model.covariance,
        thresholds=COMPONENT_EXPLAINED_VARIANCE_THRESHOLDS,
    )
    if not spectral.available or spectral.effective_rank is None:
        return _unavailable(risk_model, spectral.availability_reasons[0])
    loadings = tuple(
        ComponentLoading(
            component_id=f"Component {component_index + 1}",
            listing=listing,
            loading=component[listing_index],
        )
        for component_index, component in enumerate(spectral.component_coefficients)
        for listing_index, listing in enumerate(risk_model.listings)
    )
    clusters = _clusters(risk_model.listings, risk_model.covariance)
    first_component = [item for item in loadings if item.component_id == "Component 1"]
    strongest = max(first_component, key=lambda item: (abs(item.loading), item.listing)).listing
    identity = stable_contract_id(
        "multivariate_structure",
        {
            "contract": STRUCTURE_CONTRACT.qualified_name,
            "risk_model_id": risk_model.risk_model_id,
            "threshold": CLUSTER_CORRELATION_THRESHOLD,
        },
    )
    return MultivariateStructureArtifact(
        structure_id=identity,
        risk_model_id=risk_model.risk_model_id,
        date_start=risk_model.date_start,
        date_end=risk_model.date_end,
        observation_count=risk_model.observation_count,
        eigenvalues=spectral.eigenvalues,
        explained_variance=spectral.explained_variance,
        cumulative_explained_variance=spectral.cumulative_explained_variance,
        effective_rank=spectral.effective_rank,
        effective_independent_drivers=spectral.effective_rank,
        cluster_by_listing=clusters,
        loadings=loadings,
        strongest_common_driver=strongest,
        largest_redundancy_warning=_largest_redundancy(risk_model),
        availability_reasons=(),
    )


def _unavailable(
    risk_model: MultivariateRiskModelArtifact, reason: str
) -> MultivariateStructureArtifact:
    return MultivariateStructureArtifact(
        structure_id=stable_contract_id(
            "multivariate_structure", {"risk_model_id": risk_model.risk_model_id, "reason": reason}
        ),
        risk_model_id=risk_model.risk_model_id,
        date_start=risk_model.date_start,
        date_end=risk_model.date_end,
        observation_count=risk_model.observation_count,
        eigenvalues=(),
        explained_variance=(),
        cumulative_explained_variance=(),
        effective_rank=0.0,
        effective_independent_drivers=0.0,
        cluster_by_listing=(),
        loadings=(),
        strongest_common_driver=None,
        largest_redundancy_warning=None,
        availability_reasons=(reason,),
    )


def _clusters(
    listings: tuple[MultivariateListingKey, ...], covariance: tuple[tuple[float, ...], ...]
) -> tuple[tuple[MultivariateListingKey, str], ...]:
    parent = list(range(len(listings)))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left in range(len(listings)):
        for right in range(left + 1, len(listings)):
            denominator = sqrt(max(covariance[left][left], 0) * max(covariance[right][right], 0))
            correlation = covariance[left][right] / denominator if denominator else 0.0
            if correlation >= CLUSTER_CORRELATION_THRESHOLD:
                parent[root(right)] = root(left)
    roots = {
        value: position + 1
        for position, value in enumerate(sorted({root(index) for index in range(len(listings))}))
    }
    return tuple(
        (listing, f"Cluster {roots[root(index)]}") for index, listing in enumerate(listings)
    )


def _largest_redundancy(risk_model: MultivariateRiskModelArtifact) -> JsonRow | None:
    pairs: list[tuple[float, MultivariateListingKey, MultivariateListingKey]] = []
    for left_index, left in enumerate(risk_model.listings):
        for right_index, right in enumerate(
            risk_model.listings[left_index + 1 :], start=left_index + 1
        ):
            denominator = sqrt(
                max(risk_model.covariance[left_index][left_index], 0)
                * max(risk_model.covariance[right_index][right_index], 0)
            )
            if denominator:
                pairs.append(
                    (risk_model.covariance[left_index][right_index] / denominator, left, right)
                )
    if not pairs:
        return None
    correlation, left, right = max(pairs, key=lambda item: (item[0], item[1], item[2]))
    return {
        "left": _listing_row(left),
        "right": _listing_row(right),
        "correlation": correlation,
    }


def _listing_row(listing: MultivariateListingKey | None) -> JsonRow | None:
    if listing is None:
        return None
    return {"isin": listing.isin, "exchange": listing.exchange, "code": listing.code}
