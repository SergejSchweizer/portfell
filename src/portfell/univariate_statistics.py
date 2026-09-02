"""Univariate Statistics for approved ISIN listings."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from math import exp, log, sqrt
from typing import Any

import polars as pl

from portfell.contract_versioning import stable_contract_id
from portfell.paths import LakePaths
from portfell.return_quality import evaluate_quote_quality, filter_valid_price_points
from portfell.schemas import validate_rows
from portfell.table_io import JsonRow, read_rows, write_rows
from portfell.univariate_metrics import enrich_univariate_row

ANNUAL_TRADING_DAYS = 252
DEFAULT_CONFIDENCE_LEVEL = 0.975
UNIVARIATE_CALCULATION_CONTRACT = "univariate.statistics.v2"


def build_quote_returns(quote_rows: Sequence[Mapping[str, Any]]) -> list[JsonRow]:
    """Build per-listing daily adjusted-close return transformations from quote rows."""
    returns: list[JsonRow] = []
    frame = pl.DataFrame([dict(row) for row in quote_rows], infer_schema_length=None)
    if frame.is_empty():
        return returns
    grouped = frame.sort(  # pyright: ignore[reportUnknownMemberType]
        "isin", "exchange", "code", "date"
    ).partition_by("isin", "exchange", "code", maintain_order=True)
    for listing_rows in grouped:
        rows = listing_rows.to_dicts()
        isin, exchange, code = (str(rows[0][field]) for field in ("isin", "exchange", "code"))
        ordered = rows
        valid_quotes, _quarantined = filter_valid_price_points(ordered)
        for previous, current in zip(valid_quotes, valid_quotes[1:], strict=False):
            previous_close = float(previous["adjusted_close"])
            current_close = float(current["adjusted_close"])
            simple_return = (current_close / previous_close) - 1.0
            log_return = log(current_close / previous_close)
            returns.append(
                {
                    "isin": isin,
                    "exchange": exchange,
                    "code": code,
                    "date": str(current["date"]),
                    "return": log_return,
                    "log_return": log_return,
                    "simple_return": simple_return,
                }
            )
    return returns


def build_univariate_statistics(
    quote_rows: Sequence[Mapping[str, Any]],
    *,
    dividend_rows: Sequence[Mapping[str, Any]] = (),
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    concurrency: int | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> list[JsonRow]:
    """Compute only one-ISIN/listing statistics from quote rows.

    The output intentionally excludes pairwise, benchmark-relative, correlation,
    and covariance values so this module can be used before any cross-sectional
    analysis is available.
    """
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be in (0, 1)")

    distributions_by_listing = index_distribution_events(dividend_rows)
    dividends_by_listing: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in dividend_rows:
        key = (str(row["isin"]), str(row["exchange"]), str(row["code"]))
        dividends_by_listing.setdefault(key, []).append(row)
    quote_frame = pl.DataFrame([dict(row) for row in quote_rows], infer_schema_length=None)
    if quote_frame.is_empty():
        return []
    tasks = [
        (
            (str(rows[0]["isin"]), str(rows[0]["exchange"]), str(rows[0]["code"])),
            tuple(rows),
            distributions_by_listing.get(key, ()),
            tuple(dict(row) for row in dividends_by_listing.get(key, ())),
            confidence_level,
        )
        for listing_rows in quote_frame.sort(  # pyright: ignore[reportUnknownMemberType]
            "isin", "exchange", "code", "date"
        ).partition_by("isin", "exchange", "code", maintain_order=True)
        if (rows := listing_rows.to_dicts())
        and (key := (str(rows[0]["isin"]), str(rows[0]["exchange"]), str(rows[0]["code"])))
    ]
    workers = _worker_count(concurrency)
    if workers == 1 or len(tasks) <= 1:
        rows: list[JsonRow] = []
        for completed, task in enumerate(tasks, start=1):
            rows.append(_build_univariate_listing_statistics(task))
            if on_progress is not None:
                on_progress(completed)
        return rows
    with ProcessPoolExecutor(max_workers=workers) as executor:
        rows: list[JsonRow] = []
        computed_rows = executor.map(_build_univariate_listing_statistics, tasks)
        for completed, row in enumerate(computed_rows, start=1):
            rows.append(row)
            if on_progress is not None:
                on_progress(completed)
        return rows


def write_univariate_statistics(
    paths: LakePaths,
    quote_rows: Sequence[Mapping[str, Any]],
    *,
    dividend_rows: Sequence[Mapping[str, Any]] = (),
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    concurrency: int | None = None,
) -> list[JsonRow]:
    """Write Univariate Statistics rows to stable Gold paths by listing."""
    quotes_by_listing = _group_listing_rows(quote_rows)
    dividends_by_listing = _group_listing_rows(dividend_rows)
    cached_rows: list[JsonRow] = []
    stale_quotes: list[Mapping[str, Any]] = []
    stale_dividends: list[Mapping[str, Any]] = []
    for key, rows in sorted(quotes_by_listing.items()):
        cached = _cached_univariate_row(
            paths,
            key,
            rows,
            dividends_by_listing.get(key, ()),
            confidence_level=confidence_level,
        )
        if cached is None:
            stale_quotes.extend(rows)
            stale_dividends.extend(dividends_by_listing.get(key, ()))
        else:
            cached_rows.append(cached)

    rows = build_univariate_statistics(
        stale_quotes,
        dividend_rows=stale_dividends,
        confidence_level=confidence_level,
        concurrency=concurrency,
    )
    validate_rows("univariate_statistics", rows)
    for row in rows:
        write_rows(paths.gold_univariate_statistics(str(row["exchange"]), str(row["isin"])), [row])
    return sorted(
        cached_rows + rows,
        key=lambda row: (str(row["isin"]), str(row["exchange"]), str(row["code"])),
    )


def _group_listing_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], list[Mapping[str, Any]]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        key = (str(row["isin"]), str(row["exchange"]), str(row["code"]))
        grouped.setdefault(key, []).append(row)
    return grouped


def _cached_univariate_row(
    paths: LakePaths,
    key: tuple[str, str, str],
    quote_rows: Sequence[Mapping[str, Any]],
    dividend_rows: Sequence[Mapping[str, Any]],
    *,
    confidence_level: float,
) -> JsonRow | None:
    isin, exchange, code = key
    cached = read_rows(paths.gold_univariate_statistics(exchange, isin))
    if len(cached) != 1:
        return None
    row = cached[0]
    ordered_quotes = sorted(quote_rows, key=lambda quote: str(quote["date"]))
    valid_dividends = [
        dividend
        for dividend in dividend_rows
        if float(dividend.get("value", dividend.get("unadjustedValue", 0.0)) or 0.0) > 0
    ]
    last_distribution_date = max((str(row["date"]) for row in valid_dividends), default="")
    if (
        str(row.get("isin")) == isin
        and str(row.get("exchange")) == exchange
        and str(row.get("code")) == code
        and str(row.get("calculation_contract")) == UNIVARIATE_CALCULATION_CONTRACT
        and str(row.get("quote_input_id")) == univariate_quote_input_id(ordered_quotes)
        and str(row.get("dividend_input_id")) == univariate_dividend_input_id(valid_dividends)
        and float(row.get("confidence_level", -1.0)) == confidence_level
        and int(row.get("quote_observation_count", -1)) == len(ordered_quotes)
        and str(row.get("first_quote_date")) == str(ordered_quotes[0]["date"])
        and str(row.get("last_quote_date")) == str(ordered_quotes[-1]["date"])
        and str(row.get("last_distribution_date", "")) == last_distribution_date
        and int(row.get("distribution_observation_count", -1)) == len(valid_dividends)
    ):
        return row
    return None


def _worker_count(concurrency: int | None) -> int:
    if concurrency is not None:
        return max(1, concurrency)
    return max(1, os.cpu_count() or 1)


def univariate_quote_input_id(rows: Sequence[Mapping[str, Any]]) -> str:
    return stable_contract_id(
        "univariate_quotes",
        sorted((str(row["date"]), float(row["adjusted_close"])) for row in rows),
    )


def univariate_dividend_input_id(rows: Sequence[Mapping[str, Any]]) -> str:
    return stable_contract_id(
        "univariate_dividends",
        sorted(
            (
                str(row["date"]),
                float(row.get("value", row.get("unadjustedValue", 0.0)) or 0.0),
            )
            for row in rows
            if row.get("date")
            and float(row.get("value", row.get("unadjustedValue", 0.0)) or 0.0) > 0
        ),
    )


def _build_univariate_listing_statistics(
    task: tuple[
        tuple[str, str, str],
        tuple[Mapping[str, Any], ...],
        Sequence[date],
        Sequence[Mapping[str, Any]],
        float,
    ],
) -> JsonRow:
    (isin, exchange, code), quotes, distribution_dates, dividend_rows, confidence_level = task
    ordered_quotes = sorted(quotes, key=lambda row: str(row["date"]))
    valid_quotes, _quarantined = filter_valid_price_points(ordered_quotes)
    ordered_returns = build_quote_returns(ordered_quotes)
    returns = [float(row["return"]) for row in ordered_returns]
    simple_returns = [float(row["simple_return"]) for row in ordered_returns]
    adjusted_closes = [float(row["adjusted_close"]) for row in valid_quotes]
    monthly_returns = _monthly_returns(valid_quotes)
    first_close = adjusted_closes[0] if adjusted_closes else 0.0
    last_close = adjusted_closes[-1] if adjusted_closes else 0.0
    first_quote_date = str(ordered_quotes[0]["date"])
    last_quote_date = str(ordered_quotes[-1]["date"])
    first_valid_quote_date = str(valid_quotes[0]["date"]) if valid_quotes else ""
    last_valid_quote_date = str(valid_quotes[-1]["date"]) if valid_quotes else ""
    total_return = 0.0 if first_close <= 0 else (last_close / first_close) - 1.0
    cumulative_log_return = sum(returns)
    mean_log_return = _mean(returns)
    mean_simple_return = _mean(simple_returns)
    annualized_log_return = mean_log_return * ANNUAL_TRADING_DAYS
    annualized_simple_return = mean_simple_return * ANNUAL_TRADING_DAYS
    annualized_geometric_return = (
        0.0 if not returns else _exponential_return(mean_log_return * ANNUAL_TRADING_DAYS)
    )
    monthly_log_return = _mean(monthly_returns)
    monthly_simple_returns = [_exponential_return(value) for value in monthly_returns]
    monthly_simple_return = _mean(monthly_simple_returns)
    monthly_geometric_return = (
        0.0 if not monthly_returns else _exponential_return(monthly_log_return)
    )
    annualized_volatility = _annualized_volatility(returns)
    downside_deviation = _downside_deviation(returns)
    tail_risk = _tail_risk(returns, confidence_level)
    log_price_trend = _log_price_trend(adjusted_closes)
    distribution = distribution_features(distribution_dates)
    annual_dividend = annual_dividend_features(dividend_rows, last_valid_quote_date, last_close)
    quality = evaluate_quote_quality(ordered_quotes)
    base_row = {
        "isin": isin,
        "exchange": exchange,
        "code": code,
        "calculation_contract": UNIVARIATE_CALCULATION_CONTRACT,
        "quote_input_id": univariate_quote_input_id(ordered_quotes),
        "dividend_input_id": univariate_dividend_input_id(dividend_rows),
        "confidence_level": confidence_level,
        "first_quote_date": first_quote_date,
        "last_quote_date": last_quote_date,
        "quote_observation_count": len(ordered_quotes),
        "first_return_date": str(ordered_returns[0]["date"]) if ordered_returns else "",
        "last_return_date": str(ordered_returns[-1]["date"]) if ordered_returns else "",
        "return_observation_count": len(returns),
        "start_adjusted_close": first_close,
        "end_adjusted_close": last_close,
        "total_return": total_return,
        "cagr": _cagr(total_return, first_valid_quote_date, last_valid_quote_date),
        "cumulative_log_return": cumulative_log_return,
        "mean_log_return": mean_log_return,
        "median_log_return": _median(returns),
        "min_log_return": min(returns) if returns else 0.0,
        "max_log_return": max(returns) if returns else 0.0,
        "mean_simple_return": mean_simple_return,
        "median_simple_return": _median(simple_returns),
        "min_simple_return": min(simple_returns) if simple_returns else 0.0,
        "max_simple_return": max(simple_returns) if simple_returns else 0.0,
        "daily_log_return_std": sqrt(_sample_variance(returns)),
        "daily_simple_return_std": sqrt(_sample_variance(simple_returns)),
        "annualized_return": annualized_log_return,
        "annualized_log_return": annualized_log_return,
        "annualized_simple_return": annualized_simple_return,
        "annualized_geometric_return": annualized_geometric_return,
        "monthly_log_return": monthly_log_return,
        "monthly_simple_return": monthly_simple_return,
        "monthly_geometric_return": monthly_geometric_return,
        "monthly_return_observation_count": len(monthly_returns),
        "annualized_volatility": annualized_volatility,
        "realized_variance": sum(value * value for value in returns),
        "realized_volatility": sqrt(sum(value * value for value in returns)),
        "downside_deviation": downside_deviation,
        "sharpe_ratio": _ratio(annualized_log_return, annualized_volatility),
        "sortino_ratio": _ratio(
            annualized_log_return,
            downside_deviation,
        ),
        "autocorrelation": _lag1_autocorrelation(returns),
        "var": tail_risk[0],
        "expected_shortfall": tail_risk[1],
        "tail_observation_count": tail_risk[2],
        "max_drawdown": _max_drawdown(adjusted_closes),
        "positive_day_ratio": _positive_day_ratio(returns),
        "log_price_slope": log_price_trend[0],
        "trend_r_squared": log_price_trend[1],
        "availability_reason": "ok" if len(returns) >= 2 else "insufficient_returns",
        "distribution_frequency": distribution["distribution_frequency"],
        "distribution_events_per_year": distribution["distribution_events_per_year"],
        "last_distribution_date": distribution["last_distribution_date"],
        "distribution_observation_count": distribution["distribution_observation_count"],
        "annual_dividend_amount": annual_dividend["annual_dividend_amount"],
        "annual_dividend_yield": annual_dividend["annual_dividend_yield"],
        "quarantined_price_count": quality["quarantined_price_count"],
        "non_positive_price_detected": quality["non_positive_price_detected"],
        "duplicate_date_detected": quality["duplicate_date_detected"],
        "stale_price_detected": quality["stale_price_detected"],
        "unexplained_gap_detected": quality["unexplained_gap_detected"],
        "meets_min_history_252": quality["meets_min_history_252"],
        "meets_min_history_504": quality["meets_min_history_504"],
        "meets_min_history_756": quality["meets_min_history_756"],
        "production_eligible": quality["production_eligible"],
        "data_quality_reason": quality["data_quality_reason"],
    }
    return enrich_univariate_row(base_row, ordered_quotes, dividend_rows)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def index_distribution_events(
    dividend_rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], tuple[date, ...]]:
    indexed: dict[tuple[str, str, str], set[date]] = {}
    for row in dividend_rows:
        raw_date = str(row.get("date", "")).strip()
        if not raw_date:
            continue
        value = float(row.get("value", row.get("unadjustedValue", 0.0)) or 0.0)
        if value <= 0:
            continue
        key = (str(row["isin"]), str(row["exchange"]), str(row["code"]))
        indexed.setdefault(key, set()).add(date.fromisoformat(raw_date))
    return {key: tuple(sorted(values)) for key, values in indexed.items()}


def distribution_features(distribution_dates: Sequence[date]) -> JsonRow:
    observation_count = len(distribution_dates)
    if observation_count == 0:
        return {
            "distribution_frequency": "accumulating",
            "distribution_events_per_year": 0.0,
            "last_distribution_date": "",
            "distribution_observation_count": 0,
        }
    if observation_count == 1:
        return {
            "distribution_frequency": "unknown",
            "distribution_events_per_year": 1.0,
            "last_distribution_date": distribution_dates[-1].isoformat(),
            "distribution_observation_count": 1,
        }

    elapsed_days = max(1, (distribution_dates[-1] - distribution_dates[0]).days)
    events_per_year = ((observation_count - 1) / elapsed_days) * 365.25
    return {
        "distribution_frequency": _distribution_frequency(distribution_dates),
        "distribution_events_per_year": events_per_year,
        "last_distribution_date": distribution_dates[-1].isoformat(),
        "distribution_observation_count": observation_count,
    }


def annual_dividend_features(
    dividend_rows: Sequence[Mapping[str, Any]],
    last_quote_date: str,
    last_close: float,
) -> JsonRow:
    """Return trailing-twelve-month cash dividends and yield for one listing."""

    if not last_quote_date or last_close <= 0:
        return {"annual_dividend_amount": 0.0, "annual_dividend_yield": 0.0}
    end_date = date.fromisoformat(last_quote_date)
    start_ordinal = end_date.toordinal() - 365
    amount = sum(
        float(row.get("value", row.get("unadjustedValue", 0.0)) or 0.0)
        for row in dividend_rows
        if row.get("date")
        and start_ordinal < date.fromisoformat(str(row["date"])).toordinal() <= end_date.toordinal()
        and float(row.get("value", row.get("unadjustedValue", 0.0)) or 0.0) > 0
    )
    return {
        "annual_dividend_amount": amount,
        "annual_dividend_yield": amount / last_close,
    }


def _distribution_frequency(distribution_dates: Sequence[date]) -> str:
    gaps = [
        (current - previous).days
        for previous, current in zip(distribution_dates, distribution_dates[1:], strict=False)
    ]
    if all(20 <= gap <= 45 for gap in gaps):
        return "monthly"
    if all(70 <= gap <= 110 for gap in gaps):
        return "quarterly"
    if all(150 <= gap <= 220 for gap in gaps):
        return "semiannual"
    if all(300 <= gap <= 430 for gap in gaps):
        return "annual"
    return "irregular"


def _sample_variance(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def _lag1_autocorrelation(values: Sequence[float]) -> float:
    """Return lag-one autocorrelation of daily log returns."""
    if len(values) < 3:
        return 0.0
    mean = _mean(values)
    denominator = sum((value - mean) ** 2 for value in values[:-1])
    if denominator <= 0:
        return 0.0
    numerator = sum(
        (current - mean) * (previous - mean)
        for previous, current in zip(values, values[1:], strict=False)
    )
    return numerator / denominator


def _monthly_returns(quotes: Sequence[Mapping[str, Any]]) -> list[float]:
    """Build month-end log returns from valid adjusted-close observations."""
    month_end: dict[str, float] = {}
    for row in quotes:
        date_text = str(row.get("date", ""))
        month = date_text[:7]
        close = row.get("adjusted_close")
        if len(month) == 7 and isinstance(close, int | float) and float(close) > 0:
            month_end[month] = float(close)
    ordered = [month_end[key] for key in sorted(month_end)]
    return [
        log(current / previous)
        for previous, current in zip(ordered, ordered[1:], strict=False)
        if previous > 0 and current > 0
    ]


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _annualized_volatility(returns: Sequence[float]) -> float:
    return sqrt(_sample_variance(returns)) * sqrt(ANNUAL_TRADING_DAYS)


def _downside_deviation(returns: Sequence[float]) -> float:
    if not returns:
        return 0.0
    downside = [min(0.0, value) for value in returns]
    return sqrt(sum(value * value for value in downside) / len(downside)) * sqrt(
        ANNUAL_TRADING_DAYS
    )


def _ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _exponential_return(log_return: float) -> float:
    return exp(log_return) - 1.0


def _tail_risk(returns: Sequence[float], confidence_level: float) -> tuple[float, float, int]:
    losses = sorted(-value for value in returns)
    if not losses:
        return 0.0, 0.0, 0
    threshold_index = min(len(losses) - 1, int(confidence_level * len(losses)))
    var = losses[threshold_index]
    tail = [loss for loss in losses if loss >= var]
    return var, sum(tail) / len(tail), len(tail)


def _max_drawdown(adjusted_closes: Sequence[float]) -> float:
    peak: float | None = None
    max_drawdown = 0.0
    for close in adjusted_closes:
        peak = close if peak is None else max(peak, close)
        if peak <= 0:
            continue
        max_drawdown = min(max_drawdown, (close / peak) - 1.0)
    return max_drawdown


def _positive_day_ratio(returns: Sequence[float]) -> float:
    return 0.0 if not returns else sum(1 for value in returns if value > 0) / len(returns)


def _cagr(total_return: float, first_date: str, last_date: str) -> float:
    if not first_date or not last_date:
        return 0.0
    elapsed_days = (date.fromisoformat(last_date) - date.fromisoformat(first_date)).days
    if elapsed_days <= 0 or total_return <= -1.0:
        return 0.0
    return (1.0 + total_return) ** (365.25 / elapsed_days) - 1.0


def _log_price_trend(adjusted_closes: Sequence[float]) -> tuple[float, float]:
    if len(adjusted_closes) < 2 or any(close <= 0 for close in adjusted_closes):
        return 0.0, 0.0
    y_values = [log(close) for close in adjusted_closes]
    x_values = [float(index) for index in range(len(y_values))]
    x_mean = _mean(x_values)
    y_mean = _mean(y_values)
    x_variance = sum((value - x_mean) ** 2 for value in x_values)
    if x_variance == 0:
        return 0.0, 0.0
    slope = (
        sum(
            (x_value - x_mean) * (y_value - y_mean)
            for x_value, y_value in zip(x_values, y_values, strict=True)
        )
        / x_variance
    )
    intercept = y_mean - slope * x_mean
    total_sum_squares = sum((value - y_mean) ** 2 for value in y_values)
    if total_sum_squares == 0:
        return slope, 0.0
    residual_sum_squares = sum(
        (y_value - (intercept + slope * x_value)) ** 2
        for x_value, y_value in zip(x_values, y_values, strict=True)
    )
    return slope, 1.0 - (residual_sum_squares / total_sum_squares)


__all__ = [
    "DEFAULT_CONFIDENCE_LEVEL",
    "UNIVARIATE_CALCULATION_CONTRACT",
    "build_quote_returns",
    "build_univariate_statistics",
    "univariate_dividend_input_id",
    "univariate_quote_input_id",
    "write_univariate_statistics",
]
