"""Rolling, time-safe Multivariate Structure v2 diagnostics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_clusters import build_hierarchical_risk_clusters
from portfell.multivariate_spectral import analyze_symmetric_matrix
from portfell.multivariate_structure_v2 import correlation_from_covariance
from portfell.risk_model import estimate_risk_model

ROLLING_OBSERVATIONS = 252
ROLLING_STRIDE = 21
ROLLING_MAX_WINDOWS = 24


@dataclass(frozen=True)
class RollingStructureRow:
    date_start: str
    date_end: str
    observation_count: int
    covariance_dominant_component_share: float | None
    correlation_dominant_component_share: float | None
    covariance_effective_rank: float | None
    correlation_effective_rank: float | None
    risk_cluster_count: int | None
    availability_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RollingStructureDiagnostics:
    rows: tuple[RollingStructureRow, ...]
    availability_reasons: tuple[str, ...]

    @property
    def available(self) -> bool:
        return not self.availability_reasons


def build_rolling_structure_diagnostics(
    *,
    return_rows: Sequence[Mapping[str, Any]],
    listings: tuple[MultivariateListingKey, ...],
) -> RollingStructureDiagnostics:
    dates = _common_dates(return_rows, listings)
    if len(dates) < ROLLING_OBSERVATIONS:
        return RollingStructureDiagnostics((), ("rolling_structure_insufficient_history",))
    endpoints: list[int] = []
    endpoint = len(dates) - 1
    while endpoint >= ROLLING_OBSERVATIONS - 1 and len(endpoints) < ROLLING_MAX_WINDOWS:
        endpoints.append(endpoint)
        endpoint -= ROLLING_STRIDE
    output: list[RollingStructureRow] = []
    for end_index in reversed(endpoints):
        window_dates = dates[end_index - ROLLING_OBSERVATIONS + 1 : end_index + 1]
        date_set = set(window_dates)
        window_rows = tuple(row for row in return_rows if str(row.get("date", "")) in date_set)
        try:
            risk = estimate_risk_model(
                window_rows,
                listings=tuple(key.as_tuple() for key in listings),
                estimator="ledoit_wolf",
                window_policy="full",
            )
        except KeyError, TypeError, ValueError:
            output.append(
                _unavailable_row(
                    window_dates,
                    "rolling_structure_risk_model_unavailable",
                )
            )
            continue
        covariance = analyze_symmetric_matrix(risk.covariance)
        correlation_matrix, correlation_reason = correlation_from_covariance(risk.covariance)
        correlation = (
            analyze_symmetric_matrix(correlation_matrix) if correlation_reason is None else None
        )
        clusters = (
            build_hierarchical_risk_clusters(listings=listings, correlation=correlation_matrix)
            if correlation_reason is None
            else None
        )
        reasons: list[str] = []
        if not covariance.available:
            reasons.extend(covariance.availability_reasons)
        if correlation is None or not correlation.available:
            reasons.append(correlation_reason or "rolling_structure_correlation_unavailable")
        if clusters is None or not clusters.available:
            reasons.append("clusters_unavailable")
        output.append(
            RollingStructureRow(
                date_start=window_dates[0],
                date_end=window_dates[-1],
                observation_count=len(window_dates),
                covariance_dominant_component_share=(
                    covariance.explained_variance[0] if covariance.available else None
                ),
                correlation_dominant_component_share=(
                    correlation.explained_variance[0]
                    if correlation is not None and correlation.available
                    else None
                ),
                covariance_effective_rank=covariance.effective_rank,
                correlation_effective_rank=(
                    correlation.effective_rank if correlation is not None else None
                ),
                risk_cluster_count=(clusters.cluster_count if clusters is not None else None),
                availability_reasons=tuple(sorted(set(reasons))),
            )
        )
    return RollingStructureDiagnostics(tuple(output), ())


def _common_dates(
    return_rows: Sequence[Mapping[str, Any]], listings: tuple[MultivariateListingKey, ...]
) -> tuple[str, ...]:
    dates_by_listing: dict[MultivariateListingKey, set[str]] = {
        listing: set() for listing in listings
    }
    for row in return_rows:
        key = MultivariateListingKey(
            str(row.get("isin", "")),
            str(row.get("exchange", "")),
            str(row.get("code", "")),
        )
        if key in dates_by_listing:
            dates_by_listing[key].add(str(row.get("date", "")))
    if not listings or any(not dates_by_listing[listing] for listing in listings):
        return ()
    common = set(dates_by_listing[listings[0]])
    for listing in listings[1:]:
        common &= dates_by_listing[listing]
    return tuple(sorted(common))


def _unavailable_row(dates: tuple[str, ...], reason: str) -> RollingStructureRow:
    return RollingStructureRow(
        dates[0],
        dates[-1],
        len(dates),
        None,
        None,
        None,
        None,
        None,
        (reason,),
    )


__all__ = [
    "ROLLING_MAX_WINDOWS",
    "ROLLING_OBSERVATIONS",
    "ROLLING_STRIDE",
    "RollingStructureDiagnostics",
    "RollingStructureRow",
    "build_rolling_structure_diagnostics",
]
