"""Leakage-safe deterministic signal-component parallel analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Any, cast

from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_spectral import analyze_symmetric_matrix
from portfell.multivariate_structure_v2 import correlation_from_covariance
from portfell.risk_model import estimate_risk_model

PARALLEL_REPLICATES = 100
PARALLEL_SEED = 41
PARALLEL_QUANTILE = 0.95
PARALLEL_QUANTILE_METHOD = "higher"


@dataclass(frozen=True)
class SignalComponentDiagnostics:
    observed_eigenvalues: tuple[float, ...]
    null_thresholds: tuple[float, ...]
    signal_component_count: int | None
    replicate_count: int
    seed: int
    quantile: float
    quantile_method: str
    availability_reasons: tuple[str, ...]

    @property
    def available(self) -> bool:
        return not self.availability_reasons


def build_signal_component_diagnostics(
    *,
    return_rows: Sequence[Mapping[str, Any]],
    listings: tuple[MultivariateListingKey, ...],
) -> SignalComponentDiagnostics:
    """Run rank-wise parallel analysis using PCG64(41) and production Ledoit-Wolf."""

    try:
        numpy = cast(Any, import_module("numpy"))
    except ImportError:
        return _unavailable("signal_analysis_numpy_unavailable")
    try:
        dates, matrix = _aligned_matrix(return_rows, listings)
    except KeyError, TypeError, ValueError:
        return _unavailable("signal_analysis_invalid_input")
    if len(dates) < 2 or not listings:
        return _unavailable("signal_analysis_insufficient_history")
    observed_covariance = estimate_risk_model(
        return_rows,
        listings=tuple(key.as_tuple() for key in listings),
        estimator="ledoit_wolf",
        window_policy="full",
    ).covariance
    observed_correlation, reason = correlation_from_covariance(observed_covariance)
    if reason is not None:
        return _unavailable("signal_analysis_unavailable")
    observed = analyze_symmetric_matrix(observed_correlation)
    if not observed.available:
        return _unavailable("signal_analysis_unavailable")

    generator = numpy.random.Generator(numpy.random.PCG64(PARALLEL_SEED))
    null_by_rank: list[list[float]] = [[] for _ in listings]
    for replicate in range(PARALLEL_REPLICATES):
        permuted_columns: list[Any] = []
        for column_index in range(len(listings)):
            column = numpy.asarray([row[column_index] for row in matrix], dtype=float)
            permuted_columns.append(column[generator.permutation(len(column))])
        permuted_rows = _rows_from_columns(
            dates=dates,
            listings=listings,
            columns=permuted_columns,
            replicate=replicate,
        )
        covariance = estimate_risk_model(
            permuted_rows,
            listings=tuple(key.as_tuple() for key in listings),
            estimator="ledoit_wolf",
            window_policy="full",
        ).covariance
        correlation, correlation_reason = correlation_from_covariance(covariance)
        if correlation_reason is not None:
            return _unavailable("signal_analysis_unavailable")
        spectral = analyze_symmetric_matrix(correlation)
        if not spectral.available or len(spectral.eigenvalues) != len(listings):
            return _unavailable("signal_analysis_unavailable")
        for rank, value in enumerate(spectral.eigenvalues):
            null_by_rank[rank].append(value)
    thresholds = tuple(
        float(numpy.quantile(values, PARALLEL_QUANTILE, method=PARALLEL_QUANTILE_METHOD))
        for values in null_by_rank
    )
    count = 0
    for observed_value, threshold in zip(observed.eigenvalues, thresholds, strict=True):
        if observed_value <= threshold:
            break
        count += 1
    return SignalComponentDiagnostics(
        observed.eigenvalues,
        thresholds,
        count,
        PARALLEL_REPLICATES,
        PARALLEL_SEED,
        PARALLEL_QUANTILE,
        PARALLEL_QUANTILE_METHOD,
        (),
    )


def _aligned_matrix(
    return_rows: Sequence[Mapping[str, Any]],
    listings: tuple[MultivariateListingKey, ...],
) -> tuple[tuple[str, ...], tuple[tuple[float, ...], ...]]:
    by_listing: dict[MultivariateListingKey, dict[str, float]] = {key: {} for key in listings}
    for row in return_rows:
        key = MultivariateListingKey(str(row["isin"]), str(row["exchange"]), str(row["code"]))
        if key in by_listing:
            by_listing[key][str(row["date"])] = float(row["return"])
    if any(not values for values in by_listing.values()):
        raise ValueError("missing listing")
    common = set(next(iter(by_listing.values())))
    for values in by_listing.values():
        common &= set(values)
    dates = tuple(sorted(common))
    matrix = tuple(tuple(by_listing[key][date] for key in listings) for date in dates)
    return dates, matrix


def _rows_from_columns(
    *,
    dates: tuple[str, ...],
    listings: tuple[MultivariateListingKey, ...],
    columns: Sequence[Any],
    replicate: int,
) -> tuple[dict[str, object], ...]:
    del replicate
    return tuple(
        {
            "isin": listing.isin,
            "exchange": listing.exchange,
            "code": listing.code,
            "date": date,
            "return": float(columns[column_index][row_index]),
        }
        for row_index, date in enumerate(dates)
        for column_index, listing in enumerate(listings)
    )


def _unavailable(reason: str) -> SignalComponentDiagnostics:
    return SignalComponentDiagnostics(
        (),
        (),
        None,
        PARALLEL_REPLICATES,
        PARALLEL_SEED,
        PARALLEL_QUANTILE,
        PARALLEL_QUANTILE_METHOD,
        (reason,),
    )


__all__ = [
    "PARALLEL_QUANTILE",
    "PARALLEL_QUANTILE_METHOD",
    "PARALLEL_REPLICATES",
    "PARALLEL_SEED",
    "SignalComponentDiagnostics",
    "build_signal_component_diagnostics",
]
