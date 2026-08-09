"""Pure API read models for bivariate statistics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from portfell.bivariate_diagnostics import (
    bivariate_metric_summary,
    covariance_diagnostics,
    downside_diagnostics,
    pearson_diagnostics,
    spearman_diagnostics,
)
from portfell.gold import build_returns
from portfell.gold_pair_stats import sample_covariance
from portfell.table_io import JsonRow

_SUMMARY_METRICS = (
    "pearson_correlation",
    "spearman_correlation",
    "downside_correlation",
    "lower_tail_dependence",
    "tail_coexceedance_rate",
    "rolling_correlation_stability",
    "rolling_spearman_stability",
    "drawdown_overlap_rate",
)


def build_bivariate_summary(rows: tuple[JsonRow, ...]) -> JsonRow:
    """Aggregate pair rows for the bivariate-statistics cards."""

    date_start, date_end = _shared_date_range(rows)
    return {
        "pair_count": len(rows),
        "observation_count": _average_observations(rows),
        "date_start": date_start,
        "date_end": date_end,
        "metrics": {
            name: bivariate_metric_summary(
                [float(row[name]) for row in rows if row.get(name) is not None]
            )
            for name in _SUMMARY_METRICS
        },
        "pearson_diagnostics": pearson_diagnostics(rows),
        "spearman_diagnostics": spearman_diagnostics(rows),
        "downside_diagnostics": downside_diagnostics(rows),
    }


def build_correlation_matrix(rows: tuple[JsonRow, ...], metric: str) -> JsonRow:
    """Expose the upper triangle of one pair-metric matrix from pair results."""

    metric_key = {
        "pearson": "pearson_correlation",
        "spearman": "spearman_correlation",
        "downside": "downside_correlation",
        "lower_tail_dependence": "lower_tail_dependence",
        "tail_coexceedance_rate": "tail_coexceedance_rate",
    }[metric]
    listings = _pair_listings(rows)
    index = {listing: position for position, listing in enumerate(listings)}
    values_by_pair = {
        (
            index[_listing(row, "left")],
            index[_listing(row, "right")],
        ): float(row.get(metric_key, 0.0))
        for row in rows
    }
    date_start, date_end = _shared_date_range(rows)
    return {
        "labels": _labels(listings),
        "values": [
            [
                values_by_pair.get((row, column)) if column > row else None
                for column in range(len(listings))
            ]
            for row in range(len(listings))
        ],
        "observation_count": _average_observations(rows),
        "date_start": date_start,
        "date_end": date_end,
    }


def build_covariance_matrix(
    quote_rows: Sequence[Mapping[str, Any]], member_ids: tuple[str, ...]
) -> JsonRow:
    """Build a common-date daily log-return covariance matrix for selected listings."""

    members = set(member_ids)
    scoped_quotes = tuple(row for row in quote_rows if _member_id(row) in members)
    values_by_listing: dict[tuple[str, str, str], dict[str, float]] = {}
    for row in build_returns(scoped_quotes):
        listing = (str(row["isin"]), str(row["exchange"]), str(row["code"]))
        values_by_listing.setdefault(listing, {})[str(row["date"])] = float(row["return"])
    listings = tuple(sorted(values_by_listing))
    dates = _common_dates(values_by_listing, listings)
    values = [tuple(values_by_listing[listing][date] for date in dates) for listing in listings]
    covariance_values = _dense_covariance(values)
    return {
        "labels": _labels(listings),
        "values": [
            [value if column > row else None for column, value in enumerate(values_row)]
            for row, values_row in enumerate(covariance_values)
        ],
        "observation_count": len(dates),
        "date_start": dates[0] if dates else "",
        "date_end": dates[-1] if dates else "",
        "diagnostics": covariance_diagnostics(listings, covariance_values, len(dates)),
    }


def _pair_listings(rows: tuple[JsonRow, ...]) -> tuple[tuple[str, str, str], ...]:
    return tuple(sorted({_listing(row, side) for row in rows for side in ("left", "right")}))


def _listing(row: JsonRow, side: str) -> tuple[str, str, str]:
    return (
        str(row[side + "_isin"]),
        str(row[side + "_exchange"]),
        str(row[side + "_code"]),
    )


def _member_id(row: Mapping[str, Any]) -> str:
    return f"{row.get('isin', '')}:{row.get('exchange', '')}:{row.get('code', '')}"


def _labels(listings: tuple[tuple[str, str, str], ...]) -> list[JsonRow]:
    return [
        {"isin": isin, "exchange": exchange, "code": code, "label": f"{code}.{exchange}"}
        for isin, exchange, code in listings
    ]


def _average_observations(rows: tuple[JsonRow, ...]) -> int:
    if not rows:
        return 0
    return round(sum(int(row.get("n_observations", 0)) for row in rows) / len(rows))


def _shared_date_range(rows: tuple[JsonRow, ...]) -> tuple[str, str]:
    ranges = {
        (str(row.get("date_start", "")), str(row.get("date_end", "")))
        for row in rows
        if row.get("date_start") and row.get("date_end")
    }
    if len(ranges) > 1:
        raise ValueError("bivariate rows do not share one aligned data period")
    observation_counts = {int(row.get("n_observations", 0)) for row in rows}
    if len(observation_counts) > 1:
        raise ValueError("bivariate rows do not share one aligned observation count")
    return next(iter(ranges), ("", ""))


def _common_dates(
    values_by_listing: dict[tuple[str, str, str], dict[str, float]],
    listings: tuple[tuple[str, str, str], ...],
) -> tuple[str, ...]:
    if not listings:
        return ()
    common = set(values_by_listing[listings[0]])
    for listing in listings[1:]:
        common.intersection_update(values_by_listing[listing])
    return tuple(sorted(common))


def _dense_covariance(values: list[tuple[float, ...]]) -> list[list[float]]:
    covariance = [[0.0] * len(values) for _ in values]
    for row, left in enumerate(values):
        for column in range(row, len(values)):
            value = sample_covariance(left, values[column])
            covariance[row][column] = value
            covariance[column][row] = value
    return covariance
