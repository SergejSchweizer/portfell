"""Covariance and correlation PCA diagnostics for Multivariate Structure v2."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_model import MultivariateRiskModelArtifact
from portfell.multivariate_spectral import SpectralResult, analyze_symmetric_matrix

CORRELATION_BOUND_TOLERANCE = 1e-12


@dataclass(frozen=True)
class PcaCoefficient:
    component_id: str
    listing: MultivariateListingKey
    coefficient: float


@dataclass(frozen=True)
class PcaDiagnostics:
    eigenvalues: tuple[float, ...]
    explained_variance: tuple[float, ...]
    cumulative_explained_variance: tuple[float, ...]
    effective_rank: float | None
    components_for_80pct: int | None
    components_for_90pct: int | None
    components_for_95pct: int | None
    coefficients: tuple[PcaCoefficient, ...]
    dominant_component_representative: MultivariateListingKey | None
    dominant_component_share: float | None
    availability_reasons: tuple[str, ...]

    @property
    def available(self) -> bool:
        return not self.availability_reasons


@dataclass(frozen=True)
class StructurePcaDiagnostics:
    risk_model_id: str
    listings: tuple[MultivariateListingKey, ...]
    covariance: PcaDiagnostics
    correlation: PcaDiagnostics
    correlation_matrix: tuple[tuple[float, ...], ...]


def build_structure_pca_diagnostics(
    risk_model: MultivariateRiskModelArtifact,
) -> StructurePcaDiagnostics:
    """Compute separate covariance and correlation PCA from one canonical risk model."""

    if not risk_model.available or not risk_model.covariance:
        unavailable = _unavailable_pca("risk_model_unavailable")
        return StructurePcaDiagnostics(
            risk_model.risk_model_id, risk_model.listings, unavailable, unavailable, ()
        )
    covariance_spectral = analyze_symmetric_matrix(risk_model.covariance)
    covariance = _pca_from_spectral(covariance_spectral, risk_model.listings)
    correlation_matrix, correlation_reason = correlation_from_covariance(risk_model.covariance)
    if correlation_reason is not None:
        correlation = _unavailable_pca(correlation_reason)
    else:
        correlation = _pca_from_spectral(
            analyze_symmetric_matrix(correlation_matrix), risk_model.listings
        )
    return StructurePcaDiagnostics(
        risk_model_id=risk_model.risk_model_id,
        listings=risk_model.listings,
        covariance=covariance,
        correlation=correlation,
        correlation_matrix=correlation_matrix if correlation_reason is None else (),
    )


def correlation_from_covariance(
    covariance: tuple[tuple[float, ...], ...],
) -> tuple[tuple[tuple[float, ...], ...], str | None]:
    size = len(covariance)
    if size == 0 or any(len(row) != size for row in covariance):
        return (), "correlation_invalid_covariance"
    variances = tuple(covariance[index][index] for index in range(size))
    if any(not isfinite(value) or value <= 0.0 for value in variances):
        return (), "correlation_non_positive_variance"
    rows: list[tuple[float, ...]] = []
    for left in range(size):
        row: list[float] = []
        for right in range(size):
            value = covariance[left][right] / sqrt(variances[left] * variances[right])
            if not isfinite(value):
                return (), "correlation_non_finite"
            if value > 1.0:
                if value - 1.0 > CORRELATION_BOUND_TOLERANCE:
                    return (), "correlation_out_of_bounds"
                value = 1.0
            elif value < -1.0:
                if -1.0 - value > CORRELATION_BOUND_TOLERANCE:
                    return (), "correlation_out_of_bounds"
                value = -1.0
            if left == right:
                if abs(value - 1.0) > CORRELATION_BOUND_TOLERANCE:
                    return (), "correlation_invalid_diagonal"
                value = 1.0
            row.append(value)
        rows.append(tuple(row))
    return tuple(rows), None


def _pca_from_spectral(
    spectral: SpectralResult,
    listings: tuple[MultivariateListingKey, ...],
) -> PcaDiagnostics:
    if not spectral.available or spectral.effective_rank is None:
        reason = (
            spectral.availability_reasons[0]
            if spectral.availability_reasons
            else "spectral_unavailable"
        )
        return _unavailable_pca(reason)
    coefficients = tuple(
        PcaCoefficient(f"Component {component_index + 1}", listing, component[listing_index])
        for component_index, component in enumerate(spectral.component_coefficients)
        for listing_index, listing in enumerate(listings)
    )
    first = tuple(item for item in coefficients if item.component_id == "Component 1")
    representative = (
        sorted(first, key=lambda item: (-abs(item.coefficient), item.listing))[0].listing
        if first
        else None
    )
    return PcaDiagnostics(
        eigenvalues=spectral.eigenvalues,
        explained_variance=spectral.explained_variance,
        cumulative_explained_variance=spectral.cumulative_explained_variance,
        effective_rank=spectral.effective_rank,
        components_for_80pct=spectral.components_for(0.80),
        components_for_90pct=spectral.components_for(0.90),
        components_for_95pct=spectral.components_for(0.95),
        coefficients=coefficients,
        dominant_component_representative=representative,
        dominant_component_share=(
            spectral.explained_variance[0] if spectral.explained_variance else None
        ),
        availability_reasons=(),
    )


def _unavailable_pca(reason: str) -> PcaDiagnostics:
    return PcaDiagnostics((), (), (), None, None, None, None, (), None, None, (reason,))


__all__ = [
    "PcaCoefficient",
    "PcaDiagnostics",
    "StructurePcaDiagnostics",
    "build_structure_pca_diagnostics",
    "correlation_from_covariance",
]
