"""Deterministic risk-model estimators for Multivariate candidate construction."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from portfell.multivariate.contracts.common import ListingIdentity

Vector = tuple[float, ...]
Matrix = tuple[tuple[float, ...], ...]


class RiskModel(StrEnum):
    SAMPLE = "sample"
    LEDOIT_WOLF = "ledoit_wolf"
    EWMA = "ewma"


RISK_MODELS: tuple[RiskModel, ...] = tuple(RiskModel)


@dataclass(frozen=True, slots=True)
class AlignedReturns:
    listings: tuple[ListingIdentity, ...]
    dates: tuple[str, ...]
    rows: tuple[Vector, ...]

    def __post_init__(self) -> None:
        if any(len(row) != len(self.listings) for row in self.rows):
            raise ValueError("aligned return row width must match listings")
        if len(self.dates) != len(self.rows):
            raise ValueError("aligned dates and rows must have same length")


@dataclass(frozen=True, slots=True)
class RiskModelResult:
    model: RiskModel
    covariance: Matrix | None
    first_date: str | None
    last_date: str | None
    observation_count: int
    available: bool
    reason: str | None = None


def align_returns(
    series: dict[ListingIdentity, tuple[tuple[str, float], ...]],
) -> AlignedReturns:
    """Align all listings to their exact common dated return calendar."""

    listings = tuple(sorted(series))
    if not listings:
        return AlignedReturns((), (), ())
    maps = {listing: dict(series[listing]) for listing in listings}
    common_dates = set(maps[listings[0]])
    for listing in listings[1:]:
        common_dates &= set(maps[listing])
    dates = tuple(sorted(common_dates))
    rows = tuple(tuple(float(maps[listing][date]) for listing in listings) for date in dates)
    if any(not math.isfinite(value) for row in rows for value in row):
        raise ValueError("return observations must be finite")
    return AlignedReturns(listings, dates, rows)


def _means(rows: tuple[Vector, ...], width: int) -> Vector:
    return tuple(sum(row[index] for row in rows) / len(rows) for index in range(width))


def _center(rows: tuple[Vector, ...]) -> tuple[Vector, ...]:
    if not rows:
        return ()
    mean = _means(rows, len(rows[0]))
    return tuple(tuple(value - mean[index] for index, value in enumerate(row)) for row in rows)


def sample_covariance(rows: tuple[Vector, ...]) -> Matrix:
    if len(rows) < 2:
        raise ValueError("sample covariance requires at least two observations")
    width = len(rows[0])
    centered = _center(rows)
    denominator = len(rows) - 1
    return tuple(
        tuple(sum(row[i] * row[j] for row in centered) / denominator for j in range(width))
        for i in range(width)
    )


def ledoit_wolf_covariance(rows: tuple[Vector, ...]) -> Matrix:
    """Shrink empirical covariance toward scaled identity with data-driven intensity."""

    if len(rows) < 2:
        raise ValueError("Ledoit-Wolf covariance requires at least two observations")
    centered = _center(rows)
    n_samples = len(centered)
    width = len(centered[0])
    empirical = tuple(
        tuple(sum(row[i] * row[j] for row in centered) / n_samples for j in range(width))
        for i in range(width)
    )
    mu = sum(empirical[i][i] for i in range(width)) / width
    delta = sum(
        (empirical[i][j] - (mu if i == j else 0.0)) ** 2
        for i in range(width)
        for j in range(width)
    )
    if delta <= 1e-30:
        shrinkage = 1.0
    else:
        beta = 0.0
        for row in centered:
            for i in range(width):
                for j in range(width):
                    deviation = row[i] * row[j] - empirical[i][j]
                    beta += deviation * deviation
        beta /= n_samples * n_samples
        shrinkage = min(1.0, max(0.0, beta / delta))
    return tuple(
        tuple(
            (1.0 - shrinkage) * empirical[i][j] + shrinkage * (mu if i == j else 0.0)
            for j in range(width)
        )
        for i in range(width)
    )


def ewma_covariance(rows: tuple[Vector, ...], *, decay: float = 0.94) -> Matrix:
    if len(rows) < 2:
        raise ValueError("EWMA covariance requires at least two observations")
    if not 0.0 < decay < 1.0:
        raise ValueError("EWMA decay must be between zero and one")
    centered = _center(rows)
    width = len(centered[0])
    raw_weights = [(1.0 - decay) * decay ** (len(centered) - 1 - index) for index in range(len(centered))]
    total = sum(raw_weights)
    weights = [weight / total for weight in raw_weights]
    return tuple(
        tuple(sum(weights[k] * centered[k][i] * centered[k][j] for k in range(len(centered))) for j in range(width))
        for i in range(width)
    )


def estimate_risk_model(aligned: AlignedReturns, model: RiskModel) -> RiskModelResult:
    if len(aligned.rows) < 2:
        return RiskModelResult(model, None, None, None, len(aligned.rows), False, "insufficient_history")
    if model is RiskModel.SAMPLE:
        covariance = sample_covariance(aligned.rows)
    elif model is RiskModel.LEDOIT_WOLF:
        covariance = ledoit_wolf_covariance(aligned.rows)
    elif model is RiskModel.EWMA:
        covariance = ewma_covariance(aligned.rows)
    else:
        raise ValueError(f"unknown risk model: {model}")
    return RiskModelResult(
        model,
        covariance,
        aligned.dates[0],
        aligned.dates[-1],
        len(aligned.rows),
        True,
    )
