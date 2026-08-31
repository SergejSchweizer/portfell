"""Deterministic spectral analysis for symmetric Multivariate matrices."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite, log, sqrt

NEGATIVE_EIGENVALUE_TOLERANCE = 1e-12
SIGN_TOLERANCE = 1e-12
DEFAULT_THRESHOLDS = (0.80, 0.90, 0.95)


@dataclass(frozen=True)
class SpectralResult:
    eigenvalues: tuple[float, ...]
    component_coefficients: tuple[tuple[float, ...], ...]
    explained_variance: tuple[float, ...]
    cumulative_explained_variance: tuple[float, ...]
    effective_rank: float | None
    threshold_component_counts: tuple[tuple[float, int], ...]
    availability_reasons: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        return not self.availability_reasons

    def components_for(self, threshold: float) -> int | None:
        return dict(self.threshold_component_counts).get(threshold)


def analyze_symmetric_matrix(
    matrix: tuple[tuple[float, ...], ...],
    *,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
) -> SpectralResult:
    """Return a canonical eigensystem and entropy diagnostics or typed unavailability."""

    reason = _matrix_reason(matrix)
    if reason is not None:
        return _unavailable(reason)
    raw_values, column_vectors = _jacobi_eigensystem(matrix)
    ordered = sorted(range(len(raw_values)), key=lambda index: (-raw_values[index], index))
    values: list[float] = []
    components: list[tuple[float, ...]] = []
    for original_index in ordered:
        value = raw_values[original_index]
        if value < -NEGATIVE_EIGENVALUE_TOLERANCE:
            return _unavailable("spectral_negative_eigenvalue")
        values.append(0.0 if value < 0.0 else value)
        component = tuple(column_vectors[row][original_index] for row in range(len(matrix)))
        components.append(_canonical_sign(component))
    total = sum(values)
    if not isfinite(total) or total <= 0.0:
        return _unavailable("spectral_non_positive_total")
    explained = tuple(value / total for value in values)
    cumulative_values: list[float] = []
    running = 0.0
    for value in explained:
        running += value
        cumulative_values.append(running)
    cumulative = tuple(cumulative_values)
    entropy = -sum(share * log(share) for share in explained if share > 0.0)
    counts = tuple(
        (
            threshold,
            next(
                index + 1
                for index, cumulative_share in enumerate(cumulative)
                if cumulative_share >= threshold
            ),
        )
        for threshold in thresholds
    )
    return SpectralResult(
        eigenvalues=tuple(values),
        component_coefficients=tuple(components),
        explained_variance=explained,
        cumulative_explained_variance=cumulative,
        effective_rank=exp(entropy),
        threshold_component_counts=counts,
    )


def _matrix_reason(matrix: tuple[tuple[float, ...], ...]) -> str | None:
    size = len(matrix)
    if size == 0:
        return "spectral_empty_matrix"
    if any(len(row) != size for row in matrix):
        return "spectral_non_square_matrix"
    for row in matrix:
        if any(not isfinite(value) for value in row):
            return "spectral_non_finite_matrix"
    for left in range(size):
        for right in range(left + 1, size):
            if abs(matrix[left][right] - matrix[right][left]) > 1e-12:
                return "spectral_non_symmetric_matrix"
    return None


def _unavailable(reason: str) -> SpectralResult:
    return SpectralResult((), (), (), (), None, (), (reason,))


def _canonical_sign(component: tuple[float, ...]) -> tuple[float, ...]:
    pivot = next((value for value in component if abs(value) > SIGN_TOLERANCE), None)
    if pivot is None or pivot > 0.0:
        return component
    return tuple(-value for value in component)


def _jacobi_eigensystem(
    matrix: tuple[tuple[float, ...], ...],
) -> tuple[list[float], list[list[float]]]:
    """Jacobi diagonalization; returned vector matrix stores eigenvectors in columns."""

    size = len(matrix)
    values = [list(row) for row in matrix]
    vectors = [[1.0 if row == column else 0.0 for column in range(size)] for row in range(size)]
    for _ in range(max(1, size * size * 50)):
        left, right, largest = 0, 0, 0.0
        for row in range(size):
            for column in range(row + 1, size):
                candidate = abs(values[row][column])
                if candidate > largest:
                    left, right, largest = row, column, candidate
        if largest < 1e-12:
            break
        difference = values[right][right] - values[left][left]
        tangent = 0.5 * difference / values[left][right]
        sign = 1.0 if tangent >= 0.0 else -1.0
        rotation = sign / (abs(tangent) + sqrt(1.0 + tangent * tangent))
        cosine = 1.0 / sqrt(1.0 + rotation * rotation)
        sine = rotation * cosine
        for index in range(size):
            if index not in (left, right):
                first, second = values[index][left], values[index][right]
                values[index][left] = values[left][index] = cosine * first - sine * second
                values[index][right] = values[right][index] = sine * first + cosine * second
        first, second, cross = values[left][left], values[right][right], values[left][right]
        values[left][left] = (
            cosine * cosine * first - 2.0 * sine * cosine * cross + sine * sine * second
        )
        values[right][right] = (
            sine * sine * first + 2.0 * sine * cosine * cross + cosine * cosine * second
        )
        values[left][right] = values[right][left] = 0.0
        for index in range(size):
            first, second = vectors[index][left], vectors[index][right]
            vectors[index][left] = cosine * first - sine * second
            vectors[index][right] = sine * first + cosine * second
    return [values[index][index] for index in range(size)], vectors


__all__ = [
    "DEFAULT_THRESHOLDS",
    "NEGATIVE_EIGENVALUE_TOLERANCE",
    "SpectralResult",
    "analyze_symmetric_matrix",
]
