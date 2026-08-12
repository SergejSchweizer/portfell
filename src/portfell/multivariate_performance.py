"""Persisted cumulative and calendar-period performance for Multivariate candidates."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from math import exp
from typing import Any

from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.table_io import JsonRow


def build_multivariate_performance(
    *, candidates: Sequence[PortfolioCandidate], return_rows: Sequence[Mapping[str, Any]]
) -> JsonRow:
    """Build JSON-safe cumulative daily and compounded calendar-period returns."""
    indexed = _indexed_simple_returns(return_rows)
    instrument_series = tuple(_series_row(key, indexed.get(key, {})) for key in sorted(indexed))
    portfolio_series: list[JsonRow] = []
    period_returns: list[JsonRow] = []
    for candidate in candidates:
        if candidate.status != "feasible":
            continue
        daily = _portfolio_returns(candidate, indexed)
        portfolio_series.append(
            {
                "candidate_id": candidate.candidate_id,
                "method": candidate.method,
                "values": _cumulative_values(daily),
            }
        )
        period_returns.extend(_period_returns(candidate, daily))
    return {
        "instrument_series": list(instrument_series),
        "portfolio_series": portfolio_series,
        "period_returns": period_returns,
    }


def _indexed_simple_returns(
    rows: Sequence[Mapping[str, Any]],
) -> dict[MultivariateListingKey, dict[str, float]]:
    output: dict[MultivariateListingKey, dict[str, float]] = defaultdict(dict)
    for row in rows:
        key = MultivariateListingKey.from_row(row)
        raw = row.get("simple_return")
        output[key][str(row["date"])] = (
            float(raw) if raw is not None else exp(float(row["return"])) - 1
        )
    return dict(output)


def _series_row(key: MultivariateListingKey, daily: Mapping[str, float]) -> JsonRow:
    return {
        "isin": key.isin,
        "exchange": key.exchange,
        "code": key.code,
        "values": _cumulative_values(daily),
    }


def _cumulative_values(daily: Mapping[str, float]) -> list[JsonRow]:
    value = 1.0
    values: list[JsonRow] = []
    for date in sorted(daily):
        value *= 1.0 + daily[date]
        values.append({"date": date, "return": value - 1.0})
    return values


def _portfolio_returns(
    candidate: PortfolioCandidate,
    indexed: Mapping[MultivariateListingKey, Mapping[str, float]],
) -> dict[str, float]:
    weights = dict(candidate.weights)
    dates: set[str] | None = None
    for key in weights:
        listing_dates = set(indexed.get(key, {}).keys())
        dates = listing_dates if dates is None else dates & listing_dates
    return {
        date: sum(weight * indexed[key][date] for key, weight in weights.items())
        for date in sorted(dates or set())
    }


def _period_returns(candidate: PortfolioCandidate, daily: Mapping[str, float]) -> list[JsonRow]:
    rows: list[JsonRow] = []
    for period, width in (("monthly", 7), ("annual", 4)):
        buckets: dict[str, list[float]] = defaultdict(list)
        for date, value in daily.items():
            buckets[date[:width]].append(value)
        for label, values in sorted(buckets.items()):
            compounded = 1.0
            for value in values:
                compounded *= 1.0 + value
            rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "method": candidate.method,
                    "period": period,
                    "label": label,
                    "return": compounded - 1.0,
                }
            )
    return rows
