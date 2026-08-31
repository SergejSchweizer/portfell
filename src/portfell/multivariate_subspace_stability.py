"""PCA leading-subspace stability primitives for adjacent rolling windows."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class SubspaceStabilityRow:
    previous_date_end: str
    current_date_end: str
    covariance_stability: float | None
    correlation_stability: float | None
    component_count: int
    availability_reasons: tuple[str, ...]


def subspace_overlap(
    previous_basis: tuple[tuple[float, ...], ...],
    current_basis: tuple[tuple[float, ...], ...],
    *,
    component_count: int,
) -> float | None:
    """Compute ||U_prev^T U_curr||_F^2/k from row-wise orthonormal component vectors."""

    if component_count <= 0:
        return None
    if len(previous_basis) < component_count or len(current_basis) < component_count:
        return None
    dimension = len(previous_basis[0]) if previous_basis else 0
    if dimension == 0:
        return None
    selected_previous = previous_basis[:component_count]
    selected_current = current_basis[:component_count]
    if any(len(vector) != dimension for vector in (*selected_previous, *selected_current)):
        return None
    squared_frobenius = 0.0
    for previous in selected_previous:
        for current in selected_current:
            dot = sum(left * right for left, right in zip(previous, current, strict=True))
            squared_frobenius += dot * dot
    value = squared_frobenius / component_count
    if not isfinite(value) or value < -1e-12 or value > 1.0 + 1e-12:
        return None
    if value <= 1e-12:
        return 0.0
    if value >= 1.0 - 1e-12:
        return 1.0
    return value


def build_adjacent_subspace_stability(
    *,
    date_ends: tuple[str, ...],
    covariance_bases: tuple[tuple[tuple[float, ...], ...], ...],
    correlation_bases: tuple[tuple[tuple[float, ...], ...], ...],
    listing_count: int,
) -> tuple[SubspaceStabilityRow, ...]:
    if len(date_ends) < 2:
        return (
            SubspaceStabilityRow(
                "",
                "",
                None,
                None,
                min(3, listing_count),
                ("subspace_stability_insufficient_windows",),
            ),
        )
    if len(covariance_bases) != len(date_ends) or len(correlation_bases) != len(date_ends):
        return (
            SubspaceStabilityRow(
                "",
                "",
                None,
                None,
                min(3, listing_count),
                ("subspace_stability_invalid_basis_series",),
            ),
        )
    component_count = min(3, listing_count)
    rows: list[SubspaceStabilityRow] = []
    for index in range(1, len(date_ends)):
        covariance = subspace_overlap(
            covariance_bases[index - 1], covariance_bases[index], component_count=component_count
        )
        correlation = subspace_overlap(
            correlation_bases[index - 1], correlation_bases[index], component_count=component_count
        )
        reasons = (
            ()
            if covariance is not None and correlation is not None
            else ("subspace_stability_unavailable",)
        )
        rows.append(
            SubspaceStabilityRow(
                date_ends[index - 1],
                date_ends[index],
                covariance,
                correlation,
                component_count,
                reasons,
            )
        )
    return tuple(rows)


__all__ = ["SubspaceStabilityRow", "build_adjacent_subspace_stability", "subspace_overlap"]
