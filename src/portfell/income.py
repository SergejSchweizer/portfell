"""Jurisdiction-neutral, gross historical distribution evidence.

The income boundary deliberately only describes source-observed distributions.
It never invents a payment for an unobserved month and never treats a market
price as NAV.  All return and yield fields are gross historical quantities.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from math import sqrt
from statistics import median
from typing import Any

from portfell.contract_versioning import ContractVersion, stable_contract_id
from portfell.multivariate_inputs import MultivariateListingKey

INCOME_CONTRACT = ContractVersion("multivariate.income", 2)


@dataclass(frozen=True)
class IncomePolicy:
    version: ContractVersion = INCOME_CONTRACT
    minimum_observed_months: int = 12
    lower_percentile: float = 0.1
    trailing_days: int = 365

    def to_row(self) -> dict[str, object]:
        return {
            "version": self.version.qualified_name,
            "minimum_observed_months": self.minimum_observed_months,
            "lower_percentile": self.lower_percentile,
            "trailing_days": self.trailing_days,
        }


DEFAULT_INCOME_POLICY = IncomePolicy()


@dataclass(frozen=True)
class DistributionEvent:
    listing: MultivariateListingKey
    event_date: str
    amount: float
    currency: str
    source_id: str
    source_revision: str
    split_adjustment_factor: float
    used_payment_date_fallback: bool


@dataclass(frozen=True)
class MonthlyDistribution:
    listing: MultivariateListingKey
    month: str
    amount: float
    currency: str | None
    event_count: int
    source_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class IncomeEvidence:
    income_id: str
    listing: MultivariateListingKey
    currency: str | None
    event_count: int
    observed_month_count: int
    observed_payment_coverage: float | None
    monthly_distributions: tuple[MonthlyDistribution, ...]
    gross_ttm_distribution_amount: float | None
    gross_ttm_distribution_yield: float | None
    mean_observed_monthly_distribution: float | None
    median_observed_monthly_distribution: float | None
    lower_percentile_monthly_distribution: float | None
    coefficient_of_variation: float | None
    cut_count: int | None
    largest_cut: float | None
    longest_falling_sequence: int | None
    distribution_trend: float | None
    price_return: float | None
    total_return: float | None
    distribution_to_total_return_gap: float | None
    nav_erosion: float | None
    availability_reasons: tuple[str, ...]
    warnings: tuple[str, ...]


def normalize_distribution_events(
    rows: Sequence[Mapping[str, Any]], *, listing: MultivariateListingKey
) -> tuple[DistributionEvent, ...]:
    """Choose the latest logical revision and apply explicit split factors.

    A provider revision may use ``original_event_id`` to supersede an older
    event.  In its absence the provider event id is the logical identity.  The
    stable revision sort avoids input-order dependent corrections.
    """
    latest: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if MultivariateListingKey.from_row(row) != listing:
            continue
        source_id = str(row.get("event_id", row.get("id", row.get("source_id", ""))))
        logical_id = str(row.get("original_event_id") or row.get("logical_event_id") or source_id)
        if not logical_id:
            logical_id = stable_contract_id("income_event_source", dict(row))
        revision = _revision_key(row, source_id)
        if logical_id not in latest or revision >= _revision_key(
            latest[logical_id], str(latest[logical_id].get("event_id", ""))
        ):
            latest[logical_id] = row
    events: list[DistributionEvent] = []
    for logical_id, row in sorted(latest.items()):
        if bool(row.get("deleted", False)):
            continue
        raw_date = str(row.get("payment_date") or row.get("date") or row.get("ex_date") or "")
        if not raw_date:
            continue
        try:
            date.fromisoformat(raw_date[:10])
            amount = float(
                row.get("amount", row.get("value", row.get("unadjustedValue", 0.0))) or 0.0
            )
            split_factor = float(
                row.get("split_adjustment_factor", row.get("split_factor", 1.0)) or 1.0
            )
        except TypeError, ValueError:
            continue
        if amount < 0 or split_factor <= 0:
            continue
        source_id = str(row.get("event_id", row.get("id", row.get("source_id", logical_id))))
        events.append(
            DistributionEvent(
                listing,
                raw_date[:10],
                amount * split_factor,
                str(row.get("currency", "")),
                source_id,
                _revision_key(row, source_id),
                split_factor,
                not bool(row.get("payment_date")),
            )
        )
    return tuple(
        sorted(events, key=lambda event: (event.event_date, event.source_id, event.source_revision))
    )


def build_income_evidence(
    *,
    listing: MultivariateListingKey,
    events: Sequence[DistributionEvent],
    period_end: str,
    denominator_price: float | None,
    period_start: str | None = None,
    start_price: float | None = None,
    observed_coverage_months: int | None = None,
    genuine_nav_start: float | None = None,
    genuine_nav_end: float | None = None,
    policy: IncomePolicy = DEFAULT_INCOME_POLICY,
) -> IncomeEvidence:
    """Build immutable gross evidence from covered, normalized source events."""
    currencies = {event.currency for event in events if event.currency}
    reasons: list[str] = []
    warnings: list[str] = []
    if len(currencies) > 1:
        reasons.append("currency_mismatch")
    if not events:
        reasons.append("no_distribution_events")
    buckets = _monthly_buckets(listing, events)
    observed = tuple(bucket.amount for bucket in buckets)
    if len(observed) < policy.minimum_observed_months:
        reasons.append("insufficient_observed_months")
    if any(event.used_payment_date_fallback for event in events):
        warnings.append("payment_date_fallback_used")
    if any(event.split_adjustment_factor != 1.0 for event in events):
        warnings.append("split_adjusted_events_used")
    end = date.fromisoformat(period_end[:10])
    start = date.fromisoformat(period_start[:10]) if period_start else None
    trailing_events = tuple(
        event
        for event in events
        if 0 <= (end - date.fromisoformat(event.event_date)).days <= policy.trailing_days
    )
    price = denominator_price if denominator_price and denominator_price > 0 else None
    if price is None:
        reasons.append("dated_price_denominator_unavailable")
    coverage = _coverage(buckets, start, end, observed_coverage_months)
    monthly = sorted(observed)
    lower_index = (
        max(0, min(len(monthly) - 1, int((len(monthly) - 1) * policy.lower_percentile)))
        if monthly
        else 0
    )
    average = sum(observed) / len(observed) if observed else None
    variance = (
        sum((value - average) ** 2 for value in observed) / len(observed)
        if average is not None and observed
        else None
    )
    coefficient = (
        sqrt(variance) / average if variance is not None and average and average > 0 else None
    )
    comparable = _comparable_consecutive_buckets(buckets)
    cuts = [
        previous.amount - current.amount
        for previous, current in comparable
        if current.amount < previous.amount
    ]
    distribution_amount = sum(event.amount for event in trailing_events)
    price_return = (
        ((price / start_price) - 1.0) if price and start_price and start_price > 0 else None
    )
    total_return = (
        (price_return + distribution_amount / start_price)
        if price_return is not None and start_price
        else None
    )
    distribution_yield = distribution_amount / price if price else None
    nav_erosion = (
        ((genuine_nav_end / genuine_nav_start) - 1.0)
        if genuine_nav_start and genuine_nav_end and genuine_nav_start > 0 and genuine_nav_end > 0
        else None
    )
    if genuine_nav_start is None or genuine_nav_end is None:
        warnings.append("genuine_nav_unavailable")
    available = not reasons
    identity = stable_contract_id(
        "income_evidence",
        {
            "contract": INCOME_CONTRACT.qualified_name,
            "listing": listing.as_tuple(),
            "events": [
                (event.event_date, event.amount, event.source_id, event.source_revision)
                for event in events
            ],
            "period_end": period_end,
            "period_start": period_start,
            "price": price,
            "start_price": start_price,
            "policy": policy.to_row(),
        },
    )
    return IncomeEvidence(
        identity,
        listing,
        next(iter(currencies), None),
        len(events),
        len(observed),
        coverage,
        buckets,
        distribution_amount if available else None,
        distribution_yield if available else None,
        average if available else None,
        median(observed) if available else None,
        monthly[lower_index] if available and monthly else None,
        coefficient if available else None,
        len(cuts) if available else None,
        max(cuts) if available and cuts else None,
        _longest_falling_sequence(tuple(bucket.amount for bucket in buckets))
        if available
        else None,
        _trend(tuple(bucket.amount for bucket in buckets)) if available else None,
        price_return if available else None,
        total_return if available else None,
        (distribution_amount / start_price - total_return)
        if available and total_return is not None and start_price
        else None,
        nav_erosion,
        tuple(sorted(set(reasons))),
        tuple(sorted(set(warnings))),
    )


def build_income_artifacts(
    *,
    evidence_by_listing: Mapping[MultivariateListingKey, IncomeEvidence],
    dividend_rows: Sequence[Mapping[str, Any]],
    income_metrics: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Serialize immutable, source-addressable income evidence partitions."""
    return {
        "income_distribution_events": [
            {
                "income_id": evidence.income_id,
                "isin": key.isin,
                "exchange": key.exchange,
                "code": key.code,
                "event_date": event.event_date,
                "amount": event.amount,
                "currency": event.currency,
                "source_id": event.source_id,
                "source_revision": event.source_revision,
                "split_adjustment_factor": event.split_adjustment_factor,
                "policy_version": INCOME_CONTRACT.qualified_name,
            }
            for key, evidence in sorted(evidence_by_listing.items())
            for event in normalize_distribution_events(dividend_rows, listing=key)
        ],
        "income_monthly_distributions": [
            {
                "income_id": evidence.income_id,
                "isin": key.isin,
                "exchange": key.exchange,
                "code": key.code,
                "month": bucket.month,
                "amount": bucket.amount,
                "currency": bucket.currency,
                "event_count": bucket.event_count,
                "source_event_ids": list(bucket.source_event_ids),
                "policy_version": INCOME_CONTRACT.qualified_name,
            }
            for key, evidence in sorted(evidence_by_listing.items())
            for bucket in evidence.monthly_distributions
        ],
        "income_metrics": [dict(row) for row in income_metrics],
        "income_warnings": [
            {
                "income_id": evidence.income_id,
                "isin": key.isin,
                "exchange": key.exchange,
                "code": key.code,
                "warning": warning,
                "policy_version": INCOME_CONTRACT.qualified_name,
            }
            for key, evidence in sorted(evidence_by_listing.items())
            for warning in (*evidence.availability_reasons, *evidence.warnings)
        ],
    }


def _revision_key(row: Mapping[str, Any], source_id: str) -> str:
    return str(row.get("revision", row.get("version", row.get("corrected_at", source_id))))


def _monthly_buckets(
    listing: MultivariateListingKey, events: Sequence[DistributionEvent]
) -> tuple[MonthlyDistribution, ...]:
    grouped: dict[str, list[DistributionEvent]] = defaultdict(list)
    for event in events:
        grouped[event.event_date[:7]].append(event)
    return tuple(
        MonthlyDistribution(
            listing,
            month,
            sum(event.amount for event in values),
            next(iter({event.currency for event in values if event.currency}), None),
            len(values),
            tuple(sorted(event.source_id for event in values)),
        )
        for month, values in sorted(grouped.items())
    )


def _coverage(
    buckets: Sequence[MonthlyDistribution],
    start: date | None,
    end: date,
    covered_months: int | None,
) -> float | None:
    if covered_months is not None:
        return len(buckets) / covered_months if covered_months > 0 else None
    if start is None:
        return None
    months = (end.year - start.year) * 12 + end.month - start.month + 1
    return len(buckets) / months if months > 0 else None


def _comparable_consecutive_buckets(
    buckets: Sequence[MonthlyDistribution],
) -> tuple[tuple[MonthlyDistribution, MonthlyDistribution], ...]:
    result: list[tuple[MonthlyDistribution, MonthlyDistribution]] = []
    for previous, current in zip(buckets, buckets[1:], strict=False):
        previous_date, current_date = (
            date.fromisoformat(previous.month + "-01"),
            date.fromisoformat(current.month + "-01"),
        )
        if (
            current_date.year - previous_date.year
        ) * 12 + current_date.month - previous_date.month == 1:
            result.append((previous, current))
    return tuple(result)


def _trend(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    x_mean, y_mean = (len(values) - 1) / 2, sum(values) / len(values)
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    return (
        sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values)) / denominator
        if denominator
        else None
    )


def _longest_falling_sequence(values: Sequence[float]) -> int:
    best = current = 0
    for previous, value in zip(values, values[1:], strict=False):
        current = current + 1 if value < previous else 0
        best = max(best, current)
    return best
