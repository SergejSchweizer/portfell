"""Deterministic, empirical portfolio-structure statistics."""

from __future__ import annotations

from dataclasses import dataclass
from math import log, sqrt

from portfell.contract_versioning import ContractVersion, stable_contract_id
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_model import MultivariateRiskModelArtifact
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
    """Calculate neutral PCA and threshold clusters from a canonical artifact."""
    if not risk_model.available or not risk_model.covariance:
        return _unavailable(risk_model, "risk_model_unavailable")
    eigenvalues, vectors = _jacobi_eigensystem(risk_model.covariance)
    ordering = sorted(range(len(eigenvalues)), key=lambda index: (-eigenvalues[index], index))
    sorted_values = tuple(max(0.0, eigenvalues[index]) for index in ordering)
    total = sum(sorted_values)
    if total <= 0:
        return _unavailable(risk_model, "non_positive_total_variance")
    explained = tuple(value / total for value in sorted_values)
    cumulative = tuple(sum(explained[: index + 1]) for index in range(len(explained)))
    entropy = -sum(value * log(value) for value in explained if value > 0)
    effective_rank = pow(2.718281828459045, entropy)
    loadings = tuple(
        ComponentLoading(
            component_id=f"Component {component_index + 1}",
            listing=listing,
            loading=_normalise_sign(vectors[original_index], listing_index),
        )
        for component_index, original_index in enumerate(ordering)
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
        eigenvalues=sorted_values,
        explained_variance=explained,
        cumulative_explained_variance=cumulative,
        effective_rank=effective_rank,
        effective_independent_drivers=effective_rank,
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


def _normalise_sign(vector: list[float], listing_index: int) -> float:
    pivot = next((value for value in vector if abs(value) > 1e-12), 1.0)
    return vector[listing_index] if pivot > 0 else -vector[listing_index]


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


def _jacobi_eigensystem(
    matrix: tuple[tuple[float, ...], ...],
) -> tuple[list[float], list[list[float]]]:
    size = len(matrix)
    values = [list(row) for row in matrix]
    vectors = [[1.0 if row == column else 0.0 for column in range(size)] for row in range(size)]
    for _ in range(max(1, size * size * 50)):
        left, right, largest = 0, 0, 0.0
        for row in range(size):
            for column in range(row + 1, size):
                if abs(values[row][column]) > largest:
                    left, right, largest = row, column, abs(values[row][column])
        if largest < 1e-12:
            break
        difference = values[right][right] - values[left][left]
        tangent = 0.5 * difference / values[left][right]
        sign = 1.0 if tangent >= 0 else -1.0
        rotation = sign / (abs(tangent) + sqrt(1 + tangent * tangent))
        cosine = 1 / sqrt(1 + rotation * rotation)
        sine = rotation * cosine
        for index in range(size):
            if index not in (left, right):
                first, second = values[index][left], values[index][right]
                values[index][left] = values[left][index] = cosine * first - sine * second
                values[index][right] = values[right][index] = sine * first + cosine * second
        first, second, cross = values[left][left], values[right][right], values[left][right]
        values[left][left] = (
            cosine * cosine * first - 2 * sine * cosine * cross + sine * sine * second
        )
        values[right][right] = (
            sine * sine * first + 2 * sine * cosine * cross + cosine * cosine * second
        )
        values[left][right] = values[right][left] = 0.0
        for index in range(size):
            first, second = vectors[index][left], vectors[index][right]
            vectors[index][left] = cosine * first - sine * second
            vectors[index][right] = sine * first + cosine * second
    return [values[index][index] for index in range(size)], vectors
